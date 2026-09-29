"""Teams Router for DOGFOOD 2026 Hackathon Portal (T1 CORE subtask).

Endpoints for:
- Creating competition teams (registered participants only)
- Listing teams in an event
- Joining and leaving teams
- Inviting teammates, viewing team invitations, and accepting/declining invites
"""

from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.user import User
from src.schemas.team import (
    TeamCreate,
    TeamResponse,
    TeamListResponse,
    TeamInviteRequest,
    TeamInvitationResponse,
)
from src.services.team_service import TeamService
from src.services.auth_service import get_current_user

router = APIRouter(
    tags=["Teams & Team Invitations (T1 Core)"],
)


@router.post(
    "/events/{event_id}/teams",
    response_model=TeamResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Form a Team",
    description="""
    Form a new team for a hackathon event.
    
    **Requirements**:
    - User must be authenticated and registered as a participant of the event.
    - User cannot already be a member of another team in this event.
    - Event submissions must still be open.
    - Event must allow teams (cannot create team if max_team_size is 1).
    """,
)
def create_team(
    event_id: str,
    team_in: TeamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TeamResponse:
    return TeamService.create_team(db, event_id, current_user, team_in)


@router.get(
    "/events/{event_id}/teams",
    response_model=List[TeamResponse],
    summary="List Teams in Event",
    description="Publicly list all competition teams registered for an event.",
)
def list_teams(
    event_id: str,
    db: Session = Depends(get_db),
) -> List[TeamResponse]:
    return TeamService.list_teams(db, event_id)


@router.get(
    "/teams/{team_id}",
    response_model=TeamResponse,
    summary="Get Team Details",
    description="Retrieve details for a specific team, including member roster and attached project.",
)
def get_team(
    team_id: str,
    db: Session = Depends(get_db),
) -> TeamResponse:
    return TeamService.get_team(db, team_id)


@router.post(
    "/teams/{team_id}/join",
    response_model=TeamResponse,
    summary="Join a Team",
    description="Join an existing team. User must be a registered participant in the team's event and team must not be full.",
)
def join_team(
    team_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TeamResponse:
    return TeamService.join_team(db, team_id, current_user)


@router.post(
    "/teams/{team_id}/leave",
    status_code=status.HTTP_200_OK,
    summary="Leave a Team",
    description="Leave a team. If only one member remains, the team is dissolved and they become a normal single participant again.",
)
def leave_team(
    team_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TeamService.leave_team(db, team_id, current_user)


@router.post(
    "/teams/{team_id}/dissolve",
    status_code=status.HTTP_200_OK,
    summary="Dissolve a Team",
    description="Dissolve a competition team (Team Leader or Platform Owner only). All members become single participants again.",
)
@router.delete(
    "/teams/{team_id}",
    status_code=status.HTTP_200_OK,
    summary="Dissolve a Team (DELETE)",
)
def dissolve_team(
    team_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TeamService.dissolve_team(db, team_id, current_user)


# ---------------------------------------------------------------------------
# Team Invitations
# ---------------------------------------------------------------------------

@router.post(
    "/teams/{team_id}/invite",
    response_model=TeamInvitationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Invite Teammate",
    description="""
    Invite another registered participant to join your team.
    
    **Requirements**:
    - Caller must be an existing member of the team.
    - Team must not exceed maximum team size.
    - Invitee must be a registered participant in the same event and not on another team.
    """,
)
@router.post(
    "/teams/{team_id}/invitations",
    response_model=TeamInvitationResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def invite_teammate(
    team_id: str,
    invite_in: TeamInviteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TeamInvitationResponse:
    return TeamService.invite_teammate(
        db, team_id, current_user, user_id=invite_in.user_id, email=invite_in.email
    )


@router.get(
    "/teams/{team_id}/invitations",
    response_model=List[TeamInvitationResponse],
    summary="List Sent Team Invitations",
    description="List all pending invitations sent by this team.",
)
def list_team_invitations(
    team_id: str,
    db: Session = Depends(get_db),
) -> List[TeamInvitationResponse]:
    return TeamService.list_team_invitations(db, team_id)


@router.get(
    "/invitations/teams/my",
    response_model=List[TeamInvitationResponse],
    summary="List My Team Invitations",
    description="Retrieve all team invitations addressed to the currently logged in user.",
)
def list_my_team_invitations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[TeamInvitationResponse]:
    return TeamService.get_user_team_invitations(db, current_user.id)


@router.post(
    "/invitations/teams/{invitation_id}/accept",
    response_model=TeamInvitationResponse,
    summary="Accept Team Invitation",
    description="Accept an invitation to join a team.",
)
def accept_team_invitation(
    invitation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TeamInvitationResponse:
    return TeamService.accept_team_invitation(db, invitation_id, current_user)


@router.post(
    "/invitations/teams/{invitation_id}/decline",
    response_model=TeamInvitationResponse,
    summary="Decline Team Invitation",
    description="Decline an invitation to join a team.",
)
def decline_team_invitation(
    invitation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TeamInvitationResponse:
    return TeamService.decline_team_invitation(db, invitation_id, current_user)


@router.post(
    "/invitations/teams/{invitation_id}/cancel",
    response_model=TeamInvitationResponse,
    summary="Cancel Sent Team Invitation",
    description="Cancel or revoke an invitation sent by a team member.",
)
@router.delete(
    "/invitations/teams/{invitation_id}",
    response_model=TeamInvitationResponse,
    summary="Cancel Sent Team Invitation (DELETE)",
)
@router.delete(
    "/teams/invitations/{invitation_id}",
    response_model=TeamInvitationResponse,
    include_in_schema=False,
)
def cancel_team_invitation(
    invitation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TeamInvitationResponse:
    return TeamService.cancel_team_invitation(db, invitation_id, current_user)

