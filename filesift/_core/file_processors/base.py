from abc import ABC, abstractmethod
from typing import Dict, Any
from pathlib import Path
import logging

class BaseFileProcessor(ABC):
    """Base class for all file processors"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def process(self, file_path: Path) -> Dict[str, Any]:
        """
        Process a file and return its metadata and content.
        
        Args:
            file_path (Path): Path to the file to process
            
        Returns:
            Dict[str, Any]: Dictionary containing processed content and metadata
        """
        pass

    @abstractmethod
    def can_handle(self, file_path: Path) -> bool:
        """
        Check if this processor can handle the given file.
        
        Args:
            file_path (Path): Path to the file to check
            
        Returns:
            bool: True if this processor can handle the file, False otherwise
        """
        pass 