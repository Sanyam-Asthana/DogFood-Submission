"""Test suite directly validating DOGFOOD 2026 T1 Acceptance Criteria."""

import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.seed import seed_fixtures
from src.database import SessionLocal
from src.models.user import User, UserRole, EventMember, EventRole
from src.models.event import Event, Track
from src.models.project import Project, Team, TeamMember

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_fixtures():
    seed_fixtures()


def test_t1_gallery_is_public():
    """T1: Project gallery must be accessible without authentication and return 200."""
    response = client.get("/projects")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) > 0


def test_t1_project_from_fixtures_shown():
    """T1: Fixture project titles must appear in the gallery response."""
    response = client.get("/projects")
    assert response.status_code == 200
    text = response.text.lower()
    fixture_titles = ["glass signal", "small meadow", "deep compass"]
    assert any(title in text for title in fixture_titles)


def test_t1_closed_event_refuses_submissions():
    """T1: Late project submission to a closed event must be refused with 4xx error."""
    response = client.post(
        "/projects",
        headers={"Cookie": "session=prt_2e88"},
        json={
            "event_id": "evt_01",
            "title": "dogfood-late-submission-probe",
            "summary": "probe",
        },
    )
    assert 400 <= response.status_code < 500
    assert "closed" in response.text.lower()


def test_t1_team_formation_and_membership():
    """T1: Registered participants can form teams, list them, join, and leave."""
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:6]
    event_id = f"evt_team_{suffix}"
    alice_id = f"usr_alice_{suffix}"
    bob_id = f"usr_bob_{suffix}"
    tok_alice = f"tok_alice_{suffix}"
    tok_bob = f"tok_bob_{suffix}"

    # Create an open event
    open_event = Event(
        id=event_id,
        name=f"T1 Open Hack {suffix}",
        submissions_open=datetime.now(timezone.utc) - timedelta(hours=2),
        submissions_close=datetime.now(timezone.utc) + timedelta(hours=24),
        is_active=True,
    )
    db.add(open_event)

    # Create two participants
    alice = User(id=alice_id, name="Alice", email=f"alice_{suffix}@test.org", role=UserRole.USER.value, session_token=tok_alice)
    bob = User(id=bob_id, name="Bob", email=f"bob_{suffix}@test.org", role=UserRole.USER.value, session_token=tok_bob)
    db.add_all([alice, bob])
    db.commit()

    # Join both as participants
    db.add(EventMember(id=f"mem_alice_{suffix}", event_id=event_id, user_id=alice_id, role=EventRole.PARTICIPANT.value))
    db.add(EventMember(id=f"mem_bob_{suffix}", event_id=event_id, user_id=bob_id, role=EventRole.PARTICIPANT.value))
    db.commit()
    db.close()

    # 1. Alice forms a team
    res_create = client.post(
        f"/api/events/{event_id}/teams",
        headers={"X-Session-Token": tok_alice},
        json={"name": "CyberWizards"},
    )
    assert res_create.status_code == 201
    team = res_create.json()
    assert team["name"] == "CyberWizards"
    assert team["member_count"] == 1
    assert team["members"][0]["user_id"] == alice_id
    assert team["members"][0]["role"] == "lead"
    team_id = team["id"]

    # 2. List teams
    res_list = client.get(f"/api/events/{event_id}/teams")
    assert res_list.status_code == 200
    teams = res_list.json()
    assert any(t["id"] == team_id for t in teams)

    # 3. Bob joins Alice's team
    res_join = client.post(
        f"/api/teams/{team_id}/join",
        headers={"X-Session-Token": tok_bob},
    )
    assert res_join.status_code == 200
    updated_team = res_join.json()
    assert updated_team["member_count"] == 2
    assert any(m["user_id"] == bob_id and m["role"] == "member" for m in updated_team["members"])

    # 4. Bob leaves team
    res_leave = client.post(
        f"/api/teams/{team_id}/leave",
        headers={"X-Session-Token": tok_bob},
    )
    assert res_leave.status_code == 200
    assert res_leave.json().get("team_dissolved") is True

    # Verify team is dissolved and Alice becomes a normal single participant again
    res_get = client.get(f"/api/teams/{team_id}")
    assert res_get.status_code == 404


def test_t1_cannot_create_team_for_closed_event():
    """T1: Cannot form team for closed event."""
    res = client.post(
        "/api/events/evt_01/teams",
        headers={"Cookie": "session=prt_2e88"},
        json={"name": "LateTeam"},
    )
    assert 400 <= res.status_code < 500
    assert "closed" in res.text.lower()


def test_t1_edit_project_until_deadline_and_lock_after():
    """T1: Project author can edit submission before deadline; edits are refused after deadline."""
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:6]
    event_id = f"evt_edit_{suffix}"
    author_id = f"usr_auth_{suffix}"
    stranger_id = f"usr_str_{suffix}"
    tok_author = f"tok_auth_{suffix}"
    tok_stranger = f"tok_str_{suffix}"

    # Create an event that is open
    event_open = Event(
        id=event_id,
        name=f"Edit Test Hack {suffix}",
        submissions_open=datetime.now(timezone.utc) - timedelta(hours=1),
        submissions_close=datetime.now(timezone.utc) + timedelta(hours=5),
        is_active=True,
    )
    db.add(event_open)

    # Create author and stranger
    author = User(id=author_id, name="Author", email=f"auth_{suffix}@test.org", role=UserRole.USER.value, session_token=tok_author)
    stranger = User(id=stranger_id, name="Stranger", email=f"str_{suffix}@test.org", role=UserRole.USER.value, session_token=tok_stranger)
    db.add_all([author, stranger])
    db.commit()

    # Author joins event
    db.add(EventMember(id=f"mem_auth_{suffix}", event_id=event_id, user_id=author_id, role=EventRole.PARTICIPANT.value))
    db.commit()
    db.close()

    # 1. Author submits a project
    res_submit = client.post(
        "/api/projects",
        headers={"X-Session-Token": tok_author},
        json={
            "event_id": event_id,
            "title": "Initial Title",
            "summary": "Initial Summary",
            "repo_url": "https://github.com/test/repo",
        },
    )
    assert res_submit.status_code == 201
    proj_id = res_submit.json()["id"]

    # 2. Author edits project before deadline -> 200 OK
    res_edit = client.put(
        f"/api/projects/{proj_id}",
        headers={"X-Session-Token": tok_author},
        json={
            "title": "Updated Title v2",
            "summary": "Updated Summary v2",
        },
    )
    assert res_edit.status_code == 200
    assert res_edit.json()["title"] == "Updated Title v2"
    assert res_edit.json()["summary"] == "Updated Summary v2"

    # 3. Stranger tries to edit author's project -> 403 Forbidden
    res_stranger = client.put(
        f"/api/projects/{proj_id}",
        headers={"X-Session-Token": tok_stranger},
        json={"title": "Hacked Title"},
    )
    assert res_stranger.status_code == 403

    # 4. Now close the event deadline
    db = SessionLocal()
    ev = db.query(Event).filter(Event.id == event_id).first()
    ev.submissions_close = datetime.now(timezone.utc) - timedelta(minutes=10)
    db.commit()
    db.close()

    # 5. Author tries to edit after deadline -> 400 Bad Request
    res_late_edit = client.put(
        f"/api/projects/{proj_id}",
        headers={"X-Session-Token": tok_author},
        json={"title": "Late Edit Title"},
    )
    assert res_late_edit.status_code == 400
    assert "closed" in res_late_edit.text.lower()


def test_t1_solo_hackathon_disallows_teams():
    """T1: Events configured with max_team_size=1 disallow team formation, and max_team_size is immutable."""
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:6]
    event_id = f"evt_solo_{suffix}"
    user_id = f"usr_solo_{suffix}"
    token = f"tok_solo_{suffix}"

    solo_event = Event(
        id=event_id,
        name=f"Solo Hackathon {suffix}",
        submissions_open=datetime.now(timezone.utc) - timedelta(hours=1),
        submissions_close=datetime.now(timezone.utc) + timedelta(hours=24),
        max_team_size=1,
        is_active=True,
    )
    db.add(solo_event)

    user = User(id=user_id, name="SoloDev", email=f"solo_{suffix}@test.org", role=UserRole.USER.value, session_token=token)
    db.add(user)
    db.commit()

    db.add(EventMember(id=f"mem_solo_{suffix}", event_id=event_id, user_id=user_id, role=EventRole.PARTICIPANT.value))
    db.commit()
    db.close()

    # 1. Attempt to create a team for solo hackathon -> 400 Bad Request
    res = client.post(
        f"/api/events/{event_id}/teams",
        headers={"X-Session-Token": token},
        json={"name": "ForbiddenTeam"},
    )
    assert res.status_code == 400
    assert "solo" in res.text.lower() or "individual" in res.text.lower()

    # 2. Verify max_team_size cannot be updated via PATCH /api/events/{id}
    res_patch = client.patch(
        f"/api/events/{event_id}",
        headers={"Cookie": "session=org_58a1"},
        json={"max_team_size": 4},
    )
    if res_patch.status_code == 200:
        assert res_patch.json()["max_team_size"] == 1


def test_t1_team_invitation_flow():
    """T1: Full team invitation flow - invite teammate, list invitations, accept, decline, capacity enforcement."""
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:6]
    event_id = f"evt_invite_{suffix}"
    lead_id = f"usr_lead_{suffix}"
    charlie_id = f"usr_charlie_{suffix}"
    dave_id = f"usr_dave_{suffix}"
    extra_id = f"usr_extra_{suffix}"

    tok_lead = f"tok_lead_{suffix}"
    tok_charlie = f"tok_charlie_{suffix}"
    tok_dave = f"tok_dave_{suffix}"
    tok_extra = f"tok_extra_{suffix}"

    # Create team hackathon with max_team_size=3
    event = Event(
        id=event_id,
        name=f"Team Hack {suffix}",
        submissions_open=datetime.now(timezone.utc) - timedelta(hours=1),
        submissions_close=datetime.now(timezone.utc) + timedelta(hours=24),
        max_team_size=3,
        is_active=True,
    )
    db.add(event)

    lead = User(id=lead_id, name="Lead", email=f"lead_{suffix}@test.org", role=UserRole.USER.value, session_token=tok_lead)
    charlie = User(id=charlie_id, name="Charlie", email=f"charlie_{suffix}@test.org", role=UserRole.USER.value, session_token=tok_charlie)
    dave = User(id=dave_id, name="Dave", email=f"dave_{suffix}@test.org", role=UserRole.USER.value, session_token=tok_dave)
    extra = User(id=extra_id, name="Extra", email=f"extra_{suffix}@test.org", role=UserRole.USER.value, session_token=tok_extra)
    db.add_all([lead, charlie, dave, extra])
    db.commit()

    # Lead registers as participant
    db.add(EventMember(id=f"mem_lead_{suffix}", event_id=event_id, user_id=lead_id, role=EventRole.PARTICIPANT.value))
    db.commit()
    db.close()

    # 1. Lead creates a team
    res_team = client.post(
        f"/api/events/{event_id}/teams",
        headers={"X-Session-Token": tok_lead},
        json={"name": "RocketHacks"},
    )
    assert res_team.status_code == 201
    team_id = res_team.json()["id"]

    # 2. Lead invites Charlie and Dave by email
    res_inv = client.post(
        f"/api/teams/{team_id}/invite",
        headers={"X-Session-Token": tok_lead},
        json={"email": f"charlie_{suffix}@test.org"},
    )
    assert res_inv.status_code == 201
    inv_charlie_id = res_inv.json()["id"]

    res_inv2 = client.post(
        f"/api/teams/{team_id}/invite",
        headers={"X-Session-Token": tok_lead},
        json={"email": f"dave_{suffix}@test.org"},
    )
    assert res_inv2.status_code == 201
    inv_dave_id = res_inv2.json()["id"]

    # 3. Charlie and Dave accept -> team has 3 members (full)
    res_accept1 = client.post(
        f"/api/invitations/teams/{inv_charlie_id}/accept",
        headers={"X-Session-Token": tok_charlie},
    )
    assert res_accept1.status_code == 200

    res_accept2 = client.post(
        f"/api/invitations/teams/{inv_dave_id}/accept",
        headers={"X-Session-Token": tok_dave},
    )
    assert res_accept2.status_code == 200

    res_team_info = client.get(f"/api/teams/{team_id}")
    assert res_team_info.status_code == 200
    assert res_team_info.json()["member_count"] == 3

    # 4. Lead tries to invite extra user to full team -> 400 Bad Request (capacity reached)
    res_overflow = client.post(
        f"/api/teams/{team_id}/invite",
        headers={"X-Session-Token": tok_lead},
        json={"email": f"extra_{suffix}@test.org"},
    )
    assert res_overflow.status_code == 400

    # 5. Charlie leaves team -> 2 members remain (Lead and Dave), team remains intact
    res_leave1 = client.post(
        f"/api/teams/{team_id}/leave",
        headers={"X-Session-Token": tok_charlie},
    )
    assert res_leave1.status_code == 200
    assert res_leave1.json().get("team_dissolved") is False

    # Lead invites Extra -> Extra declines
    res_inv_extra = client.post(
        f"/api/teams/{team_id}/invite",
        headers={"X-Session-Token": tok_lead},
        json={"email": f"extra_{suffix}@test.org"},
    )
    assert res_inv_extra.status_code == 201
    inv_extra_id = res_inv_extra.json()["id"]

    res_decline = client.post(
        f"/api/invitations/teams/{inv_extra_id}/decline",
        headers={"X-Session-Token": tok_extra},
    )
    assert res_decline.status_code == 200
    assert res_decline.json()["status"] == "declined"

    # Lead invites Extra again, then cancels it
    res_inv_cancel = client.post(
        f"/api/teams/{team_id}/invite",
        headers={"X-Session-Token": tok_lead},
        json={"email": f"extra_{suffix}@test.org"},
    )
    assert res_inv_cancel.status_code == 201
    cancel_id = res_inv_cancel.json()["id"]

    res_cancel_action = client.post(
        f"/api/invitations/teams/{cancel_id}/cancel",
        headers={"X-Session-Token": tok_lead},
    )
    assert res_cancel_action.status_code == 200
    assert res_cancel_action.json()["status"] == "declined"

    # 6. Dave leaves team -> only 1 member (Lead) remains!
    # Under rule: "If only one member remains they become a normal single participant again."
    res_leave2 = client.post(
        f"/api/teams/{team_id}/leave",
        headers={"X-Session-Token": tok_dave},
    )
    assert res_leave2.status_code == 200
    assert res_leave2.json().get("team_dissolved") is True

    # Verify team_id is dissolved
    res_team_gone = client.get(f"/api/teams/{team_id}")
    assert res_team_gone.status_code == 404

    # 7. Test Dissolve Team: Lead forms a new team, invites Dave, then Lead dissolves it
    res_new_team = client.post(
        f"/api/events/{event_id}/teams",
        headers={"X-Session-Token": tok_lead},
        json={"name": "TempTeam"},
    )
    assert res_new_team.status_code == 201
    new_team_id = res_new_team.json()["id"]

    res_inv_d = client.post(
        f"/api/teams/{new_team_id}/invite",
        headers={"X-Session-Token": tok_lead},
        json={"email": f"dave_{suffix}@test.org"},
    )
    assert res_inv_d.status_code == 201
    client.post(
        f"/api/invitations/teams/{res_inv_d.json()['id']}/accept",
        headers={"X-Session-Token": tok_dave},
    )

    # Lead dissolves team
    res_dissolve = client.post(
        f"/api/teams/{new_team_id}/dissolve",
        headers={"X-Session-Token": tok_lead},
    )
    assert res_dissolve.status_code == 200
    assert "dissolved" in res_dissolve.json()["message"].lower()

    # Verify both Lead and Dave are now solo participants
    res_team_dissolved = client.get(f"/api/teams/{new_team_id}")
    assert res_team_dissolved.status_code == 404

    # 8. Organizer inspects event participants -> all are solo
    res_parts = client.get(
        f"/api/events/{event_id}/participants",
        headers={"Cookie": "session=org_7f2a"},
    )
    assert res_parts.status_code == 200
    parts_list = res_parts.json()
    assert len(parts_list) >= 3
    assert all(p["team_id"] is None for p in parts_list)



