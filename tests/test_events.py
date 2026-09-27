"""Unit and API Integration Tests for DOGFOOD 2026 Events System."""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.database import Base, get_db
from src.main import app
from src.models.user import User, UserRole
from src.models.event import Event, Track
from src.seed import seed_fixtures
from src.services.event_service import EventService
from src.schemas.event import EventCreate

# Set up test database
TEST_DB_URL = "sqlite:///./test_portal.db"
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
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    # Seed standard test users
    users = [
        User(id="org_user", email="org@test.org", name="Org Admin", role=UserRole.ORGANIZER.value, session_token="org_token_123"),
        User(id="jdg_user", email="jdg@test.org", name="Judge Test", role=UserRole.JUDGE.value, session_token="jdg_token_456"),
        User(id="prt_user", email="prt@test.org", name="Part Test", role=UserRole.PARTICIPANT.value, session_token="prt_token_789"),
    ]
    for u in users:
        existing = db.query(User).filter(User.id == u.id).first()
        if not existing:
            db.add(u)
    db.commit()

    # Seed fixture event
    fixture_event = Event(
        id="evt_01",
        name="Sample Hack 2026",
        description="Official fixture hackathon",
        submissions_open=datetime(2026, 2, 27, 18, 0, 0, tzinfo=timezone.utc),
        submissions_close=datetime(2026, 3, 1, 18, 0, 0, tzinfo=timezone.utc),  # in the past
        is_active=True,
        created_by="org_user",
    )
    existing_evt = db.query(Event).filter(Event.id == "evt_01").first()
    if not existing_evt:
        db.add(fixture_event)
        for i in range(1, 9):
            track = Track(
                id=f"trk_{i:02d}",
                event_id="evt_01",
                name=f"Track {i}",
                description=f"Description for Track {i}",
            )
            db.add(track)
        db.commit()
    db.close()

    yield

    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client():
    return TestClient(app)


def test_public_event_discovery(client):
    """Ensure any stranger can browse the event list without credentials."""
    response = client.get("/api/events")
    assert response.status_code == 200
    data = response.json()
    assert "total_count" in data
    assert data["total_count"] >= 1
    event = next(e for e in data["items"] if e["id"] == "evt_01")
    assert event["name"] == "Sample Hack 2026"
    assert event["status"] == "closed"
    assert event["is_submission_open"] is False


def test_get_current_event(client):
    """Retrieve current active event."""
    response = client.get("/api/events/current")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "evt_01"
    assert len(data["tracks"]) == 8


def test_get_event_by_id(client):
    """Retrieve event details by ID with tracks."""
    response = client.get("/api/events/evt_01")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "evt_01"
    assert data["name"] == "Sample Hack 2026"
    assert data["track_count"] == 8


def test_event_status_and_deadline(client):
    """Check real-time status: closed fixture event has 0 remaining seconds."""
    response = client.get("/api/events/evt_01/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "closed"
    assert data["is_submission_open"] is False
    assert data["time_remaining_seconds"] == 0.0


def test_create_event_unauthorized(client):
    """Unauthenticated users cannot create events."""
    payload = {
        "name": "Unauthorized Hack",
        "submissions_close": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
    }
    response = client.post("/api/events", json=payload)
    assert response.status_code == 401


def test_create_event_forbidden_for_participant(client):
    """Participants cannot create events."""
    payload = {
        "name": "Participant Hack",
        "submissions_close": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
    }
    response = client.post(
        "/api/events",
        json=payload,
        cookies={"session": "prt_token_789"},
    )
    assert response.status_code == 403


def test_create_event_success_for_organizer(client):
    """Organizers can create events with custom tracks and deadlines."""
    now = datetime.now(timezone.utc)
    close_time = now + timedelta(days=3)
    payload = {
        "id": "evt_ai_hack",
        "name": "AI Innovation Sprint",
        "description": "Building next-gen AI applications.",
        "submissions_open": now.isoformat(),
        "submissions_close": close_time.isoformat(),
        "tracks": [
            {"id": "trk_genai", "name": "Generative AI", "description": "LLM and diffusion models"},
            {"id": "trk_agents", "name": "Autonomous Agents", "description": "Multi-agent workflows"},
        ],
    }
    response = client.post(
        "/api/events",
        json=payload,
        cookies={"session": "org_token_123"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == "evt_ai_hack"
    assert data["name"] == "AI Innovation Sprint"
    assert data["status"] == "open"
    assert data["is_submission_open"] is True
    assert data["track_count"] == 2


def test_update_event_deadline_and_status(client):
    """Updating deadline dynamically transitions status."""
    # Move deadline into the future
    future_deadline = datetime.now(timezone.utc) + timedelta(days=7)
    response = client.patch(
        "/api/events/evt_ai_hack/deadline",
        json={"submissions_close": future_deadline.isoformat()},
        cookies={"session": "org_token_123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_submission_open"] is True
    assert data["time_remaining_seconds"] > 0


def test_deadline_enforcement_logic():
    """EventService.check_submission_allowed raises HTTP 400 for closed events."""
    db = TestingSessionLocal()
    try:
        with pytest.raises(Exception) as exc_info:
            EventService.check_submission_allowed(db, "evt_01")
        assert "closed" in str(exc_info.value.detail).lower()
        assert exc_info.value.status_code == 400
    finally:
        db.close()


def test_filter_events_by_status(client):
    """List events filtered by status='closed'."""
    response = client.get("/api/events?status=closed")
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["status"] == "closed"


def test_track_management_endpoints(client):
    """Organizer can add track, public can view tracks."""
    # List tracks
    res_list = client.get("/api/events/evt_ai_hack/tracks")
    assert res_list.status_code == 200
    assert len(res_list.json()) >= 2

    # Add track as organizer
    track_payload = {"name": "Robotics", "description": "Physical computing"}
    res_add = client.post(
        "/api/events/evt_ai_hack/tracks",
        json=track_payload,
        cookies={"session": "org_token_123"},
    )
    assert res_add.status_code == 201
    assert res_add.json()["name"] == "Robotics"
