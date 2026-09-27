# DOGFOOD 2026 API Reference

This document provides a comprehensive guide to all API endpoints available in the DOGFOOD 2026 Hackathon Platform.

---

## 1. Authentication & Authorization Model

### Authentication Methods
Endpoints accept credentials through any of the following mechanisms (in order of evaluation priority):
1. **HTTP Header `X-Session-Token: <token>`** (Recommended for API clients, testing tools, and script automation)
2. **HTTP Header `Authorization: Bearer <token>`** (Standard Bearer authentication)
3. **HTTP Cookie `session=<token>`** (Ambient cookie set upon browser login)

### Role Hierarchy
- **Platform Roles**:
  - `owner`: Superuser of the platform. Has all organizer, judge, and participant permissions. Can promote users to `organizer` and demote organizers. Claimed on startup via the setup key.
  - `organizer`: Can create events, edit events, adjust deadlines, manage competition tracks, and invite event participants to become judges.
  - `judge`: Can evaluate and score submissions.
  - `participant`: Default platform user role. Can browse events, join events, and submit projects.
- **Event Roles**:
  - `participant`: A user who joined the specific event.
  - `judge`: A participant who was invited by an organizer/owner and accepted the invitation.

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
- **Summary**: Interactive Testing Studio (Single Page Application)
- **Auth**: None (Public)
- **Response `200 OK`**: HTML page for testing endpoints directly in the browser.

---

## 3. Platform Administration & Role Delegation

### `POST /api/platform/claim-owner`
- **Summary**: Claim Platform Ownership
- **Auth**: Authenticated User
- **Description**: Promotes the calling user to platform `owner` if the secret setup key matches the one generated on server boot.
- **Request Body**:
  ```json
  {
    "setup_key": "string"
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "id": "usr_abc123",
    "email": "owner@platform.org",
    "name": "Platform Owner",
    "role": "owner",
    "created_at": "2026-02-27T10:00:00Z"
  }
  ```

### `GET /api/platform/users`
- **Summary**: List All Registered Users
- **Auth**: `organizer` or `owner`
- **Response `200 OK`**: Array of user objects:
  ```json
  [
    {
      "id": "usr_abc123",
      "email": "alice@platform.org",
      "name": "Alice Participant",
      "role": "participant",
      "created_at": "2026-02-27T10:00:00Z"
    }
  ]
  ```

### `POST /api/platform/promote-organizer`
- **Summary**: Promote User to Organizer
- **Auth**: `owner` only
- **Request Body**: Specify either `user_id` or `email`:
  ```json
  {
    "user_id": "usr_abc123",
    "email": null
  }
  ```
- **Response `200 OK`**: Updated user object with `role: "organizer"`.

### `POST /api/platform/demote-organizer`
- **Summary**: Demote Organizer to Participant
- **Auth**: `owner` only
- **Request Body**: Specify either `user_id` or `email`:
  ```json
  {
    "user_id": "usr_abc123",
    "email": null
  }
  ```
- **Response `200 OK`**: Updated user object with `role: "participant"`.

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
    "name": "User Name",
    "role": "participant"
  }
  ```
- **Response `201 Created`**: User profile object.

### `POST /api/auth/login` (also `/auth/login`)
- **Summary**: User Login
- **Auth**: None (Public)
- **Description**: Verifies credentials and sets `session` HttpOnly cookie.
- **Request Body**:
  ```json
  {
    "email": "user@example.com",
    "password": "SecretPassword123!"
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "access_token": "usr_tok_xyz789",
    "token_type": "bearer",
    "user": {
      "id": "usr_123",
      "email": "user@example.com",
      "name": "User Name",
      "role": "participant",
      "created_at": "2026-02-27T10:00:00Z"
    }
  }
  ```

### `POST /api/auth/logout` (also `/auth/logout`)
- **Summary**: User Logout
- **Auth**: None / Authenticated User
- **Response `200 OK`**: `{"message": "Logged out successfully"}`

### `GET /api/auth/me` (also `/auth/me`)
- **Summary**: Get Current Authenticated Profile
- **Auth**: Authenticated User
- **Response `200 OK`**: User profile object.

### Legacy Supabase Endpoints (Compatibility)
- `POST /create_account` — `{"username": "...", "password": "...", "role": "..."}`
- `POST /login` — `{"username": "...", "password": "..."}`
- `POST /logout`
- `POST /get_current_user`

---

## 5. Events Management & Deadlines

### `GET /api/events`
- **Summary**: Discover Events (Public Catalog)
- **Auth**: None (Public)
- **Query Parameters**:
  - `status` (`upcoming` | `active` | `closed`, optional)
  - `include_inactive` (boolean, default: `false`)
  - `skip` (integer, default: `0`)
  - `limit` (integer, default: `100`)
- **Response `200 OK`**:
  ```json
  {
    "total": 1,
    "skip": 0,
    "limit": 100,
    "events": [
      {
        "id": "evt_01",
        "name": "Sample Hack 2026",
        "description": "Official fixture hackathon",
        "submissions_open": "2026-02-27T18:00:00Z",
        "submissions_close": "2026-03-01T18:00:00Z",
        "is_active": true,
        "status": "closed",
        "is_submission_open": false,
        "time_remaining_seconds": 0,
        "track_count": 8,
        "tracks": [...],
        "created_by": "org_user",
        "created_at": "2026-02-27T18:00:00Z",
        "updated_at": "2026-02-27T18:00:00Z"
      }
    ]
  }
  ```

### `GET /api/events/current`
- **Summary**: Get Current / Featured Event
- **Auth**: None (Public)
- **Response `200 OK`**: Single `EventResponse` object.

### `POST /api/events`
- **Summary**: Create Event
- **Auth**: `organizer` or `owner`
- **Request Body**:
  ```json
  {
    "name": "Hackathon 2026",
    "description": "Competition description",
    "submissions_open": "2026-02-27T10:00:00Z",
    "submissions_close": "2026-03-01T18:00:00Z",
    "is_active": true,
    "tracks": [
      {
        "name": "AI & Agents",
        "description": "Autonomous agent systems"
      }
    ]
  }
  ```
- **Response `201 Created`**: Single `EventResponse` object.

### `GET /api/events/{event_id}`
- **Summary**: Get Event Details
- **Auth**: None (Public)
- **Response `200 OK`**: Detailed `EventResponse`.

### `PUT /api/events/{event_id}`
- **Summary**: Update Event
- **Auth**: `organizer` or `owner`
- **Request Body**:
  ```json
  {
    "name": "Updated Name",
    "description": "Updated Description",
    "is_active": true
  }
  ```
- **Response `200 OK`**: Updated `EventResponse`.

### `DELETE /api/events/{event_id}`
- **Summary**: Archive Event (Soft Delete)
- **Auth**: `organizer` or `owner`
- **Response `200 OK`**: `{"message": "Event 'evt_id' has been archived."}`

### `GET /api/events/{event_id}/status`
- **Summary**: Real-Time Deadline & Submission Status
- **Auth**: None (Public)
- **Response `200 OK`**:
  ```json
  {
    "event_id": "evt_01",
    "name": "Sample Hack 2026",
    "status": "closed",
    "is_submission_open": false,
    "time_remaining_seconds": 0,
    "submissions_open": "2026-02-27T18:00:00Z",
    "submissions_close": "2026-03-01T18:00:00Z",
    "server_time": "2026-09-27T16:00:00Z"
  }
  ```

### `PATCH /api/events/{event_id}/deadline`
- **Summary**: Adjust Event Deadline
- **Auth**: `organizer` or `owner`
- **Request Body**:
  ```json
  {
    "submissions_close": "2026-03-05T23:59:59Z",
    "submissions_open": null
  }
  ```
- **Response `200 OK`**: Updated `EventResponse`.

---

## 6. Competition Tracks Management

### `GET /api/events/{event_id}/tracks`
- **Summary**: List Tracks for Event
- **Auth**: None (Public)
- **Response `200 OK`**: Array of track objects.

### `POST /api/events/{event_id}/tracks`
- **Summary**: Add Competition Track
- **Auth**: `organizer` or `owner`
- **Request Body**:
  ```json
  {
    "name": "Web3 & Decentralization",
    "description": "Smart contracts and dApps"
  }
  ```
- **Response `201 Created`**: Created track object.

### `DELETE /api/events/{event_id}/tracks/{track_id}`
- **Summary**: Delete Competition Track
- **Auth**: `organizer` or `owner`
- **Response `200 OK`**: `{"message": "Track 'trk_01' has been deleted."}`

---

## 7. Event Roles & Judge Invitations

### `POST /api/events/{event_id}/join`
- **Summary**: Join Event as Participant
- **Auth**: Authenticated User
- **Response `201 Created`**:
  ```json
  {
    "id": "mem_123456",
    "event_id": "evt_01",
    "user_id": "usr_abc",
    "user_name": "Alice Participant",
    "user_email": "alice@platform.org",
    "role": "participant",
    "joined_at": "2026-02-27T10:00:00Z"
  }
  ```

### `GET /api/events/{event_id}/members`
- **Summary**: List Event Members
- **Auth**: None (Public)
- **Response `200 OK`**: Array of `EventMemberResponse` objects.

### `GET /api/events/{event_id}/judges`
- **Summary**: List Confirmed Event Judges
- **Auth**: None (Public)
- **Response `200 OK`**: Array of `EventMemberResponse` objects where `role: "judge"`.

### `POST /api/events/{event_id}/judges/invite`
- **Summary**: Invite Participant to Judge Event
- **Auth**: `organizer` or `owner`
- **Request Body**:
  ```json
  {
    "user_id": "usr_abc",
    "email": null
  }
  ```
- **Response `201 Created`**:
  ```json
  {
    "id": "inv_abcdef12",
    "event_id": "evt_01",
    "event_name": "Sample Hack 2026",
    "inviter_id": "usr_org",
    "inviter_name": "Org Admin",
    "invitee_id": "usr_abc",
    "invitee_email": "alice@platform.org",
    "status": "pending",
    "created_at": "2026-02-27T10:00:00Z",
    "responded_at": null
  }
  ```

### `GET /api/invitations/my`
- **Summary**: List My Judge Invitations
- **Auth**: Authenticated User
- **Response `200 OK`**: Array of `JudgeInvitationResponse` objects addressed to calling user.

### `POST /api/invitations/{invitation_id}/accept`
- **Summary**: Accept Judge Invitation
- **Auth**: Authenticated User (Must be invitee)
- **Description**: Changes status to `accepted` and promotes user's event role to `judge`.
- **Response `200 OK`**: Updated `JudgeInvitationResponse`.

### `POST /api/invitations/{invitation_id}/decline`
- **Summary**: Decline Judge Invitation
- **Auth**: Authenticated User (Must be invitee)
- **Description**: Changes status to `declined`.
- **Response `200 OK`**: Updated `JudgeInvitationResponse`.
