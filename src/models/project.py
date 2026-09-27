from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from src.database import Base


class Team(Base):
    """Team model representing a group of participants competing in an event."""

    __tablename__ = "teams"

    id = Column(String(64), primary_key=True, index=True)
    event_id = Column(String(64), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    projects = relationship("Project", back_populates="team", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Team(id={self.id!r}, name={self.name!r})>"


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
