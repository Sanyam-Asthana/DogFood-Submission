"""Judging Models for DOGFOOD 2026 Hackathon Platform (Tier 2).

Includes Score, RubricCriterion, and JudgeTrackAssignment tables.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Float,
    DateTime,
    ForeignKey,
    Text,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from src.database import Base


class Score(Base):
    """Evaluation score submitted by an event judge for a project."""

    __tablename__ = "scores"

    id = Column(String(64), primary_key=True)
    event_id = Column(
        String(64),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id = Column(
        String(64),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    judge_id = Column(
        String(64),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    criteria = Column(JSON, nullable=False, default=dict)
    comment = Column(Text, nullable=True)
    submitted_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("project_id", "judge_id", name="uq_project_judge_score"),
    )

    # Relationships
    project = relationship("Project", backref="scores")
    judge = relationship("User", backref="submitted_scores")
    event = relationship("Event", backref="scores")


class RubricCriterion(Base):
    """Scoring rubric criterion configured by event organizers."""

    __tablename__ = "rubric_criteria"

    id = Column(String(64), primary_key=True)
    event_id = Column(
        String(64),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(64), nullable=False)
    weight = Column(Float, nullable=False, default=1.0)
    description = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("event_id", "name", name="uq_event_criterion_name"),
    )

    event = relationship("Event", backref="rubric_criteria")


class JudgeTrackAssignment(Base):
    """Mapping of a judge to the competition tracks they are assigned to evaluate."""

    __tablename__ = "judge_track_assignments"

    id = Column(String(64), primary_key=True)
    event_id = Column(
        String(64),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    judge_id = Column(
        String(64),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    track_id = Column(
        String(64),
        ForeignKey("tracks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        UniqueConstraint("judge_id", "track_id", name="uq_judge_track_assignment"),
    )

    event = relationship("Event", backref="judge_assignments")
    judge = relationship("User", backref="track_assignments")
    track = relationship("Track", backref="assigned_judges")
