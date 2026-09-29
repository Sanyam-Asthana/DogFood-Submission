# Data Model — DOGFOOD 2026

This document specifies the database schemas, relationships, constraints, and fixture mappings used in the DOGFOOD Hackathon Platform.

---

## 1. Entity-Relationship Diagram

```mermaid
erDiagram
    USERS ||--o{ EVENT_MEMBERS : "registers"
    USERS ||--o{ TEAM_MEMBERS : "belongs to"
    USERS ||--o{ TEAM_INVITATIONS : "receives"
    USERS ||--o{ PROJECTS : "creates"

    EVENTS ||--o{ TRACKS : "contains"
    EVENTS ||--o{ EVENT_MEMBERS : "has"
    EVENTS ||--o{ TEAMS : "hosts"
    EVENTS ||--o{ PROJECTS : "collects"

    TEAMS ||--o{ TEAM_MEMBERS : "includes"
    TEAMS ||--o{ TEAM_INVITATIONS : "sends"
    TEAMS ||--o| PROJECTS : "submits"

    TRACKS ||--o{ PROJECTS : "categorizes"

    USERS {
        string id PK
        string email UK
        string name
        string role "owner | organizer | judge | user"
        string session_token UK
        datetime created_at
    }

    EVENTS {
        string id PK
        string name
        string description
        int max_team_size "Default: 4"
        datetime submissions_open
        datetime submissions_close
        boolean is_active
        string created_by FK
    }

    TRACKS {
        string id PK
        string event_id FK
        string name
        string description
    }

    EVENT_MEMBERS {
        string id PK
        string event_id FK
        string user_id FK
        string role "owner | organizer | judge | participant"
        datetime registered_at
    }

    TEAMS {
        string id PK
        string event_id FK
        string name
        datetime created_at
    }

    TEAM_MEMBERS {
        string id PK
        string team_id FK
        string user_id FK
        string role "lead | member"
        datetime joined_at
    }

    TEAM_INVITATIONS {
        string id PK
        string team_id FK
        string user_id FK
        string status "pending | accepted | rejected"
        datetime created_at
    }

    PROJECTS {
        string id PK
        string event_id FK
        string team_id FK
        string track_id FK
        string title
        string summary
        string repo_url
        datetime submitted_at
        string created_by FK
    }
```

---

## 2. Table Specifications

### `users`
Represents all accounts across the platform.
| Column | Type | Nullable | Details |
| :--- | :--- | :--- | :--- |
| `id` | `VARCHAR(64)` | No | Primary Key (`usr_*` or `jdg_*`). |
| `email` | `VARCHAR(255)` | No | Unique index. |
| `name` | `VARCHAR(255)` | No | User display name. |
| `role` | `VARCHAR(32)` | No | Platform role (`owner`, `organizer`, `judge`, `user`). |
| `session_token` | `VARCHAR(255)` | Yes | Session token matching DOGFOOD cookies. |
| `created_at` | `TIMESTAMPTZ` | No | Default UTC timestamp. |

### `events`
Hackathons managed on the platform.
| Column | Type | Nullable | Details |
| :--- | :--- | :--- | :--- |
| `id` | `VARCHAR(64)` | No | Primary Key (`evt_*`). |
| `name` | `VARCHAR(255)` | No | Event title. |
| `description` | `TEXT` | Yes | Markdown-capable event description. |
| `max_team_size` | `INTEGER` | No | Default 4. Immutable after creation. |
| `submissions_open` | `TIMESTAMPTZ` | No | Submissions window open time. |
| `submissions_close` | `TIMESTAMPTZ` | No | Submissions deadline. Writes rejected after this. |
| `is_active` | `BOOLEAN` | No | Toggle event visibility. |
| `created_by` | `VARCHAR(64)` | Yes | Foreign Key -> `users.id`. |

### `teams` & `team_members`
Team groupings formed within an event.
- Cascade rule: Deleting a `team` automatically cascades deletion of its `team_members`, `team_invitations`, and sets `team_id = NULL` on submitted `projects`.
- Uniqueness: A user can belong to at most one team per event.
- Cap: The count of `team_members` for a team cannot exceed `event.max_team_size`.

### `team_invitations`
Invitations sent by team leads to prospective members.
- Validates that the recipient is registered as an `event_member` with role `participant`.
- Prevents inviting members who already belong to another team.

### `projects`
Hackathon project submissions.
| Column | Type | Nullable | Details |
| :--- | :--- | :--- | :--- |
| `id` | `VARCHAR(64)` | No | Primary Key (`prj_*`). |
| `event_id` | `VARCHAR(64)` | No | Foreign Key -> `events.id`. |
| `team_id` | `VARCHAR(64)` | Yes | Foreign Key -> `teams.id` (nullable for solo submissions). |
| `track_id` | `VARCHAR(64)` | Yes | Foreign Key -> `tracks.id`. |
| `title` | `VARCHAR(255)` | No | Project title. |
| `summary` | `TEXT` | Yes | Elevator pitch / description. |
| `repo_url` | `VARCHAR(512)`| Yes | Repository URL. |
| `submitted_at` | `TIMESTAMPTZ` | No | Submission timestamp (UTC). |
| `created_by` | `VARCHAR(64)` | No | Foreign Key -> `users.id`. |

---

## 3. Fixtures Ingestion Mapping

When loading `fixtures.json`, the ingestion pipeline in `src/seed.py` maps data deterministically:

1. **`fixtures["event"]`** -> `events` row (`id="evt_01"`, deadline set to fixture close time).
2. **`fixtures["tracks"]`** -> `tracks` rows with respective IDs.
3. **`fixtures["judges"]`** -> `users` (`jdg_*`) and `event_members` (`role="judge"`).
4. **`fixtures["teams"]`** -> `teams` and `team_members` (lead assigned to first member).
5. **`fixtures["projects"]`** -> `projects` associated with fixture teams and tracks.
