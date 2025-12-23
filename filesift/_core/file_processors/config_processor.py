from pathlib import Path
from typing import Dict, Any, Set
import configparser
import json
from openai import OpenAI
import tiktoken

from .base import BaseFileProcessor
from filesift._config.config import config_dict

class ConfigProcessor(BaseFileProcessor):
    """Processor for handling configuration files"""
    
    def __init__(self, max_tokens_for_summary: int = 2000):
        super().__init__()
        self.supported_extensions: Set[str] = {
            ".ini", ".conf", ".config", ".cfg", ".properties",
            ".env", ".env.local", ".env.production", ".env.development"
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
        if file_path.suffix.lower() in self.supported_extensions:
            return True
        if file_path.name.startswith('.env'):
            return True
        return False
    
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
    
    def _generate_llm_summary(self, file_path: Path, content: str, config_type: str) -> str:
        """Generate summary using LLM"""
        file_info = self.extract_file_info(file_path)
        content_for_summary = self._truncate_content_for_summary(content)
        
        prompt = (
            f"Here is some information about a {config_type} configuration file:\n{file_info}\n"
            "Analyze this configuration file content and provide a concise, technical summary for a search index. "
            "Focus on what this configuration controls, key settings, and their purposes. "
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
            return f"{config_type} configuration file: {file_path.name}\n{file_info}"
    
    def process(self, file_path: Path) -> Dict[str, Any]:
        """Process a configuration file"""
        try:
            ext = file_path.suffix.lower()
            name = file_path.name.lower()
            
            if ext in {".ini", ".conf", ".config", ".cfg"}:
                content = self._process_ini(file_path)
            elif ext == ".properties" or name.endswith(".properties"):
                content = self._process_properties(file_path)
            elif ext == ".env" or name.startswith(".env"):
                content = self._process_env(file_path)
            else:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
            
            config_type = self._detect_config_type(file_path)
            if content:
                summary = self._generate_llm_summary(file_path, content, config_type)
            else:
                summary = f"{self.extract_file_info(file_path)}\n\nEmpty or unreadable configuration file."
            
            return {
                "content": content,
                "summary": summary,
                "file_type": "config",
                "config_type": config_type,
                "metadata": {
                    "path": str(file_path),
                    "size": file_path.stat().st_size,
                    "modified": file_path.stat().st_mtime,
                }
            }
        except Exception as e:
            self.logger.error(f"Error processing config file {file_path}: {str(e)}")
            raise
    
    def _process_ini(self, file_path: Path) -> str:
        """Process INI-style configuration file and return JSON-formatted content"""
        try:
            config = configparser.ConfigParser()
            config.read(file_path, encoding='utf-8')
            
            config_dict = {}
            for section in config.sections():
                config_dict[section] = dict(config.items(section))
            
            return json.dumps(config_dict, indent=2)
        except Exception as e:
            self.logger.warning(f"Error parsing INI file {file_path}: {str(e)}")
            return file_path.read_text(encoding='utf-8', errors='ignore')
    
    def _process_properties(self, file_path: Path) -> str:
        """Process Java-style properties file and return JSON-formatted content"""
        try:
            properties = {}
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        properties[key.strip()] = value.strip()
            
            return json.dumps(properties, indent=2)
        except Exception as e:
            self.logger.warning(f"Error parsing properties file {file_path}: {str(e)}")
            return file_path.read_text(encoding='utf-8', errors='ignore')
    
    def _process_env(self, file_path: Path) -> str:
        """Process .env file and return JSON-formatted content"""
        try:
            env_vars = {}
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        # Remove quotes if present
                        value = value.strip('"\'')
                        env_vars[key.strip()] = value
            
            return json.dumps(env_vars, indent=2)
        except Exception as e:
            self.logger.warning(f"Error parsing .env file {file_path}: {str(e)}")
            return file_path.read_text(encoding='utf-8', errors='ignore')
    
    def _detect_config_type(self, file_path: Path) -> str:
        """Detect the type of config file"""
        ext = file_path.suffix.lower()
        name = file_path.name.lower()
        
        if ext in {".ini", ".conf", ".config", ".cfg"}:
            return "INI"
        elif ext == ".properties" or name.endswith(".properties"):
            return "Properties"
        elif ext == ".env" or name.startswith(".env"):
            return "Environment"
        else:
            return "Config"

