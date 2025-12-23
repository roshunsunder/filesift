from pathlib import Path
from typing import Dict, Any, Set
from openai import OpenAI
from langchain_community.document_loaders import TextLoader
import tiktoken

from .base import BaseFileProcessor
from filesift._config.config import config_dict

class CodeProcessor(BaseFileProcessor):
    """Processor for handling code files"""
    
    def __init__(self, max_tokens_for_summary: int = 2000):
        super().__init__()
        self.supported_extensions: Set[str] = {
            ".py", ".js", ".java", ".cpp", ".c", ".h", ".hpp",
            ".cs", ".rb", ".go", ".rs", ".ts", ".php", ".swift",
            ".html"
        }
        llm_api_key = config_dict["llm"]["LLM_API_KEY"]
        llm_base_url = config_dict["llm"]["LLM_BASE_URL"]
        if llm_base_url and len(llm_base_url) > 0:
            self.client = OpenAI(api_key=llm_api_key, base_url=llm_base_url)
        else:
            self.client = OpenAI(api_key=llm_api_key)

        self.max_tokens_for_summary = max_tokens_for_summary

        try:
            self.encoding = tiktoken.get_encoding("cl100k_base")
        except:
            self.encoding = None
        
    def can_handle(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.supported_extensions
    
    def _truncate_code_for_summary(self, code: str) -> str:
        """Truncate code to fit within token limit for LLM summarization"""
        if self.encoding is None:
            max_chars = self.max_tokens_for_summary * 4
            if len(code) <= max_chars:
                return code
            return code[:max_chars] + "\n\n[... code truncated for summary ...]"
        
        tokens = self.encoding.encode(code)
        if len(tokens) <= self.max_tokens_for_summary:
            return code
        

        truncated_tokens = tokens[:self.max_tokens_for_summary]
        truncated_code = self.encoding.decode(truncated_tokens)
        
        return truncated_code + "\n\n[... code truncated for summary ...]"
    
    def process(self, file_path: Path) -> Dict[str, Any]:
        """Process a code file using GPT to understand its purpose"""
        try:
            loader = TextLoader(str(file_path))
            code_doc = loader.load()
            code = "".join([i.page_content for i in code_doc])
            
            full_code = code
            
            code_for_summary = self._truncate_code_for_summary(code)

            file_info = self.extract_file_info(file_path)
            
            prompt = (
                f"Here is some information about a code file:\n{file_info}\n"
                "Analyze this code and provide a concise, technical summary for a search index. "
                "Focus on the main purpose, key classes/functions, and architectural role. "
                "Do not include the source code or conversational filler. "
                "Start directly with the description.\n"
                f"```\n{code_for_summary}\n```"
            )
            messages = [{"role": "user", "content": prompt}]
            
            try:
                code_model = config_dict["models"]["MAIN_MODEL"]
                response = self.client.chat.completions.create(
                    model=code_model,
                    messages=messages,
                    temperature=0
                )
                summary = response.choices[0].message.content
            except Exception as e:
                self.logger.warning(f"LLM summarization failed for {file_path}: {str(e)}")
                summary = f"Code file: {file_path.name} ({self._detect_language(file_path)})"
            
            return {
                "content": full_code,
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