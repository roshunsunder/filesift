from pathlib import Path
from typing import Dict, Any, Set, Optional
from .base import BaseFileProcessor

try:
    import lmstudio as lms
except ImportError:
    lms = None

def extract_text(result):
    """Extract text from a PredictionResult or other response object"""
    if hasattr(result, 'text'):
        return result.text
    elif hasattr(result, 'content'):
        return result.content
    elif hasattr(result, 'message'):
        msg = result.message
        if hasattr(msg, 'content'):
            return msg.content
        return str(msg)
    else:
        return str(result)

class ImageProcessor(BaseFileProcessor):
    """Processor for handling image files using local LM Studio VLM"""
    
    def __init__(self, model_name: Optional[str] = None):
        super().__init__()
        if lms is None:
            raise ImportError(
                "lmstudio package is required for ImageProcessor. "
                "Install it with: pip install lmstudio"
            )
        self.model_name = model_name
        # LM Studio supports JPEG, PNG, and WebP, but we'll keep broader support
        # for files that might be converted or handled elsewhere
        self.supported_extensions: Set[str] = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
        
    def can_handle(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.supported_extensions
    
    def process(self, file_path: Path) -> Dict[str, Any]:
        """Process an image file using LM Studio VLM for captioning"""
        try:
            # Prepare the image for LM Studio
            image_handle = lms.prepare_image(str(file_path))
            
            # Initialize model (use specified model or default to loaded model)
            if self.model_name:
                model = lms.llm(self.model_name)
            else:
                model = lms.llm()  # Uses currently loaded model in LM Studio
            
            # Create chat and add image with prompt
            chat = lms.Chat()
            prompt = "Describe this image in detail, focusing on key visual elements, objects, people, text, colors, and any important details that would be useful for search and retrieval."
            chat.add_user_message(prompt, images=[image_handle])
            
            # Get response from model
            prediction = model.respond(chat)
            
            # Extract text from response
            description = extract_text(prediction)
            
            return {
                "content": description,
                "file_type": "image",
                "image_type": file_path.suffix.lower()[1:],  # Remove the dot
                "metadata": {
                    "path": str(file_path),
                    "size": file_path.stat().st_size,
                    "modified": file_path.stat().st_mtime,
                }
            }
        except Exception as e:
            self.logger.error(f"Error processing image file {file_path}: {str(e)}")
            raise 