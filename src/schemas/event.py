from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator, ConfigDict


# ---------------------------------------------------------------------------
# Track Schemas
# ---------------------------------------------------------------------------

class TrackBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Track name (e.g. Developer tools)")
    description: Optional[str] = Field(default="", description="Track description and criteria details")


class TrackCreate(TrackBase):
    id: Optional[str] = Field(default=None, description="Explicit track ID (e.g. trk_01) or auto-generated")


class TrackUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None)


class TrackResponse(TrackBase):
    id: str
    event_id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Event Schemas
# ---------------------------------------------------------------------------

class EventBase(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Event name (e.g. Sample Hack 2026)",
        json_schema_extra={"example": "Sample Hack 2026"},
    )
    description: Optional[str] = Field(
        default="",
        description="Detailed description or markdown about the hackathon",
        json_schema_extra={"example": "A 72-hour engineering hackathon focused on tools and data."},
    )
    submissions_open: Optional[datetime] = Field(
        default=None,
        description="ISO 8601 UTC timestamp when submissions open. Defaults to event creation if omitted.",
        json_schema_extra={"example": "2026-02-27T18:00:00Z"},
    )
    submissions_close: datetime = Field(
        ...,
        description="ISO 8601 UTC timestamp when submissions close (hard deadline enforced by T1).",
        json_schema_extra={"example": "2026-03-01T18:00:00Z"},
    )
    max_team_size: int = Field(
        default=4,
        ge=1,
        le=20,
        description="Maximum allowed team size (1 for solo/individual hackathons). Cannot be altered once created.",
        json_schema_extra={"example": 4},
    )
    is_active: bool = Field(
        default=True,
        description="Whether the event is active. Set false to archive.",
    )



class EventCreate(EventBase):
    id: Optional[str] = Field(
        default=None,
        description="Explicit event ID (e.g. evt_01 for fixture compatibility) or auto-generated",
        json_schema_extra={"example": "evt_01"},
    )
    tracks: Optional[List[TrackCreate]] = Field(
        default=None,
        description="Initial tracks to create along with this event",
    )

    @model_validator(mode="after")
    def validate_dates(self) -> "EventCreate":
        if self.submissions_open and self.submissions_close:
            if self.submissions_close <= self.submissions_open:
                raise ValueError("submissions_close must be strictly after submissions_open")
        return self


class EventUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None)
    submissions_open: Optional[datetime] = Field(default=None)
    submissions_close: Optional[datetime] = Field(default=None)
    is_active: Optional[bool] = Field(default=None)

    @model_validator(mode="after")
    def validate_dates(self) -> "EventUpdate":
        if self.submissions_open and self.submissions_close:
            if self.submissions_close <= self.submissions_open:
                raise ValueError("submissions_close must be strictly after submissions_open")
        return self


class EventDeadlineUpdate(BaseModel):
    """Payload to extend or advance the event submission deadline."""
    submissions_close: datetime = Field(
        ...,
        description="New submission closing deadline in ISO 8601 UTC",
        json_schema_extra={"example": "2026-03-02T18:00:00Z"},
    )


class EventStatusResponse(BaseModel):
    """Real-time status check response for an event deadline."""
    event_id: str
    name: str
    status: str = Field(..., description="'open', 'closed', 'upcoming', or 'archived'")
    is_submission_open: bool = Field(..., description="True if submissions can currently be accepted")
    submissions_close: datetime
    submissions_open: Optional[datetime] = None
    time_remaining_seconds: float = Field(..., description="Seconds remaining until submissions close (0 if closed)")
    server_time_utc: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Current server time in UTC",
    )


class EventResponse(EventBase):
    id: str
    status: str = Field(..., description="'open', 'closed', 'upcoming', or 'archived'")
    is_submission_open: bool = Field(..., description="True if submissions are currently accepted")
    time_remaining_seconds: float = Field(..., description="Seconds remaining until submissions close")
    track_count: int = Field(default=0, description="Total number of tracks in this event")
    tracks: List[TrackResponse] = Field(default_factory=list, description="Associated tracks")
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class EventListResponse(BaseModel):
    total_count: int
    items: List[EventResponse]
