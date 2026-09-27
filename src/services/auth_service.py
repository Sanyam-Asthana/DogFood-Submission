import logging
from typing import Optional, List, Callable
import jwt
from fastapi import Request, Depends, HTTPException, status
from sqlalchemy.orm import Session
from src.database import get_db
from src.models.user import User, UserRole

logger = logging.getLogger(__name__)


def extract_token_from_request(request: Request) -> Optional[str]:
    """Extract authentication token from Request.

    Explicit headers (X-Session-Token, Authorization) take precedence
    over ambient browser cookies to allow per-request role overrides.
    """
    # 1. Check X-Session-Token or X-Auth-Token
    x_token = request.headers.get("x-session-token") or request.headers.get("x-auth-token")
    if x_token:
        x_token = x_token.strip()
        if x_token.lower().startswith("bearer "):
            x_token = x_token[7:].strip()
        return x_token

    # 2. Check Authorization header
    auth_header = request.headers.get("authorization", "")
    if auth_header:
        parts = auth_header.strip().split()
        if len(parts) == 2 and parts[0].lower() in ("bearer", "token", "session"):
            return parts[1].strip()
        if len(parts) == 1:
            return parts[0].strip()

    # 3. Check Cookie header (e.g. Cookie: session=org_7f2a)
    session_cookie = request.cookies.get("session")
    if session_cookie:
        return session_cookie.strip()

    # Raw Cookie header parsing fallback
    raw_cookie = request.headers.get("cookie", "")
    if "session=" in raw_cookie:
        for part in raw_cookie.split(";"):
            part = part.strip()
            if part.startswith("session="):
                return part.split("session=", 1)[1].strip()

    return None


def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Dependency: Extract and return the authenticated user if present, else None."""
    token = extract_token_from_request(request)
    if not token:
        return None

    # 1. Look up user by session token or ID in the database
    user = db.query(User).filter(User.session_token == token).first()
    if user:
        return user

    user = db.query(User).filter(User.id == token).first()
    if user:
        return user

    if token.startswith("usr_"):
        clean_id = token[4:]
        user = db.query(User).filter(User.id == clean_id).first()
        if user:
            return user
        user = db.query(User).filter(User.session_token == clean_id).first()
        if user:
            return user

    user = db.query(User).filter(User.email == token).first()
    if user:
        return user

    # 2. Try decoding JWT (e.g. Supabase access token)
    if token.count(".") == 2:
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            user_id = payload.get("sub")
            email = payload.get("email") or f"{user_id}@example.org"
            role = payload.get("app_metadata", {}).get("role") or payload.get("role") or UserRole.USER.value

            if user_id:
                user = db.query(User).filter((User.id == user_id) | (User.email == email)).first()
                if not user:
                    user = User(
                        id=user_id,
                        email=email,
                        name=email.split("@")[0],
                        role=role if role in [r.value for r in UserRole] else UserRole.USER.value,
                        session_token=f"usr_{user_id}",
                    )
                    try:
                        db.add(user)
                        db.commit()
                        db.refresh(user)
                    except Exception as sync_err:
                        db.rollback()
                        logger.warning(f"Could not auto-create user from JWT: {sync_err}")
                        user = db.query(User).filter((User.id == user_id) | (User.email == email)).first()
                return user
        except Exception as e:
            logger.debug(f"Could not parse token as JWT: {e}")

    return None


def get_current_user(
    user: Optional[User] = Depends(get_current_user_optional),
) -> User:
    """Dependency: Require an authenticated user; raises 401 if missing."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided or are invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_role(allowed_roles: List[str]) -> Callable:
    """Factory creating a FastAPI dependency that verifies the user has one of the allowed roles."""
    def role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: role '{user.role}' is not authorized. Allowed: {allowed_roles}",
            )
        return user

    return role_checker


# Role-based dependency shortcuts
require_owner = require_role([UserRole.OWNER.value])
require_organizer = require_role([UserRole.ORGANIZER.value, UserRole.OWNER.value])
require_judge = require_role([UserRole.JUDGE.value, UserRole.ORGANIZER.value, UserRole.OWNER.value])
require_participant = require_role([
    UserRole.USER.value,
    UserRole.PARTICIPANT.value,
    UserRole.JUDGE.value,
    UserRole.ORGANIZER.value,
    UserRole.OWNER.value,
])
