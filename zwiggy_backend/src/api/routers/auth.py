from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.db import get_db
from src.api.deps import get_current_user
from src.api.models import User
from src.api.schemas import APIMessage, LoginRequest, SignUpRequest, TokenResponse, UserResponse
from src.api.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user account",
    description="Registers a new user as either a customer or restaurant owner.",
)
def signup(payload: SignUpRequest, db: Session = Depends(get_db)) -> UserResponse:
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=str(payload.email).lower(),
        password_hash=hash_password(payload.password),
        role=payload.role,
        full_name=payload.full_name,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and obtain an access token",
    description="Validates credentials and returns a Bearer JWT access token.",
)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == str(payload.email).lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is inactive")

    token = create_access_token(subject=str(user.id), role=user.role.value, expires_minutes=60 * 24)
    return TokenResponse(access_token=token)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
    description="Returns the authenticated user's profile.",
)
def me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(user)


@router.post(
    "/logout",
    response_model=APIMessage,
    summary="Logout (stateless)",
    description="Stateless logout endpoint (client should discard JWT).",
)
def logout() -> APIMessage:
    return APIMessage(message="Logged out (client must discard token).")
