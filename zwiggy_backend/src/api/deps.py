from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.api.db import get_db
from src.api.models import User, UserRole
from src.api.security import decode_token

bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


# PUBLIC_INTERFACE
def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Return the authenticated user from the Bearer JWT token."""
    if creds is None or not creds.credentials:
        raise _unauthorized()

    try:
        payload = decode_token(creds.credentials)
        user_id = int(payload.get("sub"))
    except Exception:
        raise _unauthorized("Invalid token")

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise _unauthorized("User not found or inactive")
    return user


# PUBLIC_INTERFACE
def require_role(role: UserRole):
    """Factory dependency that ensures the current user has a specific role."""

    def _checker(user: User = Depends(get_current_user)) -> User:
        if user.role != role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return _checker
