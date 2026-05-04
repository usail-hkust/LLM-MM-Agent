"""
File ETL Tools - Stateless file inspection utilities.
"""
import csv
import io
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Optional dependencies
try:
    from pypdf import PdfReader
    HAS_PDF = True
except ImportError:
    HAS_PDF = False


class FileETL:
    """
    Stateless File Inspection Tools.
    """
    
    @staticmethod
    def _clean_str(text: str) -> str:
        """[FIX] Removes Null bytes which crash PostgreSQL JSONB."""
        if not text:
            return ""
        return text.replace("\x00", "")
    
    @staticmethod
    def inspect(filename: str, content: bytes) -> Dict[str, Any]:
        """
        Analyzes file bytes and returns a metadata summary.
        Does not persist anything.
        """
        ext = filename.split('.')[-1].lower() if '.' in filename else ""
        size_kb = len(content) / 1024
        
        info = {
            "filename": filename,
            "size_kb": round(size_kb, 2),
            "type": "binary"
        }

        try:
            if ext == 'pdf' and HAS_PDF:
                FileETL._inspect_pdf(content, info)
            elif ext == 'csv':
                FileETL._inspect_csv(content, info)
            elif ext in ('txt', 'md', 'json', 'py', 'tex'):
                info["type"] = "text"
                # [FIX] Sanitize preview text
                raw_text = content.decode('utf-8', errors='ignore')
                info["preview"] = FileETL._clean_str(raw_text)[:500]
        except Exception as e:
            logger.warning(f"ETL failed for {filename}: {e}")
            info["etl_error"] = str(e)
            
        return info

    @staticmethod
    def extract_text(filename: str, content: bytes) -> str:
        """
        Extracts plain text content from a file (PDF or Text-based).
        Used for context injection.
        """
        ext = filename.split('.')[-1].lower() if '.' in filename else ""
        text_result = ""
        
        try:
            if ext == 'pdf' and HAS_PDF:
                reader = PdfReader(io.BytesIO(content))
                text_parts = []
                for page in reader.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text_parts.append(extracted)
                text_result = "\n".join(text_parts)
            
            else:
                # Treat others as text (md, txt, json, tex, py, etc.)
                text_result = content.decode('utf-8', errors='ignore')
            
            # [FIX] Sanitize the final output immediately
            return FileETL._clean_str(text_result)
            
        except Exception as e:
            logger.warning(f"Failed to extract text from {filename}: {e}")
            return f"[Error extracting text from {filename}]"

    @staticmethod
    def _inspect_pdf(content: bytes, info: Dict[str, Any]):
        reader = PdfReader(io.BytesIO(content))
        info["type"] = "pdf"
        info["pages"] = len(reader.pages)
        if reader.pages:
            text = reader.pages[0].extract_text() or ""
            # [FIX] Sanitize preview
            clean_text = FileETL._clean_str(text)
            info["preview"] = clean_text[:500] + "..." if len(clean_text) > 500 else clean_text

    @staticmethod
    def _inspect_csv(content: bytes, info: Dict[str, Any]):
        """
        [FIX] Enhanced CSV inspection to extract headers.
        """
        # [FIX] Sanitize raw decode
        text = FileETL._clean_str(content.decode('utf-8', errors='ignore'))
        
        # Snippet for preview - increased buffer for better header detection
        snippet = io.StringIO(text[:4096]) 
        try:
            reader = csv.reader(snippet)
            rows = list(reader)
            if rows:
                headers = rows[0]
                info["type"] = "csv"
                info["headers"] = headers
                # Estimate row count based on newlines
                info["row_count_estimate"] = len(text.splitlines())
                # Add simple preview
                info["preview"] = f"Columns: {', '.join(headers[:10])}..."
        except Exception as e:
            info["csv_error"] = str(e)
            info["type"] = "csv"
            info["headers"] = []  # Fallback: ensure headers is always a list

