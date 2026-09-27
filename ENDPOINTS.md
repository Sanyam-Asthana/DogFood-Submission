# DOGFOOD 2026 API Reference

This document provides a comprehensive, production-grade guide to all API endpoints available in the DOGFOOD 2026 Hackathon Platform.

---

## 1. Architecture: Platform Roles vs Event Roles

The platform strictly differentiates between **Platform-level accounts** and **Event-specific participation**:

### Platform Roles (Site-Wide)
- **`owner`**: Platform superuser. Can promote users to `organizer` and demote organizers to `user`. Claimed via secret setup key (`.owner_key`) on server startup. If an owner claims the key, all prior participant and judge memberships across all events are revoked.
- **`organizer`**: Can create events, modify event details and submission deadlines, manage tracks, invite users to judge events, and view event member rosters. Organizers cannot participate or submit to events.
- **`user`**: Standard platform account. Users can browse public galleries and events, join open events as participants, and accept invitations to judge events.

### Event Roles (Per-Event Scope)
- **`participant`**: A platform `user` registered for a specific hackathon event. Can form teams and submit projects before the deadline. (Owners and Organizers cannot participate).
- **`judge`**: A platform `user` invited by an organizer/owner who has accepted the judge invitation for that specific event. If a participant becomes a judge for an event, their participant status in that event is automatically revoked.

### Authentication Headers & Tokens
Endpoints accept credentials through any of the following mechanisms (in order of priority):
1. **HTTP Header `X-Session-Token: <token>`** (Used by script automation and automated test suites)
2. **HTTP Header `Authorization: Bearer <token>`** (Standard Bearer authentication)
3. **HTTP Cookie `session=<token>`** (Ambient cookie set upon browser login)

Pre-seeded fixtures provide the following test session tokens:
- **Organizer**: `session=org_7f2a`
- **Judge A**: `session=jdg_a_91bc`
- **Judge B**: `session=jdg_b_44de`
- **Participant**: `session=prt_2e88`

---

## 2. Health & System Endpoints

### `GET /`
- **Summary**: API Root & Service Info
- **Auth**: None (Public)
- **Response `200 OK`**:
  ```json
  {
    "portal": "DOGFOOD Hackathon Portal API",
    "version": "1.0.0",
    "status": "operational",
    "documentation": "/docs",
    "redoc": "/redoc",
    "api_prefix": "/api"
  }
  ```

### `GET /health`
- **Summary**: Liveness Health Probe
- **Auth**: None (Public)
- **Response `200 OK`**: `{"status": "ok"}`

### `GET /app` (or `/portal`)
- **Summary**: Interactive Testing Studio / Single Page Application
- **Auth**: None (Public)
- **Response `200 OK`**: Serves the frontend simulation interface.

---

## 3. Platform Administration & Role Delegation

### `POST /api/platform/claim-owner`
- **Summary**: Claim Platform Ownership
- **Auth**: Authenticated User
- **Description**: Promotes the authenticated user to `owner` if the provided setup key matches the one generated on startup. Automatically revokes any event-specific participant and judge roles the user currently holds.
- **Request Body**:
  ```json
  {
    "setup_key": "string"
  }
  ```
- **Response `200 OK`**: Updated user profile with `role: "owner"`.

### `GET /api/platform/users`
- **Summary**: Master List of Platform Users
- **Auth**: `organizer` or `owner`
- **Description**: Lists all registered platform accounts with their site role (`owner`, `organizer`, `user`).
- **Response `200 OK`**:
  ```json
  [
    {
      "id": "usr_123",
      "email": "user@example.com",
      "name": "Jane Doe",
      "role": "user",
      "created_at": "2026-02-27T10:00:00Z"
    }
  ]
  ```

### `POST /api/platform/promote-organizer`
- **Summary**: Promote User to Organizer
- **Auth**: `owner` only
- **Request Body**: Specify `user_id` or `email`:
  ```json
  {
    "user_id": "usr_123",
    "email": null
  }
  ```
- **Response `200 OK`**: Updated user profile with `role: "organizer"`.

### `POST /api/platform/demote-organizer`
- **Summary**: Demote Organizer to User
- **Auth**: `owner` only
- **Request Body**: Specify `user_id` or `email`:
  ```json
  {
    "user_id": "usr_123",
    "email": null
  }
  ```
- **Response `200 OK`**: Updated user profile with `role: "user"`.

---

## 4. Authentication Endpoints

### `POST /api/auth/register` (also `/auth/register`)
- **Summary**: Register New Account
- **Auth**: None (Public)
- **Request Body**:
  ```json
  {
    "email": "user@example.com",
    "password": "SecretPassword123!",
    "name": "Jane Doe",
    "role": "user"
  }
  ```
- **Response `201 Created`**: User profile object with `access_token` and `session_token`.

### `POST /api/auth/login` (also `/auth/login`)
- **Summary**: User Login
- **Auth**: None (Public)
- **Request Body**:
  ```json
  {
    "email": "user@example.com",
    "password": "SecretPassword123!"
  }
  ```
- **Response `200 OK`**: Returns access token and sets `session` cookie.

### `POST /api/auth/logout` (also `/auth/logout`)
- **Summary**: User Logout
- **Auth**: None / Authenticated User
- **Response `200 OK`**: `{"message": "Logged out successfully"}`

### `GET /api/auth/me` (also `/auth/me`)
- **Summary**: Current Authenticated Profile
- **Auth**: Authenticated User
- **Response `200 OK`**: Authenticated user's profile and site role.

---

## 5. Events Management & Deadlines

### `GET /api/events` (also `/events`)
- **Summary**: Discover Events (Public Catalog)
- **Auth**: None (Public)
- **Query Parameters**:
  - `status`: Filter by `open`, `closed`, `upcoming`, `archived`
  - `search`: Case-insensitive name search
  - `skip`: Pagination offset (default: 0)
  - `limit`: Pagination limit (default: 50)
- **Response `200 OK`**:
  ```json
  {
    "total_count": 1,
    "items": [
      {
        "id": "evt_01",
        "name": "Sample Hack 2026",
        "description": "Official DOGFOOD 2026 hackathon portal event.",
        "submissions_open": "2026-02-27T18:00:00Z",
        "submissions_close": "2026-03-01T18:00:00Z",
        "is_active": true,
        "status": "closed",
        "is_submission_open": false,
        "time_remaining_seconds": 0,
        "track_count": 8,
        "tracks": [...],
        "created_by": "usr_org",
        "created_at": "2026-02-27T18:00:00Z",
        "updated_at": "2026-02-27T18:00:00Z"
      }
    ]
  }
  ```

### `GET /api/events/current`
- **Summary**: Primary Active Hackathon Event
- **Auth**: None (Public)
- **Response `200 OK`**: Single `EventResponse` object.

### `POST /api/events`
- **Summary**: Create Event
- **Auth**: `organizer` or `owner`
- **Request Body**:
  ```json
  {
    "name": "Spring Hackathon 2026",
    "description": "Global developer challenge",
    "submissions_open": "2026-03-15T00:00:00Z",
    "submissions_close": "2026-03-17T23:59:59Z",
    "is_active": true,
    "tracks": [
      { "name": "AI Agents", "description": "Agentic workflows" }
    ]
  }
  ```
- **Response `201 Created`**: Single `EventResponse` object.

### `GET /api/events/{event_id}`
- **Summary**: Event Details by ID
- **Auth**: None (Public)
- **Response `200 OK`**: Detailed `EventResponse`.

### `PUT /api/events/{event_id}`
- **Summary**: Update Event
- **Auth**: `organizer` or `owner`
- **Response `200 OK`**: Updated `EventResponse`.

### `PATCH /api/events/{event_id}/deadline`
- **Summary**: Adjust Submission Deadline
- **Auth**: `organizer` or `owner`
- **Request Body**:
  ```json
  {
    "submissions_close": "2026-03-20T18:00:00Z"
  }
  ```
- **Response `200 OK`**: Updated `EventResponse`.

### `GET /api/events/{event_id}/status`
- **Summary**: Real-Time Submission Status & Countdown
- **Auth**: None (Public)
- **Response `200 OK`**:
  ```json
  {
    "event_id": "evt_01",
    "name": "Sample Hack 2026",
    "status": "closed",
    "is_submission_open": false,
    "submissions_close": "2026-03-01T18:00:00Z",
    "submissions_open": "2026-02-27T18:00:00Z",
    "time_remaining_seconds": 0,
    "server_time_utc": "2026-09-28T00:00:00Z"
  }
  ```

---

## 6. Event Participation & Membership Management

### `POST /api/events/{event_id}/join`
- **Summary**: Join Event as Participant
- **Auth**: Authenticated `user` (Owners and Organizers cannot join as participants)
- **Restrictions**: Fails with `400 Bad Request` if the event submission deadline has already passed.
- **Response `201 Created`**: Single `EventMemberResponse` with `role: "participant"`.

### `POST /api/events/{event_id}/leave` (also `/unregister`)
- **Summary**: Unregister from Event
- **Auth**: Authenticated User
- **Description**: Allows a registered participant to unregister, or a judge to step down from judging the event.
- **Response `200 OK`**: `{"message": "Successfully left event.", "event_id": "evt_01"}`

### `GET /api/events/{event_id}/my-membership`
- **Summary**: Check Caller's Event Role
- **Auth**: Authenticated User
- **Response `200 OK`**:
  ```json
  {
    "is_member": true,
    "role": "participant",
    "membership": {
      "id": "mem_123",
      "event_id": "evt_01",
      "user_id": "usr_prt",
      "role": "participant"
    }
  }
  ```

### `GET /api/events/{event_id}/participants`
- **Summary**: List Registered Participants
- **Auth**: `organizer` or `owner` only (`403 Forbidden` for participants, judges, and strangers)
- **Response `200 OK`**: Array of `EventMemberResponse` with `role: "participant"`.

### `GET /api/events/{event_id}/judges`
- **Summary**: List Confirmed Judges
- **Auth**: `organizer` or `owner` only (`403 Forbidden` for participants, judges, and strangers)
- **Response `200 OK`**: Array of `EventMemberResponse` with `role: "judge"`.

### `GET /api/events/{event_id}/judges/invitations`
- **Summary**: List Pending & Past Judge Invitations
- **Auth**: `organizer` or `owner` only (`403 Forbidden` for non-organizers)
- **Response `200 OK`**: Array of `JudgeInvitationResponse`.

---

## 7. Judge Invitations Workflow

### `POST /api/events/{event_id}/judges/invite`
- **Summary**: Invite a User to Judge
- **Auth**: `organizer` or `owner`
- **Description**: Invites any platform user to become a judge. This does *not* prematurely register them as a participant.
- **Request Body**:
  ```json
  {
    "user_id": "usr_abc123",
    "email": null
  }
  ```
- **Response `201 Created`**: `JudgeInvitationResponse` with `status: "pending"`.

### `GET /api/invitations/my`
- **Summary**: List Current User's Judge Invitations
- **Auth**: Authenticated User
- **Response `200 OK`**: Array of `JudgeInvitationResponse` addressed to the caller.

### `POST /api/invitations/{invitation_id}/accept`
- **Summary**: Accept Judge Invitation
- **Auth**: Authenticated Invitee
- **Restrictions**: Cannot accept if event is closed (`400 Bad Request`).
- **Effect**: Upgrades membership to `judge` and revokes any prior `participant` role for that event.
- **Response `200 OK`**: Updated invitation with `status: "accepted"`.

### `POST /api/invitations/{invitation_id}/decline`
- **Summary**: Decline Judge Invitation
- **Auth**: Authenticated Invitee
- **Response `200 OK`**: Updated invitation with `status: "declined"`.

---

## 8. Projects & Submission Gallery (T1 Core)

### `GET /api/projects` (also `/projects`)
- **Summary**: Public Project Gallery
- **Auth**: None (Public - No headers required)
- **Query Parameters**:
  - `event_id`: Filter by event
  - `track_id`: Filter by competition track
  - `skip`: Pagination offset (default: 0)
  - `limit`: Pagination limit (default: 100)
- **Response `200 OK`**:
  ```json
  {
    "total_count": 41,
    "items": [
      {
        "id": "prj_01",
        "event_id": "evt_01",
        "team_id": "tm_01",
        "track_id": "trk_04",
        "title": "Glass Signal",
        "summary": "One line of what it does.",
        "repo_url": "https://example.org/repo/01",
        "submitted_at": "2026-02-27T04:08:00Z",
        "created_by": "usr_prt"
      }
    ]
  }
  ```

### `POST /api/projects` (also `/projects`)
- **Summary**: Submit a Project
- **Auth**: Authenticated Participant
- **Description**: Submits a project to a hackathon event.
- **Deadline Enforcement**: If the event's `submissions_close` has passed (e.g. `evt_01`), the submission is rejected with **`400 Bad Request`**:
  ```json
  {
    "detail": "Submissions for event 'Sample Hack 2026' are closed. The deadline passed at 2026-03-01T18:00:00+00:00 UTC."
  }
  ```
- **Request Body**:
  ```json
  {
    "event_id": "evt_01",
    "track_id": "trk_01",
    "title": "My Awesome Project",
    "summary": "AI agents that run locally",
    "repo_url": "https://github.com/example/repo"
  }
  ```
- **Response `201 Created`**: Single `ProjectResponse` object.

### `GET /api/projects/{project_id}`
- **Summary**: Get Project Details
- **Auth**: None (Public)
- **Response `200 OK`**: Detailed `ProjectResponse`.

---

## 9. DOGFOOD 2026 Acceptance Checker Verification

The acceptance runner (`python run.py .dogfood.toml`) verifies compliance against `.DOGFOOD.TOML`:

```toml
[portal]
base_url = "http://localhost:8080"

[tiers]
claimed = ["T1"]
pitch = "Clean, modular hackathon platform with real-time deadline enforcement and role-based access control."

[auth]
organizer   = "Cookie: session=org_7f2a"
judge_a     = "Cookie: session=jdg_a_91bc"
judge_b     = "Cookie: session=jdg_b_44de"
participant = "Cookie: session=prt_2e88"

[routes]
gallery = "/projects"
submit  = "/projects"
```

### Verification Command & Output
```bash
python run.py .DOGFOOD.TOML
```
```
DOGFOOD 2026 acceptance report
portal: http://localhost:8080
claimed: T1
fixtures: fixtures.json

T1  gallery is public ................. PASS
T1  project from fixtures shown ....... PASS
T1  closed event refuses submissions .. PASS

claimed T1, verified T1
```
All criteria under Tier 1 (Public gallery, Fixture project rendering, and Submission deadline enforcement) achieve 100% PASS rate.
