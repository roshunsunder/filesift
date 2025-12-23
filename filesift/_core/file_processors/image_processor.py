from pathlib import Path
from typing import Dict, Any, Set, Optional
import base64
from openai import OpenAI

from .base import BaseFileProcessor
from filesift._config.config import config_dict

class ImageProcessor(BaseFileProcessor):
    """Processor for handling image files using local LM Studio VLM via OpenAI API"""
    
    def __init__(self, model_name: Optional[str] = None):
        super().__init__()
        self.model_name = model_name or config_dict["models"]["IMAGE_MODEL"] or config_dict["models"]["MAIN_MODEL"]
        self.supported_extensions: Set[str] = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
        llm_api_key = config_dict["llm"]["LLM_API_KEY"]
        llm_base_url = config_dict["llm"]["LLM_BASE_URL"]
        if llm_base_url and len(llm_base_url) > 0:
            self.client = OpenAI(api_key=llm_api_key, base_url=llm_base_url)
        else:
            self.client = OpenAI(api_key=llm_api_key)
        
    def _encode_image(self, image_path: Path) -> str:
        """Encode image to base64 string"""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    
    def _get_image_mime_type(self, file_path: Path) -> str:
        """Get MIME type based on file extension"""
        ext = file_path.suffix.lower()
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp"
        }
        return mime_types.get(ext, "image/jpeg")
        
    def can_handle(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.supported_extensions
    
    def process(self, file_path: Path) -> Dict[str, Any]:
        """Process an image file using LM Studio VLM for captioning via OpenAI API"""
        try:
            base64_image = self._encode_image(file_path)
            mime_type = self._get_image_mime_type(file_path)
            
            prompt = "Describe this image in detail, focusing on key visual elements, objects, people, text, colors, and any important details that would be useful for search and retrieval."
            
            response = self.client.responses.create(
                model=self.model_name,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": prompt},
                            {
                                "type": "input_image",
                                "image_url": f"data:{mime_type};base64,{base64_image}",
                            },
                        ],
                    }
                ],
            )
            
            description = response.output_text
            
            return {
                "summary": description,
                "file_type": "image",
                "image_type": file_path.suffix.lower()[1:],
                "metadata": {
                    "path": str(file_path),
                    "size": file_path.stat().st_size,
                    "modified": file_path.stat().st_mtime,
                }
            }
        except Exception as e:
            self.logger.error(f"Error processing image file {file_path}: {str(e)}")
            raise 