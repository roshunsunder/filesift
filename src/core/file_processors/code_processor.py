from pathlib import Path
from typing import Dict, Any, Set
import openai
from langchain_community.document_loaders import TextLoader

from .base import BaseFileProcessor

class CodeProcessor(BaseFileProcessor):
    """Processor for handling code files"""
    
    def __init__(self):
        super().__init__()
        self.supported_extensions: Set[str] = {
            ".py", ".js", ".java", ".cpp", ".c", ".h", ".hpp",
            ".cs", ".rb", ".go", ".rs", ".ts", ".php", ".swift"
        }
        
    def can_handle(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.supported_extensions
    
    def process(self, file_path: Path) -> Dict[str, Any]:
        """Process a code file using GPT to understand its purpose"""
        try:
            loader = TextLoader(str(file_path))
            code_doc = loader.load()
            code = "".join([i.page_content for i in code_doc])
            
            # Get code summary from GPT
            prompt = f"Summarize the purpose of the following code:\n```\n{code}\n```"
            messages = [{"role": "user", "content": prompt}]
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=0
            )
            
            return {
                "content": code,
                "summary": response.choices[0].message["content"],
                "file_type": "code",
                "language": self._detect_language(file_path),
                "metadata": {
                    "path": str(file_path),
                    "size": file_path.stat().st_size,
                    "modified": file_path.stat().st_mtime,
                }
            }
        except Exception as e:
            self.logger.error(f"Error processing code file {file_path}: {str(e)}")
            raise
            
    def _detect_language(self, file_path: Path) -> str:
        """Detect programming language based on file extension"""
        ext_to_lang = {
            ".py": "Python",
            ".js": "JavaScript",
            ".java": "Java",
            ".cpp": "C++",
            ".c": "C",
            ".h": "C Header",
            ".hpp": "C++ Header",
            ".cs": "C#",
            ".rb": "Ruby",
            ".go": "Go",
            ".rs": "Rust",
            ".ts": "TypeScript",
            ".php": "PHP",
            ".swift": "Swift"
        }
        return ext_to_lang.get(file_path.suffix.lower(), "Unknown") 