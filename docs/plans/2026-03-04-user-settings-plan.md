# User Settings Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `/settings` page for all users (profile, avatar, password change, delete account) and move admin sections into a unified sidebar settings UI.

**Architecture:** New `/settings` route with sidebar layout (Profile | Admin section for admins). Four new `/auth/me` backend endpoints secured by a new `require_user` guard. Icon stored as base64 data URL in a new `icon TEXT` column. Admin pages redirect non-admins to `/settings`.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, bcrypt, Next.js 16, next-auth v4, Tailwind, lucide-react

---

### Task 1: DB migration — add `icon` column

**Files:**
- Create: `alembic/versions/07_add_user_icon.py`
- Modify: `backend/models/auth.py`

**Step 1: Create the migration file**

```python
# alembic/versions/07_add_user_icon.py
"""add_user_icon

Revision ID: 07_add_user_icon
Revises: 06_extend_auth_users
Create Date: 2026-03-04
"""
from alembic import op
import sqlalchemy as sa

revision = '07_add_user_icon'
down_revision = '06_extend_auth_users'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('icon', sa.Text(), nullable=True), schema='auth')


def downgrade() -> None:
    op.drop_column('users', 'icon', schema='auth')
```

**Step 2: Add `icon` to the SQLAlchemy model**

In `backend/models/auth.py`, add after the `google_id` line:

```python
icon = Column(sa.Text, nullable=True)
```

(Add `import sqlalchemy as sa` if not present — check the existing imports first; the file currently uses bare `Column` from sqlalchemy, so add `icon = Column(String, nullable=True)` using the existing `String` import.)

**Step 3: Run the migration inside the backend container**

```bash
docker compose exec backend alembic upgrade head
```

Expected: `Running upgrade 06_extend_auth_users -> 07_add_user_icon`

**Step 4: Commit**

```bash
git add alembic/versions/07_add_user_icon.py backend/models/auth.py
git commit -m "🗄️ [FEAT] Add icon column to auth.users"
```

---

### Task 2: Add `require_user` guard

**Files:**
- Modify: `backend/auth/guards.py`

**Step 1: Write the failing test**

In `backend/tests/test_auth.py`, add to the existing test file:

```python
def test_require_user_valid_token(make_token):
    token = make_token(role="user")
    creds = _make_creds(token)
    payload = guards.require_user.impl(creds)
    assert payload["role"] == "user"

def test_require_user_accepts_admin(make_token):
    token = make_token(role="admin")
    creds = _make_creds(token)
    payload = guards.require_user.impl(creds)
    assert payload["role"] == "admin"

def test_require_user_rejects_expired(make_token):
    token = make_token(role="user", exp=int(time.time()) - 1)
    creds = _make_creds(token)
    with pytest.raises(HTTPException) as exc:
        guards.require_user.impl(creds)
    assert exc.value.status_code == 401
```

Check `backend/tests/test_auth.py` for the existing `make_token` and `_make_creds` fixtures/helpers to understand the pattern before adding these tests.

**Step 2: Run to verify failure**

```bash
docker compose exec backend pytest backend/tests/test_auth.py -k "require_user" -v
```

Expected: `ERROR` — `require_user` not defined.

**Step 3: Add `require_user` to guards**

Append to `backend/auth/guards.py`:

```python
def _require_user_impl(token: HTTPAuthorizationCredentials) -> dict:
    secret = os.environ.get("NEXTAUTH_SECRET", "")
    try:
        payload = jwt.decode(token.credentials, secret, algorithms=["HS256"],
                             options={"verify_exp": False})
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    if "exp" not in payload:
        raise HTTPException(status_code=401, detail="Token missing exp claim")
    if payload["exp"] < int(time.time()):
        raise HTTPException(status_code=401, detail="Token expired")

    return payload


def require_user(token: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    return _require_user_impl(token)


require_user.impl = _require_user_impl
```

**Step 4: Run to verify pass**

```bash
docker compose exec backend pytest backend/tests/test_auth.py -k "require_user" -v
```

Expected: 3 PASSED.

**Step 5: Commit**

```bash
git add backend/auth/guards.py backend/tests/test_auth.py
git commit -m "🔐 [FEAT] Add require_user guard for self-service endpoints"
```

---

### Task 3: Add schemas for `/auth/me` endpoints

**Files:**
- Modify: `backend/schemas/user.py`

**Step 1: Add three new schema classes**

Append to `backend/schemas/user.py`:

```python
class UserProfileOut(BaseModel):
    id: UUID
    email: Optional[str] = None
    name: Optional[str] = None
    username: Optional[str] = None
    role: str
    icon: Optional[str] = None
    google_id: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str
```

**Step 2: Commit**

```bash
git add backend/schemas/user.py
git commit -m "📋 [FEAT] Add UserProfileOut, UserProfileUpdate, PasswordChangeRequest schemas"
```

---

### Task 4: Add `/auth/me` endpoints

**Files:**
- Modify: `backend/routers/auth.py`

**Step 1: Write failing tests first** (see Task 5 — write tests before implementing)

**Step 2: Add the imports and endpoints**

At the top of `backend/routers/auth.py`, add to the existing imports:

```python
from backend.auth.guards import require_admin, require_user
from backend.schemas.user import (
    UserOut, UserProfileOut, UserProfileUpdate, PasswordChangeRequest,
    RegisterCredentialsRequest, RegisterGoogleRequest,
    AdminCreateUserRequest, AdminUpdateUserRequest, GoogleAuthorizeRequest,
)
```

Then append four new endpoints after the existing `delete_user` endpoint:

```python
# ---------------------------------------------------------------------------
# Self-service endpoints (any authenticated user)
# ---------------------------------------------------------------------------

@router.get("/me", response_model=UserProfileOut)
def get_me(payload: dict = Depends(require_user), db: Session = Depends(get_db)):
    user = _get_user_by_id(db, UUID(payload["sub"]))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/me", response_model=UserProfileOut)
def update_me(data: UserProfileUpdate, payload: dict = Depends(require_user),
              db: Session = Depends(get_db)):
    user = _get_user_by_id(db, UUID(payload["sub"]))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


@router.post("/me/password", status_code=204)
def change_password(data: PasswordChangeRequest, payload: dict = Depends(require_user),
                    db: Session = Depends(get_db)):
    user = _get_user_by_id(db, UUID(payload["sub"]))
    if not user or not user.hashed_password:
        raise HTTPException(status_code=400,
                            detail="Password change not available for this account")
    if not bcrypt.checkpw(data.current_password.encode(), user.hashed_password.encode()):
        raise HTTPException(status_code=400, detail="Current password incorrect")
    user.hashed_password = bcrypt.hashpw(
        data.new_password.encode(), bcrypt.gensalt()
    ).decode()
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    return Response(status_code=204)


@router.delete("/me", status_code=204)
def delete_me(payload: dict = Depends(require_user), db: Session = Depends(get_db)):
    user = _get_user_by_id(db, UUID(payload["sub"]))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    _delete_user(db, user)
    return Response(status_code=204)
```

---

### Task 5: Backend tests for `/auth/me`

**Files:**
- Modify: `backend/tests/test_auth.py`

**Step 1: Study the existing test file pattern**

Read `backend/tests/test_auth.py` and `backend/tests/conftest.py` to understand the test client setup, how tokens are generated, and how the DB is mocked/used.

**Step 2: Write tests for all four endpoints**

Add a new test class/section:

```python
# --- /auth/me tests ---

def test_get_me_returns_profile(client, user_token, db_user):
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {user_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(db_user.id)
    assert "icon" in data

def test_get_me_unauthorized():
    # No token
    resp = client.get("/auth/me")
    assert resp.status_code == 403  # HTTPBearer returns 403 when no credentials

def test_update_me_name(client, user_token, db_user):
    resp = client.patch("/auth/me",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"name": "New Name"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"

def test_update_me_icon(client, user_token):
    icon = "data:image/webp;base64,abc123"
    resp = client.patch("/auth/me",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"icon": icon})
    assert resp.status_code == 200
    assert resp.json()["icon"] == icon

def test_change_password_success(client, credentials_user_token, credentials_db_user):
    resp = client.post("/auth/me/password",
        headers={"Authorization": f"Bearer {credentials_user_token}"},
        json={"current_password": "testpass", "new_password": "newpass123"})
    assert resp.status_code == 204

def test_change_password_wrong_current(client, credentials_user_token):
    resp = client.post("/auth/me/password",
        headers={"Authorization": f"Bearer {credentials_user_token}"},
        json={"current_password": "wrongpass", "new_password": "newpass123"})
    assert resp.status_code == 400

def test_change_password_google_only_user(client, google_user_token):
    resp = client.post("/auth/me/password",
        headers={"Authorization": f"Bearer {google_user_token}"},
        json={"current_password": "any", "new_password": "any"})
    assert resp.status_code == 400

def test_delete_me(client, user_token):
    resp = client.delete("/auth/me",
        headers={"Authorization": f"Bearer {user_token}"})
    assert resp.status_code == 204
```

Adapt fixture names to match what's in the existing conftest. If fixtures don't exist, create minimal ones that insert a real user into the test DB.

**Step 3: Run tests**

```bash
docker compose exec backend pytest backend/tests/test_auth.py -v
```

Expected: All tests pass.

**Step 4: Commit**

```bash
git add backend/routers/auth.py backend/tests/test_auth.py backend/schemas/user.py
git commit -m "🔐 [FEAT] Add /auth/me self-service endpoints (get, update, password, delete)"
```

---

### Task 6: Frontend — rename `/admin/users` → `/admin/user-management`

**Files:**
- Rename: `frontend/app/admin/users/` → `frontend/app/admin/user-management/`
- Modify: `frontend/app/admin/layout.tsx`
- Modify: `frontend/app/admin/user-management/page.tsx` (update redirect target)

**Step 1: Move the directory**

```bash
mv frontend/app/admin/users frontend/app/admin/user-management
```

**Step 2: Update redirect in the page**

In `frontend/app/admin/user-management/page.tsx`, change the non-admin redirect from `redirect('/')` to `redirect('/settings')`.

**Step 3: Update admin layout sidebar**

In `frontend/app/admin/layout.tsx`, change the `sidebarItems` array:

```ts
const sidebarItems = [
  { href: '/admin/scraper-settings', label: 'Scraper Settings' },
  { href: '/admin/user-management', label: 'User Management' },
]
```

**Step 4: Update scraper-settings redirect**

In `frontend/app/admin/scraper-settings/page.tsx`, change:
```ts
if (status === 'authenticated' && (session?.user as any)?.role !== 'admin') redirect('/login')
```
to:
```ts
if (status === 'authenticated' && (session?.user as any)?.role !== 'admin') redirect('/settings')
```

**Step 5: Commit**

```bash
git add frontend/app/admin/
git commit -m "🔄 [REFACTOR] Rename admin/users → admin/user-management, fix redirects"
```

---

### Task 7: Frontend — settings layout

**Files:**
- Create: `frontend/app/settings/layout.tsx`

**Step 1: Create the layout**

```tsx
'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useSession } from 'next-auth/react'
import { redirect } from 'next/navigation'
import { cn } from '@/lib/utils'

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  const { data: session, status } = useSession()
  const pathname = usePathname()
  const isAdmin = (session?.user as any)?.role === 'admin'

  if (status === 'unauthenticated') redirect('/login')

  const navItems = [
    { href: '/settings', label: 'Profile' },
    ...(isAdmin ? [
      { href: '/admin/scraper-settings', label: 'Scraper Settings', section: 'Admin' },
      { href: '/admin/user-management', label: 'User Management', section: 'Admin' },
    ] : []),
  ]

  return (
    <div className="flex min-h-[calc(100vh-4rem)]">
      <aside className="w-56 shrink-0 border-r border-border pt-8 px-3">
        <p className="px-3 mb-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          Settings
        </p>
        <nav className="space-y-0.5">
          <Link
            href="/settings"
            className={cn(
              'flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-colors duration-150',
              pathname === '/settings'
                ? 'bg-muted text-foreground'
                : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
            )}
          >
            Profile
          </Link>
        </nav>

        {isAdmin && (
          <>
            <p className="px-3 mt-6 mb-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Admin
            </p>
            <nav className="space-y-0.5">
              {[
                { href: '/admin/scraper-settings', label: 'Scraper Settings' },
                { href: '/admin/user-management', label: 'User Management' },
              ].map(item => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-colors duration-150',
                    pathname === item.href
                      ? 'bg-muted text-foreground'
                      : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
                  )}
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </>
        )}
      </aside>

      <main className="flex-1 px-10 py-8 overflow-auto">
        {children}
      </main>
    </div>
  )
}
```

**Step 2: Commit**

```bash
git add frontend/app/settings/layout.tsx
git commit -m "🎨 [FEAT] Add settings layout with sidebar"
```

---

### Task 8: Frontend — settings profile page

**Files:**
- Create: `frontend/app/settings/page.tsx`

**Step 1: Create the icon resize utility**

Add a helper inside the page file (top of file, before the component):

```ts
async function resizeToBase64(file: File, size = 128): Promise<string> {
  return new Promise((resolve) => {
    const img = new Image()
    const url = URL.createObjectURL(file)
    img.onload = () => {
      const canvas = document.createElement('canvas')
      canvas.width = size
      canvas.height = size
      canvas.getContext('2d')!.drawImage(img, 0, 0, size, size)
      URL.revokeObjectURL(url)
      resolve(canvas.toDataURL('image/webp', 0.85))
    }
    img.src = url
  })
}
```

**Step 2: Create the full page component**

```tsx
'use client'
import { useSession } from 'next-auth/react'
import { useState, useEffect, useRef } from 'react'
import { signOut } from 'next-auth/react'
import { apiFetch } from '@/lib/api-fetch'
import { Button } from '@/components/ui/button'

async function resizeToBase64(file: File, size = 128): Promise<string> {
  return new Promise((resolve) => {
    const img = new Image()
    const url = URL.createObjectURL(file)
    img.onload = () => {
      const canvas = document.createElement('canvas')
      canvas.width = size
      canvas.height = size
      canvas.getContext('2d')!.drawImage(img, 0, 0, size, size)
      URL.revokeObjectURL(url)
      resolve(canvas.toDataURL('image/webp', 0.85))
    }
    img.src = url
  })
}

export default function SettingsPage() {
  const { data: session } = useSession()
  const token = (session as any)?.accessToken
  const isGoogleOnly = !(session?.user as any)?.username && !!(session?.user as any)?.google_id

  const [profile, setProfile] = useState<any>(null)
  const [name, setName] = useState('')
  const [icon, setIcon] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [savedMsg, setSavedMsg] = useState('')

  const [currentPw, setCurrentPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [pwMsg, setPwMsg] = useState('')

  const [confirmDelete, setConfirmDelete] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!token) return
    apiFetch('/auth/me', { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json())
      .then(data => {
        setProfile(data)
        setName(data.name ?? '')
        setIcon(data.icon ?? null)
      })
  }, [token])

  async function handleIconChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    const base64 = await resizeToBase64(file)
    setIcon(base64)
  }

  async function handleSaveProfile(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    const res = await apiFetch('/auth/me', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ name, icon }),
    })
    setSaving(false)
    if (res.ok) setSavedMsg('Saved.')
    else setSavedMsg('Failed to save.')
    setTimeout(() => setSavedMsg(''), 3000)
  }

  async function handleChangePassword(e: React.FormEvent) {
    e.preventDefault()
    const res = await apiFetch('/auth/me/password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ current_password: currentPw, new_password: newPw }),
    })
    if (res.ok) {
      setPwMsg('Password changed.')
      setCurrentPw(''); setNewPw('')
    } else {
      const err = await res.json()
      setPwMsg(err.detail ?? 'Failed.')
    }
    setTimeout(() => setPwMsg(''), 4000)
  }

  async function handleDeleteAccount() {
    const res = await apiFetch('/auth/me', {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    })
    if (res.ok) signOut({ callbackUrl: '/login' })
  }

  function initials(n: string) {
    return n ? n.split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase() : '?'
  }

  return (
    <div className="max-w-lg space-y-10">
      <div className="border-b border-border pb-6">
        <h1 className="text-2xl font-bold">Profile</h1>
        <p className="text-sm text-muted-foreground mt-1">Update your personal details.</p>
      </div>

      {/* Profile form */}
      <form onSubmit={handleSaveProfile} className="space-y-6">
        {/* Avatar */}
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            className="h-16 w-16 rounded-full overflow-hidden border-2 border-border hover:border-primary transition-colors shrink-0"
          >
            {icon
              ? <img src={icon} alt="avatar" className="h-full w-full object-cover" />
              : <div className="h-full w-full bg-primary flex items-center justify-center text-primary-foreground text-xl font-bold">
                  {initials(name)}
                </div>
            }
          </button>
          <div>
            <p className="text-sm font-medium">Profile photo</p>
            <p className="text-xs text-muted-foreground">Click to upload. Resized to 128×128.</p>
          </div>
          <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={handleIconChange} />
        </div>

        {/* Name */}
        <div className="space-y-1.5">
          <label className="text-sm font-medium">Name</label>
          <input
            value={name}
            onChange={e => setName(e.target.value)}
            className="w-full h-10 px-3 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>

        <div className="flex items-center gap-3">
          <Button type="submit" disabled={saving}>
            {saving ? 'Saving…' : 'Save changes'}
          </Button>
          {savedMsg && <span className="text-sm text-muted-foreground">{savedMsg}</span>}
        </div>
      </form>

      {/* Password change — credentials users only */}
      {!isGoogleOnly && (
        <div className="space-y-4 border-t border-border pt-8">
          <div>
            <h2 className="text-base font-semibold">Change password</h2>
            <p className="text-sm text-muted-foreground mt-0.5">Choose a strong new password.</p>
          </div>
          <form onSubmit={handleChangePassword} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Current password</label>
              <input
                type="password"
                value={currentPw}
                onChange={e => setCurrentPw(e.target.value)}
                className="w-full h-10 px-3 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">New password</label>
              <input
                type="password"
                value={newPw}
                onChange={e => setNewPw(e.target.value)}
                className="w-full h-10 px-3 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div className="flex items-center gap-3">
              <Button type="submit" variant="outline">Update password</Button>
              {pwMsg && <span className="text-sm text-muted-foreground">{pwMsg}</span>}
            </div>
          </form>
        </div>
      )}

      {/* Delete account */}
      <div className="space-y-3 border-t border-border pt-8">
        <div>
          <h2 className="text-base font-semibold text-destructive">Delete account</h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            Permanently remove your account. This cannot be undone.
          </p>
        </div>
        {!confirmDelete ? (
          <Button variant="outline" className="border-destructive text-destructive hover:bg-destructive/10"
            onClick={() => setConfirmDelete(true)}>
            Delete my account
          </Button>
        ) : (
          <div className="flex items-center gap-3">
            <Button variant="destructive" onClick={handleDeleteAccount}>Yes, delete</Button>
            <Button variant="outline" onClick={() => setConfirmDelete(false)}>Cancel</Button>
          </div>
        )}
      </div>
    </div>
  )
}
```

**Step 3: Commit**

```bash
git add frontend/app/settings/
git commit -m "👤 [FEAT] Add /settings profile page with avatar, name, password, delete"
```

---

### Task 9: Frontend — update NavBar (gear icon, visible to all)

**Files:**
- Modify: `frontend/components/nav-bar.tsx`

**Step 1: Check that `Settings` icon is available in lucide-react**

```bash
grep -r "Settings" frontend/node_modules/lucide-react/dist/esm/icons/ --include="*.js" -l | head -3
```

Expected: some files returned (it exists).

**Step 2: Replace the current Admin link with a gear icon**

In `frontend/components/nav-bar.tsx`:

1. Add `Settings` to the lucide-react import:
   ```ts
   import { Rss, Settings } from 'lucide-react'
   ```

2. In the right nav section, replace the `{isAdmin && <Link>Admin</Link>}` block with:
   ```tsx
   {session && (
     <Link
       href="/settings"
       className="text-muted-foreground hover:text-foreground transition-colors duration-200"
       aria-label="Settings"
     >
       <Settings className="h-5 w-5" />
     </Link>
   )}
   ```

**Step 3: Commit**

```bash
git add frontend/components/nav-bar.tsx
git commit -m "🎨 [FEAT] Replace admin link with settings gear icon in navbar"
```

---

### Task 10: Apply the migration on the running DB and rebuild

**Step 1: Run migration**

```bash
docker compose exec backend alembic upgrade head
```

**Step 2: Rebuild frontend (code changes)**

```bash
docker compose up -d frontend
```

(No rebuild needed — Next.js dev mode hot-reloads. But if HMR misses something:)

```bash
docker compose up -d --build frontend
```

**Step 3: Verify**

- Visit `http://localhost:3000` → gear icon visible in navbar when logged in
- Click gear → `/settings` page with Profile sidebar
- Admin users see Admin section in sidebar
- `/admin/scraper-settings` visited by non-admin → redirects to `/settings`
- Avatar upload resizes and saves
- Password change works for credentials users, hidden for Google-only users
- Delete account signs out and redirects to login
