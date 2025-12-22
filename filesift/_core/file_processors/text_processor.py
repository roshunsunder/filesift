from pathlib import Path
from typing import Dict, Any, Set
from langchain_community.document_loaders import TextLoader

from .base import BaseFileProcessor

class TextProcessor(BaseFileProcessor):
    """Processor for handling plain text files"""
    
    def __init__(self):
        super().__init__()
        self.supported_extensions: Set[str] = {
            ".txt", ".md", ".markdown", ".rst", ".log", ".text",
            ".readme", ".license", ".changelog", ".history",
            ".gitignore", ".gitattributes", ".editorconfig"
        }
        
    def can_handle(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.supported_extensions
    
    def process(self, file_path: Path) -> Dict[str, Any]:
        """Process a plain text file"""
        try:
            loader = TextLoader(str(file_path))
            doc = loader.load()
            content = "".join([page.page_content for page in doc])
            
            file_info = self.extract_file_info(file_path)
            
            # For markdown files, include structure info in summary
            if file_path.suffix.lower() in {".md", ".markdown"}:
                summary = self._create_markdown_summary(file_path, content)
            else:
                # Create a simple summary from first lines
                summary = self._create_text_summary(file_path, content)
            
            return {
                "content": content,
                "summary": summary,
                "file_type": "text",
                "text_type": self._detect_text_type(file_path),
                "metadata": {
                    "path": str(file_path),
                    "size": file_path.stat().st_size,
                    "modified": file_path.stat().st_mtime,
                }
            }
        except Exception as e:
            self.logger.error(f"Error processing text file {file_path}: {str(e)}")
            raise
    
    def _create_text_summary(self, file_path: Path, content: str) -> str:
        """Create a summary from the first portion of text content"""
        lines = content.split('\n')
        first_lines = lines[:20]  # First 20 lines
        preview = '\n'.join(first_lines)
        
        if len(lines) > 20:
            preview += f"\n\n[... {len(lines) - 20} more lines ...]"
        
        file_info = self.extract_file_info(file_path)
        return f"{file_info}\n\nContent preview:\n{preview}"
    
    def _create_markdown_summary(self, file_path: Path, content: str) -> str:
        """Create a summary for markdown files, extracting structure"""
        lines = content.split('\n')
        
        # Extract headers and structure
        headers = []
        for line in lines[:100]:  # Check first 100 lines for headers
            stripped = line.strip()
            if stripped.startswith('#'):
                level = len(stripped) - len(stripped.lstrip('#'))
                header_text = stripped.lstrip('#').strip()
                if header_text:
                    headers.append(f"{'  ' * (level - 1)}- {header_text}")
        
        file_info = self.extract_file_info(file_path)
        
        summary_parts = [file_info]
        
        if headers:
            summary_parts.append("\nDocument structure:")
            summary_parts.extend(headers[:15])  # Limit to 15 headers
            if len(headers) > 15:
                summary_parts.append(f"\n[... {len(headers) - 15} more sections ...]")
        
        # Add content preview
        preview_lines = lines[:30]
        preview = '\n'.join(preview_lines)
        if len(lines) > 30:
            preview += f"\n\n[... {len(lines) - 30} more lines ...]"
        
        summary_parts.append(f"\n\nContent preview:\n{preview}")
        
        return '\n'.join(summary_parts)
    
    def _detect_text_type(self, file_path: Path) -> str:
        """Detect the type of text file based on extension"""
        ext = file_path.suffix.lower()
        text_types = {
            ".txt": "plain text",
            ".md": "markdown",
            ".markdown": "markdown",
            ".rst": "reStructuredText",
            ".log": "log file",
            ".text": "plain text",
            ".readme": "readme",
            ".license": "license",
            ".changelog": "changelog",
            ".history": "history",
            ".gitignore": "gitignore",
            ".gitattributes": "gitattributes",
            ".editorconfig": "editorconfig"
        }
        return text_types.get(ext, "plain text")

