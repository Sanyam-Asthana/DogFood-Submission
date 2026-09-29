import enum
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from src.database import Base


class TeamMemberRole(str, enum.Enum):
    LEAD = "lead"
    MEMBER = "member"


class TeamInvitationStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"


class Team(Base):
    """Team model representing a group of participants competing in an event (T1 CORE subtask)."""

    __tablename__ = "teams"

    id = Column(String(64), primary_key=True, index=True)
    event_id = Column(String(64), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan", lazy="joined")
    projects = relationship("Project", back_populates="team", cascade="all, delete-orphan")
    invitations = relationship("TeamInvitation", back_populates="team", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Team(id={self.id!r}, name={self.name!r}, event_id={self.event_id!r})>"


class TeamMember(Base):
    """Associates a participant User with a Team."""

    __tablename__ = "team_members"

    id = Column(String(64), primary_key=True, index=True)
    team_id = Column(String(64), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(32), default=TeamMemberRole.MEMBER.value, nullable=False)
    joined_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    team = relationship("Team", back_populates="members")
    user = relationship("User")

    __table_args__ = (
        UniqueConstraint("team_id", "user_id", name="uq_team_user"),
    )

    def __repr__(self) -> str:
        return f"<TeamMember(team_id={self.team_id!r}, user_id={self.user_id!r}, role={self.role!r})>"


class TeamInvitation(Base):
    """Represents an invitation sent to a participant to join a hackathon team."""

    __tablename__ = "team_invitations"

    id = Column(String(64), primary_key=True, index=True)
    team_id = Column(String(64), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    event_id = Column(String(64), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    inviter_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    invitee_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(32), default=TeamInvitationStatus.PENDING.value, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    responded_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    team = relationship("Team", back_populates="invitations")
    event = relationship("Event")
    inviter = relationship("User", foreign_keys=[inviter_id])
    invitee = relationship("User", foreign_keys=[invitee_id])

    def __repr__(self) -> str:
        return f"<TeamInvitation(id={self.id!r}, team_id={self.team_id!r}, invitee_id={self.invitee_id!r}, status={self.status!r})>"


class Project(Base):
    """Project model representing a hackathon submission (T1 CORE subtask)."""

    __tablename__ = "projects"

    id = Column(String(64), primary_key=True, index=True)
    event_id = Column(String(64), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    team_id = Column(String(64), ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True)
    track_id = Column(String(64), ForeignKey("tracks.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=True, default="")
    repo_url = Column(String(512), nullable=True)
    submitted_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    created_by = Column(String(64), nullable=True)

    team = relationship("Team", back_populates="projects")

    def __repr__(self) -> str:
        return f"<Project(id={self.id!r}, title={self.title!r}, event_id={self.event_id!r})>"
