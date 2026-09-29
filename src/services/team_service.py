"""Team Service handling hackathon team formation and invitations (T1 CORE subtask).

Supports:
- Creating a team for an event (leader role)
- Listing teams and their members
- Joining a team
- Leaving a team
- Sending, listing, accepting, and declining team invitations
- Enforcing max team size and event submission deadlines
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.models.user import User, EventMember, EventRole
from src.models.event import Event, _ensure_utc
from src.models.project import Team, TeamMember, TeamMemberRole, Project, TeamInvitation, TeamInvitationStatus
from src.schemas.team import TeamCreate, TeamResponse, TeamMemberResponse, TeamInvitationResponse
from src.services.event_service import EventService


class TeamService:

    @staticmethod
    def _to_team_response(team: Team) -> TeamResponse:
        members = []
        for m in (team.members or []):
            user_name = m.user.name if m.user else None
            user_email = m.user.email if m.user else None
            members.append(
                TeamMemberResponse(
                    id=m.id,
                    team_id=m.team_id,
                    user_id=m.user_id,
                    role=m.role,
                    joined_at=_ensure_utc(m.joined_at),
                    user_name=user_name,
                    user_email=user_email,
                )
            )
        project_id = team.projects[0].id if team.projects else None
        return TeamResponse(
            id=team.id,
            event_id=team.event_id,
            name=team.name,
            created_at=_ensure_utc(team.created_at),
            member_count=len(members),
            members=members,
            project_id=project_id,
        )

    @staticmethod
    def _to_invitation_response(inv: TeamInvitation) -> TeamInvitationResponse:
        inviter_name = inv.inviter.name if inv.inviter else None
        invitee_email = inv.invitee.email if inv.invitee else None
        team_name = inv.team.name if inv.team else None
        event_name = inv.event.name if inv.event else None
        return TeamInvitationResponse(
            id=inv.id,
            team_id=inv.team_id,
            team_name=team_name,
            event_id=inv.event_id,
            event_name=event_name,
            inviter_id=inv.inviter_id,
            inviter_name=inviter_name,
            invitee_id=inv.invitee_id,
            invitee_email=invitee_email,
            status=inv.status,
            created_at=_ensure_utc(inv.created_at),
            responded_at=_ensure_utc(inv.responded_at),
        )

    @classmethod
    def create_team(cls, db: Session, event_id: str, user: User, team_in: TeamCreate) -> TeamResponse:
        """Create a new team for an event. User must be a registered participant and not already in a team."""
        # 1. Enforce deadline
        event = EventService.check_submission_allowed(db, event_id)

        # 2. Enforce solo hackathon check
        if getattr(event, "max_team_size", 4) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Event '{event.name}' is an individual (solo) hackathon. Team formation is not allowed.",
            )

        # 3. Check participant membership
        membership = (
            db.query(EventMember)
            .filter(EventMember.event_id == event_id, EventMember.user_id == user.id)
            .first()
        )
        if not membership or membership.role != EventRole.PARTICIPANT.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User '{user.email}' is not a registered participant of event '{event_id}'. Only participants can form teams.",
            )

        # 4. Check if user is already on a team for this event
        existing_membership = (
            db.query(TeamMember)
            .join(Team, TeamMember.team_id == Team.id)
            .filter(Team.event_id == event_id, TeamMember.user_id == user.id)
            .first()
        )
        if existing_membership:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User is already a member of team '{existing_membership.team_id}' in event '{event_id}'.",
            )

        # 5. Create team and team leader
        team_id = f"tm_{uuid.uuid4().hex[:8]}"
        team = Team(
            id=team_id,
            event_id=event_id,
            name=team_in.name,
            created_at=datetime.now(timezone.utc),
        )
        db.add(team)

        lead_member = TeamMember(
            id=f"tmem_{uuid.uuid4().hex[:8]}",
            team_id=team_id,
            user_id=user.id,
            role=TeamMemberRole.LEAD.value,
            joined_at=datetime.now(timezone.utc),
        )
        db.add(lead_member)
        db.commit()
        db.refresh(team)

        return cls._to_team_response(team)

    @classmethod
    def list_teams(cls, db: Session, event_id: str) -> List[TeamResponse]:
        """List all teams participating in an event."""
        teams = db.query(Team).filter(Team.event_id == event_id).all()
        return [cls._to_team_response(t) for t in teams]

    @classmethod
    def get_team(cls, db: Session, team_id: str) -> TeamResponse:
        """Get details of a specific team."""
        team = db.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Team '{team_id}' not found.",
            )
        return cls._to_team_response(team)

    @classmethod
    def join_team(cls, db: Session, team_id: str, user: User) -> TeamResponse:
        """Join an existing team. User must be a participant in the event and team must not be full."""
        team = db.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Team '{team_id}' not found.",
            )

        # 1. Enforce deadline
        event = EventService.check_submission_allowed(db, team.event_id)

        # 2. Check team capacity
        max_size = getattr(event, "max_team_size", 4)
        if len(team.members) >= max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Team '{team.name}' has already reached its maximum capacity of {max_size} members.",
            )

        # 3. Check participant membership
        membership = (
            db.query(EventMember)
            .filter(EventMember.event_id == team.event_id, EventMember.user_id == user.id)
            .first()
        )
        if not membership or membership.role != EventRole.PARTICIPANT.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only registered participants can join a team.",
            )

        # 4. Check if user already on a team in this event
        existing_membership = (
            db.query(TeamMember)
            .join(Team, TeamMember.team_id == Team.id)
            .filter(Team.event_id == team.event_id, TeamMember.user_id == user.id)
            .first()
        )
        if existing_membership:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already a member of a team in this event.",
            )

        # 5. Add member
        new_member = TeamMember(
            id=f"tmem_{uuid.uuid4().hex[:8]}",
            team_id=team.id,
            user_id=user.id,
            role=TeamMemberRole.MEMBER.value,
            joined_at=datetime.now(timezone.utc),
        )
        db.add(new_member)
        db.commit()
        db.refresh(team)

        return cls._to_team_response(team)

    @classmethod
    def dissolve_team(cls, db: Session, team_id: str, user: User) -> dict:
        """Dissolve a team (Team Leader or Platform Owner only). All members become single participants again."""
        team = db.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Team '{team_id}' not found.",
            )

        # 1. Enforce deadline
        EventService.check_submission_allowed(db, team.event_id)

        # 2. Check caller is lead or owner
        member = (
            db.query(TeamMember)
            .filter(TeamMember.team_id == team_id, TeamMember.user_id == user.id)
            .first()
        )
        is_lead = member and member.role == TeamMemberRole.LEAD.value
        if not is_lead and user.role != "owner":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the team leader or platform owner can dissolve the team.",
            )

        team_name = team.name
        db.delete(team)
        db.commit()
        return {
            "status": "success",
            "message": f"Team '{team_name}' has been dissolved. All former members are now single participants.",
            "team_id": team_id,
        }

    @classmethod
    def leave_team(cls, db: Session, team_id: str, user: User) -> dict:
        """Leave a team. If only one member remains, they become a normal single participant again."""
        team = db.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Team '{team_id}' not found.",
            )

        # 1. Enforce deadline
        EventService.check_submission_allowed(db, team.event_id)

        # 2. Lookup user's team membership
        member = (
            db.query(TeamMember)
            .filter(TeamMember.team_id == team_id, TeamMember.user_id == user.id)
            .first()
        )
        if not member:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is not a member of this team.",
            )

        # 3. Remove membership
        db.delete(member)
        db.commit()

        # 4. Check remaining members count
        remaining_members = db.query(TeamMember).filter(TeamMember.team_id == team_id).all()
        remaining_count = len(remaining_members)

        if remaining_count <= 1:
            # If only one member remains, they become a normal single participant again (team dissolves)
            db.delete(team)
            db.commit()
            return {
                "status": "success",
                "message": f"Left team '{team_id}'. As only one or zero members remained, the team was dissolved and any remaining member is now a single participant.",
                "team_id": team_id,
                "team_dissolved": True,
            }
        else:
            # If leaving member was lead, promote first remaining member to lead
            lead_exists = any(m.role == TeamMemberRole.LEAD.value for m in remaining_members)
            if not lead_exists and remaining_members:
                remaining_members[0].role = TeamMemberRole.LEAD.value
                db.commit()

            return {
                "status": "success",
                "message": f"Successfully left team '{team_id}'.",
                "team_id": team_id,
                "team_dissolved": False,
            }

    @classmethod
    def invite_teammate(
        cls,
        db: Session,
        team_id: str,
        inviter: User,
        user_id: Optional[str] = None,
        email: Optional[str] = None,
    ) -> TeamInvitationResponse:
        """Invite a participant to join a team."""
        team = db.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Team '{team_id}' not found.",
            )

        # 1. Enforce deadline
        event = EventService.check_submission_allowed(db, team.event_id)

        # 2. Verify inviter is in this team
        inviter_membership = (
            db.query(TeamMember)
            .filter(TeamMember.team_id == team_id, TeamMember.user_id == inviter.id)
            .first()
        )
        if not inviter_membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only current team members can invite new teammates.",
            )

        # 3. Check team capacity
        max_size = getattr(event, "max_team_size", 4)
        if len(team.members) >= max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Team '{team.name}' has already reached its maximum capacity of {max_size} members.",
            )

        # 4. Resolve invitee
        if not user_id and not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Must provide either user_id or email of the participant to invite.",
            )

        invitee = None
        if user_id:
            invitee = db.query(User).filter(User.id == user_id).first()
        if not invitee and email:
            invitee = db.query(User).filter(User.email == email.strip().lower()).first()

        if not invitee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The specified user does not exist on the platform.",
            )

        if invitee.id == inviter.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot invite yourself to your own team.",
            )

        # 5. Check invitee is not owner, organizer, or judge in this event
        if invitee.role in ("owner", "organizer"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User '{invitee.name}' is an administrator and cannot participate in competitions.",
            )
        judge_membership = (
            db.query(EventMember)
            .filter(EventMember.event_id == team.event_id, EventMember.user_id == invitee.id, EventMember.role == EventRole.JUDGE.value)
            .first()
        )
        if judge_membership:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User '{invitee.name}' is assigned as a Judge for this hackathon and cannot join a team.",
            )

        # 6. Check invitee is not already on a team in this event
        existing_team = (
            db.query(TeamMember)
            .join(Team, TeamMember.team_id == Team.id)
            .filter(Team.event_id == team.event_id, TeamMember.user_id == invitee.id)
            .first()
        )
        if existing_team:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User '{invitee.name}' is already a member of a team in this hackathon.",
            )

        # 7. Check for existing pending invitation
        existing_inv = (
            db.query(TeamInvitation)
            .filter(
                TeamInvitation.team_id == team_id,
                TeamInvitation.invitee_id == invitee.id,
                TeamInvitation.status == TeamInvitationStatus.PENDING.value,
            )
            .first()
        )
        if existing_inv:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A pending invitation has already been sent to '{invitee.name}'.",
            )

        # 8. Create invitation
        inv_id = f"tinv_{uuid.uuid4().hex[:8]}"
        inv = TeamInvitation(
            id=inv_id,
            team_id=team_id,
            event_id=team.event_id,
            inviter_id=inviter.id,
            invitee_id=invitee.id,
            status=TeamInvitationStatus.PENDING.value,
            created_at=datetime.now(timezone.utc),
        )
        db.add(inv)
        db.commit()
        db.refresh(inv)

        return cls._to_invitation_response(inv)

    @classmethod
    def list_team_invitations(cls, db: Session, team_id: str) -> List[TeamInvitationResponse]:
        """List all pending invitations sent by a team, expiring any for unavailable users."""
        invs = (
            db.query(TeamInvitation)
            .filter(TeamInvitation.team_id == team_id, TeamInvitation.status == TeamInvitationStatus.PENDING.value)
            .all()
        )
        active_invs = []
        needs_commit = False
        for inv in invs:
            event = db.query(Event).filter(Event.id == inv.event_id).first()
            if event and not event.is_submission_open():
                inv.status = TeamInvitationStatus.EXPIRED.value
                needs_commit = True
                continue

            invitee = db.query(User).filter(User.id == inv.invitee_id).first()
            if not invitee or invitee.role in ("owner", "organizer"):
                inv.status = TeamInvitationStatus.EXPIRED.value
                needs_commit = True
                continue

            # Check if invitee joined another team in this event
            other_team = (
                db.query(TeamMember)
                .join(Team, TeamMember.team_id == Team.id)
                .filter(Team.event_id == inv.event_id, TeamMember.user_id == inv.invitee_id)
                .first()
            )
            if other_team:
                inv.status = TeamInvitationStatus.EXPIRED.value
                needs_commit = True
                continue

            # Check if invitee is a judge for this event
            is_judge = (
                db.query(EventMember)
                .filter(EventMember.event_id == inv.event_id, EventMember.user_id == inv.invitee_id, EventMember.role == EventRole.JUDGE.value)
                .first()
            )
            if is_judge:
                inv.status = TeamInvitationStatus.EXPIRED.value
                needs_commit = True
                continue

            active_invs.append(inv)

        if needs_commit:
            db.commit()
        return [cls._to_invitation_response(i) for i in active_invs]

    @classmethod
    def cancel_team_invitation(cls, db: Session, invitation_id: str, user: User) -> TeamInvitationResponse:
        """Cancel a pending team invitation. Caller must be in the team or platform owner."""
        inv = db.query(TeamInvitation).filter(TeamInvitation.id == invitation_id).first()
        if not inv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Invitation '{invitation_id}' not found.",
            )

        member = (
            db.query(TeamMember)
            .filter(TeamMember.team_id == inv.team_id, TeamMember.user_id == user.id)
            .first()
        )
        if not member and user.role != "owner":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only team members can cancel pending invitations.",
            )

        inv.status = TeamInvitationStatus.DECLINED.value
        db.commit()
        db.refresh(inv)
        return cls._to_invitation_response(inv)

    @classmethod
    def get_user_team_invitations(cls, db: Session, user_id: str) -> List[TeamInvitationResponse]:
        """List all team invitations received by the user."""
        invs = (
            db.query(TeamInvitation)
            .filter(TeamInvitation.invitee_id == user_id)
            .order_by(TeamInvitation.created_at.desc())
            .all()
        )
        # Update expired statuses if event closed
        for inv in invs:
            if inv.status == TeamInvitationStatus.PENDING.value:
                event = db.query(Event).filter(Event.id == inv.event_id).first()
                if event and not event.is_submission_open():
                    inv.status = TeamInvitationStatus.EXPIRED.value
        db.commit()

        return [cls._to_invitation_response(i) for i in invs]

    @classmethod
    def accept_team_invitation(cls, db: Session, invitation_id: str, user: User) -> TeamInvitationResponse:
        """Accept a team invitation and join the team."""
        inv = db.query(TeamInvitation).filter(TeamInvitation.id == invitation_id).first()
        if not inv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Invitation '{invitation_id}' not found.",
            )

        if inv.invitee_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot respond to an invitation not addressed to you.",
            )

        if inv.status != TeamInvitationStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invitation has already been {inv.status}.",
            )

        event = EventService.check_submission_allowed(db, inv.event_id)

        team = db.query(Team).filter(Team.id == inv.team_id).first()
        if not team:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team no longer exists.",
            )

        max_size = getattr(event, "max_team_size", 4)
        if len(team.members) >= max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Team '{team.name}' has already reached its maximum capacity of {max_size} members.",
            )

        # Check user is not already on another team in this event
        existing_membership = (
            db.query(TeamMember)
            .join(Team, TeamMember.team_id == Team.id)
            .filter(Team.event_id == team.event_id, TeamMember.user_id == user.id)
            .first()
        )
        if existing_membership:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already a member of a team in this event.",
            )

        # Ensure user is registered as an EventMember participant
        participant_membership = (
            db.query(EventMember)
            .filter(EventMember.event_id == inv.event_id, EventMember.user_id == user.id)
            .first()
        )
        if not participant_membership:
            db.add(EventMember(
                id=f"em_{uuid.uuid4().hex[:8]}",
                event_id=inv.event_id,
                user_id=user.id,
                role=EventRole.PARTICIPANT.value,
                joined_at=datetime.now(timezone.utc),
            ))

        # Add member to team
        new_member = TeamMember(
            id=f"tmem_{uuid.uuid4().hex[:8]}",
            team_id=team.id,
            user_id=user.id,
            role=TeamMemberRole.MEMBER.value,
            joined_at=datetime.now(timezone.utc),
        )
        db.add(new_member)

        # Update invitation
        inv.status = TeamInvitationStatus.ACCEPTED.value
        inv.responded_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(inv)

        return cls._to_invitation_response(inv)

    @classmethod
    def decline_team_invitation(cls, db: Session, invitation_id: str, user: User) -> TeamInvitationResponse:
        """Decline a team invitation."""
        inv = db.query(TeamInvitation).filter(TeamInvitation.id == invitation_id).first()
        if not inv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Invitation '{invitation_id}' not found.",
            )

        if inv.invitee_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot respond to an invitation not addressed to you.",
            )

        if inv.status != TeamInvitationStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invitation has already been {inv.status}.",
            )

        inv.status = TeamInvitationStatus.DECLINED.value
        inv.responded_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(inv)

        return cls._to_invitation_response(inv)
