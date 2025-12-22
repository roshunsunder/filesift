from pathlib import Path
from typing import Dict, Any, Set, Optional

from .base import BaseFileProcessor

class DocumentProcessor(BaseFileProcessor):
    """Processor for handling document files (PDF, DOCX, ODT)"""
    
    def __init__(self):
        super().__init__()
        self.supported_extensions: Set[str] = {
            ".pdf", ".docx", ".odt"
        }
        
        # Try to import optional dependencies
        self.pdf_available = False
        self.docx_available = False
        self.odt_available = False
        
        try:
            import PyPDF2
            self.pdf_available = True
            self.PyPDF2 = PyPDF2
        except ImportError:
            pass
        
        try:
            from docx import Document as DocxDocument
            self.docx_available = True
            self.DocxDocument = DocxDocument
        except ImportError:
            pass
        
        try:
            import odf.opendocument
            import odf.text
            self.odt_available = True
            self.odf = odf
        except ImportError:
            pass
        
    def can_handle(self, file_path: Path) -> bool:
        ext = file_path.suffix.lower()
        if ext == ".pdf" and not self.pdf_available:
            return False
        if ext == ".docx" and not self.docx_available:
            return False
        if ext == ".odt" and not self.odt_available:
            return False
        return ext in self.supported_extensions
    
    def process(self, file_path: Path) -> Dict[str, Any]:
        """Process a document file"""
        try:
            ext = file_path.suffix.lower()
            
            if ext == ".pdf":
                content, summary = self._process_pdf(file_path)
            elif ext == ".docx":
                content, summary = self._process_docx(file_path)
            elif ext == ".odt":
                content, summary = self._process_odt(file_path)
            else:
                # Fallback
                content = ""
                summary = f"{self.extract_file_info(file_path)}\n\nUnsupported document format."
            
            return {
                "content": content,
                "summary": summary,
                "file_type": "document",
                "document_type": self._detect_document_type(file_path),
                "metadata": {
                    "path": str(file_path),
                    "size": file_path.stat().st_size,
                    "modified": file_path.stat().st_mtime,
                }
            }
        except Exception as e:
            self.logger.error(f"Error processing document file {file_path}: {str(e)}")
            raise
    
    def _process_pdf(self, file_path: Path) -> tuple[str, str]:
        """Process PDF file"""
        if not self.pdf_available:
            raise ImportError("PyPDF2 is required for PDF processing. Install with: pip install PyPDF2")
        
        try:
            text_parts = []
            with open(file_path, 'rb') as f:
                pdf_reader = self.PyPDF2.PdfReader(f)
                num_pages = len(pdf_reader.pages)
                
                for page_num, page in enumerate(pdf_reader.pages[:10]):  # Limit to first 10 pages
                    text = page.extract_text()
                    if text.strip():
                        text_parts.append(f"--- Page {page_num + 1} ---\n{text}")
                
                if num_pages > 10:
                    text_parts.append(f"\n[... {num_pages - 10} more pages ...]")
            
            content = "\n\n".join(text_parts)
            
            file_info = self.extract_file_info(file_path)
            
            summary = f"{file_info}\n\nPDF Document:\n"
            summary += f"Total pages: {num_pages}\n"
            summary += f"Extracted text from first {min(10, num_pages)} pages:\n\n"
            summary += content[:2000]
            if len(content) > 2000:
                summary += "\n[... content truncated ...]"
            
            return content, summary
        except Exception as e:
            self.logger.warning(f"Error processing PDF {file_path}: {str(e)}")
            file_info = self.extract_file_info(file_path)
            summary = f"{file_info}\n\nError extracting text from PDF: {str(e)}"
            return "", summary
    
    def _process_docx(self, file_path: Path) -> tuple[str, str]:
        """Process DOCX file"""
        if not self.docx_available:
            raise ImportError("python-docx is required for DOCX processing. Install with: pip install python-docx")
        
        try:
            doc = self.DocxDocument(file_path)
            
            # Extract text from paragraphs
            paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
            content = "\n".join(paragraphs)
            
            # Extract tables
            table_texts = []
            for table in doc.tables:
                table_rows = []
                for row in table.rows:
                    row_cells = [cell.text.strip() for cell in row.cells]
                    table_rows.append(" | ".join(row_cells))
                if table_rows:
                    table_texts.append("\n".join(table_rows))
            
            if table_texts:
                content += "\n\n--- Tables ---\n" + "\n\n".join(table_texts)
            
            file_info = self.extract_file_info(file_path)
            
            summary = f"{file_info}\n\nDOCX Document:\n"
            summary += f"Paragraphs: {len(paragraphs)}\n"
            summary += f"Tables: {len(doc.tables)}\n\n"
            summary += "Content:\n" + content[:2000]
            if len(content) > 2000:
                summary += "\n[... content truncated ...]"
            
            return content, summary
        except Exception as e:
            self.logger.warning(f"Error processing DOCX {file_path}: {str(e)}")
            file_info = self.extract_file_info(file_path)
            summary = f"{file_info}\n\nError extracting text from DOCX: {str(e)}"
            return "", summary
    
    def _process_odt(self, file_path: Path) -> tuple[str, str]:
        """Process ODT file"""
        if not self.odt_available:
            raise ImportError("odfpy is required for ODT processing. Install with: pip install odfpy")
        
        try:
            doc = self.odf.opendocument.load(file_path)
            
            # Extract text from paragraphs
            paragraphs = []
            for para in doc.getElementsByType(self.odf.text.P):
                text = ""
                for node in para.childNodes:
                    if node.nodeType == 3:  # Text node
                        text += node.data
                if text.strip():
                    paragraphs.append(text.strip())
            
            content = "\n".join(paragraphs)
            
            file_info = self.extract_file_info(file_path)
            
            summary = f"{file_info}\n\nODT Document:\n"
            summary += f"Paragraphs: {len(paragraphs)}\n\n"
            summary += "Content:\n" + content[:2000]
            if len(content) > 2000:
                summary += "\n[... content truncated ...]"
            
            return content, summary
        except Exception as e:
            self.logger.warning(f"Error processing ODT {file_path}: {str(e)}")
            file_info = self.extract_file_info(file_path)
            summary = f"{file_info}\n\nError extracting text from ODT: {str(e)}"
            return "", summary
    
    def _detect_document_type(self, file_path: Path) -> str:
        """Detect the type of document file"""
        ext = file_path.suffix.lower()
        doc_types = {
            ".pdf": "PDF",
            ".docx": "DOCX",
            ".odt": "ODT"
        }
        return doc_types.get(ext, "unknown")

