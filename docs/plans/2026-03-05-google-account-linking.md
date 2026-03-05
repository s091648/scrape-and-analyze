# Google Account Linking Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace silent Google-to-credentials account auto-linking with an explicit user-initiated link flow from the Settings page, using a signed state JWT round-trip through Google OAuth.

**Architecture:** The `google-login` sign-in callback returns a 409 redirect instead of auto-linking. A pair of custom Next.js API routes (`/api/link-google/start` and `/api/link-google/callback`) implement Option A: the current user's identity is encoded in a short-lived signed state JWT that survives the Google OAuth round-trip without touching NextAuth internals. Backend gains two new authenticated endpoints for link and unlink.

**Tech Stack:** FastAPI (Python), Next.js 14 App Router, NextAuth v4, `jose` (HS256 JWT), Google OAuth 2.0 authorization code flow, Alembic migrations, PostgreSQL.

---

## Pre-flight Checklist

Before starting, confirm:
1. `NEXTAUTH_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `NEXTAUTH_URL`, `BACKEND_URL` are all set in `.env`
2. You can run backend tests: `cd backend && pytest tests/test_auth.py -v`
3. You can run the Alembic CLI: `alembic current` (should show `07_add_user_icon`)
4. **Add `{NEXTAUTH_URL}/api/link-google/callback` as an authorised redirect URI in Google Cloud Console** before Task 5 or the OAuth callback will be rejected by Google.

---

## Task 1: Merge migration 07 into 06

**Files:**
- Modify: `alembic/versions/06_extend_auth_users.py`
- Delete: `alembic/versions/07_add_user_icon.py`

**Step 1: Downgrade the database to revision 05**

```bash
alembic downgrade 05_normalize_tags
alembic current   # should show 05_normalize_tags
```

**Step 2: Add the `icon` column to migration 06**

Open `alembic/versions/06_extend_auth_users.py` and add to the end of `upgrade()`:

```python
    # Icon (merged from 07_add_user_icon)
    op.add_column('users', sa.Column('icon', sa.Text(), nullable=True), schema='auth')
```

And to the start of `downgrade()` (before any other drops):

```python
    op.drop_column('users', 'icon', schema='auth')
```

**Step 3: Delete migration 07**

```bash
rm alembic/versions/07_add_user_icon.py
```

**Step 4: Re-upgrade and verify**

```bash
alembic upgrade head
alembic current   # should show 06_extend_auth_users
```

Expected: no errors. Verify icon column exists:
```bash
psql $DATABASE_URL -c "\d auth.users" | grep icon
```

**Step 5: Commit**

```bash
git add alembic/versions/06_extend_auth_users.py
git rm alembic/versions/07_add_user_icon.py
git commit -m "🗄️ [CHORE] Merge migration 07 (icon) into 06"
```

---

## Task 2: Backend — Modify `/auth/google/authorize` to return 409

**Files:**
- Modify: `backend/routers/auth.py` (lines ~140–151)
- Modify: `backend/tests/test_auth.py`

**Step 1: Write the new failing test**

Add to `backend/tests/test_auth.py`:

```python
def test_google_authorize_unlinked_email_returns_409():
    """Email exists but has no google_id — must not auto-link, return 409."""
    from backend.main import app
    from unittest.mock import patch, MagicMock
    client = TestClient(app)
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    mock_user.email = "creds@test.com"
    mock_user.name = "Creds User"
    mock_user.username = "credsuser"
    mock_user.role = "user"
    mock_user.is_allowed = True
    mock_user.google_id = None      # <-- no google_id linked yet
    mock_user.created_at = None
    mock_user.updated_at = None
    with patch("backend.routers.auth._get_user_by_email", return_value=mock_user):
        response = client.post("/auth/google/authorize", json={
            "email": "creds@test.com", "google_id": "new-sub-456", "name": "Creds User"
        })
    assert response.status_code == 409
```

**Step 2: Run and confirm it fails**

```bash
cd /home/s0916/side/scrape-analyzer
pytest backend/tests/test_auth.py::test_google_authorize_unlinked_email_returns_409 -v
```

Expected: FAIL — the endpoint currently returns 200 and auto-links.

**Step 3: Update the existing test that expects 200 when google_id is None**

The test `test_google_authorize_known_user_returns_200` currently patches `_update_google_id` and expects 200 when `google_id=None`. Change the mock to have `google_id` already set, matching the new 200 path (google_id already matches):

```python
def test_google_authorize_known_user_returns_200():
    """Email exists and google_id already set — sign in succeeds."""
    from backend.main import app
    from unittest.mock import patch, MagicMock
    client = TestClient(app)
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    mock_user.email = "known@test.com"
    mock_user.name = "Known"
    mock_user.username = None
    mock_user.role = "user"
    mock_user.is_allowed = True
    mock_user.google_id = "sub-abc"   # already linked
    mock_user.created_at = None
    mock_user.updated_at = None
    with patch("backend.routers.auth._get_user_by_email", return_value=mock_user):
        response = client.post("/auth/google/authorize", json={
            "email": "known@test.com", "google_id": "sub-abc", "name": "Known"
        })
    assert response.status_code == 200
    assert response.json()["role"] == "user"
```

**Step 4: Implement the change in `backend/routers/auth.py`**

Replace the `google_authorize` function body:

```python
@router.post("/google/authorize", response_model=UserOut)
def google_authorize(data: GoogleAuthorizeRequest, db: Session = Depends(get_db)):
    """Called by NextAuth signIn callback for google-login provider."""
    user = _get_user_by_email(db, data.email)
    if not user:
        raise HTTPException(status_code=404, detail="Email not registered")
    if not user.is_allowed:
        raise HTTPException(status_code=403, detail="Account disabled")
    if not user.google_id:
        raise HTTPException(status_code=409, detail="Google account not linked")
    return user
```

Note: `_update_google_id` is no longer called here. It can remain as a helper — it will be used by the new link endpoint.

**Step 5: Run all auth tests**

```bash
pytest backend/tests/test_auth.py -v
```

Expected: all tests pass.

**Step 6: Commit**

```bash
git add backend/routers/auth.py backend/tests/test_auth.py
git commit -m "🔒 [FEAT] google/authorize returns 409 instead of auto-linking"
```

---

## Task 3: Backend — New link/unlink endpoints

**Files:**
- Modify: `backend/schemas/user.py`
- Modify: `backend/routers/auth.py`
- Modify: `backend/tests/test_auth.py`

**Step 1: Add the request schema**

Add to `backend/schemas/user.py`:

```python
class LinkGoogleRequest(BaseModel):
    google_id: str
```

Also add the import at the top of `backend/routers/auth.py`:

```python
from backend.schemas.user import (
    UserOut, UserProfileOut, UserProfileUpdate, PasswordChangeRequest,
    RegisterCredentialsRequest, RegisterGoogleRequest,
    AdminCreateUserRequest, AdminUpdateUserRequest, GoogleAuthorizeRequest,
    LinkGoogleRequest,
)
```

**Step 2: Write failing tests for both new endpoints**

Add to `backend/tests/test_auth.py`:

```python
def user_token(user_id: str):
    """Create a valid require_user Bearer token for the given user ID."""
    return make_token(role="user", exp_offset=3600)


def test_link_google_success():
    from backend.main import app
    from unittest.mock import patch, MagicMock
    client = TestClient(app)
    user_id = uuid.uuid4()
    mock_user = MagicMock()
    mock_user.id = user_id
    mock_user.google_id = None
    mock_user.username = "alice"
    mock_user.name = "Alice"
    mock_user.email = "alice@test.com"
    mock_user.role = "user"
    mock_user.is_allowed = True
    mock_user.icon = None
    mock_user.created_at = None
    token = make_token(role="user")
    # _get_user_by_id is keyed by payload["sub"] = "admin" (from make_token)
    with patch("backend.routers.auth._get_user_by_id", return_value=mock_user), \
         patch("backend.routers.auth._get_user_by_google_id", return_value=None):
        response = client.post(
            "/auth/me/link-google",
            json={"google_id": "new-google-sub"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 204


def test_link_google_already_linked_returns_400():
    from backend.main import app
    from unittest.mock import patch, MagicMock
    client = TestClient(app)
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    mock_user.google_id = "existing-sub"
    token = make_token(role="user")
    with patch("backend.routers.auth._get_user_by_id", return_value=mock_user):
        response = client.post(
            "/auth/me/link-google",
            json={"google_id": "new-sub"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 400


def test_link_google_id_taken_returns_409():
    from backend.main import app
    from unittest.mock import patch, MagicMock
    client = TestClient(app)
    current_user = MagicMock()
    current_user.id = uuid.uuid4()
    current_user.google_id = None
    other_user = MagicMock()
    other_user.id = uuid.uuid4()
    token = make_token(role="user")
    with patch("backend.routers.auth._get_user_by_id", return_value=current_user), \
         patch("backend.routers.auth._get_user_by_google_id", return_value=other_user):
        response = client.post(
            "/auth/me/link-google",
            json={"google_id": "taken-sub"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 409


def test_unlink_google_success():
    from backend.main import app
    from unittest.mock import patch, MagicMock
    client = TestClient(app)
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    mock_user.google_id = "some-sub"
    mock_user.username = "alice"  # has username — safe to unlink
    token = make_token(role="user")
    with patch("backend.routers.auth._get_user_by_id", return_value=mock_user):
        response = client.delete(
            "/auth/me/link-google",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 204


def test_unlink_google_no_username_returns_400():
    from backend.main import app
    from unittest.mock import patch, MagicMock
    client = TestClient(app)
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    mock_user.google_id = "some-sub"
    mock_user.username = None  # Google-only account — would be locked out
    token = make_token(role="user")
    with patch("backend.routers.auth._get_user_by_id", return_value=mock_user):
        response = client.delete(
            "/auth/me/link-google",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 400
```

**Step 3: Run and confirm they fail**

```bash
pytest backend/tests/test_auth.py -k "link_google or unlink_google" -v
```

Expected: FAIL — endpoints don't exist yet.

**Step 4: Implement the endpoints**

Add to `backend/routers/auth.py`, after the `delete_me` endpoint:

```python
@router.post("/me/link-google", status_code=204)
def link_google(data: LinkGoogleRequest, payload: dict = Depends(require_user),
                db: Session = Depends(get_db)):
    user = _get_user_by_id(db, UUID(payload["sub"]))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.google_id:
        raise HTTPException(status_code=400, detail="Google account already linked")
    if _get_user_by_google_id(db, data.google_id):
        raise HTTPException(status_code=409, detail="Google account already in use")
    _update_google_id(db, user, data.google_id)
    return Response(status_code=204)


@router.delete("/me/link-google", status_code=204)
def unlink_google(payload: dict = Depends(require_user), db: Session = Depends(get_db)):
    user = _get_user_by_id(db, UUID(payload["sub"]))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.username:
        raise HTTPException(status_code=400,
                            detail="Cannot unlink Google from a Google-only account")
    user.google_id = None
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    return Response(status_code=204)
```

**Step 5: Run all auth tests**

```bash
pytest backend/tests/test_auth.py -v
```

Expected: all pass.

**Step 6: Commit**

```bash
git add backend/schemas/user.py backend/routers/auth.py backend/tests/test_auth.py
git commit -m "🔗 [FEAT] Add link/unlink Google endpoints on /auth/me"
```

---

## Task 4: NextAuth — Handle 409 from `google/authorize`

**Files:**
- Modify: `frontend/lib/auth.ts` (lines 68–88)

**Step 1: Update the `google-login` signIn callback**

Find the `google-login` block in `signIn`:

```typescript
if (account?.provider === 'google-login') {
  try {
    const res = await fetch(`${BACKEND_URL}/auth/google/authorize`, { ... })
    if (res.status === 404) return '/login?error=not_registered'
    if (res.status === 403) return '/login?error=account_disabled'
    if (!res.ok) return false
    ...
```

Add the 409 case after the 403 line:

```typescript
    if (res.status === 409) return '/login?error=link_required'
```

The full updated block:

```typescript
if (account?.provider === 'google-login') {
  try {
    const res = await fetch(`${BACKEND_URL}/auth/google/authorize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: user.email,
        google_id: account.providerAccountId,
        name: user.name,
      }),
    })
    if (res.status === 404) return '/login?error=not_registered'
    if (res.status === 403) return '/login?error=account_disabled'
    if (res.status === 409) return '/login?error=link_required'
    if (!res.ok) return false
    const dbUser = await res.json()
    user.id = dbUser.id
    ;(user as any).role = dbUser.role
    return true
  } catch {
    return false
  }
}
```

**Step 2: Verify no TypeScript errors**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

**Step 3: Commit**

```bash
git add frontend/lib/auth.ts
git commit -m "🔒 [FEAT] Redirect to link_required on Google sign-in conflict"
```

---

## Task 5: Next.js API routes — `/api/link-google/start` and `/api/link-google/callback`

**Files:**
- Create: `frontend/app/api/link-google/start/route.ts`
- Create: `frontend/app/api/link-google/callback/route.ts`

**Prerequisites:**
- `NEXTAUTH_URL` must be set in `.env` (e.g. `http://localhost:3000`). This is the base for the callback redirect URI registered in Google Cloud Console.
- The redirect URI `{NEXTAUTH_URL}/api/link-google/callback` must be added to your Google Cloud Console OAuth client's **Authorised redirect URIs**.

**Step 1: Create the start route**

Create `frontend/app/api/link-google/start/route.ts`:

```typescript
import { NextRequest, NextResponse } from 'next/server'
import { SignJWT, jwtVerify } from 'jose'

const SECRET = new TextEncoder().encode(process.env.NEXTAUTH_SECRET!)
const GOOGLE_CLIENT_ID = process.env.GOOGLE_CLIENT_ID!
const NEXTAUTH_URL = process.env.NEXTAUTH_URL!

export async function GET(req: NextRequest) {
  const authHeader = req.headers.get('authorization')
  if (!authHeader?.startsWith('Bearer ')) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }
  const accessToken = authHeader.slice(7)

  let userId: string
  let role: string
  try {
    const { payload } = await jwtVerify(accessToken, SECRET)
    userId = payload.sub as string
    role = payload.role as string
    if (!userId) throw new Error('no sub')
  } catch {
    return NextResponse.json({ error: 'Invalid token' }, { status: 401 })
  }

  // Short-lived state JWT: survives the Google OAuth round-trip (~5 min)
  const state = await new SignJWT({ userId, role })
    .setProtectedHeader({ alg: 'HS256' })
    .setIssuedAt()
    .setExpirationTime('5m')
    .sign(SECRET)

  const redirectUri = `${NEXTAUTH_URL}/api/link-google/callback`
  const params = new URLSearchParams({
    client_id: GOOGLE_CLIENT_ID,
    redirect_uri: redirectUri,
    response_type: 'code',
    scope: 'openid email profile',
    state,
  })

  return NextResponse.redirect(
    `https://accounts.google.com/o/oauth2/v2/auth?${params}`,
    { status: 302 }
  )
}
```

**Step 2: Create the callback route**

Create `frontend/app/api/link-google/callback/route.ts`:

```typescript
import { NextRequest, NextResponse } from 'next/server'
import { SignJWT, jwtVerify } from 'jose'

const SECRET = new TextEncoder().encode(process.env.NEXTAUTH_SECRET!)
const GOOGLE_CLIENT_ID = process.env.GOOGLE_CLIENT_ID!
const GOOGLE_CLIENT_SECRET = process.env.GOOGLE_CLIENT_SECRET!
const NEXTAUTH_URL = process.env.NEXTAUTH_URL!
// Internal URL for server-to-server calls (Docker/Railway)
const BACKEND_URL = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

export async function GET(req: NextRequest) {
  const { searchParams } = req.nextUrl
  const code = searchParams.get('code')
  const state = searchParams.get('state')
  const errorParam = searchParams.get('error')

  if (errorParam || !code || !state) {
    return NextResponse.redirect(`${NEXTAUTH_URL}/settings?linked=error`)
  }

  // 1. Verify state JWT
  let userId: string
  let role: string
  try {
    const { payload } = await jwtVerify(state, SECRET)
    userId = payload.userId as string
    role = payload.role as string
    if (!userId) throw new Error('no userId')
  } catch {
    return NextResponse.redirect(`${NEXTAUTH_URL}/settings?linked=error`)
  }

  // 2. Exchange code for Google tokens
  const redirectUri = `${NEXTAUTH_URL}/api/link-google/callback`
  let googleId: string
  try {
    const tokenRes = await fetch('https://oauth2.googleapis.com/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        code,
        client_id: GOOGLE_CLIENT_ID,
        client_secret: GOOGLE_CLIENT_SECRET,
        redirect_uri: redirectUri,
        grant_type: 'authorization_code',
      }),
    })
    if (!tokenRes.ok) throw new Error('token exchange failed')
    const tokenData = await tokenRes.json()

    // id_token is a JWT; decode without verification (Google already verified it)
    const [, payloadB64] = tokenData.id_token.split('.')
    const idPayload = JSON.parse(Buffer.from(payloadB64, 'base64url').toString())
    googleId = idPayload.sub
    if (!googleId) throw new Error('no sub in id_token')
  } catch {
    return NextResponse.redirect(`${NEXTAUTH_URL}/settings?linked=error`)
  }

  // 3. Construct a short-lived backend bearer token for this user
  const bearerToken = await new SignJWT({ sub: userId, role })
    .setProtectedHeader({ alg: 'HS256' })
    .setIssuedAt()
    .setExpirationTime('2m')
    .sign(SECRET)

  // 4. Call the backend link endpoint
  try {
    const linkRes = await fetch(`${BACKEND_URL}/auth/me/link-google`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${bearerToken}`,
      },
      body: JSON.stringify({ google_id: googleId }),
    })
    if (!linkRes.ok) {
      return NextResponse.redirect(`${NEXTAUTH_URL}/settings?linked=error`)
    }
  } catch {
    return NextResponse.redirect(`${NEXTAUTH_URL}/settings?linked=error`)
  }

  return NextResponse.redirect(`${NEXTAUTH_URL}/settings?linked=success`)
}
```

**Step 3: Verify TypeScript**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

**Step 4: Commit**

```bash
git add frontend/app/api/link-google/
git commit -m "🔗 [FEAT] Add /api/link-google/start and /callback routes"
```

---

## Task 6: Login page — `link_required` error message

**Files:**
- Modify: `frontend/app/login/page.tsx`

**Step 1: Add the `link_required` case**

In `LoginPage`, find the line:

```typescript
const notRegistered = authError === 'not_registered'
const disabled = authError === 'account_disabled'
```

Add after:

```typescript
const linkRequired = authError === 'link_required'
```

In the error block JSX, add alongside the other conditions:

```tsx
{linkRequired && (
  <p>
    This email is already registered. Sign in with your username and password,
    then link Google in{' '}
    <Link href="/settings" className="underline font-medium">Settings</Link>.
  </p>
)}
```

And include `linkRequired` in the outer condition:

```tsx
{(error || notRegistered || disabled || linkRequired) && (
```

**Step 2: Verify TypeScript**

```bash
cd frontend && npx tsc --noEmit
```

**Step 3: Commit**

```bash
git add frontend/app/login/page.tsx
git commit -m "💬 [FEAT] Show link_required message on login page"
```

---

## Task 7: Settings page — Connected accounts card

**Files:**
- Modify: `frontend/app/settings/page.tsx`

**Step 1: Read the existing `useSearchParams` import situation**

The page is already `'use client'` and imports `useSession`. Add `useSearchParams` and `useEffect`/`useRouter` for the query param feedback. `useEffect` is already imported. Add `useSearchParams` and `useRouter`:

```typescript
import { useEffect, useRef, useState } from 'react'
import { useSession, signOut } from 'next-auth/react'
import { useSearchParams, useRouter } from 'next/navigation'
```

**Step 2: Add state and effect for the `linked` query param**

After the existing state declarations, add:

```typescript
const searchParams = useSearchParams()
const router = useRouter()
const [linkMsg, setLinkMsg] = useState<{ ok: boolean; text: string } | null>(null)

useEffect(() => {
  const linked = searchParams.get('linked')
  if (linked === 'success') {
    setLinkMsg({ ok: true, text: 'Google account linked successfully.' })
    setProfile(prev => prev ? { ...prev, google_id: '__linked__' } : prev)
    router.replace('/settings')
  } else if (linked === 'error') {
    setLinkMsg({ ok: false, text: 'Failed to link Google account. It may already be in use.' })
    router.replace('/settings')
  }
}, [searchParams, router])
```

**Step 3: Add the handleUnlinkGoogle function**

After `handleDeleteAccount`:

```typescript
async function handleUnlinkGoogle() {
  if (!confirm('Unlink your Google account?')) return
  const res = await apiFetch('/auth/me/link-google', {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (res.ok) {
    setProfile(prev => prev ? { ...prev, google_id: null } : prev)
    setLinkMsg({ ok: true, text: 'Google account unlinked.' })
  } else {
    setLinkMsg({ ok: false, text: 'Failed to unlink.' })
  }
}
```

**Step 4: Add the "Connected accounts" card JSX**

Insert the new card between the Name section and the Password section (after the closing `</div>` of the Name card, before the `{profile && !profile.google_id && (` block):

```tsx
{/* Connected accounts */}
<div className="rounded-2xl border border-border bg-card p-6 space-y-4">
  <h2 className="font-semibold text-sm">Connected accounts</h2>

  {linkMsg && (
    <p className={`text-sm ${linkMsg.ok ? 'text-green-600' : 'text-destructive'}`}>
      {linkMsg.text}
    </p>
  )}

  <div className="flex items-center justify-between">
    <div className="flex items-center gap-3">
      {/* Google icon */}
      <svg className="h-5 w-5 shrink-0" viewBox="0 0 24 24">
        <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
        <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
        <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
        <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
      </svg>
      <div>
        <p className="text-sm font-medium">Google</p>
        <p className="text-xs text-muted-foreground">
          {profile?.google_id ? 'Connected' : 'Not connected'}
        </p>
      </div>
    </div>

    {profile && !profile.google_id && (
      <Button
        variant="outline"
        size="sm"
        onClick={() => {
          // Redirect via the start route — the Bearer token is passed in the header.
          // We can't send custom headers on a browser redirect, so we hit our
          // own Next.js route first (it will be a server-side redirect to Google).
          fetch('/api/link-google/start', {
            headers: { Authorization: `Bearer ${token}` },
            redirect: 'manual',
          }).then(res => {
            // res.type === 'opaqueredirect' means the server redirected us.
            // Follow the redirect by navigating the browser to the same URL.
            if (res.type === 'opaqueredirect' || res.status === 302 || res.url.includes('google')) {
              window.location.href = res.url || '/api/link-google/start'
            } else {
              window.location.href = '/api/link-google/start'
            }
          }).catch(() => {
            window.location.href = '/api/link-google/start'
          })
        }}
      >
        Link Google
      </Button>
    )}

    {profile?.google_id && profile.username && (
      <Button
        variant="outline"
        size="sm"
        className="text-destructive border-destructive/40 hover:bg-destructive/10 hover:text-destructive"
        onClick={handleUnlinkGoogle}
      >
        Unlink
      </Button>
    )}
  </div>
</div>
```

> **Note on the Link button approach:** The `/api/link-google/start` route requires an `Authorization` header, but browsers cannot set headers on navigation. The `fetch(..., { redirect: 'manual' })` trick captures the redirect response and extracts the URL. However, since the redirect goes to `accounts.google.com`, the `res.url` will be empty due to CORS opaque response rules. The simplest fix is to make `/api/link-google/start` return the Google OAuth URL as JSON instead of a redirect, and then `window.location.href = url` from the client. **Update the start route** to accept this pattern:

**Step 5: Adjust `/api/link-google/start` to return JSON**

In `frontend/app/api/link-google/start/route.ts`, replace the final `return NextResponse.redirect(...)` with:

```typescript
  return NextResponse.json({ url: `https://accounts.google.com/o/oauth2/v2/auth?${params}` })
```

And update the button's `onClick` in the settings page:

```tsx
onClick={async () => {
  const res = await fetch('/api/link-google/start', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (res.ok) {
    const { url } = await res.json()
    window.location.href = url
  }
}}
```

**Step 6: Verify TypeScript**

```bash
cd frontend && npx tsc --noEmit
```

**Step 7: Commit**

```bash
git add frontend/app/settings/page.tsx frontend/app/api/link-google/start/route.ts
git commit -m "🔗 [FEAT] Connected accounts card in Settings with Google link/unlink"
```

---

## Task 8: Manual smoke test

Run the app and verify all paths work end-to-end:

```bash
docker compose up --build
```

**Checklist:**
- [ ] Credentials user signs in with Google (same email) → sees "link_required" message on login page
- [ ] Credentials user goes to Settings → sees "Google — Not connected" + "Link Google" button
- [ ] Clicks "Link Google" → redirected to Google → returns to `/settings?linked=success` → card shows "Connected"
- [ ] Unlink button appears (user has `username`) → click → card shows "Not connected"
- [ ] Google-only user (no `username`) → no Unlink button shown
- [ ] `alembic current` shows `06_extend_auth_users`

---

## Summary of New Files

| File | Purpose |
|---|---|
| `frontend/app/api/link-google/start/route.ts` | Verifies Bearer token, returns Google OAuth URL |
| `frontend/app/api/link-google/callback/route.ts` | Exchanges code, links google_id via backend |

## Summary of Modified Files

| File | Change |
|---|---|
| `alembic/versions/06_extend_auth_users.py` | + icon column, absorbed from 07 |
| `alembic/versions/07_add_user_icon.py` | Deleted |
| `backend/schemas/user.py` | + `LinkGoogleRequest` |
| `backend/routers/auth.py` | 409 on authorize, + link/unlink endpoints |
| `backend/tests/test_auth.py` | Updated 200 test, + 5 new tests |
| `frontend/lib/auth.ts` | + 409 → link_required redirect |
| `frontend/app/login/page.tsx` | + link_required error message |
| `frontend/app/settings/page.tsx` | + Connected accounts card |
