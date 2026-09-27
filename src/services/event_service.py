import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from src.models.event import Event, Track, _ensure_utc
from src.schemas.event import EventCreate, EventUpdate, TrackCreate, EventStatusResponse


class EventService:
    """Business logic service for managing Events and Tracks in T1."""

    @staticmethod
    def create_event(
        db: Session,
        event_in: EventCreate,
        created_by: Optional[str] = None,
    ) -> Event:
        """Create a new hackathon event, optionally with initial tracks."""
        event_id = event_in.id or f"evt_{uuid.uuid4().hex[:8]}"

        # Check for ID clash
        existing = db.query(Event).filter(Event.id == event_id).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An event with ID '{event_id}' already exists.",
            )

        open_time = _ensure_utc(event_in.submissions_open or datetime.now(timezone.utc))
        close_time = _ensure_utc(event_in.submissions_close)

        event = Event(
            id=event_id,
            name=event_in.name,
            description=event_in.description or "",
            submissions_open=open_time,
            submissions_close=close_time,
            is_active=event_in.is_active,
            created_by=created_by,
        )
        db.add(event)
        db.flush()

        # Add initial tracks if provided
        if event_in.tracks:
            for idx, track_data in enumerate(event_in.tracks):
                track_id = track_data.id or f"trk_{event_id}_{idx+1:02d}"
                track = Track(
                    id=track_id,
                    event_id=event.id,
                    name=track_data.name,
                    description=track_data.description or "",
                )
                db.add(track)

        db.commit()
        db.refresh(event)
        return event

    @staticmethod
    def get_event_by_id(db: Session, event_id: str) -> Optional[Event]:
        """Retrieve an event by ID."""
        return db.query(Event).filter(Event.id == event_id).first()

    @staticmethod
    def get_events(
        db: Session,
        status_filter: Optional[str] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Event], int]:
        """List events with optional status filtering and pagination."""
        query = db.query(Event)

        if search:
            query = query.filter(Event.name.ilike(f"%{search}%"))

        all_events = query.order_by(Event.created_at.desc()).all()

        # Filter by status if requested
        if status_filter:
            status_filter = status_filter.lower()
            filtered = [e for e in all_events if e.status == status_filter]
        else:
            filtered = all_events

        total_count = len(filtered)
        paginated = filtered[skip : skip + limit]
        return paginated, total_count

    @staticmethod
    def get_active_event(db: Session) -> Optional[Event]:
        """Get the primary active event (e.g. evt_01 or first active event)."""
        # First check for fixture default evt_01
        fixture_event = db.query(Event).filter(Event.id == "evt_01").first()
        if fixture_event and fixture_event.is_active:
            return fixture_event

        # Otherwise pick the most recent active event
        return db.query(Event).filter(Event.is_active == True).order_by(Event.created_at.desc()).first()

    @staticmethod
    def update_event(
        db: Session,
        event_id: str,
        event_in: EventUpdate,
    ) -> Event:
        """Update event details and/or deadline."""
        event = EventService.get_event_by_id(db, event_id)
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Event with ID '{event_id}' not found.",
            )

        update_data = event_in.model_dump(exclude_unset=True)

        if "submissions_open" in update_data and update_data["submissions_open"] is not None:
            update_data["submissions_open"] = _ensure_utc(update_data["submissions_open"])

        if "submissions_close" in update_data and update_data["submissions_close"] is not None:
            update_data["submissions_close"] = _ensure_utc(update_data["submissions_close"])

        for field, value in update_data.items():
            setattr(event, field, value)

        db.commit()
        db.refresh(event)
        return event

    @staticmethod
    def update_deadline(
        db: Session,
        event_id: str,
        new_deadline: datetime,
    ) -> Event:
        """Update an event's submission deadline."""
        event = EventService.get_event_by_id(db, event_id)
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Event with ID '{event_id}' not found.",
            )

        event.submissions_close = _ensure_utc(new_deadline)
        db.commit()
        db.refresh(event)
        return event

    @staticmethod
    def delete_event(db: Session, event_id: str) -> None:
        """Delete an event and its cascading tracks."""
        event = EventService.get_event_by_id(db, event_id)
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Event with ID '{event_id}' not found.",
            )
        db.delete(event)
        db.commit()

    @staticmethod
    def add_track(
        db: Session,
        event_id: str,
        track_in: TrackCreate,
    ) -> Track:
        """Add a competition track to an existing event."""
        event = EventService.get_event_by_id(db, event_id)
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Event with ID '{event_id}' not found.",
            )

        track_id = track_in.id or f"trk_{event_id}_{uuid.uuid4().hex[:6]}"
        existing = db.query(Track).filter(Track.id == track_id).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A track with ID '{track_id}' already exists.",
            )

        track = Track(
            id=track_id,
            event_id=event.id,
            name=track_in.name,
            description=track_in.description or "",
        )
        db.add(track)
        db.commit()
        db.refresh(track)
        return track

    @staticmethod
    def get_tracks_for_event(db: Session, event_id: str) -> List[Track]:
        """List all tracks for a given event."""
        event = EventService.get_event_by_id(db, event_id)
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Event with ID '{event_id}' not found.",
            )
        return db.query(Track).filter(Track.event_id == event_id).all()

    @staticmethod
    def get_event_status(db: Session, event_id: str) -> EventStatusResponse:
        """Get the real-time status and deadline details for an event."""
        event = EventService.get_event_by_id(db, event_id)
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Event with ID '{event_id}' not found.",
            )

        now = datetime.now(timezone.utc)
        return EventStatusResponse(
            event_id=event.id,
            name=event.name,
            status=event.status,
            is_submission_open=event.is_submission_open(now),
            submissions_close=event.submissions_close,
            submissions_open=event.submissions_open,
            time_remaining_seconds=event.time_remaining_seconds(now),
            server_time_utc=now,
        )

    @staticmethod
    def check_submission_allowed(db: Session, event_id: str) -> Event:
        """Enforces T1 deadline check: raises HTTP 400 if submissions are closed.

        This is the critical assertion for DOGFOOD 2026:
        'deadline actually stops submissions', 'closed event refuses submissions'.
        """
        event = EventService.get_event_by_id(db, event_id)
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cannot submit: Event '{event_id}' does not exist.",
            )

        if not event.is_submission_open():
            close_iso = event.submissions_close.isoformat() if event.submissions_close else "the past"
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Submissions for event '{event.name}' are closed. "
                    f"The deadline passed at {close_iso} UTC."
                ),
            )

        return event
