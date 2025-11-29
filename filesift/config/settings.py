from pathlib import Path
from typing import Set, Dict, Any
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Settings:
    """Global settings for the application"""
    
    # API Keys
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    HF_BEARER_TOKEN: str = os.getenv("HF_BEARER_TOKEN", "")
    
    # Server settings
    API_HOST: str = os.getenv("API_HOST", "127.0.0.1")
    API_PORT: int = int(os.getenv("API_PORT", "8686"))
    DEBUG_MODE: bool = os.getenv("DEBUG_MODE", "False").lower() == "true"
    
    # Search settings
    MAX_RESULTS: int = int(os.getenv("MAX_RESULTS", "10"))
    SIMILARITY_THRESHOLD: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.7"))
    
    # Indexing settings
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1000"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "200"))
    
    # File type settings
    EXCLUDED_DIRS: Set[str] = {
        ".git", "node_modules", "__pycache__", 
        "venv", "env", ".env", "build", "dist"
    }
    
    # Cache settings
    ENABLE_CACHE: bool = os.getenv("ENABLE_CACHE", "True").lower() == "true"
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "3600"))  # 1 hour default
    
    @classmethod
    def validate(cls) -> Dict[str, Any]:
        """Validate the configuration and return any issues"""
        issues = {}
        
        if not cls.OPENAI_API_KEY:
            issues["OPENAI_API_KEY"] = "Missing OpenAI API key"
        if not cls.HF_BEARER_TOKEN:
            issues["HF_BEARER_TOKEN"] = "Missing Hugging Face bearer token"
            
        return issues

# Create a global settings instance
settings = Settings() 