from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Column, String, Text, DateTime, Boolean, ForeignKey, Integer
from sqlalchemy.orm import relationship
from src.database import Base


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class Event(Base):
    """Event model representing a hackathon event (T1 EVENTS subtask).

    Enforces the submission deadline logic required by DOGFOOD 2026 T1:
    'deadline actually stops submissions', 'closed event refuses submissions'.
    """

    __tablename__ = "events"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True, default="")
    submissions_open = Column(DateTime(timezone=True), nullable=True)
    submissions_close = Column(DateTime(timezone=True), nullable=False)
    max_team_size = Column(Integer, default=4, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    created_by = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    tracks = relationship("Track", back_populates="event", cascade="all, delete-orphan", lazy="joined")
    members = relationship("EventMember", back_populates="event", cascade="all, delete-orphan")
    invitations = relationship("JudgeInvitation", back_populates="event", cascade="all, delete-orphan")

    def is_submission_open(self, now: Optional[datetime] = None) -> bool:
        """Check if submissions are currently allowed for this event."""
        if not self.is_active:
            return False

        current_time = _ensure_utc(now or datetime.now(timezone.utc))
        deadline = _ensure_utc(self.submissions_close)

        if deadline is not None and current_time >= deadline:
            return False

        start_time = _ensure_utc(self.submissions_open)
        if start_time is not None and current_time < start_time:
            return False

        return True

    @property
    def status(self) -> str:
        """Derive the human-readable status of the event."""
        if not self.is_active:
            return "archived"

        now = datetime.now(timezone.utc)
        deadline = _ensure_utc(self.submissions_close)
        start_time = _ensure_utc(self.submissions_open)

        if deadline is not None and now >= deadline:
            return "closed"
        if start_time is not None and now < start_time:
            return "upcoming"
        return "open"

    def time_remaining_seconds(self, now: Optional[datetime] = None) -> float:
        """Return the number of seconds remaining until the submissions close deadline."""
        current_time = _ensure_utc(now or datetime.now(timezone.utc))
        deadline = _ensure_utc(self.submissions_close)
        if deadline is None:
            return 0.0
        diff = (deadline - current_time).total_seconds()
        return max(0.0, diff)

    def __repr__(self) -> str:
        return f"<Event(id={self.id!r}, name={self.name!r}, status={self.status!r})>"


class Track(Base):
    """Track model representing competition categories within a hackathon event."""

    __tablename__ = "tracks"

    id = Column(String(64), primary_key=True, index=True)
    event_id = Column(String(64), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True, default="")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    event = relationship("Event", back_populates="tracks")

    def __repr__(self) -> str:
        return f"<Track(id={self.id!r}, name={self.name!r}, event_id={self.event_id!r})>"
