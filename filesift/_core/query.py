import os
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
import pickle
import numpy as np

from langchain_core.documents import Document
from filesift._config.config import config_dict


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
            "metadata": self.metadata,
        }


class QueryDriver:
    """Enhanced query system with filtering"""

    def __init__(self):
        try:
            from langchain_community.vectorstores.faiss import FAISS
            from langchain_huggingface import HuggingFaceEmbeddings
            from rank_bm25 import BM25Okapi
        except ImportError:
            print("Failed to find necessary libraries, QueryDriver ctor failed.")
            return
        
        self.logger = logging.getLogger(__name__)
        self.embedding_model = HuggingFaceEmbeddings(
            model_name=config_dict["models"]["EMBEDDING_MODEL"]
        )
        self.vector_store: Optional[FAISS] = None
        self.bm25_index: Optional[BM25Okapi] = None
        self.bm25_documents: List[Document] = []

    def load_from_disk(self, path: str):
        """Load the vector store and BM25 index from disk"""
        path_obj = Path(path)
        try:
            from langchain_community.vectorstores.faiss import FAISS
        except ImportError:
            print("Could not load FAISS, aborting.")
            return
        try:
            index_dir_name = config_dict["paths"]["INDEX_DIR_NAME"]
            self.vector_store = FAISS.load_local(
                str(path_obj / index_dir_name),
                self.embedding_model,
                allow_dangerous_deserialization=True,
            )
        except Exception as e:
            self.logger.error(f"Error loading vector store: {str(e)}")
            raise

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
        
    def _apply_filters(
        self, results: List[SearchResult], filters: Dict[str, Any]
    ) -> List[SearchResult]:
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
    
    def _reciprocal_rank_fusion(
        self,
        semantic_results: List[tuple],
        bm25_results: List[int],
        alpha: float = 0.5,
        k: int = 60,
    ) -> Dict[str, float]:
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
        # We want intuitive, per-file behavior: each file should contribute at most
        # once per ranking source (semantic and BM25), regardless of how many chunks
        # it produced. To achieve this, we:
        #   1. Track the *best* (lowest) rank per file path for semantic results.
        #   2. Track the best rank per file path for BM25 results.
        #   3. Compute a single RRF contribution per file per source.
        #
        # This avoids over‑rewarding large, heavily-chunked files compared to small
        # files like single-caption images.
        rrf_scores: Dict[str, float] = {}

        semantic_best_ranks: Dict[str, int] = {}
        for rank, (doc, _) in enumerate(semantic_results):
            doc_path = doc.metadata.get("path", "")
            if not doc_path:
                continue
            if doc_path not in semantic_best_ranks:
                semantic_best_ranks[doc_path] = rank

        bm25_best_ranks: Dict[str, int] = {}
        for rank, doc_idx in enumerate(bm25_results):
            if doc_idx >= len(self.bm25_documents):
                continue
            doc = self.bm25_documents[doc_idx]
            doc_path = doc.metadata.get("path", "")
            if not doc_path:
                continue
            if doc_path not in bm25_best_ranks:
                bm25_best_ranks[doc_path] = rank

        for doc_path, rank in semantic_best_ranks.items():
            rrf_scores[doc_path] = rrf_scores.get(doc_path, 0.0) + alpha / (k + rank + 1)

        for doc_path, rank in bm25_best_ranks.items():
            rrf_scores[doc_path] = rrf_scores.get(doc_path, 0.0) + (1 - alpha) / (k + rank + 1)

        return rrf_scores
        
    def search(
        self, query: str, filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
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

        max_results = config_dict["search"]["MAX_RESULTS"]
        
        semantic_results = self.vector_store.similarity_search_with_score(
            query, k=max_results * 2  # Get more candidates for hybrid search
        )
        
        if self.bm25_index and self.bm25_documents:
            tokenized_query = query.lower().split()
            bm25_scores = self.bm25_index.get_scores(tokenized_query)
            bm25_top_k = np.argsort(bm25_scores)[-max_results * 2:][::-1]
            bm25_top_k = [int(idx) for idx in bm25_top_k if bm25_scores[idx] > 0]
        else:
            bm25_top_k = []
        
        if bm25_top_k:
            rrf_scores = self._reciprocal_rank_fusion(semantic_results, bm25_top_k)
            
            semantic_map: Dict[str, tuple[Document, float]] = {}
            for doc, score in semantic_results:
                path = doc.metadata.get("path", "")
                if not path:
                    continue
                if path not in semantic_map:
                    semantic_map[path] = (doc, 1.0 - score)
            
            sorted_paths = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
            results = []
            
            for path, rrf_score in sorted_paths[:max_results]:
                if path in semantic_map:
                    doc, semantic_sim = semantic_map[path]
                    results.append(SearchResult(
                        path=path,
                        score=rrf_score,
                        metadata=doc.metadata
                    ))
        else:
            similarity_threshold = config_dict["search"]["SIMILARITY_THRESHOLD"]
            results = [
                SearchResult(
                    path=doc.metadata["path"],
                    score=1.0 - score,
                    metadata=doc.metadata
                )
                for doc, score in semantic_results
                if (1.0 - score) >= similarity_threshold
            ][:max_results]
        
        results = self._apply_filters(results, filters)

        return results