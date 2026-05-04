"""
File utilities.
[UPDATED] Added 'is_safe_for_sandbox' for Asset Stratification.
"""
import os
from pathlib import Path


def ensure_dir(path: Path) -> None:
    """Ensure directory exists, creating parents if needed."""
    path.mkdir(parents=True, exist_ok=True)


def sanitize_path(path_str: str) -> str:
    """Prevents directory traversal."""
    return os.path.normpath(path_str).replace("..", "")


def guess_mime_type(filename: str) -> str:
    """Guess MIME type from filename extension."""
    suffix = Path(filename).suffix.lower()
    mime_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".svg": "image/svg+xml",
        ".pdf": "application/pdf",
        ".csv": "text/csv",
        ".json": "application/json",
        ".txt": "text/plain",
        # [FIX] Added LaTeX support
        ".tex": "application/x-tex",
        ".sty": "application/x-tex",
        ".cls": "application/x-tex",
        ".py": "text/x-python",
        ".md": "text/markdown"
    }
    return mime_types.get(suffix, "application/octet-stream")


def is_safe_for_sandbox(filename: str) -> bool:
    """
    [Asset Stratification]
    Determines if a file should be injected into the Sandbox Context.
    
    Strategy:
    - ALLOW: Source code, Data, Configs, Text (Lightweight, Computational)
    - BLOCK: Images, Videos, binaries (Heavy, Visual-only)
    
    This prevents 'Snowball Effect' where 100s of generated plots 
    clog the network for subsequent code execution nodes.
    """
    if not filename:
        return False

    # 1. Filter Hidden/System files (Allow .env)
    if filename.startswith('.') and not filename.startswith('.env'):
        return False
    if '__pycache__' in filename:
        return False
    
    # [FIX] Support exact filenames without extensions
    if filename.lower() in {'dockerfile', 'makefile', 'requirements.txt', 'license', 'readme'}:
        return True

    # 2. Whitelist Extensions (Core Context)
    ALLOWED_EXTENSIONS = {
        # Structured Data
        '.csv', '.tsv', '.xlsx', '.xls', '.parquet', '.json', '.jsonl', '.xml', '.txt',
        # [FIX] Data Science Binary Formats (Critical for Python context handover)
        '.pkl', '.pickle', '.npy', '.npz', '.h5', '.hdf5', '.joblib', '.pt', '.pth',
        # [FIX] Notebooks
        '.ipynb',
        # Code & Scripts
        '.py', '.js', '.ts', '.java', '.c', '.cpp', '.h', '.go', '.rs', '.sh', '.bat',
        # Config/Web
        '.yaml', '.yml', '.toml', '.ini', '.md', '.rst', '.log', '.conf', '.env', '.properties',
        '.html', '.css',
        # LaTeX (Source is text)
        '.tex', '.bib', '.sty', '.cls', '.bst'
    }
    
    ext = Path(filename).suffix.lower()
    return ext in ALLOWED_EXTENSIONS


def is_visual_asset(filename: str) -> bool:
    """
    Checks if the file is a visual artifact (Image/PDF).
    These are usually excluded from context unless specifically required (e.g. by Reporting nodes).
    """
    VISUAL_EXTENSIONS = {
        '.png', '.jpg', '.jpeg', '.svg', '.gif', '.bmp', '.tiff', 
        '.pdf', '.eps', '.mp4', '.avi'
    }
    ext = Path(filename).suffix.lower()
    return ext in VISUAL_EXTENSIONS


def is_file_type_allowed(filename: str) -> tuple[bool, str]:
    """
    Check if file type is allowed for upload.
    Returns (is_allowed, error_message).
    Prohibits images and zip files.
    """
    suffix = Path(filename).suffix.lower()
    
    # Prohibited file types: images and zip
    prohibited_extensions = {
        # Image formats
        ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", 
        ".ico", ".tiff", ".tif", ".heic", ".heif",
        # Archive formats
        ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"
    }
    
    if suffix in prohibited_extensions:
        file_type = "图片" if suffix in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", ".ico", ".tiff", ".tif", ".heic", ".heif"} else "压缩文件"
        return False, f"不支持上传{file_type}文件类型 ({suffix})"
    
    return True, ""

