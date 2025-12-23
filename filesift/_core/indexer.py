import os
# Set TOKENIZERS_PARALLELISM before any tokenizers are loaded to avoid fork warnings
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from pathlib import Path
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime
import json
import hashlib
import pickle
import re

from langchain_community.vectorstores.faiss import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi
from tqdm import tqdm

from filesift._config.config import config_dict

from .file_processors.base import BaseFileProcessor
from .file_processors.code_processor import CodeProcessor
from .file_processors.image_processor import ImageProcessor
from .file_processors.text_processor import TextProcessor
from .file_processors.data_processor import DataProcessor
from .file_processors.config_processor import ConfigProcessor
from .file_processors.document_processor import DocumentProcessor

class IndexMetadata:
    """Stores metadata about the index"""
    def __init__(self, root: Path):
        self.root = root
        self.last_indexed: datetime = datetime.now()
        self.indexed_files: Dict[str, float] = {}
        self.version: str = "1.0.0"
        
    def to_json(self) -> Dict[str, Any]:
        return {
            "root": str(self.root),
            "last_indexed": self.last_indexed.isoformat(),
            "indexed_files": self.indexed_files,
            "version": self.version
        }
        
    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'IndexMetadata':
        metadata = cls(Path(data["root"]))
        metadata.last_indexed = datetime.fromisoformat(data["last_indexed"])
        metadata.indexed_files = data["indexed_files"]
        metadata.version = data["version"]
        return metadata

class Indexer:
    """Enhanced indexer with incremental updates and caching"""
    
    def __init__(self, root: Path):
        self.root = Path(root)
        self.logger = logging.getLogger(__name__)
        self.metadata = IndexMetadata(root)
        
        self.embedding_function = HuggingFaceEmbeddings(
            model_name=config_dict["models"]["EMBEDDING_MODEL"]
        )
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=config_dict["indexing"]["CHUNK_SIZE"],
            chunk_overlap=config_dict["indexing"]["CHUNK_OVERLAP"],
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        self.processors: List[BaseFileProcessor] = [
            CodeProcessor(),
            ImageProcessor(),
            TextProcessor(),
            DataProcessor(),
            ConfigProcessor(),
            DocumentProcessor(),
        ]
        
        self.vector_store: Optional[FAISS] = None
        
        self.bm25_index: Optional[BM25Okapi] = None
        self.bm25_documents: List[Document] = []
        self.bm25_file_mapping: Dict[str, List[int]] = {}
        
    def needs_indexing(self, file_path: Path) -> bool:
        """Check if a file needs to be reindexed based on modification time"""
        if str(file_path) not in self.metadata.indexed_files:
            return True
            
        last_indexed_time = self.metadata.indexed_files[str(file_path)]
        current_mtime = file_path.stat().st_mtime
        return current_mtime > last_indexed_time
        
    def get_processor(self, file_path: Path) -> Optional[BaseFileProcessor]:
        """Get the appropriate processor for a file"""
        for processor in self.processors:
            if processor.can_handle(file_path):
                return processor
        return None
    
    def _extract_year(self, file_path: Path, content: str = "") -> Optional[int]:
        """Extract year from filename or content using regex"""
        year_match = re.search(r'\b(19|20)\d{2}\b', file_path.name)
        if year_match:
            return int(year_match.group())
        
        year_match = re.search(r'\b(19|20)\d{2}\b', str(file_path))
        if year_match:
            return int(year_match.group())
        
        if content:
            year_match = re.search(r'\b(19|20)\d{2}\b', content[:200])
            if year_match:
                return int(year_match.group())
        
        return None
    
    def _extract_keywords(self, file_path: Path) -> List[str]:
        """Extract keywords from filename stem for metadata purposes.
        
        Note: This is primarily for display/filtering. Actual keyword matching
        is handled by BM25 search on the full document content.
        """
        stem = file_path.stem.lower()
        stem_keywords = re.split(r'[_\-\s.]+', stem)
        keywords = [k for k in stem_keywords if len(k) > 2]
        return keywords
        
    def process_file(self, file_path: Path) -> List[Document]:
        """Process a single file and return a list of Documents (chunks) if successful"""
        try:
            processor = self.get_processor(file_path)
            if not processor:
                return []
                
            result = processor.process(file_path)
            summary = result["summary"]
            
            chunk_size = config_dict["indexing"]["CHUNK_SIZE"]
            if result.get("file_type") == "image" or len(summary) <= chunk_size:
                chunks = [summary]
            else:
                chunks = self.text_splitter.split_text(summary)
            
            file_path_str = str(file_path)
            enriched_metadata = {
                **result["metadata"],
                "file_type": result["file_type"],
                "summary": result.get("summary", ""),
                "filename": file_path.name,
                "filename_stem": file_path.stem,
                "extension": file_path.suffix,
                "parent_dir": file_path.parent.name,
                "full_path": file_path_str,
                "path": file_path_str,
            }
            
            year = self._extract_year(file_path, summary)
            if year:
                enriched_metadata["year"] = year
            
            keywords = self._extract_keywords(file_path)
            if keywords:
                enriched_metadata["keywords"] = keywords
            
            documents = []
            for i, chunk in enumerate(chunks):
                documents.append(Document(
                    page_content=chunk,
                    metadata={
                        **enriched_metadata,
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                    }
                ))
            
            return documents
        except Exception as e:
            self.logger.error(f"Error processing {file_path}: {str(e)}")
            return []
            
    def index(self):
        """Index the filesystem, updating only changed files"""
        documents = []
        
        indexable_files = []
        excluded_dirs = config_dict["indexing"]["EXCLUDED_DIRS"]
        for file_path in self.root.rglob("*"):
            if file_path.is_dir() or any(excluded in str(file_path) 
                                       for excluded in excluded_dirs):
                continue
                
            if not self.needs_indexing(file_path):
                continue
            
            if self.get_processor(file_path):
                indexable_files.append(file_path)
        
        print(f"\nFound {len(indexable_files)} supported file(s) that need to be indexed")
        
        if not indexable_files:
            print("No files to index.")
            return
        
        pbar = tqdm(
            total=len(indexable_files),
            desc="",
            unit="file",
            bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt}',
            leave=False
        )
        
        for file_path in indexable_files:
            try:
                relative_path = file_path.relative_to(self.root)
            except ValueError:
                relative_path = file_path
            
            path_str = str(relative_path)
            if len(path_str) > 60:
                path_str = "..." + path_str[-(60-3):]
            
            pbar.set_description_str(f"Indexing {path_str}")
            
            file_path_str = str(file_path)
            docs = self.process_file(file_path)
            if docs:
                documents.extend(docs)
                self.metadata.indexed_files[file_path_str] = file_path.stat().st_mtime
                
                if file_path_str in self.bm25_file_mapping:
                    old_indices = sorted(self.bm25_file_mapping[file_path_str], reverse=True)
                    for idx in old_indices:
                        if idx < len(self.bm25_documents):
                            del self.bm25_documents[idx]
                    for path, indices in self.bm25_file_mapping.items():
                        if path != file_path_str:
                            self.bm25_file_mapping[path] = [
                                i - sum(1 for oi in old_indices if oi < i)
                                for i in indices
                            ]
                
                start_idx = len(self.bm25_documents)
                self.bm25_documents.extend(docs)
                self.bm25_file_mapping[file_path_str] = list(range(start_idx, len(self.bm25_documents)))
            
            pbar.update(1)
        
        pbar.close()
                
        if self.vector_store is None and documents:
            self.vector_store = FAISS.from_documents(
                documents, self.embedding_function, distance_strategy="COSINE"
            )
        elif documents:
            self.vector_store.add_documents(documents)
        
        if self.bm25_documents:
            tokenized_docs = [
                doc.page_content.lower().split() 
                for doc in self.bm25_documents
            ]
            
            if tokenized_docs:
                self.bm25_index = BM25Okapi(tokenized_docs)
            
        self.metadata.last_indexed = datetime.now()
        
    def save(self, directory: Path):
        """Save the index and metadata to disk"""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        
        if self.vector_store:
            index_dir_name = config_dict["paths"]["INDEX_DIR_NAME"]
            self.vector_store.save_local(str(directory / index_dir_name))
        
        if self.bm25_index and self.bm25_documents:
            with open(directory / "bm25_index.pkl", "wb") as f:
                pickle.dump(self.bm25_index, f)
            with open(directory / "bm25_documents.pkl", "wb") as f:
                pickle.dump(self.bm25_documents, f)
            with open(directory / "bm25_file_mapping.pkl", "wb") as f:
                pickle.dump(self.bm25_file_mapping, f)
            
        with open(directory / "metadata.json", "w") as f:
            json.dump(self.metadata.to_json(), f, indent=2)
            
    def load(self, directory: Path):
        """Load the index and metadata from disk"""
        directory = Path(directory)
        
        try:
            with open(directory / "metadata.json", "r") as f:
                self.metadata = IndexMetadata.from_json(json.load(f))
        except FileNotFoundError:
            self.logger.warning("No metadata found, starting fresh")
            
        try:
            index_dir_name = config_dict["paths"]["INDEX_DIR_NAME"]
            self.vector_store = FAISS.load_local(
                str(directory / index_dir_name),
                self.embedding_function,
                allow_dangerous_deserialization=True
            )
        except Exception as e:
            self.logger.warning(f"Could not load vector store: {str(e)}")
            self.vector_store = None
        
        try:
            with open(directory / "bm25_index.pkl", "rb") as f:
                self.bm25_index = pickle.load(f)
            with open(directory / "bm25_documents.pkl", "rb") as f:
                self.bm25_documents = pickle.load(f)
            try:
                with open(directory / "bm25_file_mapping.pkl", "rb") as f:
                    self.bm25_file_mapping = pickle.load(f)
            except FileNotFoundError:
                self.bm25_file_mapping = {}
                self.logger.warning("BM25 file mapping not found, will be rebuilt on next index")
        except FileNotFoundError:
            self.logger.warning("No BM25 index found, will be rebuilt on next index")
            self.bm25_index = None
            self.bm25_documents = []
            self.bm25_file_mapping = {}
        except Exception as e:
            self.logger.warning(f"Could not load BM25 index: {str(e)}")
            self.bm25_index = None
            self.bm25_documents = []
            self.bm25_file_mapping = {} 