# Quickstart: Public API Endpoint Authentication

## For a contributor adding a new endpoint

1. **Does this endpoint need a specific logged-in user or admin?** Use the existing `require_user`/`require_admin` dependency exactly as today — nothing about those changes.
2. **Otherwise, does it need to reject fully-anonymous callers (no token at all)?** If yes (the default for any new endpoint that returns real data — see spec.md FR-001), add the new `require_any_token` dependency (`backend/auth/guards.py`). It accepts a real user/admin token or a guest access token; it does not check role.
3. **Never accept a guest *refresh* token as proof of access** — `require_any_token` already rejects it, so just don't build a second, competing check.

## Verifying the mapping works end-to-end

```bash
# 1. Run backend tests (Docker-only per Constitution Principle III)
make test-backend

# 2. Manually exercise the flow against a running stack
docker compose up -d backend postgres

# 2a. No token at all → 401
curl -i http://localhost:8000/articles
# Expect: HTTP/1.1 401, body {"error": {"code": "UNAUTHORIZED", ...}}

# 2b. Obtain a guest token pair
curl -s -X POST http://localhost:8000/auth/guest | tee /tmp/guest.json
ACCESS=$(jq -r .access_token /tmp/guest.json)
REFRESH=$(jq -r .refresh_token /tmp/guest.json)

# 2c. Guest access token works on a previously-public endpoint
curl -i http://localhost:8000/articles -H "Authorization: Bearer $ACCESS"
# Expect: HTTP/1.1 200, real article data

# 2d. Guest access token still refused on an admin-only endpoint
curl -i http://localhost:8000/scraper-settings -H "Authorization: Bearer $ACCESS"
# Expect: HTTP/1.1 403 (or 401 if the admin check runs before decoding tier — either way, refused)

# 2e. Refresh token cannot be used as an access token
curl -i http://localhost:8000/articles -H "Authorization: Bearer $REFRESH"
# Expect: HTTP/1.1 401

# 2f. Refresh flow returns a fresh access token with the same guest_id
curl -s -X POST http://localhost:8000/auth/guest/refresh -H "Content-Type: application/json" -d "{\"refresh_token\": \"$REFRESH\"}"
# Expect: HTTP/1.1 200, {"access_token": "...", "expires_in": 3600}
```

## Checking existing logged-in flows are unaffected

```bash
# Existing real user/admin JWTs must keep working unchanged on both their existing
# protected endpoints AND the newly-gated ones — no re-login, no new prompt.
curl -i http://localhost:8000/articles -H "Authorization: Bearer $EXISTING_USER_JWT"
curl -i http://localhost:8000/scraper-settings -H "Authorization: Bearer $EXISTING_ADMIN_JWT"
```
