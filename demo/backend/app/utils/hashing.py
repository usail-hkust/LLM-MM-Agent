"""
Hashing utilities.
"""
import hashlib
from uuid import uuid4


def compute_sha256(data: bytes) -> str:
    """Compute SHA256 hash of bytes."""
    return hashlib.sha256(data).hexdigest()


def generate_id() -> str:
    """Generate a UUID string."""
    return str(uuid4())

