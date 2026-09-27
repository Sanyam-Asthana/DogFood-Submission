import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from src.database import Base


class UserRole(str, enum.Enum):
    """Platform-level roles."""
    OWNER = "owner"
    ORGANIZER = "organizer"
    USER = "user"
    PARTICIPANT = "participant"
    JUDGE = "judge"


class EventRole(str, enum.Enum):
    """Event-specific roles."""
    PARTICIPANT = "participant"
    JUDGE = "judge"


class InvitationStatus(str, enum.Enum):
    """Judge invitation statuses."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"


class User(Base):
    """User account model supporting platform roles."""

    __tablename__ = "users"

    id = Column(String(64), primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    role = Column(String(32), default=UserRole.USER.value, nullable=False)
    session_token = Column(String(128), unique=True, index=True, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    event_memberships = relationship("EventMember", back_populates="user", cascade="all, delete-orphan")
    sent_invitations = relationship("JudgeInvitation", foreign_keys="JudgeInvitation.inviter_id", back_populates="inviter")
    received_invitations = relationship("JudgeInvitation", foreign_keys="JudgeInvitation.invitee_id", back_populates="invitee")

    def __repr__(self) -> str:
        return f"<User(id={self.id!r}, email={self.email!r}, role={self.role!r})>"


class EventMember(Base):
    """Associates a user with an event under an event-specific role (participant or judge)."""

    __tablename__ = "event_members"

    id = Column(String(64), primary_key=True, index=True)
    event_id = Column(String(64), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(32), default=EventRole.PARTICIPANT.value, nullable=False)
    joined_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_event_user_membership"),
    )

    # Relationships
    user = relationship("User", back_populates="event_memberships")
    event = relationship("Event", back_populates="members")

    def __repr__(self) -> str:
        return f"<EventMember(event={self.event_id!r}, user={self.user_id!r}, role={self.role!r})>"


class JudgeInvitation(Base):
    """Event judge invitation sent by an organizer to a participant."""

    __tablename__ = "judge_invitations"

    id = Column(String(64), primary_key=True, index=True)
    event_id = Column(String(64), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    inviter_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    invitee_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(32), default=InvitationStatus.PENDING.value, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    responded_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    inviter = relationship("User", foreign_keys=[inviter_id], back_populates="sent_invitations")
    invitee = relationship("User", foreign_keys=[invitee_id], back_populates="received_invitations")
    event = relationship("Event", back_populates="invitations")

    def __repr__(self) -> str:
        return f"<JudgeInvitation(id={self.id!r}, event={self.event_id!r}, invitee={self.invitee_id!r}, status={self.status!r})>"
