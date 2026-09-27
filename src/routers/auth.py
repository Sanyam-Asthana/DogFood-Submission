"""Authentication Router for DOGFOOD 2026 Hackathon Portal.

Supports standard session management and pre-configured test logins matching .dogfood.toml.
"""

from typing import Dict
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.user import User
from src.schemas.user import LoginRequest, LoginResponse, UserResponse
from src.services.auth_service import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="User Login",
    description="Authenticate with email and receive a session token and session cookie.",
)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> LoginResponse:
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or user does not exist.",
        )

    # Set cookie on response for standard browser session
    token = user.session_token or f"session_{user.id}"
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        samesite="lax",
    )

    return LoginResponse(
        user=UserResponse.model_validate(user),
        session_token=token,
        token_type="Bearer",
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
    description="Retrieve the authenticated user's information and role.",
)
def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.get(
    "/test-logins",
    summary="Get test logins for verification",
    description="Returns pre-seeded test logins and cookies for automated testing and .dogfood.toml.",
)
def get_test_logins(db: Session = Depends(get_db)) -> Dict[str, str]:
    users = db.query(User).all()
    result = {}
    for u in users:
        result[u.role] = f"Cookie: session={u.session_token}"
    return result
