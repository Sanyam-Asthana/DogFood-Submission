"""Projects Router for DOGFOOD 2026 Hackathon Portal (T1 CORE subtask).

Handles:
- Public project gallery (no auth required)
- Project submission with deadline enforcement
- Project details and editing prior to submission deadline
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.user import User, EventMember, EventRole
from src.models.project import Project, Team
from src.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectListResponse,
)
from src.services.event_service import EventService
from src.services.auth_service import get_current_user

router = APIRouter(
    prefix="/projects",
    tags=["Projects & Gallery"],
)


@router.get(
    "",
    response_model=ProjectListResponse,
    summary="Public Project Gallery",
    description="""
    Publicly accessible gallery of hackathon projects.
    Returns project titles, summaries, and track associations without requiring authentication.
    """,
)
def list_projects(
    event_id: Optional[str] = Query(None, description="Filter projects by event ID"),
    track_id: Optional[str] = Query(None, description="Filter projects by competition track"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=200, description="Pagination limit"),
    db: Session = Depends(get_db),
) -> ProjectListResponse:
    query = db.query(Project)
    if event_id:
        query = query.filter(Project.event_id == event_id)
    if track_id:
        query = query.filter(Project.track_id == track_id)

    total = query.count()
    projects = query.order_by(Project.submitted_at.desc()).offset(skip).limit(limit).all()

    return ProjectListResponse(
        total_count=total,
        items=[ProjectResponse.model_validate(p) for p in projects],
    )


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a Hackathon Project",
    description="""
    Submit a project to a hackathon event.
    
    **Deadline Enforcement**:
    If the event submission deadline has passed, the submission is strictly rejected
    with HTTP 400 Bad Request.
    """,
)
def submit_project(
    project_in: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectResponse:
    # 1. Enforce submission deadline (raises 400 if closed)
    target_event_id = project_in.event_id or "evt_01"
    event = EventService.check_submission_allowed(db, target_event_id)

    # 2. Check if user is an event member (or auto-register as participant if event is open)
    membership = (
        db.query(EventMember)
        .filter(EventMember.event_id == target_event_id, EventMember.user_id == current_user.id)
        .first()
    )
    if not membership:
        # Auto-join open event as participant
        membership = EventMember(
            id=f"mem_{uuid.uuid4().hex[:12]}",
            event_id=target_event_id,
            user_id=current_user.id,
            role=EventRole.PARTICIPANT.value,
        )
        db.add(membership)
        db.commit()

    # 3. Create project
    proj_id = f"prj_{uuid.uuid4().hex[:8]}"
    project = Project(
        id=proj_id,
        event_id=target_event_id,
        track_id=project_in.track_id,
        title=project_in.title,
        summary=project_in.summary or "",
        repo_url=project_in.repo_url,
        submitted_at=datetime.now(timezone.utc),
        created_by=current_user.id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    return ProjectResponse.model_validate(project)


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Get Project Details",
    description="Retrieve full details for a single project submission.",
)
def get_project(
    project_id: str,
    db: Session = Depends(get_db),
) -> ProjectResponse:
    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found.",
        )
    return ProjectResponse.model_validate(proj)
