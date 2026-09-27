"""Test suite directly validating DOGFOOD 2026 T1 Acceptance Criteria."""

import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.seed import seed_fixtures

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
