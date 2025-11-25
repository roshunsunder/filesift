from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime, timedelta
import openai
import pickle
import numpy as np
from langchain.embeddings.sentence_transformer import SentenceTransformerEmbeddings
from langchain.vectorstores import FAISS
from langchain.schema import Document
from rank_bm25 import BM25Okapi

from ..config.settings import settings

class SearchResult:
    """Represents a single search result"""
    def __init__(self, path: str, score: float, metadata: Dict[str, Any]):
        self.path = path
        self.score = score
        self.metadata = metadata
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "score": self.score,
            "metadata": self.metadata
        }

class QueryCache:
    """Simple in-memory cache for search results"""
    def __init__(self, ttl_seconds: int = 3600):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl = timedelta(seconds=ttl_seconds)
        
    def get(self, key: str) -> Optional[List[SearchResult]]:
        if key not in self.cache:
            return None
            
        entry = self.cache[key]
        if datetime.now() - entry["timestamp"] > self.ttl:
            del self.cache[key]
            return None
            
        return entry["results"]
        
    def set(self, key: str, results: List[SearchResult]):
        self.cache[key] = {
            "timestamp": datetime.now(),
            "results": results
        }

class QueryDriver:
    """Enhanced query system with caching and filtering"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.embedding_model = SentenceTransformerEmbeddings(
            model_name="BAAI/bge-small-en-v1.5"
        )
        self.vector_store: Optional[FAISS] = None
        self.bm25_index: Optional[BM25Okapi] = None
        self.bm25_documents: List[Document] = []
        self.cache = QueryCache(ttl_seconds=settings.CACHE_TTL)
        
    def load_from_disk(self, path: str):
        """Load the vector store and BM25 index from disk"""
        path_obj = Path(path)
        try:
            self.vector_store = FAISS.load_local(str(path_obj / "faiss_index"), self.embedding_model)
        except Exception as e:
            self.logger.error(f"Error loading vector store: {str(e)}")
            raise
        
        # Load BM25 index and documents
        try:
            with open(path_obj / "bm25_index.pkl", "rb") as f:
                self.bm25_index = pickle.load(f)
            with open(path_obj / "bm25_documents.pkl", "rb") as f:
                self.bm25_documents = pickle.load(f)
        except FileNotFoundError:
            self.logger.warning("No BM25 index found, will use semantic search only")
            self.bm25_index = None
            self.bm25_documents = []
        except Exception as e:
            self.logger.warning(f"Could not load BM25 index: {str(e)}")
            self.bm25_index = None
            self.bm25_documents = []
            
    def _create_cache_key(self, query: str, filters: Dict[str, Any]) -> str:
        """Create a cache key from query and filters"""
        filter_str = "&".join(f"{k}={v}" for k, v in sorted(filters.items()))
        return f"{query}|{filter_str}"
        
    def _apply_filters(self, results: List[SearchResult], filters: Dict[str, Any]) -> List[SearchResult]:
        """Apply filters to search results"""
        filtered = results
        
        for key, value in filters.items():
            if key == "file_type":
                filtered = [r for r in filtered if r.metadata.get("file_type") == value]
            elif key == "min_date":
                min_date = datetime.fromisoformat(value)
                filtered = [r for r in filtered if datetime.fromtimestamp(r.metadata.get("modified", 0)) >= min_date]
            elif key == "max_date":
                max_date = datetime.fromisoformat(value)
                filtered = [r for r in filtered if datetime.fromtimestamp(r.metadata.get("modified", 0)) <= max_date]
            elif key == "min_size":
                filtered = [r for r in filtered if r.metadata.get("size", 0) >= value]
            elif key == "max_size":
                filtered = [r for r in filtered if r.metadata.get("size", 0) <= value]
                
        return filtered
    
    def _reciprocal_rank_fusion(self, semantic_results: List[tuple], bm25_results: List[int], 
                                alpha: float = 0.5, k: int = 60) -> Dict[str, float]:
        """
        Combine semantic and BM25 search results using Reciprocal Rank Fusion (RRF).
        
        Args:
            semantic_results: List of (doc, score) tuples from semantic search
            bm25_results: List of document indices from BM25 search (sorted by score)
            alpha: Weight for semantic search (1-alpha for BM25)
            k: RRF constant (typically 60)
        
        Returns:
            Dictionary mapping document paths to combined RRF scores
        """
        rrf_scores: Dict[str, float] = {}
        
        # Add semantic search scores
        for rank, (doc, _) in enumerate(semantic_results):
            doc_path = doc.metadata.get("path", "")
            if doc_path:
                rrf_scores[doc_path] = rrf_scores.get(doc_path, 0) + alpha / (k + rank + 1)
        
        # Add BM25 search scores
        for rank, doc_idx in enumerate(bm25_results):
            if doc_idx < len(self.bm25_documents):
                doc = self.bm25_documents[doc_idx]
                doc_path = doc.metadata.get("path", "")
                if doc_path:
                    rrf_scores[doc_path] = rrf_scores.get(doc_path, 0) + (1 - alpha) / (k + rank + 1)
        
        return rrf_scores
        
    def search(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        """
        Search the vector store with optional filters
        
        Args:
            query: The search query
            filters: Optional filters to apply. Supported filters:
                    - file_type: str
                    - min_date: ISO format date string
                    - max_date: ISO format date string
                    - min_size: int (bytes)
                    - max_size: int (bytes)
        """
        if not self.vector_store:
            raise ValueError("Vector store not loaded")
            
        filters = filters or {}
        cache_key = self._create_cache_key(query, filters)
        
        # Check cache
        if settings.ENABLE_CACHE:
            cached_results = self.cache.get(cache_key)
            if cached_results:
                return cached_results
        
        # Perform semantic search
        semantic_results = self.vector_store.similarity_search_with_score(
            query, k=settings.MAX_RESULTS * 2  # Get more candidates for hybrid search
        )
        
        # Perform BM25 search if available
        if self.bm25_index and self.bm25_documents:
            tokenized_query = query.lower().split()
            bm25_scores = self.bm25_index.get_scores(tokenized_query)
            # Get top-k BM25 results
            bm25_top_k = np.argsort(bm25_scores)[-settings.MAX_RESULTS * 2:][::-1]
            bm25_top_k = [int(idx) for idx in bm25_top_k if bm25_scores[idx] > 0]
        else:
            bm25_top_k = []
        
        # Combine results using RRF if BM25 is available, otherwise use semantic only
        if bm25_top_k:
            # Hybrid search with RRF
            rrf_scores = self._reciprocal_rank_fusion(semantic_results, bm25_top_k)
            
            # Create a mapping of path -> (doc, semantic_score) for easy lookup
            semantic_map = {
                doc.metadata.get("path", ""): (doc, 1.0 - score)
                for doc, score in semantic_results
            }
            
            # Sort by RRF score and create SearchResult objects
            sorted_paths = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
            results = []
            
            for path, rrf_score in sorted_paths[:settings.MAX_RESULTS]:
                if path in semantic_map:
                    doc, semantic_sim = semantic_map[path]
                    # Use RRF score as the final score
                    results.append(SearchResult(
                        path=path,
                        score=rrf_score,
                        metadata=doc.metadata
                    ))
        else:
            # Semantic search only (fallback if BM25 not available)
            results = [
                SearchResult(
                    path=doc.metadata["path"],
                    score=1.0 - score,  # Convert distance to similarity (higher = better)
                    metadata=doc.metadata
                )
                for doc, score in semantic_results
                if (1.0 - score) >= settings.SIMILARITY_THRESHOLD
            ][:settings.MAX_RESULTS]
        
        # Apply filters
        results = self._apply_filters(results, filters)
        
        # Update cache
        if settings.ENABLE_CACHE:
            self.cache.set(cache_key, results)
            
        return results 