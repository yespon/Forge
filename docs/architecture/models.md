# Database Models

## Overview

The platform uses SQLAlchemy 2.0 with async PostgreSQL. All models use declarative mapping with type hints.

## Entity Relationship Diagram

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│      Org        │     │      Team       │     │      User       │
├─────────────────┤     ├─────────────────┤     ├─────────────────┤
│ id (PK)         │◄────┤ org_id (FK)     │     │ id (PK)         │
│ name            │     │ id (PK)         │◄────┤ org_id (FK)     │
│ slug (unique)   │     │ name            │     │ email           │
│ status          │     │ slug            │     │ role            │
│ settings (JSON) │     │ settings (JSON) │     │ status          │
│ quota (JSON)    │     │ created_at      │     │ settings (JSON) │
│ created_at      │     │ updated_at      │     │ password_hash   │
│ updated_at      │     └─────────────────┘     │ mfa_enabled     │
│ deleted_at      │           ▲                 │ last_login_at   │
└─────────────────┘           │                 │ created_at      │
                              │                 │ updated_at      │
                              │                 │ deleted_at      │
                              │                 └─────────────────┘
                              │                           │
                              │     ┌─────────────────┐   │
                              └─────┤    UserTeam     ├───┘
                                    ├─────────────────┤
                                    │ user_id (PK/FK) │
                                    │ team_id (PK/FK) │
                                    │ role            │
                                    │ joined_at       │
                                    └─────────────────┘
```

## Models

### Org

Organization entity with multi-tenant isolation.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key, auto-generated |
| `name` | String(100) | Organization name |
| `slug` | String(50) | URL-friendly unique identifier |
| `status` | String(20) | active, inactive, suspended |
| `settings` | JSON | Organization-specific settings |
| `quota` | JSON | Resource limits (users, sandboxes, etc.) |
| `billing_info` | JSON | Billing configuration |
| `created_at` | DateTime | Creation timestamp |
| `updated_at` | DateTime | Last update timestamp |
| `deleted_at` | DateTime | Soft delete timestamp |

**Relationships:**
- `users` → User[] (one-to-many)
- `teams` → Team[] (one-to-many)

**Default Quota:**
```json
{
  "max_users": 100,
  "max_sandboxes": 50,
  "max_concurrent_sessions": 30,
  "monthly_token_budget": 10000000
}
```

---

### Team

Team entity for grouping users within an organization.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `org_id` | UUID | Foreign key to Org |
| `name` | String(100) | Team name |
| `slug` | String(50) | Team slug (unique within org) |
| `description` | Text | Optional description |
| `settings` | JSON | Team-specific settings |
| `created_at` | DateTime | Creation timestamp |
| `updated_at` | DateTime | Last update timestamp |

**Relationships:**
- `org` → Org (many-to-one)
- `members` → UserTeam[] (one-to-many)

**Constraints:**
- Unique constraint on `(org_id, slug)`

---

### User

User entity with authentication and role-based access.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `org_id` | UUID | Foreign key to Org |
| `external_id` | String(200) | SSO/external auth ID |
| `email` | String(200) | User email |
| `display_name` | String(100) | Display name |
| `avatar_url` | String(500) | Avatar image URL |
| `role` | Enum | platform_admin, org_admin, team_admin, developer, viewer |
| `status` | Enum | active, inactive, suspended |
| `settings` | JSON | User preferences |
| `quota_override` | JSON | Individual quota overrides |
| `password_hash` | String(255) | Bcrypt password hash |
| `mfa_enabled` | Boolean | MFA enabled flag |
| `last_login_at` | DateTime | Last login timestamp |
| `login_count` | Integer | Total login count |
| `created_at` | DateTime | Creation timestamp |
| `updated_at` | DateTime | Last update timestamp |
| `deleted_at` | DateTime | Soft delete timestamp |

**Relationships:**
- `org` → Org (many-to-one)
- `teams` → UserTeam[] (one-to-many)

**Constraints:**
- Unique constraint on `(org_id, email)`

**Properties:**
- `is_active` → True if status is ACTIVE and not deleted
- `is_admin` → True if role is PLATFORM_ADMIN or ORG_ADMIN

**Roles:**

| Role | Permissions |
|------|-------------|
| `platform_admin` | Full platform access |
| `org_admin` | Organization management |
| `team_admin` | Team management |
| `developer` | Create and run agents |
| `viewer` | Read-only access |

---

### UserTeam

Association table for user-team membership.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | UUID | Foreign key to User (PK) |
| `team_id` | UUID | Foreign key to Team (PK) |
| `role` | String(20) | Member role in team |
| `joined_at` | DateTime | Membership start timestamp |

**Relationships:**
- `user` → User (many-to-one)
- `team` → Team (many-to-one)

**Composite Primary Key:** `(user_id, team_id)`

## Soft Delete Pattern

All models support soft delete via `deleted_at` field:

```python
# Query active records only
session.query(User).filter(User.deleted_at.is_(None))

# Soft delete
user.deleted_at = datetime.now(timezone.utc)
```

## JSON Fields

JSON fields provide flexibility for settings and quotas:

```python
# Access nested settings
user.settings["theme"] = "dark"
org.quota["max_users"] = 200
```

## Indexes

Recommended indexes for performance:

```sql
CREATE INDEX idx_users_org_email ON users(org_id, email) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_status ON users(status) WHERE deleted_at IS NULL;
CREATE INDEX idx_teams_org ON teams(org_id);
CREATE INDEX idx_user_teams_user ON user_teams(user_id);
CREATE INDEX idx_user_teams_team ON user_teams(team_id);
```
