"""Platform Administration and Event Roles Router.

Handles:
- Platform ownership claiming via setup key generated on boot
- Organizer promotion and demotion (Owner only)
- User directory listing for role management
- Event participant joining
- Judge invitation workflows (Invite -> Accept / Decline)
- Event judges and members discovery
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.user import User, UserRole
from src.schemas.platform import (
    ClaimOwnerRequest,
    RoleChangeRequest,
    UserAdminResponse,
    JudgeInviteRequest,
    JudgeInvitationResponse,
    EventMemberResponse,
)
from src.services.platform_service import PlatformService
from src.services.auth_service import (
    get_current_user,
    require_owner,
    require_organizer,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Platform & Roles"])


def _to_invitation_response(inv) -> JudgeInvitationResponse:
    return JudgeInvitationResponse(
        id=inv.id,
        event_id=inv.event_id,
        event_name=inv.event.name if inv.event else None,
        inviter_id=inv.inviter_id,
        inviter_name=inv.inviter.name if inv.inviter else None,
        invitee_id=inv.invitee_id,
        invitee_email=inv.invitee.email if inv.invitee else None,
        status=inv.status,
        created_at=inv.created_at,
        responded_at=inv.responded_at,
    )


def _to_member_response(m) -> EventMemberResponse:
    return EventMemberResponse(
        id=m.id,
        event_id=m.event_id,
        user_id=m.user_id,
        user_name=m.user.name if m.user else None,
        user_email=m.user.email if m.user else None,
        role=m.role,
        joined_at=m.joined_at,
        team_id=getattr(m, "team_id", None),
        team_name=getattr(m, "team_name", None),
        team_role=getattr(m, "team_role", None),
    )



# ---------------------------------------------------------------------------
# Platform Ownership & Role Management
# ---------------------------------------------------------------------------

@router.post(
    "/platform/claim-owner",
    response_model=UserAdminResponse,
    summary="Claim Platform Ownership",
    description="Promote the currently authenticated user to Platform Owner using the server's setup key.",
)
def claim_owner(
    req: ClaimOwnerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    updated_user = PlatformService.claim_owner_role(db, current_user, req.setup_key)
    return UserAdminResponse.model_validate(updated_user)


@router.get(
    "/platform/users",
    response_model=List[UserAdminResponse],
    summary="List Platform Users",
    description="Retrieve all registered users and their platform roles. Requires Organizer or Owner role.",
)
def list_users(
    _: User = Depends(require_organizer),
    db: Session = Depends(get_db),
):
    users = PlatformService.list_users(db)
    return [UserAdminResponse.model_validate(u) for u in users]


@router.post(
    "/platform/promote-organizer",
    response_model=UserAdminResponse,
    summary="Promote User to Organizer",
    description="Promote a platform user to Organizer. Only the platform Owner can perform this action.",
)
def promote_to_organizer(
    req: RoleChangeRequest,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    target = PlatformService.promote_to_organizer(db, current_user, req)
    return UserAdminResponse.model_validate(target)


@router.post(
    "/platform/demote-organizer",
    response_model=UserAdminResponse,
    summary="Demote Organizer to Participant",
    description="Demote an Organizer back to Participant/User role. Only the platform Owner can perform this action.",
)
def demote_to_user(
    req: RoleChangeRequest,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    target = PlatformService.demote_to_user(db, current_user, req)
    return UserAdminResponse.model_validate(target)


# ---------------------------------------------------------------------------
# Event Participation & Judge Assignment
# ---------------------------------------------------------------------------

@router.post(
    "/events/{event_id}/join",
    response_model=EventMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Join Event as Participant",
    description="Join a hackathon event as a participant. Requires authentication.",
)
def join_event(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    membership = PlatformService.join_event(db, event_id, current_user)
    return _to_member_response(membership)


@router.post(
    "/events/{event_id}/leave",
    summary="Leave / Unregister from Event",
    description="Unregister the currently authenticated user from being a participant or judge for an event.",
)
@router.post(
    "/events/{event_id}/unregister",
    summary="Unregister from Event (Alias)",
    description="Alias for /events/{event_id}/leave.",
)
def leave_event(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return PlatformService.leave_event(db, event_id, current_user)


@router.get(
    "/events/{event_id}/my-membership",
    response_model=Optional[EventMemberResponse],
    summary="Get My Event Membership",
    description="Check the current user's membership role for a specific event.",
)
def get_my_event_membership(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mem = PlatformService.get_my_event_membership(db, event_id, current_user)
    return _to_member_response(mem) if mem else None


@router.get(
    "/events/{event_id}/members",
    response_model=List[EventMemberResponse],
    summary="List Event Members",
    description="List all members (participants and judges) associated with an event. Only Organizers and Owners can access.",
)
def list_event_members(
    event_id: str,
    current_user: User = Depends(require_organizer),
    db: Session = Depends(get_db),
):
    members = PlatformService.get_event_members(db, event_id)
    return [_to_member_response(m) for m in members]


@router.get(
    "/events/{event_id}/participants",
    response_model=List[EventMemberResponse],
    summary="List Event Participants",
    description="List all confirmed participants for a specific event. Only Organizers and Owners can access.",
)
def list_event_participants(
    event_id: str,
    current_user: User = Depends(require_organizer),
    db: Session = Depends(get_db),
):
    participants = PlatformService.get_event_participants(db, event_id)
    return [_to_member_response(p) for p in participants]


@router.get(
    "/events/{event_id}/judges",
    response_model=List[EventMemberResponse],
    summary="List Confirmed Event Judges",
    description="List all confirmed judges for a specific event. Only Organizers and Owners can access (judges cannot view).",
)
def list_event_judges(
    event_id: str,
    current_user: User = Depends(require_organizer),
    db: Session = Depends(get_db),
):
    judges = PlatformService.get_event_judges(db, event_id)
    return [_to_member_response(j) for j in judges]


@router.get(
    "/events/{event_id}/judges/invitations",
    response_model=List[JudgeInvitationResponse],
    summary="List Event Judge Invitations",
    description="List all judge invitations sent for this event. Requires Organizer or Owner role.",
)
def list_event_judge_invitations(
    event_id: str,
    status: Optional[str] = None,
    current_user: User = Depends(require_organizer),
    db: Session = Depends(get_db),
):
    invitations = PlatformService.get_event_judge_invitations(db, event_id, status)
    return [_to_invitation_response(i) for i in invitations]


@router.post(
    "/events/{event_id}/judges/invite",
    response_model=JudgeInvitationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Invite User to Judge Event",
    description="Invite any platform user to become a Judge for this event. Requires Organizer or Owner role.",
)
def invite_judge(
    event_id: str,
    req: JudgeInviteRequest,
    current_user: User = Depends(require_organizer),
    db: Session = Depends(get_db),
):
    invitation = PlatformService.invite_judge(db, event_id, current_user, req)
    return _to_invitation_response(invitation)


# ---------------------------------------------------------------------------
# Judge Invitations Management
# ---------------------------------------------------------------------------

@router.get(
    "/invitations/my",
    response_model=List[JudgeInvitationResponse],
    summary="List My Judge Invitations",
    description="Retrieve all judge invitations sent to the currently authenticated user.",
)
def get_my_invitations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    invitations = PlatformService.get_my_invitations(db, current_user)
    return [_to_invitation_response(i) for i in invitations]


@router.post(
    "/invitations/{invitation_id}/accept",
    response_model=JudgeInvitationResponse,
    summary="Accept Judge Invitation",
    description="Accept a pending judge invitation. Elevates the user's role in this event to Judge.",
)
def accept_invitation(
    invitation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    invitation = PlatformService.respond_to_invitation(db, invitation_id, current_user, accept=True)
    return _to_invitation_response(invitation)


@router.post(
    "/invitations/{invitation_id}/decline",
    response_model=JudgeInvitationResponse,
    summary="Decline Judge Invitation",
    description="Decline a pending judge invitation.",
)
def decline_invitation(
    invitation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    invitation = PlatformService.respond_to_invitation(db, invitation_id, current_user, accept=False)
    return _to_invitation_response(invitation)


@router.post(
    "/events/judges/invitations/{invitation_id}/cancel",
    response_model=JudgeInvitationResponse,
    summary="Cancel Pending Judge Invitation",
    description="Cancel/revoke a pending judge invitation. Requires Organizer or Owner role.",
)
@router.delete(
    "/events/judges/invitations/{invitation_id}",
    response_model=JudgeInvitationResponse,
    summary="Cancel Pending Judge Invitation (DELETE)",
)
def cancel_judge_invitation(
    invitation_id: str,
    current_user: User = Depends(require_organizer),
    db: Session = Depends(get_db),
):
    invitation = PlatformService.cancel_judge_invitation(db, invitation_id, current_user)
    return _to_invitation_response(invitation)


# ---------------------------------------------------------------------------
# Platform Reset & Maintenance (Owner Only)
# ---------------------------------------------------------------------------

@router.post(
    "/platform/reset-database",
    summary="Flush and Reseed Platform Database",
    description="Wipes all transient platform records (invitations, teams, submissions, events, dynamic users) and reseeds default accounts and fixtures. Requires Owner role.",
)
def reset_database(
    _: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    PlatformService.flush_and_reseed(db)
    return {"message": "Platform database successfully flushed and reseeded with default fixtures."}

