"""Seed script for DOGFOOD 2026 Hackathon Portal (T1 EVENTS subtask).

Loads fixtures.json, creates tables, seeds the hackathon event, tracks,
and test users with session tokens matching .dogfood.toml and spec.MD.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.database import SessionLocal, init_db
from src.models.user import User, UserRole
from src.models.event import Event, Track

logger = logging.getLogger(__name__)


def parse_iso_datetime(dt_str: str) -> datetime:
    """Safely parse an ISO 8601 UTC timestamp."""
    if not dt_str:
        return datetime.now(timezone.utc)
    if dt_str.endswith("Z"):
        dt_str = dt_str[:-1] + "+00:00"
    return datetime.fromisoformat(dt_str)


def seed_fixtures(fixture_path: str = "fixtures.json") -> None:
    """Seed database from fixtures.json."""
    init_db()
    db = SessionLocal()

    try:
        path = Path(fixture_path)
        if not path.exists():
            root_path = Path(__file__).resolve().parent.parent / "fixtures.json"
            if root_path.exists():
                path = root_path
            else:
                logger.error(f"Fixture file '{fixture_path}' not found.")
                return

        with open(path, "r", encoding="utf-8") as f:
            fixtures = json.load(f)

        # 1. Seed Users with session tokens matching .dogfood.toml
        users_to_seed = [
            User(
                id="usr_org",
                name="Organizer Admin",
                email="organizer@hackathon.org",
                role=UserRole.ORGANIZER.value,
                session_token="org_7f2a",
            ),
            User(
                id="jdg_01",
                name="Tomas Varga (Judge A)",
                email="tomas.varga@example.org",
                role=UserRole.JUDGE.value,
                session_token="jdg_a_91bc",
            ),
            User(
                id="jdg_02",
                name="Wei Lindqvist (Judge B)",
                email="wei.lindqvist@example.org",
                role=UserRole.JUDGE.value,
                session_token="jdg_b_44de",
            ),
            User(
                id="usr_prt",
                name="Ada Okonkwo (User)",
                email="ada@example.org",
                role=UserRole.USER.value,
                session_token="prt_2e88",
            ),
        ]

        for u in users_to_seed:
            existing = db.query(User).filter(User.id == u.id).first()
            if not existing:
                existing_email = db.query(User).filter(User.email == u.email).first()
                if existing_email:
                    existing_email.session_token = u.session_token
                    existing_email.role = u.role
                else:
                    db.add(u)
            else:
                existing.session_token = u.session_token
                existing.role = u.role

        db.commit()

        # 2. Seed Event
        event_data = fixtures.get("event", {})
        if event_data:
            event_id = event_data.get("id", "evt_01")
            close_time = parse_iso_datetime(event_data.get("submissions_close", "2026-03-01T18:00:00Z"))

            event = db.query(Event).filter(Event.id == event_id).first()
            if not event:
                event = Event(
                    id=event_id,
                    name=event_data.get("name", "Sample Hack 2026"),
                    description="Official DOGFOOD 2026 hackathon portal event.",
                    submissions_open=datetime(2026, 2, 27, 18, 0, 0, tzinfo=timezone.utc),
                    submissions_close=close_time,
                    is_active=True,
                    created_by="usr_org",
                )
                db.add(event)
            else:
                event.name = event_data.get("name", "Sample Hack 2026")
                event.submissions_close = close_time
                event.is_active = True

            db.commit()

            # 3. Seed Tracks
            tracks_data = fixtures.get("tracks", [])
            for t in tracks_data:
                track_id = t["id"]
                track = db.query(Track).filter(Track.id == track_id).first()
                if not track:
                    track = Track(
                        id=track_id,
                        event_id=event_id,
                        name=t["name"],
                        description=f"Track category for {t['name']}",
                    )
                    db.add(track)
                else:
                    track.name = t["name"]

            db.commit()

        logger.info(f"Database seeded successfully with event '{event_data.get('name', 'evt_01')}' and tracks.")
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed_fixtures()
