from pathlib import Path
from typing import Dict, Any, Set
import configparser
import json

from .base import BaseFileProcessor

class ConfigProcessor(BaseFileProcessor):
    """Processor for handling configuration files"""
    
    def __init__(self):
        super().__init__()
        self.supported_extensions: Set[str] = {
            ".ini", ".conf", ".config", ".cfg", ".properties",
            ".env", ".env.local", ".env.production", ".env.development"
        }
        
    def can_handle(self, file_path: Path) -> bool:
        # Check extension
        if file_path.suffix.lower() in self.supported_extensions:
            return True
        # Also check for .env files (which might not have extension)
        if file_path.name.startswith('.env'):
            return True
        return False
    
    def process(self, file_path: Path) -> Dict[str, Any]:
        """Process a configuration file"""
        try:
            ext = file_path.suffix.lower()
            name = file_path.name.lower()
            
            if ext in {".ini", ".conf", ".config", ".cfg"}:
                content, summary = self._process_ini(file_path)
            elif ext == ".properties" or name.endswith(".properties"):
                content, summary = self._process_properties(file_path)
            elif ext == ".env" or name.startswith(".env"):
                content, summary = self._process_env(file_path)
            else:
                # Fallback: read as text
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                summary = self._create_fallback_summary(file_path, content)
            
            return {
                "content": content,
                "summary": summary,
                "file_type": "config",
                "config_type": self._detect_config_type(file_path),
                "metadata": {
                    "path": str(file_path),
                    "size": file_path.stat().st_size,
                    "modified": file_path.stat().st_mtime,
                }
            }
        except Exception as e:
            self.logger.error(f"Error processing config file {file_path}: {str(e)}")
            raise
    
    def _process_ini(self, file_path: Path) -> tuple[str, str]:
        """Process INI-style configuration file"""
        try:
            config = configparser.ConfigParser()
            config.read(file_path, encoding='utf-8')
            
            # Convert to JSON-like structure for content
            config_dict = {}
            for section in config.sections():
                config_dict[section] = dict(config.items(section))
            
            content = json.dumps(config_dict, indent=2)
            
            file_info = self.extract_file_info(file_path)
            
            # Create summary
            summary_parts = [file_info, "\nConfiguration sections:"]
            for section in config.sections():
                items = dict(config.items(section))
                summary_parts.append(f"  [{section}]")
                for key, value in list(items.items())[:5]:  # First 5 items per section
                    # Truncate long values
                    display_value = value if len(value) < 100 else value[:100] + "..."
                    summary_parts.append(f"    {key} = {display_value}")
                if len(items) > 5:
                    summary_parts.append(f"    ... and {len(items) - 5} more settings")
            
            summary = "\n".join(summary_parts)
            summary += f"\n\nFull content:\n{content}"
            
            return content, summary
        except Exception as e:
            self.logger.warning(f"Error parsing INI file {file_path}: {str(e)}")
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            summary = f"{self.extract_file_info(file_path)}\n\nINI file. Raw content:\n{content[:1000]}"
            return content, summary
    
    def _process_properties(self, file_path: Path) -> tuple[str, str]:
        """Process Java-style properties file"""
        try:
            properties = {}
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        properties[key.strip()] = value.strip()
            
            content = json.dumps(properties, indent=2)
            
            file_info = self.extract_file_info(file_path)
            
            summary_parts = [file_info, "\nConfiguration properties:"]
            for key, value in list(properties.items())[:20]:  # First 20 properties
                display_value = value if len(value) < 100 else value[:100] + "..."
                summary_parts.append(f"  {key} = {display_value}")
            
            if len(properties) > 20:
                summary_parts.append(f"\n... and {len(properties) - 20} more properties")
            
            summary = "\n".join(summary_parts)
            summary += f"\n\nFull content:\n{content}"
            
            return content, summary
        except Exception as e:
            self.logger.warning(f"Error parsing properties file {file_path}: {str(e)}")
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            summary = f"{self.extract_file_info(file_path)}\n\nProperties file. Raw content:\n{content[:1000]}"
            return content, summary
    
    def _process_env(self, file_path: Path) -> tuple[str, str]:
        """Process .env file"""
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
            
            content = json.dumps(env_vars, indent=2)
            
            file_info = self.extract_file_info(file_path)
            
            summary_parts = [file_info, "\nEnvironment variables:"]
            for key, value in list(env_vars.items())[:20]:  # First 20 variables
                # Mask sensitive values
                if any(sensitive in key.lower() for sensitive in ['password', 'secret', 'key', 'token', 'api']):
                    display_value = "***MASKED***"
                else:
                    display_value = value if len(value) < 100 else value[:100] + "..."
                summary_parts.append(f"  {key} = {display_value}")
            
            if len(env_vars) > 20:
                summary_parts.append(f"\n... and {len(env_vars) - 20} more variables")
            
            summary = "\n".join(summary_parts)
            summary += f"\n\nFull content (sensitive values may be masked):\n{content}"
            
            return content, summary
        except Exception as e:
            self.logger.warning(f"Error parsing .env file {file_path}: {str(e)}")
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            summary = f"{self.extract_file_info(file_path)}\n\n.env file. Raw content:\n{content[:1000]}"
            return content, summary
    
    def _create_fallback_summary(self, file_path: Path, content: str) -> str:
        """Create a fallback summary for unhandled config files"""
        file_info = self.extract_file_info(file_path)
        preview = content[:1000]
        if len(content) > 1000:
            preview += "\n[... content truncated ...]"
        return f"{file_info}\n\nContent:\n{preview}"
    
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

