import os
import secrets
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.models.user import User, UserRole, EventRole, EventMember, JudgeInvitation, InvitationStatus
from src.models.event import Event
from src.schemas.platform import (
    RoleChangeRequest,
    JudgeInviteRequest,
    JudgeInvitationResponse,
    EventMemberResponse,
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OWNER_KEY_FILE = PROJECT_ROOT / ".owner_key"


class PlatformService:
    """Manages platform ownership, organizer delegations, and event-specific judge invitations."""

    _active_owner_key: Optional[str] = None

    @staticmethod
    def is_event_closed(event: Optional[Event]) -> bool:
        """Check if an event is closed or submissions have ended, safely handling tz-naive and tz-aware datetimes."""
        if not event:
            return True
        if not event.is_active or event.status == "closed":
            return True
        if event.submissions_close:
            now = datetime.now(timezone.utc)
            sub_close = event.submissions_close
            if sub_close.tzinfo is None:
                sub_close = sub_close.replace(tzinfo=timezone.utc)
            if sub_close <= now:
                return True
        return False

    @classmethod
    def generate_new_owner_key(cls) -> str:
        """Always generate a fresh secure random owner key on platform spin-up."""
        env_key = os.getenv("OWNER_SETUP_KEY")
        if env_key and env_key.strip():
            cls._active_owner_key = env_key.strip()
        else:
            cls._active_owner_key = secrets.token_urlsafe(24)

        try:
            OWNER_KEY_FILE.write_text(cls._active_owner_key, encoding="utf-8")
        except Exception as e:
            logger.warning(f"Could not persist owner key to {OWNER_KEY_FILE}: {e}")

        return cls._active_owner_key

    @classmethod
    def get_or_create_owner_key(cls) -> str:
        """Retrieve the currently active owner setup key."""
        if cls._active_owner_key:
            return cls._active_owner_key

        if OWNER_KEY_FILE.exists():
            try:
                key = OWNER_KEY_FILE.read_text(encoding="utf-8").strip()
                if key:
                    cls._active_owner_key = key
                    return key
            except Exception:
                pass

        return cls.generate_new_owner_key()

    @classmethod
    def claim_owner_role(cls, db: Session, current_user: User, setup_key: str) -> User:
        """Promote current user to platform owner if the setup key matches."""
        valid_key = cls.get_or_create_owner_key()
        cleaned_input = (setup_key or "").strip().strip('"').strip("'").strip()
        cleaned_valid = (valid_key or "").strip().strip('"').strip("'").strip()

        if not cleaned_input or cleaned_input != cleaned_valid:
            logger.warning(f"Owner claim rejected: input length={len(cleaned_input)} vs expected length={len(cleaned_valid)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid owner setup key. Please verify the key from the startup terminal logs or .owner_key file.",
            )

        current_user.role = UserRole.OWNER.value

        # Revoke all participant and judge memberships across all events for this user
        db.query(EventMember).filter(EventMember.user_id == current_user.id).delete()

        # Decline/revoke any pending judge invitations for this user
        db.query(JudgeInvitation).filter(
            JudgeInvitation.invitee_id == current_user.id,
            JudgeInvitation.status == InvitationStatus.PENDING.value,
        ).update({"status": InvitationStatus.DECLINED.value})

        db.commit()
        db.refresh(current_user)
        logger.info(f"User '{current_user.email}' (ID: {current_user.id}) claimed platform OWNER role. All participant/judge statuses revoked.")
        return current_user

    @staticmethod
    def promote_to_organizer(db: Session, current_user: User, target_in: RoleChangeRequest) -> User:
        """Promote a user to Organizer (Only Owner can execute)."""
        if current_user.role != UserRole.OWNER.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the platform Owner can promote users to Organizer.",
            )

        target = None
        if target_in.user_id:
            target = db.query(User).filter(User.id == target_in.user_id).first()
        elif target_in.email:
            target = db.query(User).filter(User.email == target_in.email).first()

        if not target:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target user not found.",
            )

        if target.role == UserRole.OWNER.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot modify the platform Owner.",
            )

        if target.role == UserRole.ORGANIZER.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already an Organizer.",
            )

        if target.role not in (UserRole.USER.value, UserRole.PARTICIPANT.value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot promote account with role '{target.role}'. Promotion is between User and Organizer only.",
            )

        target.role = UserRole.ORGANIZER.value
        db.commit()
        db.refresh(target)
        logger.info(f"Owner '{current_user.id}' promoted user '{target.email}' to ORGANIZER.")
        return target

    @staticmethod
    def demote_to_user(db: Session, current_user: User, target_in: RoleChangeRequest) -> User:
        """Demote an Organizer to User (Only Owner can execute)."""
        if current_user.role != UserRole.OWNER.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the platform Owner can demote Organizers.",
            )

        target = None
        if target_in.user_id:
            target = db.query(User).filter(User.id == target_in.user_id).first()
        elif target_in.email:
            target = db.query(User).filter(User.email == target_in.email).first()

        if not target:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target user not found.",
            )

        if target.role == UserRole.OWNER.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote the platform Owner.",
            )

        if target.role != UserRole.ORGANIZER.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot demote account with role '{target.role}'. Demotion is between Organizer and User only.",
            )

        target.role = UserRole.USER.value
        db.commit()
        db.refresh(target)
        logger.info(f"Owner '{current_user.id}' demoted user '{target.email}' to USER.")
        return target

    @staticmethod
    def list_users(db: Session) -> List[User]:
        """List all platform users and their current roles."""
        users = db.query(User).order_by(User.created_at.desc()).all()
        needs_commit = False
        for u in users:
            if u.role == "participant":
                u.role = UserRole.USER.value
                needs_commit = True
        if needs_commit:
            db.commit()
        return users

    # -----------------------------------------------------------------------
    # Event-Specific Roles & Judge Invitations
    # -----------------------------------------------------------------------

    @staticmethod
    def join_event(db: Session, event_id: str, user: User) -> EventMember:
        """Join an event as a participant.
        
        Rules:
        - Only users can participate in an event.
        - Platform Owners and Organisers are forbidden from participating.
        - An official Judge of this event cannot participate in their own event (may only participate in other events).
        """
        # 1. Platform Owners cannot participate
        if user.role == UserRole.OWNER.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Platform Owners are forbidden from participating in hackathons.",
            )

        # 2. Platform Organisers cannot participate
        if user.role == UserRole.ORGANIZER.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Platform Organisers are forbidden from participating in hackathons.",
            )

        # 3. Verify event exists and is open
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Event '{event_id}' not found.",
            )

        if PlatformService.is_event_closed(event):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot join event '{event.name}': submissions are closed for this hackathon.",
            )

        # 4. Official Judge of this event cannot participate in their own event
        existing_judge = db.query(EventMember).filter(
            EventMember.event_id == event_id,
            EventMember.user_id == user.id,
            EventMember.role == EventRole.JUDGE.value,
        ).first()
        if existing_judge:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are an official Judge for this event and cannot participate in it. Judges may only participate in other events.",
            )

        # 5. Retrieve or create participant membership
        membership = db.query(EventMember).filter(
            EventMember.event_id == event_id,
            EventMember.user_id == user.id,
        ).first()

        if not membership:
            membership = EventMember(
                id=f"mem_{secrets.token_hex(6)}",
                event_id=event_id,
                user_id=user.id,
                role=EventRole.PARTICIPANT.value,
            )
            db.add(membership)
            db.commit()
            db.refresh(membership)

        return membership

    @staticmethod
    def invite_judge(
        db: Session,
        event_id: str,
        inviter: User,
        invite_in: JudgeInviteRequest,
    ) -> JudgeInvitation:
        """Invite an event participant to become a Judge for that event (Organizer or Owner only)."""
        # 1. Verify inviter permission
        if inviter.role not in (UserRole.OWNER.value, UserRole.ORGANIZER.value):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only platform Organizers or the Owner can invite judges to an event.",
            )

        # 2. Verify event exists and is open
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Event '{event_id}' not found.",
            )

        if PlatformService.is_event_closed(event):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot invite judges to event '{event.name}': hackathon event is closed.",
            )

        # 3. Resolve invitee
        invitee = None
        if invite_in.user_id:
            invitee = db.query(User).filter(User.id == invite_in.user_id).first()
        elif invite_in.email:
            invitee = db.query(User).filter(User.email == invite_in.email).first()

        if not invitee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User to invite as judge was not found on the platform.",
            )

        # 4. Check if already a judge for this event
        existing_judge = db.query(EventMember).filter(
            EventMember.event_id == event_id,
            EventMember.user_id == invitee.id,
            EventMember.role == EventRole.JUDGE.value,
        ).first()
        if existing_judge:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User '{invitee.email}' is already a judge for event '{event.name}'.",
            )

        # 5. Check if an active pending invitation already exists
        existing_invite = db.query(JudgeInvitation).filter(
            JudgeInvitation.event_id == event_id,
            JudgeInvitation.invitee_id == invitee.id,
            JudgeInvitation.status == InvitationStatus.PENDING.value,
        ).first()
        if existing_invite:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A pending invitation for '{invitee.email}' is already awaiting response.",
            )

        # 6. Ensure user is at least an event member (participant)
        membership = db.query(EventMember).filter(
            EventMember.event_id == event_id,
            EventMember.user_id == invitee.id,
        ).first()
        if not membership:
            membership = EventMember(
                id=f"mem_{secrets.token_hex(6)}",
                event_id=event_id,
                user_id=invitee.id,
                role=EventRole.PARTICIPANT.value,
            )
            db.add(membership)

        invitation = JudgeInvitation(
            id=f"inv_{secrets.token_hex(8)}",
            event_id=event_id,
            inviter_id=inviter.id,
            invitee_id=invitee.id,
            status=InvitationStatus.PENDING.value,
        )
        db.add(invitation)
        db.commit()
        db.refresh(invitation)
        logger.info(f"Organizer '{inviter.id}' invited '{invitee.email}' to judge event '{event_id}'.")
        return invitation

    @staticmethod
    def get_my_invitations(db: Session, user: User) -> List[JudgeInvitation]:
        """List all judge invitations sent to the current user."""
        invitations = db.query(JudgeInvitation).filter(
            JudgeInvitation.invitee_id == user.id
        ).order_by(JudgeInvitation.created_at.desc()).all()

        needs_commit = False
        for inv in invitations:
            if inv.status == InvitationStatus.PENDING.value and inv.event:
                if PlatformService.is_event_closed(inv.event):
                    inv.status = InvitationStatus.EXPIRED.value
                    needs_commit = True
        if needs_commit:
            db.commit()

        return invitations

    @staticmethod
    def respond_to_invitation(
        db: Session,
        invitation_id: str,
        user: User,
        accept: bool,
    ) -> JudgeInvitation:
        """Accept or decline a judge invitation. If accepted, elevates event role to Judge."""
        invitation = db.query(JudgeInvitation).filter(
            JudgeInvitation.id == invitation_id,
            JudgeInvitation.invitee_id == user.id,
        ).first()

        if not invitation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invitation not found or not addressed to you.",
            )

        # Check if event has closed or invitation has expired
        if invitation.status == InvitationStatus.EXPIRED.value or (
            invitation.event and PlatformService.is_event_closed(invitation.event)
        ):
            if invitation.status == InvitationStatus.PENDING.value:
                invitation.status = InvitationStatus.EXPIRED.value
                db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot respond to invitation: this hackathon event has closed and the invitation has expired.",
            )

        if invitation.status != InvitationStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invitation has already been {invitation.status}.",
            )

        invitation.responded_at = datetime.now(timezone.utc)
        if accept:
            invitation.status = InvitationStatus.ACCEPTED.value
            # Elevate user's event role to Judge
            member = db.query(EventMember).filter(
                EventMember.event_id == invitation.event_id,
                EventMember.user_id == user.id,
            ).first()
            if member:
                member.role = EventRole.JUDGE.value
            else:
                member = EventMember(
                    id=f"mem_{secrets.token_hex(6)}",
                    event_id=invitation.event_id,
                    user_id=user.id,
                    role=EventRole.JUDGE.value,
                )
                db.add(member)
            logger.info(f"User '{user.email}' accepted judge invitation for event '{invitation.event_id}'.")
        else:
            invitation.status = InvitationStatus.DECLINED.value
            logger.info(f"User '{user.email}' declined judge invitation for event '{invitation.event_id}'.")

        db.commit()
        db.refresh(invitation)
        return invitation

    @staticmethod
    def get_event_judges(db: Session, event_id: str) -> List[EventMember]:
        """List all confirmed judges for a specific event."""
        return db.query(EventMember).filter(
            EventMember.event_id == event_id,
            EventMember.role == EventRole.JUDGE.value,
        ).all()

    @staticmethod
    def get_event_members(db: Session, event_id: str) -> List[EventMember]:
        """List all members (participants and judges) for an event."""
        return db.query(EventMember).filter(
            EventMember.event_id == event_id,
        ).all()
