from pathlib import Path
from typing import Dict, Any, Set
from openai import OpenAI
from langchain_community.document_loaders import TextLoader
import tiktoken

from .base import BaseFileProcessor
from src.config.settings import settings

class CodeProcessor(BaseFileProcessor):
    """Processor for handling code files"""
    
    def __init__(self, max_tokens_for_summary: int = 2000):
        super().__init__()
        self.supported_extensions: Set[str] = {
            ".py", ".js", ".java", ".cpp", ".c", ".h", ".hpp",
            ".cs", ".rb", ".go", ".rs", ".ts", ".php", ".swift"
        }
        self.client = OpenAI(api_key="lm-studio", base_url="http://localhost:1234/v1")
        # Reserve tokens for prompt and response (4096 - 3000 = 1096 for prompt + response)
        self.max_tokens_for_summary = max_tokens_for_summary
        # Use cl100k_base encoding (used by GPT models)
        try:
            self.encoding = tiktoken.get_encoding("cl100k_base")
        except:
            self.encoding = None
        
    def can_handle(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.supported_extensions
    
    def _truncate_code_for_summary(self, code: str) -> str:
        """Truncate code to fit within token limit for LLM summarization"""
        if self.encoding is None:
            # Fallback: rough estimate (1 token ≈ 4 characters)
            max_chars = self.max_tokens_for_summary * 4
            if len(code) <= max_chars:
                return code
            # Truncate and add indicator
            return code[:max_chars] + "\n\n[... code truncated for summary ...]"
        
        # Count tokens in the code
        tokens = self.encoding.encode(code)
        if len(tokens) <= self.max_tokens_for_summary:
            return code
        
        # Truncate to fit within token limit
        truncated_tokens = tokens[:self.max_tokens_for_summary]
        truncated_code = self.encoding.decode(truncated_tokens)
        
        # Add truncation indicator
        return truncated_code + "\n\n[... code truncated for summary ...]"
    
    def process(self, file_path: Path) -> Dict[str, Any]:
        """Process a code file using GPT to understand its purpose"""
        try:
            loader = TextLoader(str(file_path))
            code_doc = loader.load()
            code = "".join([i.page_content for i in code_doc])
            
            # Store full code for indexing (will be chunked later)
            full_code = code
            
            # Truncate code for LLM summarization to avoid context length issues
            code_for_summary = self._truncate_code_for_summary(code)
            
            # Get code summary from GPT
            prompt = f"Summarize the purpose of the following code:\n```\n{code_for_summary}\n```"
            messages = [{"role": "user", "content": prompt}]
            
            try:
                response = self.client.chat.completions.create(
                    model="google/gemma-3-4b",
                    messages=messages,
                    temperature=0
                )
                summary = response.choices[0].message.content
            except Exception as e:
                # If LLM call fails, use a fallback summary
                self.logger.warning(f"LLM summarization failed for {file_path}: {str(e)}")
                summary = f"Code file: {file_path.name} ({self._detect_language(file_path)})"
            
            return {
                "content": full_code,  # Use full code for indexing
                "summary": summary,
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