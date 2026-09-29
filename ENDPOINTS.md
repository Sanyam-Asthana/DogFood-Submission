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

### `POST /api/platform/reset-database`
- **Summary**: Flush and Reseed Database
- **Auth**: `owner` only (`403 Forbidden` for non-owners)
- **Description**: Wipes all transient platform records (teams, team invitations, judge invitations, event registrations, competition submissions, custom users) and reseeds the platform with default fixture accounts (`org_7f2a`, `jdg_a_91bc`, `jdg_b_44de`, `prt_2e88`).
- **Response `200 OK`**:
  ```json
  {
    "message": "Platform database successfully flushed and reseeded with default fixtures."
  }
  ```

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
    "max_team_size": 4,
    "is_active": true,
    "tracks": [
      { "name": "AI Agents", "description": "Agentic workflows" }
    ]
  }
  ```
- **Note on `max_team_size`**: Specifies the team capacity constraint (`1` for solo/individual competition, `2`–`20` for team hackathons). Locked upon creation and immutable thereafter.
- **Response `201 Created`**: Single `EventResponse` object containing `max_team_size`.

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

### `POST /api/events/judges/invitations/{invitation_id}/cancel` (also `DELETE /api/events/judges/invitations/{invitation_id}`)
- **Summary**: Cancel / Revoke Pending Judge Invitation
- **Auth**: `organizer` or `owner`
- **Description**: Revokes a pending judge invitation sent to a user.
- **Response `200 OK`**: Updated invitation with `status: "declined"`.

---

## 8. Team Formation & Membership (T1 Core)

Participants can form teams, join teams, and submit projects as a team.

### `POST /api/events/{event_id}/teams` (also `/events/{event_id}/teams`)
- **Summary**: Form a Competition Team
- **Auth**: Authenticated `participant` of the event
- **Restrictions**: 
  - Submissions must be open (`400 Bad Request` if deadline passed).
  - User cannot already be in a team for this event (`400 Bad Request`).
  - Creator automatically becomes team `lead`.
- **Request Body**:
  ```json
  {
    "name": "Team CyberWizards"
  }
  ```
- **Response `201 Created`**:
  ```json
  {
    "id": "tm_12345678",
    "event_id": "evt_01",
    "name": "Team CyberWizards",
    "created_at": "2026-03-01T12:00:00Z",
    "member_count": 1,
    "members": [
      {
        "id": "tmem_abc12345",
        "team_id": "tm_12345678",
        "user_id": "usr_prt",
        "role": "lead",
        "joined_at": "2026-03-01T12:00:00Z",
        "user_name": "Ada Okonkwo",
        "user_email": "ada@example.org"
      }
    ],
    "project_id": null
  }
  ```

### `GET /api/events/{event_id}/teams` (also `/events/{event_id}/teams`)
- **Summary**: List Teams in Event
- **Auth**: None (Public)
- **Response `200 OK`**: Array of `TeamResponse` objects with full member rosters.

### `GET /api/teams/{team_id}` (also `/teams/{team_id}`)
- **Summary**: Get Team Details
- **Auth**: None (Public)
- **Response `200 OK`**: Detailed `TeamResponse` object.

### `POST /api/teams/{team_id}/join` (also `/teams/{team_id}/join`)
- **Summary**: Join a Team
- **Auth**: Authenticated `participant` of the same event
- **Restrictions**: Event submissions must be open; caller must not be on another team.
- **Response `200 OK`**: Updated `TeamResponse` with caller added as `member`.

### `POST /api/teams/{team_id}/leave` (also `/teams/{team_id}/leave`)
- **Summary**: Leave a Team
- **Auth**: Authenticated team member
- **Rule**: If only one or zero members remain after leaving, the team is automatically dissolved and the remaining member becomes a normal single participant again.
- **Response `200 OK`**:
  ```json
  {
    "status": "success",
    "message": "Left team 'tm_123'. As only one or zero members remained, the team was dissolved and any remaining member is now a single participant.",
    "team_id": "tm_123",
    "team_dissolved": true
  }
  ```

### `POST /api/teams/{team_id}/dissolve` (also `DELETE /api/teams/{team_id}`)
- **Summary**: Dissolve a Team
- **Auth**: Team Leader or Platform `owner` (`403 Forbidden` for non-leaders)
- **Description**: Dissolves the team. All team members are released and become normal single participants again. Any pending invitations to the team are cancelled.
- **Response `200 OK`**:
  ```json
  {
    "status": "success",
    "message": "Team 'Team Name' has been dissolved. All former members are now single participants.",
    "team_id": "tm_123"
  }
  ```

---

## 9. Projects & Submission Gallery (T1 Core)

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
        "team_name": "Nightshift",
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
- **Description**: Submits a project to a hackathon event. Binds optional track and team.
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
    "team_id": "tm_01",
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

### `PUT /api/projects/{project_id}` (also `PATCH /api/projects/{project_id}`)
- **Summary**: Edit Project (Until Deadline)
- **Auth**: Authenticated Author or Team Member
- **Description**: Allows modifying submission details (`title`, `summary`, `repo_url`, `track_id`, `team_id`) before the submission deadline closes.
- **Deadline Enforcement**: If the event's deadline has passed, edits are strictly rejected with **`400 Bad Request`**:
  ```json
  {
    "detail": "Submissions for event 'Sample Hack 2026' are closed."
  }
  ```
- **Authorization Enforcement**: If non-author / non-teammate attempts edits, rejected with **`403 Forbidden`**.
- **Response `200 OK`**: Updated `ProjectResponse`.

### `DELETE /api/projects/{project_id}`
- **Summary**: Delete Project Submission (Until Deadline)
- **Auth**: Authenticated Author or Platform Admin
- **Response `200 OK`**: `{"message": "Project 'prj_01' deleted successfully.", "project_id": "prj_01"}`

---

## 10. Teams & Team Invitations (T1 Core)

### `POST /api/events/{event_id}/teams`
- **Summary**: Form a Team
- **Auth**: Authenticated Participant in Event
- **Description**: Creates a new team in the specified event with caller as team leader (`lead`).
- **Solo Constraint**: If event has `max_team_size == 1`, returns **`400 Bad Request`** ("Solo hackathon: team formation is not allowed").
- **Request Body**:
  ```json
  {
    "name": "Team Hyperion"
  }
  ```
- **Response `201 Created`**: Single `TeamResponse` object.

### `GET /api/events/{event_id}/teams`
- **Summary**: List Teams in Event
- **Auth**: None (Public)
- **Response `200 OK`**: Array of `TeamResponse` objects with roster and member count.

### `GET /api/teams/{team_id}`
- **Summary**: Get Team Details
- **Auth**: None (Public)
- **Response `200 OK`**: Detailed `TeamResponse` with members and linked project.

### `POST /api/teams/{team_id}/join`
- **Summary**: Join an Open Team
- **Auth**: Authenticated Participant in Event
- **Description**: Joins an existing team if it has open capacity (`len(members) < max_team_size`).
- **Response `200 OK`**: Updated `TeamResponse`.

### `POST /api/teams/{team_id}/leave`
- **Summary**: Leave a Team
- **Auth**: Authenticated Team Member
- **Description**: Leaves current team. If last member leaves, the team is removed. If leader leaves, leadership transfers to first remaining member.
- **Response `200 OK`**: `{"message": "Successfully left team 'tm_123'.", "team_id": "tm_123"}`

### `POST /api/teams/{team_id}/invite`
- **Summary**: Invite Teammate to Team
- **Auth**: Authenticated Team Member
- **Description**: Sends a team invitation to any registered user on the platform by email or user ID.
- **Capacity Enforcement**: Fails with **`400 Bad Request`** if team is already full.
- **Request Body**:
  ```json
  {
    "email": "teammate@example.com"
  }
  ```
- **Response `201 Created`**: Single `TeamInvitationResponse` with `status: "pending"`.

### `GET /api/teams/{team_id}/invitations`
- **Summary**: List Sent Team Invitations
- **Auth**: Authenticated Team Member
- **Response `200 OK`**: Array of pending `TeamInvitationResponse` objects sent by this team.

### `GET /api/invitations/teams/my`
- **Summary**: List My Team Invitations
- **Auth**: Authenticated User
- **Description**: Retrieves all team invitations addressed to the current user (displayed in "My Invitations").
- **Response `200 OK`**: Array of `TeamInvitationResponse` objects.

### `POST /api/invitations/teams/{invitation_id}/accept`
- **Summary**: Accept Team Invitation
- **Auth**: Authenticated Invitee
- **Description**: Accepts invitation, auto-enrolls invitee as event participant if not already registered, and joins the team.
- **Response `200 OK`**: `TeamInvitationResponse` with `status: "accepted"`.

### `POST /api/invitations/teams/{invitation_id}/decline`
- **Summary**: Decline Team Invitation
- **Auth**: Authenticated Invitee
- **Description**: Declines the team invitation.
- **Response `200 OK`**: `TeamInvitationResponse` with `status: "declined"`.

### `POST /api/invitations/teams/{invitation_id}/cancel` (also `DELETE /api/invitations/teams/{invitation_id}`)
- **Summary**: Cancel / Revoke Team Invitation
- **Auth**: Team member or `owner`
- **Description**: Cancels or revokes a team invitation sent to a user.
- **Response `200 OK`**: `TeamInvitationResponse` with `status: "declined"`.

---

## 11. Judging, Evaluation & CSV Export (Tier 2)

### `GET /api/judge/scores` (also `/judge/scores`)
- **Summary**: Retrieve Submitted Scores with Peer Isolation Defense
- **Auth**: Confirmed Judge, Organizer, or Platform Owner
- **Query Parameters**:
  - `judge`: Target judge ID or alias (`judge_a`, `judge_b`, `jdg_01`).
  - `event_id`: Optional event ID filter.
- **Security & Peer Isolation Guard**:
  - A judge querying their own scores (e.g. `judge_a` fetching `judge_a`): **`200 OK`**.
  - A judge querying a peer's scores (e.g. `judge_b` querying `judge_a`): **`403 Forbidden`** ("Judges are not permitted to view peer scores. Score confidentiality enforced.").
  - A participant attempting to access scores: **`403 Forbidden`** ("Participants are not permitted to access judging scores.").
  - Organizers/owners can inspect scores across judges.
- **Response `200 OK`**:
  ```json
  [
    {
      "id": "scr_jdg_01_prj_07",
      "event_id": "evt_01",
      "project_id": "prj_07",
      "project_title": "Quiet Hours",
      "judge_id": "jdg_01",
      "judge_name": "Tomas Varga (Judge A)",
      "criteria": {
        "functionality": 4.0,
        "quality": 3.0,
        "innovation": 5.0
      },
      "comment": "Solid architecture and clear documentation.",
      "submitted_at": "2026-03-01T14:22:00Z"
    }
  ]
  ```

### `POST /api/judge/scores` (also `/judge/scores`)
- **Summary**: Submit or Update Evaluation Score
- **Auth**: Confirmed Judge, Organizer, or Owner
- **Payload (`ScoreCreate`)**:
  ```json
  {
    "project_id": "prj_01",
    "criteria": {
      "functionality": 4.5,
      "quality": 4.0,
      "innovation": 5.0
    },
    "comment": "Exceptional code quality and clean execution."
  }
  ```
- **Validation**: Ratings must be between 1.0 and 5.0. Returns **`400 Bad Request`** if invalid.
- **Response `201 Created`**: `ScoreResponse`.

### `GET /api/judge/assignments` (also `/judge/assignments`)
- **Summary**: List Projects Assigned to Current Judge
- **Auth**: Confirmed Judge or Organizer
- **Query Parameters**:
  - `event_id`: Optional event ID filter.
- **Response `200 OK`**:
  ```json
  [
    {
      "project_id": "prj_01",
      "title": "Quiet Hours",
      "summary": "One line of what it does.",
      "repo_url": "https://example.org/repo/01",
      "track_id": "trk_03",
      "track_name": "Developer tools",
      "team_name": "Nightshift",
      "evaluated": true,
      "existing_score": { ... }
    }
  ]
  ```

### `GET /api/events/{event_id}/rubric`
- **Summary**: Get Scoring Rubric Criteria
- **Auth**: Public / Authenticated
- **Response `200 OK`**:
  ```json
  [
    { "name": "functionality", "weight": 0.4, "description": "System functions correctly." },
    { "name": "quality", "weight": 0.3, "description": "Code structure and reliability." },
    { "name": "innovation", "weight": 0.3, "description": "Novelty and creative design." }
  ]
  ```

### `PUT /api/events/{event_id}/rubric`
- **Summary**: Update Scoring Rubric Weights
- **Auth**: Event Organizer or Platform Owner (Non-organizers receive `403 Forbidden`)
- **Payload**:
  ```json
  {
    "criteria": [
      { "name": "functionality", "weight": 0.5 },
      { "name": "quality", "weight": 0.3 },
      { "name": "innovation", "weight": 0.2 }
    ]
  }
  ```
- **Response `200 OK`**: Updated list of rubric criteria.

### `GET /api/events/{event_id}/judging/progress`
- **Summary**: Event Judging Progress Matrix & Normalized Metrics
- **Auth**: Event Organizer or Platform Owner
- **Response `200 OK`**:
  ```json
  {
    "event_id": "evt_01",
    "total_projects": 40,
    "total_scores": 126,
    "total_judges": 30,
    "projects": [
      {
        "project_id": "prj_01",
        "project_title": "Quiet Hours",
        "track_name": "Developer tools",
        "team_name": "Nightshift",
        "reviews_count": 3,
        "raw_average": 3.67,
        "normalized_score": 78.4,
        "completed": true
      }
    ]
  }
  ```

### `GET /api/export.csv` (also `/export.csv`, `/api/events/{event_id}/export.csv`)
- **Summary**: Export Judging Results as CSV
- **Auth**: Event Organizer or Platform Owner only
- **Access Control**: Participants and judges requesting this endpoint receive **`403 Forbidden`**.
- **Response `200 OK`**:
  - `Content-Type: text/csv; charset=utf-8`
  - `Content-Disposition: attachment; filename=judging_results.csv`
  - Body:
    ```csv
    project_id,project_title,track,team_name,reviews_count,average_score,normalized_score,rank
    prj_01,Quiet Hours,Developer tools,Nightshift,3,3.67,78.40,1
    prj_07,Local First Sync,Developer tools,Individual,2,3.50,75.10,2
    ```

---

## 12. DOGFOOD 2026 Acceptance Checker Verification

The acceptance runner (`python run.py .dogfood.toml`) verifies compliance against `.dogfood.toml`:

```toml
[portal]
base_url = "http://localhost:8080"

[tiers]
claimed = ["T1", "T2"]
pitch = "Clean, modular hackathon platform with real-time deadline locks, peer score isolation, and Z-score normalized judging."

[auth]
organizer   = "Cookie: session=org_7f2a"
judge_a     = "Cookie: session=jdg_a_91bc"
judge_b     = "Cookie: session=jdg_b_44de"
participant = "Cookie: session=prt_2e88"

[routes]
gallery      = "/projects"
submit       = "/projects"
judge_scores = "/api/judge/scores"
peer_scores  = "/api/judge/scores?judge=judge_a"
csv_export   = "/api/export.csv"
```

### Verification Command & Output
```bash
python run.py .dogfood.toml
```
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
All criteria under Tier 1 and Tier 2 achieve a 100% PASS rate.

