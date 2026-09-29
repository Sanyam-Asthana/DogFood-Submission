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
from src.models.user import User, UserRole, EventMember, EventRole
from src.models.event import Event, Track
from src.models.project import Project, Team, TeamMember, TeamMemberRole
from src.models.judging import Score, RubricCriterion, JudgeTrackAssignment


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

            # 4. Link fixture judges and participants to event
            judges_data = fixtures.get("judges", [])
            for j in judges_data:
                j_id = j["id"]
                j_name = j.get("name", f"Judge {j_id}")
                j_email = j.get("email", f"{j_id}@example.org")
                j_tracks = j.get("tracks", [])

                # Map specific session tokens for judge_a and judge_b
                session_tok = "jdg_a_91bc" if j_id == "jdg_01" else ("jdg_b_44de" if j_id == "jdg_02" else f"usr_{j_id}")

                u = db.query(User).filter(User.id == j_id).first()
                if not u:
                    u = User(
                        id=j_id,
                        name=j_name,
                        email=j_email,
                        role=UserRole.JUDGE.value,
                        session_token=session_tok,
                    )
                    db.add(u)
                else:
                    u.role = UserRole.JUDGE.value
                    if session_tok:
                        u.session_token = session_tok

                mem = db.query(EventMember).filter(
                    EventMember.event_id == event_id,
                    EventMember.user_id == j_id,
                ).first()
                if not mem:
                    db.add(EventMember(id=f"mem_{j_id}", event_id=event_id, user_id=j_id, role=EventRole.JUDGE.value))
                else:
                    mem.role = EventRole.JUDGE.value

                # Assign judge to tracks
                for trk_id in j_tracks:
                    existing_assign = db.query(JudgeTrackAssignment).filter(
                        JudgeTrackAssignment.judge_id == j_id,
                        JudgeTrackAssignment.track_id == trk_id,
                    ).first()
                    if not existing_assign:
                        db.add(
                            JudgeTrackAssignment(
                                id=f"jta_{j_id}_{trk_id}",
                                event_id=event_id,
                                judge_id=j_id,
                                track_id=trk_id,
                            )
                        )

            # Ensure usr_prt is participant
            existing_prt = db.query(EventMember).filter(
                EventMember.event_id == event_id,
                EventMember.user_id == "usr_prt",
            ).first()
            if not existing_prt:
                db.add(EventMember(id="mem_usr_prt", event_id=event_id, user_id="usr_prt", role=EventRole.PARTICIPANT.value))

            db.commit()

            # 5. Seed Teams and Team Members
            teams_data = fixtures.get("teams", [])
            for tm in teams_data:
                team_id = tm["id"]
                team = db.query(Team).filter(Team.id == team_id).first()
                if not team:
                    team = Team(
                        id=team_id,
                        event_id=event_id,
                        name=tm.get("name", team_id),
                    )
                    db.add(team)
                else:
                    team.name = tm.get("name", team_id)
                db.commit()

                for idx, email in enumerate(tm.get("members", [])):
                    member_user = db.query(User).filter(User.email == email).first()
                    if member_user:
                        existing_tm = db.query(TeamMember).filter(
                            TeamMember.team_id == team_id,
                            TeamMember.user_id == member_user.id,
                        ).first()
                        if not existing_tm:
                            db.add(
                                TeamMember(
                                    id=f"tmem_{team_id}_{member_user.id}",
                                    team_id=team_id,
                                    user_id=member_user.id,
                                    role=TeamMemberRole.LEAD.value if idx == 0 else TeamMemberRole.MEMBER.value,
                                )
                            )
            db.commit()

            # 6. Seed Projects
            projects_data = fixtures.get("projects", [])
            for p in projects_data:
                proj_id = p["id"]
                proj = db.query(Project).filter(Project.id == proj_id).first()
                sub_at = parse_iso_datetime(p.get("submitted_at"))
                if not proj:
                    proj = Project(
                        id=proj_id,
                        event_id=event_id,
                        team_id=p.get("team"),
                        track_id=p.get("track"),
                        title=p.get("title", "Untitled Project"),
                        summary=p.get("summary", ""),
                        repo_url=p.get("repo_url", ""),
                        submitted_at=sub_at,
                        created_by="usr_prt",
                    )
                    db.add(proj)
                else:
                    proj.title = p.get("title", proj.title)
                    proj.summary = p.get("summary", proj.summary)
                    proj.repo_url = p.get("repo_url", proj.repo_url)
            db.commit()

            # 7. Seed Rubric Criteria
            default_rubrics = [
                ("functionality", 0.4, "System functions correctly according to specification."),
                ("quality", 0.3, "Code structure, reliability, and clean execution."),
                ("innovation", 0.3, "Novelty, elegance, and creative design."),
            ]
            for r_name, r_weight, r_desc in default_rubrics:
                existing_crit = db.query(RubricCriterion).filter(
                    RubricCriterion.event_id == event_id,
                    RubricCriterion.name == r_name,
                ).first()
                if not existing_crit:
                    db.add(
                        RubricCriterion(
                            id=f"crit_{event_id}_{r_name}",
                            event_id=event_id,
                            name=r_name,
                            weight=r_weight,
                            description=r_desc,
                        )
                    )
            db.commit()

            # 8. Seed Scores
            scores_data = fixtures.get("scores", [])
            for s in scores_data:
                s_judge = s["judge"]
                s_proj = s["project"]
                s_crit = s.get("criteria", {})
                s_comment = s.get("comment", "")

                existing_score = db.query(Score).filter(
                    Score.project_id == s_proj,
                    Score.judge_id == s_judge,
                ).first()
                if not existing_score:
                    db.add(
                        Score(
                            id=f"scr_{s_judge}_{s_proj}",
                            event_id=event_id,
                            project_id=s_proj,
                            judge_id=s_judge,
                            criteria=s_crit,
                            comment=s_comment,
                        )
                    )
                else:
                    existing_score.criteria = s_crit
                    existing_score.comment = s_comment
            db.commit()

        logger.info(
            f"Database seeded successfully with event '{event_data.get('name', 'evt_01')}', tracks, {len(judges_data)} judges, "
            f"teams, {len(fixtures.get('projects', []))} projects, and {len(fixtures.get('scores', []))} scores."
        )
    finally:
        db.close()



if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed_fixtures()
