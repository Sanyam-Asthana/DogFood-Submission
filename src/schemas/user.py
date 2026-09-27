from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict


class UserBase(BaseModel):
    email: EmailStr
    name: str
    role: str = "user"


class UserCreate(UserBase):
    id: Optional[str] = None
    session_token: Optional[str] = None


class UserResponse(UserBase):
    id: str
    session_token: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    email: EmailStr


class LoginResponse(BaseModel):
    user: UserResponse
    session_token: str
    token_type: str = "Bearer"
