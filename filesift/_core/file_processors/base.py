from abc import ABC, abstractmethod
from typing import Dict, Any
from pathlib import Path
import logging
from datetime import datetime

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
    
    def extract_file_info(self, file_path: Path) -> str:
        """
        Return key information about a file such as its name, type, modification date, etc. in
        an LLM-friendly format for prompt enrichment.

        Args:
            file_path (Path): Path to the file to extract information from
        
        Returns:
            string: Text representation of the information
        """
        try:
            stat_info = file_path.stat()
            
            file_name = file_path.name
            file_extension = file_path.suffix if file_path.suffix else "no extension"
            file_type = file_extension[1:] if file_extension.startswith('.') else file_extension
            
            size_bytes = stat_info.st_size
            if size_bytes < 1024:
                size_str = f"{size_bytes} bytes"
            elif size_bytes < 1024 * 1024:
                size_str = f"{size_bytes / 1024:.2f} KB"
            else:
                size_str = f"{size_bytes / (1024 * 1024):.2f} MB"
            
            mod_time = datetime.fromtimestamp(stat_info.st_mtime)
            mod_date_str = mod_time.strftime("%Y-%m-%d %H:%M:%S")
            
            abs_path = str(file_path.resolve())
            
            info_lines = [
                f"File: {file_name}",
                f"Type: {file_type}",
                f"Extension: {file_extension}",
                f"Size: {size_str}",
                f"Modified: {mod_date_str}",
                f"Path: {abs_path}"
            ]
            
            return "\n".join(info_lines)
        except Exception as e:
            self.logger.warning(f"Error extracting file info for {file_path}: {str(e)}")
            # Return basic info even if stat fails
            return f"File: {file_path.name}\nPath: {str(file_path)}"