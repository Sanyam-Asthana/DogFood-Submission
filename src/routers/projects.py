"""Projects Router for DOGFOOD 2026 Hackathon Portal (T1 CORE subtask).

Handles:
- Public project gallery (no auth required)
- Project submission with deadline enforcement and team binding
- Project details and editing with deadline locking and author verification
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.user import User, EventMember, EventRole
from src.models.project import Project, Team, TeamMember
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
    tags=["Projects & Gallery (T1 Core)"],
)


def _to_project_response(p: Project) -> ProjectResponse:
    team_name = p.team.name if p.team else None
    return ProjectResponse(
        id=p.id,
        event_id=p.event_id,
        team_id=p.team_id,
        team_name=team_name,
        track_id=p.track_id,
        title=p.title,
        summary=p.summary or "",
        repo_url=p.repo_url,
        submitted_at=p.submitted_at,
        created_by=p.created_by,
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
        items=[_to_project_response(p) for p in projects],
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

    # 3. Resolve team association if provided
    team_id = project_in.team_id
    if not team_id and project_in.team_name:
        # Create team for user if not existing
        team_id = f"tm_{uuid.uuid4().hex[:8]}"
        new_team = Team(
            id=team_id,
            event_id=target_event_id,
            name=project_in.team_name,
            created_at=datetime.now(timezone.utc),
        )
        db.add(new_team)
        db.add(
            TeamMember(
                id=f"tmem_{uuid.uuid4().hex[:8]}",
                team_id=team_id,
                user_id=current_user.id,
                role="lead",
                joined_at=datetime.now(timezone.utc),
            )
        )
        db.commit()

    # 4. Create project
    proj_id = f"prj_{uuid.uuid4().hex[:8]}"
    project = Project(
        id=proj_id,
        event_id=target_event_id,
        team_id=team_id,
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

    return _to_project_response(project)


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
    return _to_project_response(proj)


@router.put(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Edit Project (Until Deadline)",
    description="""
    Edit a project submission until the event submission deadline closes (T1 CORE subtask).
    
    **Authorization**: User must be the author or a team member.
    **Deadline Enforcement**: If the event has closed, edits are strictly rejected with HTTP 400 Bad Request.
    """,
)
@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    include_in_schema=False,
)
def update_project(
    project_id: str,
    project_update: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectResponse:
    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found.",
        )

    # 1. Enforce deadline (T1 requirement: "edit it until the deadline")
    EventService.check_submission_allowed(db, proj.event_id)

    # 2. Enforce author or team membership authorization
    is_author = proj.created_by == current_user.id
    is_team_member = False
    if proj.team_id:
        team_membership = (
            db.query(TeamMember)
            .filter(TeamMember.team_id == proj.team_id, TeamMember.user_id == current_user.id)
            .first()
        )
        if team_membership:
            is_team_member = True

    if not is_author and not is_team_member and current_user.role not in ("owner", "organizer"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to edit this project.",
        )

    # 3. Apply updates
    if project_update.title is not None:
        proj.title = project_update.title
    if project_update.summary is not None:
        proj.summary = project_update.summary
    if project_update.repo_url is not None:
        proj.repo_url = project_update.repo_url
    if project_update.track_id is not None:
        proj.track_id = project_update.track_id
    if project_update.team_id is not None:
        proj.team_id = project_update.team_id

    db.commit()
    db.refresh(proj)

    return _to_project_response(proj)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Project (Until Deadline)",
    description="Delete a project submission before the deadline.",
)
def delete_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found.",
        )

    # 1. Enforce deadline
    EventService.check_submission_allowed(db, proj.event_id)

    # 2. Author check
    is_author = proj.created_by == current_user.id
    if not is_author and current_user.role not in ("owner", "organizer"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this project.",
        )

    db.delete(proj)
    db.commit()
    return {"message": f"Project '{project_id}' deleted successfully.", "project_id": project_id}
