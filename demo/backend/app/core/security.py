"""
Security utilities - JWT and password hashing.
"""
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Union, Any

from jose import jwt
import bcrypt
from app.core.config import settings


def _prehash_password(password: bytes) -> bytes:
    """
    Pre-hash password with SHA-256 to handle bcrypt's 72-byte limit.
    This ensures passwords of any length can be securely hashed.
    """
    return hashlib.sha256(password).digest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    if isinstance(plain_password, str):
        plain_password = plain_password.encode('utf-8')
    if isinstance(hashed_password, str):
        hashed_password = hashed_password.encode('utf-8')
    
    # Pre-hash the password to handle bcrypt's 72-byte limit
    prehashed = _prehash_password(plain_password)
    return bcrypt.checkpw(prehashed, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash a password using SHA-256 + bcrypt to handle passwords longer than 72 bytes.
    This ensures bcrypt's 72-byte limit is never exceeded while maintaining security.
    """
    if isinstance(password, str):
        password = password.encode('utf-8')
    
    # Pre-hash with SHA-256 to ensure we're always under bcrypt's 72-byte limit
    prehashed = _prehash_password(password)
    
    # Use default 12 rounds and decode to string for storage
    return bcrypt.hashpw(prehashed, bcrypt.gensalt()).decode('utf-8')


def create_access_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt
