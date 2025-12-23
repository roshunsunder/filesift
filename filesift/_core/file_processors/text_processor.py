from pathlib import Path
from typing import Dict, Any, Set
from langchain_community.document_loaders import TextLoader
from openai import OpenAI
import tiktoken

from .base import BaseFileProcessor
from filesift._config.config import config_dict

class TextProcessor(BaseFileProcessor):
    """Processor for handling plain text files"""
    
    def __init__(self, max_tokens_for_summary: int = 2000):
        super().__init__()
        self.supported_extensions: Set[str] = {
            ".txt", ".md", ".markdown", ".rst", ".log", ".text",
            ".readme", ".license", ".changelog", ".history",
            ".gitignore", ".gitattributes", ".editorconfig"
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
    
    def _truncate_content_for_summary(self, content: str) -> str:
        """Truncate content to fit within token limit for LLM summarization"""
        if self.encoding is None:
            max_chars = self.max_tokens_for_summary * 4
            if len(content) <= max_chars:
                return content
            return content[:max_chars] + "\n\n[... content truncated for summary ...]"
        
        tokens = self.encoding.encode(content)
        if len(tokens) <= self.max_tokens_for_summary:
            return content
        
        truncated_tokens = tokens[:self.max_tokens_for_summary]
        truncated_content = self.encoding.decode(truncated_tokens)
        
        return truncated_content + "\n\n[... content truncated for summary ...]"
    
    def _generate_llm_summary(self, file_path: Path, content: str, text_type: str) -> str:
        """Generate summary using LLM"""
        file_info = self.extract_file_info(file_path)
        content_for_summary = self._truncate_content_for_summary(content)
        
        prompt = (
            f"Here is some information about a {text_type} text file:\n{file_info}\n"
            "Analyze this text file content and provide a concise, technical summary for a search index. "
            "Focus on the main topics, key information, structure, and important details. "
            "Do not include the full content or conversational filler. "
            "Start directly with the description.\n"
            f"```\n{content_for_summary}\n```"
        )
        messages = [{"role": "user", "content": prompt}]
        
        try:
            model = config_dict["models"]["MAIN_MODEL"]
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0
            )
            return response.choices[0].message.content
        except Exception as e:
            self.logger.warning(f"LLM summarization failed for {file_path}: {str(e)}")
            return f"{text_type} text file: {file_path.name}\n{file_info}"
    
    def process(self, file_path: Path) -> Dict[str, Any]:
        """Process a plain text file"""
        try:
            loader = TextLoader(str(file_path))
            doc = loader.load()
            content = "".join([page.page_content for page in doc])
            
            text_type = self._detect_text_type(file_path)
            if content:
                summary = self._generate_llm_summary(file_path, content, text_type)
            else:
                summary = f"{self.extract_file_info(file_path)}\n\nEmpty text file."
            
            return {
                "content": content,
                "summary": summary,
                "file_type": "text",
                "text_type": text_type,
                "metadata": {
                    "path": str(file_path),
                    "size": file_path.stat().st_size,
                    "modified": file_path.stat().st_mtime,
                }
            }
        except Exception as e:
            self.logger.error(f"Error processing text file {file_path}: {str(e)}")
            raise
    
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

