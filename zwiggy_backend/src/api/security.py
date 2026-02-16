import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _get_env(name: str, default: Optional[str] = None) -> str:
    val = os.getenv(name, default)
    if not val:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return val


def hash_password(password: str) -> str:
    """Hash a plain text password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against an existing hash."""
    return pwd_context.verify(password, password_hash)


def create_access_token(subject: str, role: str, expires_minutes: int) -> str:
    """
    Create JWT access token.

    subject: user id as string
    role: user role
    """
    secret = _get_env("JWT_SECRET", "dev-secret-change-me")  # orchestrator should set in .env for production
    algorithm = _get_env("JWT_ALGORITHM", "HS256")
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=expires_minutes)
    to_encode: Dict[str, Any] = {"sub": subject, "role": role, "iat": int(now.timestamp()), "exp": exp}
    return jwt.encode(to_encode, secret, algorithm=algorithm)


def decode_token(token: str) -> Dict[str, Any]:
    """Decode and validate JWT token, raising JWTError on failure."""
    secret = _get_env("JWT_SECRET", "dev-secret-change-me")
    algorithm = _get_env("JWT_ALGORITHM", "HS256")
    return jwt.decode(token, secret, algorithms=[algorithm])
