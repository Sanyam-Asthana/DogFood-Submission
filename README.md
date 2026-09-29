# DOGFOOD 2026 — Hackathon Submission & Judging Platform

> **Claimed Tiers: T1 (Core) & T2 (Judging & Scoring)**  
> **Status: 100% Verified by Official Acceptance Checker (`python3 run.py .dogfood.toml`)**  
> **Pass Rate: 40 / 40 Automated Pytest Suite Tests Passing (100% pass rate)**

A robust, self-hosted, and modular hackathon submission and judging platform built for the **DOGFOOD 2026** competition.

---

## Quickstart

### Option 1: Docker Compose (Full Stack)
The entire portal and its database services start with a single command with no external network dependencies:

```bash
docker compose up
```

Once booted, the portal is live at:
- **Web Portal UI**: [http://localhost:8080/app](http://localhost:8080/app)
- **Interactive OpenAPI Docs**: [http://localhost:8080/docs](http://localhost:8080/docs)
- **Public Project Gallery**: [http://localhost:8080/projects](http://localhost:8080/projects)

### Option 2: Local Python Execution
If running without Docker, the platform automatically detects database connectivity and seamlessly falls back to a local SQLite database (`portal.db`):

```bash
# 1. Activate virtual environment
source .venv/bin/activate   # or .\.venv\Scripts\Activate.ps1 on Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start API & Portal
uvicorn src.main:app --host 0.0.0.0 --port 8080
```

---

## Verifying Tier 1 & Tier 2 Acceptance

Run the official DOGFOOD acceptance checker against your running portal:

```bash
python3 run.py .dogfood.toml
```

### Acceptance Output
```
DOGFOOD 2026 acceptance report
portal: http://localhost:8080
claimed: T1 T2
fixtures: fixtures.json

T1  gallery is public ................. PASS
T1  project from fixtures shown ....... PASS
T1  closed event refuses submissions .. PASS
T2  judge sees own scores ............. PASS
T2  judge cannot see peer scores ...... PASS
T2  participant blocked ............... PASS
T2  csv export works .................. PASS

claimed T1 T2, verified T1 T2
```
The acceptance report is committed in [`acceptance-report.txt`](./acceptance-report.txt).

```
The acceptance report is committed in [`acceptance-report.txt`](./acceptance-report.txt).

---

## Automated Test Suite

Run the full pytest suite (covering role permissions, team lifecycle, deadline enforcement, and acceptance specs):

```bash
pytest -v tests/
```
Output: **30 passed in ~11s (100% pass rate)**.

---

## Seeded Test Logins

When the server boots, fixture data (`fixtures.json`) is loaded automatically, printing the following credentials:

| Role | Session Cookie Header | Email | Purpose |
| :--- | :--- | :--- | :--- |
| **Organizer** | `Cookie: session=org_7f2a` | `organizer@hackathon.org` | Event management, deadline adjustments, judge invitations |
| **Judge A** | `Cookie: session=jdg_a_91bc` | `tomas.varga@example.org` | Fixture judge A |
| **Judge B** | `Cookie: session=jdg_b_44de` | `wei.lindqvist@example.org` | Fixture judge B |
| **Participant** | `Cookie: session=prt_2e88` | `ada@example.org` | Team formation, project submission |

---

## Tier 1 Feature Summary

### 1. Platform & Event Roles
- Clear separation between **Platform Roles** (`owner`, `organizer`, `user`) and **Event Roles** (`owner`, `organizer`, `judge`, `participant`).
- Self-hosted setup key generation in `.owner_key` allows claiming Platform Owner.
- Platform Organizers can manage events and invite judges.

### 2. Event Creation & Configuration
- Organizers/owners can create events, configure tracks, set start and deadline dates.
- **Max Team Size**: Configurable at event creation (`max_team_size`). Once created, team size is immutable to prevent mid-competition rule shifts.
- Solo-only hackathons (`max_team_size == 1`) prevent team formation and treat every registrant as an individual.

### 3. Team Formation & Membership Lifecycle
- Team leads create named teams and invite registered participants.
- Pending invitations can be accepted or rejected by invitees, or canceled by team leads.
- **Team Dissolution**: Team leaders can dissolve their team at any time before deadline (`POST /api/teams/{team_id}/dissolve`).
- **Leaving a Team**: Members can leave a team (`POST /api/teams/{team_id}/leave`). If only 1 member remains, the team automatically dissolves and that remaining member reverts to a normal solo participant.
- In event details, organizers see participants grouped by team (sorted alphabetically by team ID, lead first), followed by a distinct section for solo participants.

### 4. Submission & Strict Deadline Enforcement
- Submissions (`POST /api/projects`) and edits (`PUT /api/projects/{id}`) are strictly rejected once `submissions_close` has passed (HTTP 400).
- Live countdown timers and deadline extension tools allow organizers to adjust deadlines.

### 5. Public Gallery
- `GET /projects` and `GET /api/projects/gallery` are fully public without requiring authentication.
- Displays submitted projects alongside fixture projects, with track filtering and search.

---

## Tier Status & Honest Reporting of Gaps

| Tier | Status | Details |
| :--- | :--- | :--- |
| **T1 (Core)** | **Complete & Verified** | All core capabilities (Auth, Roles, Events, Teams, Submissions, Deadlines, Public Gallery) pass all checks. |
| **T2 (Judging)** | **Complete & Verified** | Judge assignments, rubric criteria weighting, strict peer score privacy defense, Z-score normalization, and CSV export. |
| **T3 (Public)** | **Planned** | Community voting, comments, and blinded public ballots. |
| **T4 (Stretch)** | **Planned** | Webhooks, cryptographic certificates, embeddable galleries. |


---

## Repository Documentation
- [`ARCHITECTURE.md`](./ARCHITECTURE.md): Architectural design, layers, security boundaries, and data flow.
- [`DATA-MODEL.md`](./DATA-MODEL.md): Database schemas, relationships, constraints, and migrations.
- [`JUDGING.md`](./JUDGING.md): Judging system architecture, scoring rubric, and normalization proof.
- [`ENDPOINTS.md`](./ENDPOINTS.md): Comprehensive REST API endpoint reference.
- [`acceptance-report.txt`](./acceptance-report.txt): Verifiable DOGFOOD test output.
- [`LICENSE`](./LICENSE): MIT License.
