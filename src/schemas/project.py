from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    event_id: Optional[str] = Field("evt_01", description="Event ID to submit project for")
    track_id: Optional[str] = Field(None, description="Optional competition track ID")
    team_name: Optional[str] = Field(None, description="Optional team name")
    title: str = Field(..., min_length=1, max_length=255, description="Project title")
    summary: Optional[str] = Field("", max_length=5000, description="Short summary of what it does")
    repo_url: Optional[str] = Field(None, max_length=512, description="Source code repository URL")


class ProjectUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    summary: Optional[str] = Field(None, max_length=5000)
    repo_url: Optional[str] = Field(None, max_length=512)
    track_id: Optional[str] = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_id: str
    team_id: Optional[str] = None
    track_id: Optional[str] = None
    title: str
    summary: Optional[str] = ""
    repo_url: Optional[str] = None
    submitted_at: datetime
    created_by: Optional[str] = None


class ProjectListResponse(BaseModel):
    total_count: int
    items: List[ProjectResponse]
