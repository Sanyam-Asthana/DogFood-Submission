"""Events Router for DOGFOOD 2026 Hackathon Portal (T1 EVENTS subtask).

Provides robust, versatile, and well-documented endpoints for:
- Event creation with submission deadlines and competition tracks (Organizer role)
- Public event discovery, details, and real-time deadline monitoring
- Event modification, deadline adjustment, and archiving (Organizer role)
- Competition track management per event
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.user import User
from src.schemas.event import (
    EventCreate,
    EventUpdate,
    EventDeadlineUpdate,
    EventResponse,
    EventListResponse,
    EventStatusResponse,
    TrackCreate,
    TrackResponse,
)
from src.services.event_service import EventService
from src.services.auth_service import require_organizer

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/events",
    tags=["Events"],
    responses={
        401: {"description": "Unauthorized - Missing or invalid credentials"},
        403: {"description": "Forbidden - Insufficient permissions (Organizer role required)"},
        404: {"description": "Not Found - Event or track does not exist"},
    },
)


def _to_event_response(event) -> EventResponse:
    """Helper to convert Event ORM model to EventResponse schema with computed properties."""
    from src.models.event import _ensure_utc
    return EventResponse(
        id=event.id,
        name=event.name,
        description=event.description,
        submissions_open=_ensure_utc(event.submissions_open),
        submissions_close=_ensure_utc(event.submissions_close),
        max_team_size=getattr(event, "max_team_size", 4) or 4,
        is_active=event.is_active,
        status=event.status,
        is_submission_open=event.is_submission_open(),
        time_remaining_seconds=event.time_remaining_seconds(),
        track_count=len(event.tracks) if event.tracks else 0,
        tracks=[TrackResponse.model_validate(t) for t in (event.tracks or [])],
        created_by=event.created_by,
        created_at=_ensure_utc(event.created_at),
        updated_at=_ensure_utc(event.updated_at),
    )



@router.post(
    "",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new hackathon event",
    description="""
    Create a new hackathon event with submission deadlines and optional competition tracks.

    **Authorization**: Requires **Organizer** role.

    - **name**: Name of the hackathon (e.g. 'Sample Hack 2026').
    - **submissions_close**: ISO 8601 UTC timestamp when submissions close. This deadline is strictly enforced.
    - **submissions_open**: (Optional) ISO 8601 UTC timestamp when submissions open. Defaults to current time.
    - **tracks**: (Optional) List of initial tracks to create with the event.
    """,
)
def create_event(
    event_in: EventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_organizer),
) -> EventResponse:
    logger.info(f"Organizer '{current_user.id}' is creating event '{event_in.name}'")
    event = EventService.create_event(db, event_in, created_by=current_user.id)
    return _to_event_response(event)


@router.get(
    "",
    response_model=EventListResponse,
    summary="List all hackathon events",
    description="""
    Publicly list hackathon events with optional status filtering, search by name, and pagination.

    **Status options**:
    - `open`: Currently accepting project submissions.
    - `closed`: Submission deadline has passed.
    - `upcoming`: Submissions open in the future.
    - `archived`: Event is inactive.
    """,
)
def list_events(
    status: Optional[str] = Query(
        None,
        description="Filter events by status: 'open', 'closed', 'upcoming', 'archived'",
        pattern="^(open|closed|upcoming|archived)$",
    ),
    search: Optional[str] = Query(None, description="Search event name"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=100, description="Pagination limit"),
    db: Session = Depends(get_db),
) -> EventListResponse:
    events, total = EventService.get_events(db, status_filter=status, search=search, skip=skip, limit=limit)
    return EventListResponse(
        total_count=total,
        items=[_to_event_response(e) for e in events],
    )


@router.get(
    "/current",
    response_model=EventResponse,
    summary="Get current active hackathon event",
    description="Retrieve the primary active event (e.g. `evt_01` loaded from fixtures).",
)
def get_current_event(db: Session = Depends(get_db)) -> EventResponse:
    event = EventService.get_active_event(db)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active hackathon event found.",
        )
    return _to_event_response(event)


@router.get(
    "/{event_id}",
    response_model=EventResponse,
    summary="Get event details by ID",
    description="Publicly retrieve detailed information for a specific hackathon event, including tracks and deadline status.",
)
def get_event(
    event_id: str,
    db: Session = Depends(get_db),
) -> EventResponse:
    event = EventService.get_event_by_id(db, event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with ID '{event_id}' was not found.",
        )
    return _to_event_response(event)


@router.put(
    "/{event_id}",
    response_model=EventResponse,
    summary="Update event details",
    description="""
    Update event information such as name, description, deadlines, or active status.

    **Authorization**: Requires **Organizer** role.
    """,
)
def update_event(
    event_id: str,
    event_in: EventUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_organizer),
) -> EventResponse:
    logger.info(f"Organizer '{current_user.id}' updating event '{event_id}'")
    updated = EventService.update_event(db, event_id, event_in)
    return _to_event_response(updated)


@router.patch(
    "/{event_id}/deadline",
    response_model=EventResponse,
    summary="Update event submission deadline",
    description="""
    Extend or advance the submission closing deadline for a hackathon event.

    **Authorization**: Requires **Organizer** role.
    """,
)
def update_event_deadline(
    event_id: str,
    deadline_in: EventDeadlineUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_organizer),
) -> EventResponse:
    logger.info(f"Organizer '{current_user.id}' adjusting deadline for '{event_id}' to {deadline_in.submissions_close}")
    updated = EventService.update_deadline(db, event_id, deadline_in.submissions_close)
    return _to_event_response(updated)


@router.delete(
    "/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an event",
    description="""
    Delete an event and its associated tracks.

    **Authorization**: Requires **Organizer** role.
    """,
)
def delete_event(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_organizer),
) -> None:
    logger.info(f"Organizer '{current_user.id}' deleting event '{event_id}'")
    EventService.delete_event(db, event_id)


@router.get(
    "/{event_id}/status",
    response_model=EventStatusResponse,
    summary="Check real-time event submission status and deadline",
    description="""
    Public endpoint providing real-time evaluation of whether an event is accepting submissions,
    the exact closing deadline, and the seconds remaining.
    """,
)
def check_event_status(
    event_id: str,
    db: Session = Depends(get_db),
) -> EventStatusResponse:
    return EventService.get_event_status(db, event_id)


# ---------------------------------------------------------------------------
# Track Sub-resources
# ---------------------------------------------------------------------------

@router.post(
    "/{event_id}/tracks",
    response_model=TrackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a competition track to an event",
    description="""
    Add a new competition track (category) to an existing hackathon event.

    **Authorization**: Requires **Organizer** role.
    """,
)
def add_track_to_event(
    event_id: str,
    track_in: TrackCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_organizer),
) -> TrackResponse:
    logger.info(f"Organizer '{current_user.id}' adding track '{track_in.name}' to event '{event_id}'")
    track = EventService.add_track(db, event_id, track_in)
    return TrackResponse.model_validate(track)


@router.get(
    "/{event_id}/tracks",
    response_model=List[TrackResponse],
    summary="List all tracks for an event",
    description="Publicly list all competition tracks available in a specific hackathon event.",
)
def list_event_tracks(
    event_id: str,
    db: Session = Depends(get_db),
) -> List[TrackResponse]:
    tracks = EventService.get_tracks_for_event(db, event_id)
    return [TrackResponse.model_validate(t) for t in tracks]
