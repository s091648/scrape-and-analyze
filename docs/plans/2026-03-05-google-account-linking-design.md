# Google Account Linking Design

**Date:** 2026-03-05
**Status:** Approved

## Problem

When a user logs in with Google and their email already exists in the database (belonging to a credentials user), the current system silently updates that account's `google_id`. This is a privacy and security problem — a different person with the same Google email could inadvertently take over another user's account.

## Goals

- Remove automatic Google-to-credentials account linking
- Allow users to explicitly link their Google account from the Settings page
- Allow users to unlink Google if they also have a password (no lockout)
- Keep email UNIQUE — no duplicate email accounts
- Merge migration 07 (icon column) into migration 06

## Non-Goals

- Allowing two accounts to share the same email
- A "it's not me" path that creates a duplicate-email account
- Changing the google-register or credentials login flows

---

## Database Migration

Migration `06_extend_auth_users` is revised in-place to include the `icon` column (previously migration `07_add_user_icon`). Migration `07_add_user_icon` is deleted.

To apply: downgrade to revision `05_normalize_tags`, then upgrade.

No constraint changes — `email` stays UNIQUE, `google_id` stays UNIQUE.

---

## Backend Changes

### `/auth/google/authorize` (modified)

Currently auto-links `google_id` when found by email but `google_id` is null. New behavior:

| Condition | Response |
|---|---|
| Email not found | `404 Not Found` |
| Account disabled | `403 Forbidden` |
| Email found, `google_id` is null | `409 Conflict` |
| Email found, `google_id` matches | `200 OK` |

The `409` tells NextAuth to redirect the user to the login page with an instruction to link via Settings.

### `POST /auth/me/link-google` (new)

Authenticated (Bearer JWT). Body: `{ google_id: string }`.

- Sets `google_id` on the current user if it is not already set.
- Returns `204 No Content`.
- Returns `400` if `google_id` is already set on this account.
- Returns `409` if the `google_id` is already used by another account.

### `DELETE /auth/me/link-google` (new)

Authenticated (Bearer JWT). No body.

- Clears `google_id` on the current user.
- Returns `204 No Content`.
- Returns `400` if the user has no `username` (would lock them out of their account).

---

## NextAuth Changes

In the `signIn` callback for `google-login`:

- `409` response from `/auth/google/authorize` → return `'/login?error=link_required'`
- Existing `404 → /login?error=not_registered` and `403 → /login?error=account_disabled` paths unchanged.

No new NextAuth providers are added. The link flow uses custom Next.js API routes.

---

## New Next.js API Routes (Option A — Signed State JWT)

### `GET /api/link-google/start`

- Requires `Authorization: Bearer <accessToken>` header.
- Verifies the token against `NEXTAUTH_SECRET` (HS256).
- Extracts `userId` from the token payload.
- Creates a signed state JWT: `{ userId, exp: now + 5 min }` using the same secret.
- Constructs a Google OAuth authorization URL with:
  - `client_id`, `redirect_uri = /api/link-google/callback`
  - `scope = openid email profile`
  - `state = <signed JWT>`
- Returns `302` redirect to Google.

### `GET /api/link-google/callback`

- Receives `?code=...&state=...` from Google.
- Verifies the state JWT (signature + expiry). On failure → redirect to `/settings?linked=error`.
- Exchanges `code` for Google tokens via Google token endpoint.
- Extracts `sub` (the Google user's unique ID) from the ID token.
- Reconstructs the user's backend Bearer token from the state JWT's `userId` and the shared secret.
- Calls `POST /auth/me/link-google` on the internal backend with `{ google_id: sub }`.
- On success → redirect to `/settings?linked=success`.
- On failure (e.g. `409` google_id already taken) → redirect to `/settings?linked=error`.

---

## Frontend Changes

### Login page

Add handling for `?error=link_required`:

> "This email is already registered. Sign in with your username and password, then link Google in Settings."

### Settings page — "Connected accounts" card

New card inserted below the Name section. Behavior depends on profile state:

**No `google_id`:**
- Shows "Link Google account" button.
- Clicking the button: sends `GET /api/link-google/start` with `Authorization: Bearer <token>` header, follows the redirect.

**Has `google_id` and has `username` (safe to unlink):**
- Shows "Google connected" status indicator.
- Shows "Unlink" button → calls `DELETE /auth/me/link-google`.

**Has `google_id` but no `username` (Google-only account):**
- Shows "Google connected" status indicator.
- No unlink button (would lock the user out).

**After return from OAuth:**
- `?linked=success` → inline success message: "Google account linked."
- `?linked=error` → inline error message: "Failed to link Google account. It may already be in use."

---

## Security Notes

- State JWT is short-lived (5 min) and signed with `NEXTAUTH_SECRET` — prevents CSRF.
- The Bearer token reconstructed in the callback is a standard HS256 JWT, same as the one NextAuth issues. Backend verifies it as normal.
- Unlink is blocked when the user has no password to prevent account lockout.
