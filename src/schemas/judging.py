"""Judging schemas for DOGFOOD 2026 Hackathon Platform (Tier 2)."""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class ScoreCreate(BaseModel):
    """Payload to submit or update a score for a project."""

    project_id: str
    criteria: Dict[str, float] = Field(
        ...,
        description="Rubric criteria mapped to ratings (e.g. {'functionality': 4, 'quality': 3, 'innovation': 5})",
    )
    comment: Optional[str] = Field(None, description="Optional judge comments / feedback")


class ScoreResponse(BaseModel):
    """Response model for a submitted score."""

    id: str
    event_id: str
    project_id: str
    project_title: Optional[str] = None
    judge_id: str
    judge_name: Optional[str] = None
    criteria: Dict[str, float]
    comment: Optional[str] = None
    submitted_at: datetime

    model_config = {"from_attributes": True}



class RubricCriterionSchema(BaseModel):
    """Schema for a single rubric criterion with weight."""

    name: str
    weight: float = Field(..., ge=0.0, le=1.0)
    description: Optional[str] = None


class RubricUpdateRequest(BaseModel):
    """Payload for updating an event's rubric criteria weights."""

    criteria: List[RubricCriterionSchema]


class JudgingProgressProject(BaseModel):
    """Review progress and metrics for a specific project."""

    project_id: str
    project_title: str
    track_id: Optional[str] = None
    track_name: Optional[str] = None
    team_name: Optional[str] = None
    reviews_count: int = 0
    raw_average: Optional[float] = None
    normalized_score: Optional[float] = None
    completed: bool = False


class JudgingProgressResponse(BaseModel):
    """Judging progress summary across the entire event."""

    event_id: str
    total_projects: int
    total_scores: int
    total_judges: int
    projects: List[JudgingProgressProject]


class JudgeAssignmentResponse(BaseModel):
    """Project assigned to a judge with submission details and existing review status."""

    project_id: str
    title: str
    summary: Optional[str] = None
    repo_url: Optional[str] = None
    track_id: Optional[str] = None
    track_name: Optional[str] = None
    team_name: Optional[str] = None
    evaluated: bool = False
    existing_score: Optional[ScoreResponse] = None
