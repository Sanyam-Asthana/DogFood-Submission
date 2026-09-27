"""Tests for Platform Ownership, Organizer Management, and Event Judge Invitations."""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base, get_db
from src.main import app
from src.models.user import User, UserRole, EventMember, EventRole, JudgeInvitation, InvitationStatus
from src.models.event import Event
from src.services.platform_service import PlatformService

TEST_DB_URL = "sqlite:///./test_platform.db"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()

    # Pre-seed users
    users = [
        User(id="user_alice", email="alice@test.org", name="Alice Participant", role=UserRole.PARTICIPANT.value, session_token="tok_alice"),
        User(id="user_bob", email="bob@test.org", name="Bob Participant", role=UserRole.PARTICIPANT.value, session_token="tok_bob"),
        User(id="user_charlie", email="charlie@test.org", name="Charlie Candidate", role=UserRole.PARTICIPANT.value, session_token="tok_charlie"),
    ]
    for u in users:
        db.add(u)

    # Pre-seed event
    event = Event(
        id="evt_hack_01",
        name="Innovation Hackathon",
        description="Test event for roles",
        submissions_open=datetime.now(timezone.utc) - timedelta(hours=2),
        submissions_close=datetime.now(timezone.utc) + timedelta(hours=24),
        is_active=True,
        created_by="user_alice",
    )
    db.add(event)
    db.commit()
    db.close()

    yield

    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client():
    return TestClient(app)


def test_claim_owner_role(client):
    # Setup key
    owner_key = PlatformService.get_or_create_owner_key()

    # 1. Invalid key fails
    res_bad = client.post(
        "/api/platform/claim-owner",
        json={"setup_key": "wrong_key_12345"},
        headers={"X-Session-Token": "tok_alice"},
    )
    assert res_bad.status_code == 400

    # 2. Valid key succeeds
    res_ok = client.post(
        "/api/platform/claim-owner",
        json={"setup_key": owner_key},
        headers={"X-Session-Token": "tok_alice"},
    )
    assert res_ok.status_code == 200
    data = res_ok.json()
    assert data["role"] == "owner"
    assert data["email"] == "alice@test.org"


def test_promote_and_demote_organizer(client):
    # Alice is now Owner. Bob is participant.
    # Non-owner (Bob) trying to promote Charlie fails
    res_forbidden = client.post(
        "/api/platform/promote-organizer",
        json={"user_id": "user_charlie"},
        headers={"X-Session-Token": "tok_bob"},
    )
    assert res_forbidden.status_code == 403

    # Owner (Alice) promotes Bob to organizer
    res_promote = client.post(
        "/api/platform/promote-organizer",
        json={"user_id": "user_bob"},
        headers={"X-Session-Token": "tok_alice"},
    )
    assert res_promote.status_code == 200
    assert res_promote.json()["role"] == "organizer"

    # Bob can now list all platform users
    res_list = client.get(
        "/api/platform/users",
        headers={"X-Session-Token": "tok_bob"},
    )
    assert res_list.status_code == 200
    users = res_list.json()
    assert len(users) >= 3

    # Owner (Alice) demotes Bob back to user
    res_demote = client.post(
        "/api/platform/demote-organizer",
        json={"user_id": "user_bob"},
        headers={"X-Session-Token": "tok_alice"},
    )
    assert res_demote.status_code == 200
    assert res_demote.json()["role"] in ("user", "participant")


def test_event_participation_and_judge_flow(client):
    # Promote Bob back to organizer so he can invite judges
    client.post(
        "/api/platform/promote-organizer",
        json={"user_id": "user_bob"},
        headers={"X-Session-Token": "tok_alice"},
    )

    # 1. Charlie joins the event as participant
    res_join = client.post(
        "/api/events/evt_hack_01/join",
        headers={"X-Session-Token": "tok_charlie"},
    )
    assert res_join.status_code == 201
    member_data = res_join.json()
    assert member_data["role"] == "participant"
    assert member_data["user_id"] == "user_charlie"

    # 2. Bob (organizer) invites Charlie to be a Judge
    res_invite = client.post(
        "/api/events/evt_hack_01/judges/invite",
        json={"user_id": "user_charlie"},
        headers={"X-Session-Token": "tok_bob"},
    )
    assert res_invite.status_code == 201
    inv_data = res_invite.json()
    inv_id = inv_data["id"]
    assert inv_data["status"] == "pending"
    assert inv_data["event_id"] == "evt_hack_01"

    # 3. Inviting again fails with 409 conflict
    res_duplicate = client.post(
        "/api/events/evt_hack_01/judges/invite",
        json={"user_id": "user_charlie"},
        headers={"X-Session-Token": "tok_bob"},
    )
    assert res_duplicate.status_code == 409

    # 4. Charlie checks his invitations
    res_my_invites = client.get(
        "/api/invitations/my",
        headers={"X-Session-Token": "tok_charlie"},
    )
    assert res_my_invites.status_code == 200
    my_invites = res_my_invites.json()
    assert len(my_invites) >= 1
    assert any(i["id"] == inv_id for i in my_invites)

    # 5. Charlie accepts the judge invitation
    res_accept = client.post(
        f"/api/invitations/{inv_id}/accept",
        headers={"X-Session-Token": "tok_charlie"},
    )
    assert res_accept.status_code == 200
    assert res_accept.json()["status"] == "accepted"

    # 6. Verify Organizer (Bob) can see judges
    res_judges = client.get("/api/events/evt_hack_01/judges", headers={"X-Session-Token": "tok_bob"})
    assert res_judges.status_code == 200
    judges = res_judges.json()
    assert any(j["user_id"] == "user_charlie" and j["role"] == "judge" for j in judges)

    # 7. Verify Judge (Charlie) CANNOT see event judges list (403 Forbidden)
    res_judge_forbidden = client.get("/api/events/evt_hack_01/judges", headers={"X-Session-Token": "tok_charlie"})
    assert res_judge_forbidden.status_code == 403

    # 8. Verify Judge (Charlie) CANNOT see event participants list (403 Forbidden)
    res_part_forbidden = client.get("/api/events/evt_hack_01/participants", headers={"X-Session-Token": "tok_charlie"})
    assert res_part_forbidden.status_code == 403

    # 9. Verify Charlie CAN check their own membership
    res_my_mem = client.get("/api/events/evt_hack_01/my-membership", headers={"X-Session-Token": "tok_charlie"})
    assert res_my_mem.status_code == 200
    assert res_my_mem.json()["role"] == "judge"

    # 10. Verify Organizer can see participants list
    res_part_org = client.get("/api/events/evt_hack_01/participants", headers={"X-Session-Token": "tok_bob"})
    assert res_part_org.status_code == 200


def test_owner_promote_demote_restrictions(client):
    # Setup: Alice is Owner, Bob is Organizer
    # 1. Demoting someone who is already a user fails with 400
    res_demote_user = client.post(
        "/api/platform/demote-organizer",
        json={"user_id": "user_charlie"},
        headers={"X-Session-Token": "tok_alice"},
    )
    assert res_demote_user.status_code == 400

    # 2. Promoting someone who is already an organizer fails with 400
    res_promote_org = client.post(
        "/api/platform/promote-organizer",
        json={"user_id": "user_bob"},
        headers={"X-Session-Token": "tok_alice"},
    )
    assert res_promote_org.status_code == 400

    # 3. Cannot promote or demote the platform owner
    res_owner_promote = client.post(
        "/api/platform/promote-organizer",
        json={"user_id": "user_alice"},
        headers={"X-Session-Token": "tok_alice"},
    )
    assert res_owner_promote.status_code == 400

    res_owner_demote = client.post(
        "/api/platform/demote-organizer",
        json={"user_id": "user_alice"},
        headers={"X-Session-Token": "tok_alice"},
    )
    assert res_owner_demote.status_code == 400


def test_event_participation_restrictions(client):
    # Setup: Alice is Owner, Bob is Organizer, Charlie is Judge of evt_hack_01
    # 1. Platform Owner (Alice) cannot participate
    res_owner_join = client.post(
        "/api/events/evt_hack_01/join",
        headers={"X-Session-Token": "tok_alice"},
    )
    assert res_owner_join.status_code == 403
    assert "owner" in res_owner_join.json()["detail"].lower()

    # 2. Platform Organizer (Bob) cannot participate
    res_org_join = client.post(
        "/api/events/evt_hack_01/join",
        headers={"X-Session-Token": "tok_bob"},
    )
    assert res_org_join.status_code == 403
    assert "organise" in res_org_join.json()["detail"].lower() or "organize" in res_org_join.json()["detail"].lower()

    # 3. Judge of evt_hack_01 (Charlie) cannot participate in evt_hack_01
    res_judge_own = client.post(
        "/api/events/evt_hack_01/join",
        headers={"X-Session-Token": "tok_charlie"},
    )
    assert res_judge_own.status_code == 403
    assert "judge" in res_judge_own.json()["detail"].lower()

    # 4. Judge of evt_hack_01 CAN participate in another event (evt_hack_02)
    # First, organizer creates evt_hack_02
    res_create_evt2 = client.post(
        "/api/events",
        json={
            "id": "evt_hack_02",
            "name": "Second Hackathon",
            "submissions_close": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
        },
        headers={"X-Session-Token": "tok_bob"},
    )
    assert res_create_evt2.status_code == 201

    # Charlie joins evt_hack_02 as a participant
    res_join_evt2 = client.post(
        "/api/events/evt_hack_02/join",
        headers={"X-Session-Token": "tok_charlie"},
    )
    assert res_join_evt2.status_code == 201
    assert res_join_evt2.json()["role"] == "participant"


def test_owner_claim_revokes_memberships_and_invitations(client):
    # Setup Dave
    db = TestingSessionLocal()
    dave = User(
        id="user_dave",
        email="dave@test.org",
        name="Dave User",
        role=UserRole.PARTICIPANT.value,
        session_token="tok_dave",
    )
    db.add(dave)
    db.commit()

    # Dave joins evt_hack_02 as a participant
    res_join = client.post(
        "/api/events/evt_hack_02/join",
        headers={"X-Session-Token": "tok_dave"},
    )
    assert res_join.status_code == 201

    # Bob (Organizer) invites Dave to be Judge of evt_hack_02
    res_invite = client.post(
        "/api/events/evt_hack_02/judges/invite",
        json={"user_id": "user_dave"},
        headers={"X-Session-Token": "tok_bob"},
    )
    assert res_invite.status_code == 201
    inv_id = res_invite.json()["id"]

    # Verify Dave currently has an event membership
    mems_before = db.query(EventMember).filter(EventMember.user_id == "user_dave").all()
    assert len(mems_before) > 0

    # Dave claims platform ownership using the owner key
    key = PlatformService.get_or_create_owner_key()
    res_claim = client.post(
        "/api/platform/claim-owner",
        json={"setup_key": key},
        headers={"X-Session-Token": "tok_dave"},
    )
    assert res_claim.status_code == 200
    assert res_claim.json()["role"] == "owner"

    # Verify all memberships for Dave are revoked
    mems_after = db.query(EventMember).filter(EventMember.user_id == "user_dave").all()
    assert len(mems_after) == 0

    # Verify pending invitation was marked declined
    inv = db.query(JudgeInvitation).filter(JudgeInvitation.id == inv_id).first()
    assert inv.status == InvitationStatus.DECLINED.value
    db.close()


def test_cannot_join_closed_event(client):
    # Bob creates an event with submissions_close in the past
    past_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    res_create = client.post(
        "/api/events",
        json={
            "id": "evt_closed_01",
            "name": "Expired Hackathon",
            "submissions_close": past_time,
        },
        headers={"X-Session-Token": "tok_bob"},
    )
    assert res_create.status_code == 201

    # Charlie (User) attempts to join the closed event
    res_join = client.post(
        "/api/events/evt_closed_01/join",
        headers={"X-Session-Token": "tok_charlie"},
    )
    assert res_join.status_code == 400
    assert "closed" in res_join.json()["detail"].lower()


def test_judge_invitation_expires_when_event_closed(client):
    db = TestingSessionLocal()
    # 1. Organizer invites Charlie to evt_hack_02 (which is open)
    res_invite = client.post(
        "/api/events/evt_hack_02/judges/invite",
        json={"user_id": "user_charlie"},
        headers={"X-Session-Token": "tok_bob"},
    )
    assert res_invite.status_code == 201
    inv_id = res_invite.json()["id"]

    # 2. Close evt_hack_02 by updating its submissions_close to past
    event2 = db.query(Event).filter(Event.id == "evt_hack_02").first()
    event2.submissions_close = datetime.now(timezone.utc) - timedelta(hours=1)
    db.commit()

    # 3. Charlie checks his invitations -> status should now be 'expired'
    res_my_invites = client.get(
        "/api/invitations/my",
        headers={"X-Session-Token": "tok_charlie"},
    )
    assert res_my_invites.status_code == 200
    my_invites = res_my_invites.json()
    expired_inv = next(i for i in my_invites if i["id"] == inv_id)
    assert expired_inv["status"] == "expired"

    # 4. Charlie attempts to accept the expired invitation -> rejected with 400
    res_accept = client.post(
        f"/api/invitations/{inv_id}/accept",
        headers={"X-Session-Token": "tok_charlie"},
    )
    assert res_accept.status_code == 400
    assert "expired" in res_accept.json()["detail"].lower()

    # 5. Organizer cannot invite judges to a closed event
    res_closed_invite = client.post(
        "/api/events/evt_hack_02/judges/invite",
        json={"user_id": "user_charlie"},
        headers={"X-Session-Token": "tok_bob"},
    )
    assert res_closed_invite.status_code == 400
    assert "closed" in res_closed_invite.json()["detail"].lower()
    db.close()


def test_invite_user_does_not_make_participant_and_accept_revokes_participant(client):
    db = TestingSessionLocal()
    # Setup open event evt_open_test
    res_evt = client.post(
        "/api/events",
        json={
            "id": "evt_open_test",
            "name": "Judge Flow Hackathon",
            "submissions_close": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat(),
        },
        headers={"X-Session-Token": "tok_bob"},
    )
    assert res_evt.status_code == 201

    # Create two users: user_frank and user_grace
    frank = User(id="user_frank", email="frank@test.org", name="Frank", role=UserRole.USER.value, session_token="tok_frank")
    grace = User(id="user_grace", email="grace@test.org", name="Grace", role=UserRole.USER.value, session_token="tok_grace")
    db.add_all([frank, grace])
    db.commit()

    # 1. Grace joins as a participant
    res_grace_join = client.post("/api/events/evt_open_test/join", headers={"X-Session-Token": "tok_grace"})
    assert res_grace_join.status_code == 201

    # 2. Bob invites Frank (who has NOT registered) to judge
    res_frank_inv = client.post(
        "/api/events/evt_open_test/judges/invite",
        json={"user_id": "user_frank"},
        headers={"X-Session-Token": "tok_bob"},
    )
    assert res_frank_inv.status_code == 201

    # Verify Frank is NOT in participants!
    res_parts = client.get("/api/events/evt_open_test/participants", headers={"X-Session-Token": "tok_bob"})
    assert res_parts.status_code == 200
    parts = res_parts.json()
    assert not any(p["user_id"] == "user_frank" for p in parts)
    assert any(p["user_id"] == "user_grace" for p in parts)

    # Verify Frank is in invited judges!
    res_invs = client.get("/api/events/evt_open_test/judges/invitations", headers={"X-Session-Token": "tok_bob"})
    assert res_invs.status_code == 200
    invs = res_invs.json()
    assert any(i["invitee_id"] == "user_frank" and i["status"] == "pending" for i in invs)

    # 3. Bob also invites Grace (who IS currently a registered participant) to judge
    res_grace_inv = client.post(
        "/api/events/evt_open_test/judges/invite",
        json={"user_id": "user_grace"},
        headers={"X-Session-Token": "tok_bob"},
    )
    assert res_grace_inv.status_code == 201
    grace_inv_id = res_grace_inv.json()["id"]

    # Grace accepts judge invitation
    res_grace_accept = client.post(
        f"/api/invitations/{grace_inv_id}/accept",
        headers={"X-Session-Token": "tok_grace"},
    )
    assert res_grace_accept.status_code == 200

    # Verify Grace's participant status is revoked:
    # She should now be in judges, and NOT in participants!
    res_judges_after = client.get("/api/events/evt_open_test/judges", headers={"X-Session-Token": "tok_bob"})
    assert res_judges_after.status_code == 200
    assert any(j["user_id"] == "user_grace" for j in res_judges_after.json())

    res_parts_after = client.get("/api/events/evt_open_test/participants", headers={"X-Session-Token": "tok_bob"})
    assert res_parts_after.status_code == 200
    assert not any(p["user_id"] == "user_grace" for p in res_parts_after.json())

    # Grace cannot join as participant anymore because she is now a judge
    res_rejoin = client.post("/api/events/evt_open_test/join", headers={"X-Session-Token": "tok_grace"})
    assert res_rejoin.status_code == 403
    db.close()


def test_unregister_participant_and_judge(client):
    db = TestingSessionLocal()
    # Create user_helen and user_ian
    helen = User(id="user_helen", email="helen@test.org", name="Helen", role=UserRole.USER.value, session_token="tok_helen")
    ian = User(id="user_ian", email="ian@test.org", name="Ian", role=UserRole.USER.value, session_token="tok_ian")
    db.add_all([helen, ian])
    db.commit()

    # 1. Helen joins evt_open_test as participant
    res_join = client.post("/api/events/evt_open_test/join", headers={"X-Session-Token": "tok_helen"})
    assert res_join.status_code == 201

    # Verify Helen is participant
    res_mem = client.get("/api/events/evt_open_test/my-membership", headers={"X-Session-Token": "tok_helen"})
    assert res_mem.status_code == 200
    assert res_mem.json()["role"] == "participant"

    # Helen unregisters as participant
    res_leave = client.post("/api/events/evt_open_test/leave", headers={"X-Session-Token": "tok_helen"})
    assert res_leave.status_code == 200
    assert "unregistered as participant" in res_leave.json()["message"].lower()

    # Helen is no longer a member
    res_mem_after = client.get("/api/events/evt_open_test/my-membership", headers={"X-Session-Token": "tok_helen"})
    assert res_mem_after.status_code == 200
    assert res_mem_after.json() is None

    # Leaving again returns 400
    res_leave_again = client.post("/api/events/evt_open_test/leave", headers={"X-Session-Token": "tok_helen"})
    assert res_leave_again.status_code == 400

    # 2. Ian is invited as judge to evt_open_test and accepts
    res_inv = client.post(
        "/api/events/evt_open_test/judges/invite",
        json={"user_id": "user_ian"},
        headers={"X-Session-Token": "tok_bob"},
    )
    assert res_inv.status_code == 201
    ian_inv_id = res_inv.json()["id"]

    res_accept = client.post(f"/api/invitations/{ian_inv_id}/accept", headers={"X-Session-Token": "tok_ian"})
    assert res_accept.status_code == 200

    # Verify Ian is judge
    res_ian_mem = client.get("/api/events/evt_open_test/my-membership", headers={"X-Session-Token": "tok_ian"})
    assert res_ian_mem.status_code == 200
    assert res_ian_mem.json()["role"] == "judge"

    # Ian steps down / unregisters as judge
    res_ian_leave = client.post("/api/events/evt_open_test/leave", headers={"X-Session-Token": "tok_ian"})
    assert res_ian_leave.status_code == 200
    assert "unregistered as judge" in res_ian_leave.json()["message"].lower()

    # Verify Ian is no longer listed in judges
    res_judges = client.get("/api/events/evt_open_test/judges", headers={"X-Session-Token": "tok_bob"})
    assert not any(j["user_id"] == "user_ian" for j in res_judges.json())

    # Verify Ian can now join as participant if he wishes (since he is no longer a judge)
    res_ian_join = client.post("/api/events/evt_open_test/join", headers={"X-Session-Token": "tok_ian"})
    assert res_ian_join.status_code == 201
    assert res_ian_join.json()["role"] == "participant"
    db.close()
