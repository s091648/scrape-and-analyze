# User Settings Design

**Date:** 2026-03-04

## Summary

Add a `/settings` page accessible to all authenticated users, with a gear icon in the navbar replacing the current admin link. Settings includes profile management (name, avatar, password change for credentials users, delete account). Admins get an additional sidebar section linking to scraper settings and user management.

## Navbar Changes

- Replace the "Admin" text link with a `Settings` gear icon (`lucide-react` `Settings` icon).
- Icon is visible to **all** authenticated users.
- Clicking navigates to `/settings`.

## Settings Page Layout

Reuses the sidebar-left / content-right layout pattern from `/admin`. Sidebar items:

```
Profile
──────────────────
Admin (admin-only section header)
  Scraper Settings  → /admin/scraper-settings
  User Management   → /admin/user-management
```

### Profile Tab (`/settings` or `/settings/profile`)

- **Avatar**: circular preview of current icon; upload button triggers file input, resized client-side to 128×128px WebP via Canvas API before base64 encoding and submission.
- **Name**: editable text field, saved on submit.
- **Change password**: visible only for credentials users (i.e. `google_id` is null). Fields: current password + new password. Hidden entirely for Google-only users.
- **Delete account**: destructive action with confirmation dialog. Deletes own account via `DELETE /auth/me`, then signs out.

## Access Control Changes

- `/admin/scraper-settings` and `/admin/user-management`: redirect non-admin users to `/settings` instead of `/login`.
- "Users" page renamed to "User Management" (`/admin/user-management`).

## Database

New Alembic migration (`07_add_user_icon.py`):

```sql
ALTER TABLE auth.users ADD COLUMN icon TEXT;
```

Stored as a base64 data URL string (e.g. `data:image/webp;base64,...`). Nullable, no default.

## New Backend Endpoints

All under `backend/routers/auth.py`. Require a valid JWT for the authenticated user.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/auth/me` | Return own profile: id, name, email, icon, role, google_id |
| `PATCH` | `/auth/me` | Update name and/or icon |
| `POST` | `/auth/me/password` | Change password — verifies current password, hashed with bcrypt. Rejects if user has no `hashed_password`. |
| `DELETE` | `/auth/me` | Delete own account |

Existing admin endpoints (`/auth/users`, `/auth/users/{id}`) are unchanged.

## Frontend Components

- `app/settings/layout.tsx` — sidebar layout (shared with admin pattern)
- `app/settings/page.tsx` — Profile tab content
- `app/admin/user-management/page.tsx` — renamed from `/admin/users/page.tsx`
- `app/admin/layout.tsx` — updated sidebar: "User Management" replaces "Users"

## Client-side Icon Resizing

Before uploading, the browser resizes the selected image to 128×128px using the Canvas API and encodes it as WebP at 0.85 quality. This keeps the base64 payload under ~20KB in all cases.

## Out of Scope

- Email change (requires verification flow)
- Profile visibility settings
- Notification preferences
