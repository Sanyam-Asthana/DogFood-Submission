from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr, ConfigDict


class ClaimOwnerRequest(BaseModel):
    setup_key: str = Field(..., min_length=8, description="Secret platform owner setup key generated at startup")


class RoleChangeRequest(BaseModel):
    user_id: Optional[str] = Field(default=None, description="User ID to update")
    email: Optional[EmailStr] = Field(default=None, description="User email to update (if ID not provided)")


class UserAdminResponse(BaseModel):
    id: str
    email: EmailStr
    name: str
    role: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class JudgeInviteRequest(BaseModel):
    user_id: Optional[str] = Field(default=None, description="User ID of participant to invite as judge")
    email: Optional[EmailStr] = Field(default=None, description="Email of participant to invite as judge")


class JudgeInvitationResponse(BaseModel):
    id: str
    event_id: str
    event_name: Optional[str] = None
    inviter_id: str
    inviter_name: Optional[str] = None
    invitee_id: str
    invitee_email: Optional[str] = None
    status: str
    created_at: datetime
    responded_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class EventMemberResponse(BaseModel):
    id: str
    event_id: str
    user_id: str
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    role: str
    joined_at: datetime
    model_config = ConfigDict(from_attributes=True)
