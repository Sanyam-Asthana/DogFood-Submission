from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class TeamMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    team_id: str
    user_id: str
    role: str
    joined_at: datetime
    user_name: Optional[str] = None
    user_email: Optional[str] = None


class TeamCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255, description="Team name")


class TeamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_id: str
    name: str
    created_at: datetime
    member_count: int = 0
    members: List[TeamMemberResponse] = []
    project_id: Optional[str] = None


class TeamListResponse(BaseModel):
    total_count: int
    items: List[TeamResponse]


class TeamInviteRequest(BaseModel):
    user_id: Optional[str] = Field(default=None, description="Platform user ID of the invitee")
    email: Optional[str] = Field(default=None, description="Email address of the invitee")


class TeamInvitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    team_id: str
    team_name: Optional[str] = None
    event_id: str
    event_name: Optional[str] = None
    inviter_id: str
    inviter_name: Optional[str] = None
    invitee_id: str
    invitee_email: Optional[str] = None
    status: str
    created_at: datetime
    responded_at: Optional[datetime] = None
