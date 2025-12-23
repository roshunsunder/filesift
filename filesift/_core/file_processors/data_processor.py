from pathlib import Path
from typing import Dict, Any, Set
import json
import csv
import xml.etree.ElementTree as ET
from openai import OpenAI
import tiktoken

from .base import BaseFileProcessor
from filesift._config.config import config_dict

try:
    import yaml
    yaml_available = True
except ImportError:
    yaml_available = False

try:
    import tomllib
    tomllib_available = True
except ImportError:
    tomllib_available = False

class DataProcessor(BaseFileProcessor):
    """Processor for handling structured data files"""
    
    def __init__(self, max_tokens_for_summary: int = 2000):
        super().__init__()
        self.supported_extensions: Set[str] = {
            ".json", ".yaml", ".yml", ".xml", ".csv", ".toml"
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
        ext = file_path.suffix.lower()
        if ext in {".yaml", ".yml"} and not yaml_available:
            return False
        if ext == ".toml" and not tomllib_available:
            return False
        return ext in self.supported_extensions
    
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
    
    def _generate_llm_summary(self, file_path: Path, content: str, data_type: str) -> str:
        """Generate summary using LLM"""
        file_info = self.extract_file_info(file_path)
        content_for_summary = self._truncate_content_for_summary(content)
        
        prompt = (
            f"Here is some information about a {data_type} data file:\n{file_info}\n"
            "Analyze this data file content and provide a concise, technical summary for a search index. "
            "Focus on the data structure, key fields, important values, and what this data represents. "
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
            return f"{data_type} data file: {file_path.name}\n{file_info}"
    
    def process(self, file_path: Path) -> Dict[str, Any]:
        """Process a structured data file"""
        try:
            ext = file_path.suffix.lower()
            
            if ext == ".json":
                content = self._process_json(file_path)
            elif ext in {".yaml", ".yml"}:
                content = self._process_yaml(file_path)
            elif ext == ".xml":
                content = self._process_xml(file_path)
            elif ext == ".csv":
                content = self._process_csv(file_path)
            elif ext == ".toml":
                content = self._process_toml(file_path)
            else:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
            
            data_type = self._detect_data_type(file_path)
            if content:
                summary = self._generate_llm_summary(file_path, content, data_type)
            else:
                summary = f"{self.extract_file_info(file_path)}\n\nEmpty or unreadable data file."
            
            return {
                "content": content,
                "summary": summary,
                "file_type": "data",
                "data_type": data_type,
                "metadata": {
                    "path": str(file_path),
                    "size": file_path.stat().st_size,
                    "modified": file_path.stat().st_mtime,
                }
            }
        except Exception as e:
            self.logger.error(f"Error processing data file {file_path}: {str(e)}")
            raise
    
    def _process_json(self, file_path: Path) -> str:
        """Process JSON file and return formatted content"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            return json.dumps(data, indent=2)
        except json.JSONDecodeError as e:
            self.logger.warning(f"Invalid JSON in {file_path}: {str(e)}")
            return file_path.read_text(encoding='utf-8', errors='ignore')
    
    def _process_yaml(self, file_path: Path) -> str:
        """Process YAML file and return formatted content"""
        if not yaml_available:
            raise ImportError("PyYAML is required for YAML processing. Install with: pip install PyYAML")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            return yaml.dump(data, default_flow_style=False, allow_unicode=True)
        except yaml.YAMLError as e:
            self.logger.warning(f"Invalid YAML in {file_path}: {str(e)}")
            return file_path.read_text(encoding='utf-8', errors='ignore')
    
    def _process_xml(self, file_path: Path) -> str:
        """Process XML file and return formatted content"""
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            ET.indent(tree, space="  ")
            return ET.tostring(root, encoding='unicode')
        except ET.ParseError as e:
            self.logger.warning(f"Invalid XML in {file_path}: {str(e)}")
            return file_path.read_text(encoding='utf-8', errors='ignore')
    
    def _process_csv(self, file_path: Path) -> str:
        """Process CSV file and return JSON-formatted content"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                sample = f.read(1024)
                f.seek(0)
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter
                
                reader = csv.DictReader(f, delimiter=delimiter)
                rows = list(reader)
                
                content = json.dumps(rows[:100], indent=2)
                if len(rows) > 100:
                    content += f"\n[... {len(rows) - 100} more rows ...]"
                
                return content
        except Exception as e:
            self.logger.warning(f"Error processing CSV {file_path}: {str(e)}")
            return file_path.read_text(encoding='utf-8', errors='ignore')
    
    def _process_toml(self, file_path: Path) -> str:
        """Process TOML file and return content"""
        if not tomllib_available:
            raise ImportError("tomllib is required for TOML processing (Python 3.11+)")
        
        try:
            return file_path.read_text(encoding='utf-8')
        except Exception as e:
            self.logger.warning(f"Invalid TOML in {file_path}: {str(e)}")
            return file_path.read_text(encoding='utf-8', errors='ignore')
    
    def _describe_json_structure(self, data: Any, depth: int = 0, max_depth: int = 3) -> str:
        """Describe the structure of a JSON object"""
        if depth > max_depth:
            return "..."
        
        if isinstance(data, dict):
            items = []
            for key, value in list(data.items())[:10]:
                value_type = type(value).__name__
                if isinstance(value, (dict, list)):
                    items.append(f"  {key}: {value_type} ({self._describe_json_structure(value, depth+1, max_depth)})")
                else:
                    items.append(f"  {key}: {value_type}")
            if len(data) > 10:
                items.append(f"  ... and {len(data) - 10} more keys")
            return "{\n" + "\n".join(items) + "\n}"
        elif isinstance(data, list):
            if len(data) > 0:
                item_type = type(data[0]).__name__
                return f"list[{item_type}] (length: {len(data)})"
            return "list[]"
        else:
            return type(data).__name__
    
    def _describe_yaml_structure(self, data: Any, depth: int = 0, max_depth: int = 3) -> str:
        """Describe the structure of a YAML object"""
        return self._describe_json_structure(data, depth, max_depth)
    
    def _describe_toml_structure(self, data: Any, depth: int = 0, max_depth: int = 3) -> str:
        """Describe the structure of a TOML object"""
        return self._describe_json_structure(data, depth, max_depth)
    
    def _describe_xml_structure(self, root: ET.Element, depth: int = 0, max_depth: int = 3) -> str:
        """Describe the structure of an XML document"""
        if depth > max_depth:
            return "..."
        
        lines = []
        lines.append(f"Root element: {root.tag}")
        
        if root.attrib:
            lines.append(f"  Attributes: {', '.join(root.attrib.keys())}")
        
        children = list(root)
        if children:
            child_tags = {}
            for child in children[:10]:
                tag = child.tag
                child_tags[tag] = child_tags.get(tag, 0) + 1
            
            for tag, count in child_tags.items():
                lines.append(f"  {tag}: {count} occurrence(s)")
            
            if len(children) > 10:
                lines.append(f"  ... and {len(children) - 10} more elements")
        
        return "\n".join(lines)
    
    def _detect_data_type(self, file_path: Path) -> str:
        """Detect the type of data file"""
        ext = file_path.suffix.lower()
        data_types = {
            ".json": "JSON",
            ".yaml": "YAML",
            ".yml": "YAML",
            ".xml": "XML",
            ".csv": "CSV",
            ".toml": "TOML"
        }
        return data_types.get(ext, "unknown")

