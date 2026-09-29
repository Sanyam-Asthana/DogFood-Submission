"""Judging Router for DOGFOOD 2026 Hackathon Portal (Tier 2).

Provides endpoints for:
- Score submission and judge score retrieval (with strict peer isolation)
- Project assignments for judges
- Scoring rubric configuration and criteria weights
- Judging progress monitoring for organizers
- CSV export for organizers
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.user import User
from src.schemas.judging import (
    ScoreCreate,
    ScoreResponse,
    RubricCriterionSchema,
    RubricUpdateRequest,
    JudgingProgressResponse,
    JudgeAssignmentResponse,
)
from src.services.auth_service import get_current_user
from src.services.judging_service import JudgingService

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Judging & Scoring"],
)


@router.get(
    "/judge/scores",
    response_model=List[ScoreResponse],
    summary="Get Judge Scores (with Peer Isolation Defense)",
)
def get_scores(
    judge: Optional[str] = Query(None, description="Target judge ID or alias (e.g. judge_a)"),
    event_id: Optional[str] = Query(None, description="Filter by event ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve scores for a judge.

    Enforces strict confidentiality:
    - Judges can only access their own scores.
    - Querying another judge's scores returns HTTP 403 Forbidden.
    - Participants attempting to access scores return HTTP 403 Forbidden.
    - Organizers can view scores for any judge.
    """
    return JudgingService.get_judge_scores(
        db=db,
        current_user=current_user,
        judge_param=judge,
        event_id=event_id,
    )


@router.post(
    "/judge/scores",
    response_model=ScoreResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit or Update Project Evaluation",
)
def submit_score(
    payload: ScoreCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit or update ratings and comments for an assigned project."""
    return JudgingService.submit_score(
        db=db,
        current_user=current_user,
        payload=payload,
    )


@router.get(
    "/judge/assignments",
    response_model=List[JudgeAssignmentResponse],
    summary="List Projects Assigned to Current Judge",
)
def get_assignments(
    event_id: Optional[str] = Query(None, description="Event ID filter"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all projects assigned to the calling judge with evaluation status."""
    return JudgingService.get_judge_assignments(
        db=db,
        current_user=current_user,
        event_id=event_id,
    )


@router.get(
    "/events/{event_id}/rubric",
    response_model=List[RubricCriterionSchema],
    summary="Get Event Scoring Rubric Criteria",
)
def get_rubric(
    event_id: str,
    db: Session = Depends(get_db),
):
    """Get rubric criteria names, weights, and descriptions for an event."""
    criteria = JudgingService.get_rubric(db=db, event_id=event_id)
    return [
        RubricCriterionSchema(
            name=c.name,
            weight=c.weight,
            description=c.description,
        )
        for c in criteria
    ]


@router.put(
    "/events/{event_id}/rubric",
    response_model=List[RubricCriterionSchema],
    summary="Update Event Scoring Rubric Weights",
)
def update_rubric(
    event_id: str,
    payload: RubricUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update criteria weights (Organizer / Owner only)."""
    updated = JudgingService.update_rubric(
        db=db,
        event_id=event_id,
        criteria_payload=payload.criteria,
        current_user=current_user,
    )
    return [
        RubricCriterionSchema(
            name=c.name,
            weight=c.weight,
            description=c.description,
        )
        for c in updated
    ]


@router.get(
    "/events/{event_id}/judging/progress",
    response_model=JudgingProgressResponse,
    summary="Event Judging Progress & Normalized Metrics",
)
def get_judging_progress(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Review progress matrix and Z-score normalized metrics (Organizer / Owner only)."""
    return JudgingService.get_judging_progress(
        db=db,
        event_id=event_id,
        current_user=current_user,
    )


@router.get(
    "/export.csv",
    summary="Export Judging Results as CSV (Organizer Only)",
)
@router.get(
    "/events/{event_id}/export.csv",
    summary="Export Event Judging Results as CSV (Organizer Only)",
)
def export_csv(
    event_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export hackathon judging results as a downloadable CSV.

    Strictly restricted to Organizers and Owners. Non-organizers receive HTTP 403 Forbidden.
    """
    csv_content = JudgingService.export_csv(
        db=db,
        event_id=event_id,
        current_user=current_user,
    )
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=judging_results.csv",
        },
    )
