from pathlib import Path
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime
import json
import hashlib
from langchain.vectorstores import FAISS
from langchain.embeddings.sentence_transformer import SentenceTransformerEmbeddings
from langchain.schema import Document

from ..config.settings import settings
from .file_processors.base import BaseFileProcessor
from .file_processors.code_processor import CodeProcessor
from .file_processors.image_processor import ImageProcessor

class IndexMetadata:
    """Stores metadata about the index"""
    def __init__(self, root: Path):
        self.root = root
        self.last_indexed: datetime = datetime.now()
        self.indexed_files: Dict[str, float] = {}  # path -> last_modified_time
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
        
        # Initialize embedding function
        self.embedding_function = SentenceTransformerEmbeddings(
            model_name="all-MiniLM-L6-v2"
        )
        
        # Initialize processors
        self.processors: List[BaseFileProcessor] = [
            CodeProcessor(),
            ImageProcessor()  # Uses default model loaded in LM Studio
        ]
        
        # Initialize vector store
        self.vector_store: Optional[FAISS] = None
        
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
        
    def process_file(self, file_path: Path) -> Optional[Document]:
        """Process a single file and return a Document if successful"""
        try:
            processor = self.get_processor(file_path)
            if not processor:
                return None
                
            result = processor.process(file_path)
            
            # Create a Document for the vector store
            return Document(
                page_content=result["content"],
                metadata={
                    **result["metadata"],
                    "file_type": result["file_type"],
                    "summary": result.get("summary", ""),
                }
            )
        except Exception as e:
            self.logger.error(f"Error processing {file_path}: {str(e)}")
            return None
            
    def index(self):
        """Index the filesystem, updating only changed files"""
        documents = []
        
        for file_path in self.root.rglob("*"):
            # Skip directories and excluded paths
            if file_path.is_dir() or any(excluded in str(file_path) 
                                       for excluded in settings.EXCLUDED_DIRS):
                continue
                
            # Check if file needs indexing
            if not self.needs_indexing(file_path):
                continue
                
            # Process the file
            doc = self.process_file(file_path)
            if doc:
                documents.append(doc)
                self.metadata.indexed_files[str(file_path)] = file_path.stat().st_mtime
                
        # Update or create vector store
        if self.vector_store is None and documents:
            self.vector_store = FAISS.from_documents(
                documents, self.embedding_function
            )
        elif documents:
            self.vector_store.add_documents(documents)
            
        # Update metadata
        self.metadata.last_indexed = datetime.now()
        
    def save(self, directory: Path):
        """Save the index and metadata to disk"""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        
        # Save vector store
        if self.vector_store:
            self.vector_store.save_local(str(directory / "faiss_index"))
            
        # Save metadata
        with open(directory / "metadata.json", "w") as f:
            json.dump(self.metadata.to_json(), f, indent=2)
            
    def load(self, directory: Path):
        """Load the index and metadata from disk"""
        directory = Path(directory)
        
        # Load metadata
        try:
            with open(directory / "metadata.json", "r") as f:
                self.metadata = IndexMetadata.from_json(json.load(f))
        except FileNotFoundError:
            self.logger.warning("No metadata found, starting fresh")
            
        # Load vector store
        try:
            self.vector_store = FAISS.load_local(
                str(directory / "faiss_index"),
                self.embedding_function
            )
        except Exception as e:
            self.logger.warning(f"Could not load vector store: {str(e)}")
            self.vector_store = None 