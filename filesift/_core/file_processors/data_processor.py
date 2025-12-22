from pathlib import Path
from typing import Dict, Any, Set
import json
import csv
import xml.etree.ElementTree as ET

from .base import BaseFileProcessor

# Optional dependencies
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
    
    def __init__(self):
        super().__init__()
        self.supported_extensions: Set[str] = {
            ".json", ".yaml", ".yml", ".xml", ".csv", ".toml"
        }
        
    def can_handle(self, file_path: Path) -> bool:
        ext = file_path.suffix.lower()
        if ext in {".yaml", ".yml"} and not yaml_available:
            return False
        if ext == ".toml" and not tomllib_available:
            return False
        return ext in self.supported_extensions
    
    def process(self, file_path: Path) -> Dict[str, Any]:
        """Process a structured data file"""
        try:
            ext = file_path.suffix.lower()
            
            if ext == ".json":
                content, summary = self._process_json(file_path)
            elif ext in {".yaml", ".yml"}:
                content, summary = self._process_yaml(file_path)
            elif ext == ".xml":
                content, summary = self._process_xml(file_path)
            elif ext == ".csv":
                content, summary = self._process_csv(file_path)
            elif ext == ".toml":
                content, summary = self._process_toml(file_path)
            else:
                # Fallback: read as text
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                summary = self._create_fallback_summary(file_path, content)
            
            return {
                "content": content,
                "summary": summary,
                "file_type": "data",
                "data_type": self._detect_data_type(file_path),
                "metadata": {
                    "path": str(file_path),
                    "size": file_path.stat().st_size,
                    "modified": file_path.stat().st_mtime,
                }
            }
        except Exception as e:
            self.logger.error(f"Error processing data file {file_path}: {str(e)}")
            raise
    
    def _process_json(self, file_path: Path) -> tuple[str, str]:
        """Process JSON file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            content = json.dumps(data, indent=2)
            file_info = self.extract_file_info(file_path)
            
            # Create summary with structure info
            structure = self._describe_json_structure(data)
            summary = f"{file_info}\n\nJSON Structure:\n{structure}\n\nContent:\n{content[:2000]}"
            if len(content) > 2000:
                summary += "\n[... content truncated ...]"
            
            return content, summary
        except json.JSONDecodeError as e:
            self.logger.warning(f"Invalid JSON in {file_path}: {str(e)}")
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            summary = f"{self.extract_file_info(file_path)}\n\nInvalid JSON file. Raw content:\n{content[:1000]}"
            return content, summary
    
    def _process_yaml(self, file_path: Path) -> tuple[str, str]:
        """Process YAML file"""
        if not yaml_available:
            raise ImportError("PyYAML is required for YAML processing. Install with: pip install PyYAML")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            content = yaml.dump(data, default_flow_style=False, allow_unicode=True)
            file_info = self.extract_file_info(file_path)
            
            # Create summary with structure info
            structure = self._describe_yaml_structure(data)
            summary = f"{file_info}\n\nYAML Structure:\n{structure}\n\nContent:\n{content[:2000]}"
            if len(content) > 2000:
                summary += "\n[... content truncated ...]"
            
            return content, summary
        except yaml.YAMLError as e:
            self.logger.warning(f"Invalid YAML in {file_path}: {str(e)}")
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            summary = f"{self.extract_file_info(file_path)}\n\nInvalid YAML file. Raw content:\n{content[:1000]}"
            return content, summary
    
    def _process_xml(self, file_path: Path) -> tuple[str, str]:
        """Process XML file"""
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # Get XML as string
            ET.indent(tree, space="  ")
            content = ET.tostring(root, encoding='unicode')
            
            file_info = self.extract_file_info(file_path)
            
            # Describe XML structure
            structure = self._describe_xml_structure(root)
            summary = f"{file_info}\n\nXML Structure:\n{structure}\n\nContent:\n{content[:2000]}"
            if len(content) > 2000:
                summary += "\n[... content truncated ...]"
            
            return content, summary
        except ET.ParseError as e:
            self.logger.warning(f"Invalid XML in {file_path}: {str(e)}")
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            summary = f"{self.extract_file_info(file_path)}\n\nInvalid XML file. Raw content:\n{content[:1000]}"
            return content, summary
    
    def _process_csv(self, file_path: Path) -> tuple[str, str]:
        """Process CSV file"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Try to detect delimiter
                sample = f.read(1024)
                f.seek(0)
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter
                
                reader = csv.DictReader(f, delimiter=delimiter)
                rows = list(reader)
                
                # Get headers
                headers = reader.fieldnames or []
                
                # Convert to JSON-like structure for content
                content = json.dumps(rows[:100], indent=2)  # Limit to first 100 rows
                if len(rows) > 100:
                    content += f"\n[... {len(rows) - 100} more rows ...]"
            
            file_info = self.extract_file_info(file_path)
            
            summary = f"{file_info}\n\nCSV Structure:\n"
            summary += f"Columns: {', '.join(headers)}\n"
            summary += f"Total rows: {len(rows)}\n\n"
            summary += f"Sample data (first 5 rows):\n{json.dumps(rows[:5], indent=2)}"
            if len(rows) > 5:
                summary += f"\n[... {len(rows) - 5} more rows ...]"
            
            return content, summary
        except Exception as e:
            self.logger.warning(f"Error processing CSV {file_path}: {str(e)}")
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            summary = f"{self.extract_file_info(file_path)}\n\nCSV file. Raw content:\n{content[:1000]}"
            return content, summary
    
    def _process_toml(self, file_path: Path) -> tuple[str, str]:
        """Process TOML file"""
        if not tomllib_available:
            raise ImportError("tomllib is required for TOML processing (Python 3.11+)")
        
        try:
            # Read content as text for output
            content = file_path.read_text(encoding='utf-8')
            
            # Parse with tomllib for structure analysis (requires binary mode)
            with open(file_path, 'rb') as f:
                data = tomllib.load(f)
            
            file_info = self.extract_file_info(file_path)
            
            # Create summary with structure info
            structure = self._describe_toml_structure(data)
            summary = f"{file_info}\n\nTOML Structure:\n{structure}\n\nContent:\n{content[:2000]}"
            if len(content) > 2000:
                summary += "\n[... content truncated ...]"
            
            return content, summary
        except Exception as e:
            self.logger.warning(f"Invalid TOML in {file_path}: {str(e)}")
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            summary = f"{self.extract_file_info(file_path)}\n\nInvalid TOML file. Raw content:\n{content[:1000]}"
            return content, summary
    
    def _describe_json_structure(self, data: Any, depth: int = 0, max_depth: int = 3) -> str:
        """Describe the structure of a JSON object"""
        if depth > max_depth:
            return "..."
        
        if isinstance(data, dict):
            items = []
            for key, value in list(data.items())[:10]:  # Limit to 10 keys
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
    
    def _create_fallback_summary(self, file_path: Path, content: str) -> str:
        """Create a fallback summary for unhandled data files"""
        file_info = self.extract_file_info(file_path)
        preview = content[:1000]
        if len(content) > 1000:
            preview += "\n[... content truncated ...]"
        return f"{file_info}\n\nContent:\n{preview}"
    
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

