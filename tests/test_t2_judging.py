"""Pytest Suite for DOGFOOD 2026 Tier 2 (T2 Judging & Evaluation).

Rigorous verification of:
1. Judge reading own scores (200 OK)
2. Judge peer score isolation: Judge B querying Judge A (403 Forbidden)
3. Participant blocked from judge scores (403 Forbidden)
4. Unauthenticated blocked (401 Unauthorized)
5. Organizer viewing judge scores (200 OK)
6. Judge submitting project evaluations with validation
7. Judge assigned projects queue
8. Rubric criteria and weight updates by organizer
9. Organizer judging progress & Z-score normalized metrics
10. CSV export permissions and formatting
"""

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.database import SessionLocal, init_db
from src.seed import seed_fixtures
from src.models.user import User, UserRole
from src.models.event import Event
from src.models.project import Project
from src.models.judging import Score


@pytest.fixture(scope="module", autouse=True)
def setup_test_data():
    """Initialize DB and seed fixtures before running T2 tests."""
    init_db()
    seed_fixtures()


@pytest.fixture
def client():
    return TestClient(app)


def test_judge_sees_own_scores(client):
    """T2 Check 1: A judge can read their own scores."""
    headers = {"Cookie": "session=jdg_a_91bc"}
    response = client.get("/api/judge/scores", headers=headers)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    # Verify scores belong to jdg_01
    for s in data:
        assert s["judge_id"] == "jdg_01"


def test_judge_peer_isolation_forbidden(client):
    """T2 Check 2: A judge cannot read another judge's scores."""
    headers = {"Cookie": "session=jdg_b_44de"}

    # Probe 1: Querying via alias 'judge_a'
    response = client.get("/api/judge/scores?judge=judge_a", headers=headers)
    assert response.status_code in (401, 403), f"Expected 401/403, got {response.status_code}"

    # Probe 2: Querying via ID 'jdg_01'
    response = client.get("/api/judge/scores?judge=jdg_01", headers=headers)
    assert response.status_code in (401, 403), f"Expected 401/403, got {response.status_code}"


def test_participant_blocked_from_judge_scores(client):
    """T2 Check 3: A participant is not a judge and cannot access judging scores."""
    headers = {"Cookie": "session=prt_2e88"}
    response = client.get("/api/judge/scores", headers=headers)
    assert response.status_code in (401, 403), f"Expected 401/403, got {response.status_code}"


def test_unauthenticated_blocked_from_judge_scores(client):
    """Unauthenticated visitor is rejected when accessing judging scores."""
    response = client.get("/api/judge/scores")
    assert response.status_code == 401


def test_organizer_can_view_judge_scores(client):
    """Organizers have administrative visibility to inspect judge evaluations."""
    headers = {"Cookie": "session=org_7f2a"}
    # Organizer queries Judge A's scores
    response = client.get("/api/judge/scores?judge=judge_a", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_judge_submit_score_flow(client):
    """Judge submits evaluation for a project."""
    headers = {"Cookie": "session=jdg_a_91bc"}

    # Valid score submission
    payload = {
        "project_id": "prj_02",
        "criteria": {
            "functionality": 4.5,
            "quality": 4.0,
            "innovation": 5.0,
        },
        "comment": "Exceptional implementation and clear documentation.",
    }
    response = client.post("/api/judge/scores", json=payload, headers=headers)
    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
    data = response.json()
    assert data["project_id"] == "prj_02"
    assert data["judge_id"] == "jdg_01"
    assert data["criteria"]["functionality"] == 4.5

    # Invalid score (rating out of bounds > 5.0)
    invalid_payload = {
        "project_id": "prj_02",
        "criteria": {"functionality": 7.0},
    }
    res_err = client.post("/api/judge/scores", json=invalid_payload, headers=headers)
    assert res_err.status_code == 400


def test_judge_assignments_queue(client):
    """Judge retrieves queue of assigned projects."""
    headers = {"Cookie": "session=jdg_a_91bc"}
    response = client.get("/api/judge/assignments?event_id=evt_01", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    first = data[0]
    assert "project_id" in first
    assert "title" in first
    assert "evaluated" in first


def test_rubric_criteria_management(client):
    """Organizers can configure rubric criteria weights; participants are blocked."""
    org_headers = {"Cookie": "session=org_7f2a"}
    prt_headers = {"Cookie": "session=prt_2e88"}

    # 1. Fetch rubric
    res_get = client.get("/api/events/evt_01/rubric")
    assert res_get.status_code == 200
    rubric = res_get.json()
    assert len(rubric) >= 3

    # 2. Update rubric as organizer
    update_payload = {
        "criteria": [
            {"name": "functionality", "weight": 0.5, "description": "Working software"},
            {"name": "quality", "weight": 0.3, "description": "Code quality"},
            {"name": "innovation", "weight": 0.2, "description": "Novelty"},
        ]
    }
    res_update = client.put("/api/events/evt_01/rubric", json=update_payload, headers=org_headers)
    assert res_update.status_code == 200
    updated = res_update.json()
    crit_map = {c["name"]: c["weight"] for c in updated}
    assert crit_map["functionality"] == 0.5

    # 3. Participant forbidden from updating rubric
    res_prt = client.put("/api/events/evt_01/rubric", json=update_payload, headers=prt_headers)
    assert res_prt.status_code == 403


def test_organizer_judging_progress(client):
    """Organizer monitors judging review metrics and normalized scores."""
    org_headers = {"Cookie": "session=org_7f2a"}
    response = client.get("/api/events/evt_01/judging/progress", headers=org_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["event_id"] == "evt_01"
    assert data["total_projects"] >= 1
    assert data["total_scores"] >= 100
    assert len(data["projects"]) > 0
    # Projects have normalized scores calculated
    top_project = data["projects"][0]
    assert "project_id" in top_project
    assert "normalized_score" in top_project


def test_csv_export_works_and_restricted(client):
    """T2 Check 4: Organizer can export CSV; participants and judges are rejected."""
    org_headers = {"Cookie": "session=org_7f2a"}
    prt_headers = {"Cookie": "session=prt_2e88"}
    jdg_headers = {"Cookie": "session=jdg_a_91bc"}

    # 1. Organizer export succeeds
    res_org = client.get("/api/export.csv", headers=org_headers)
    assert res_org.status_code == 200
    assert "text/csv" in res_org.headers.get("content-type", "")
    csv_text = res_org.text
    first_line = csv_text.splitlines()[0] if csv_text.splitlines() else ""
    assert "," in first_line
    assert "project_id" in first_line
    assert len(csv_text.splitlines()) > 5

    # 2. Participant blocked
    res_prt = client.get("/api/export.csv", headers=prt_headers)
    assert res_prt.status_code in (401, 403)

    # 3. Judge blocked
    res_jdg = client.get("/api/export.csv", headers=jdg_headers)
    assert res_jdg.status_code in (401, 403)
