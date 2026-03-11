'use client'
import { useEffect, useState } from 'react'
import { useSession } from 'next-auth/react'
import { redirect } from 'next/navigation'
import { apiFetch } from '@/lib/api-fetch'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'

interface User {
  id: string
  email: string | null
  name: string | null
  username: string | null
  role: 'admin' | 'user'
  is_allowed: boolean
  google_id: string | null
  created_at: string | null
}

export default function UsersPage() {
  const { data: session, status } = useSession()
  const [users, setUsers] = useState<User[]>([])
  const [creating, setCreating] = useState(false)
  const [newEmail, setNewEmail] = useState('')
  const [newRole, setNewRole] = useState<'admin' | 'user'>('user')
  const [newUsername, setNewUsername] = useState('')
  const [newPassword, setNewPassword] = useState('')

  if (status === 'unauthenticated') redirect('/login')
  if (status === 'authenticated' && (session?.user as any)?.role !== 'admin') redirect('/settings')

  const token = (session as any)?.accessToken

  useEffect(() => {
    if (!token) return
    apiFetch('/auth/users', { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json())
      .then(setUsers)
  }, [token])

  async function toggleAllowed(user: User) {
    const res = await apiFetch(`/auth/users/${user.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ is_allowed: !user.is_allowed }),
    }, false)
    if (res.ok) setUsers(users.map(u => u.id === user.id ? { ...u, is_allowed: !u.is_allowed } : u))
  }

  async function changeRole(user: User, role: 'admin' | 'user') {
    const res = await apiFetch(`/auth/users/${user.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ role }),
    }, false)
    if (res.ok) setUsers(users.map(u => u.id === user.id ? { ...u, role } : u))
  }

  async function deleteUser(userId: string) {
    if (!confirm('Delete this user?')) return
    const res = await apiFetch(`/auth/users/${userId}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    }, false)
    if (res.ok) setUsers(users.filter(u => u.id !== userId))
  }

  async function createUser(e: React.FormEvent) {
    e.preventDefault()
    const body: Record<string, string> = { role: newRole }
    if (newEmail) body.email = newEmail
    if (newUsername) body.username = newUsername
    if (newPassword) body.password = newPassword
    const res = await apiFetch('/auth/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify(body),
    }, false)
    if (res.ok) {
      const created = await res.json()
      setUsers([created, ...users])
      setCreating(false)
      setNewEmail(''); setNewUsername(''); setNewPassword(''); setNewRole('user')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">User Management</h1>
          <p className="text-sm text-muted-foreground mt-1">Manage user accounts and roles</p>
        </div>
        <Button onClick={() => setCreating(!creating)} variant={creating ? 'outline' : 'default'}>
          {creating ? 'Cancel' : 'Add user'}
        </Button>
      </div>

      {creating && (
        <form onSubmit={createUser}
          className="rounded-2xl border border-border bg-card p-6 space-y-4">
          <h2 className="font-semibold text-sm">New user</h2>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Email</label>
              <input value={newEmail} onChange={e => setNewEmail(e.target.value)}
                placeholder="user@example.com"
                className="w-full h-10 px-3 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Role</label>
              <select value={newRole} onChange={e => setNewRole(e.target.value as 'admin' | 'user')}
                className="w-full h-10 px-3 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring">
                <option value="user">user</option>
                <option value="admin">admin</option>
              </select>
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Username (optional)</label>
              <input value={newUsername} onChange={e => setNewUsername(e.target.value)}
                className="w-full h-10 px-3 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Password (if username set)</label>
              <input type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)}
                className="w-full h-10 px-3 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
            </div>
          </div>
          <Button type="submit" size="sm">Create user</Button>
        </form>
      )}

      <div className="rounded-2xl border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/40 border-b border-border">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">User</th>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">Auth</th>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">Role</th>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">Active</th>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">Joined</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {users.map(user => (
              <tr key={user.id} className="hover:bg-muted/20 transition-colors">
                <td className="px-4 py-3">
                  <div className="font-medium">{user.name ?? user.username ?? '—'}</div>
                  <div className="text-xs text-muted-foreground">{user.email ?? user.username}</div>
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-1 flex-wrap">
                    {user.username && (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-muted font-medium">
                        credentials
                      </span>
                    )}
                    {user.google_id && (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 font-medium">
                        google
                      </span>
                    )}
                  </div>
                </td>
                <td className="px-4 py-3">
                  <select
                    value={user.role}
                    onChange={e => changeRole(user, e.target.value as 'admin' | 'user')}
                    className="h-8 px-2 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  >
                    <option value="user">user</option>
                    <option value="admin">admin</option>
                  </select>
                </td>
                <td className="px-4 py-3">
                  <Switch checked={user.is_allowed} onCheckedChange={() => toggleAllowed(user)} />
                </td>
                <td className="px-4 py-3 text-xs text-muted-foreground">
                  {user.created_at ? new Date(user.created_at).toLocaleDateString() : '—'}
                </td>
                <td className="px-4 py-3 text-right">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-destructive hover:text-destructive hover:bg-destructive/10"
                    onClick={() => deleteUser(user.id)}
                  >
                    Delete
                  </Button>
                </td>
              </tr>
            ))}
            {users.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground text-sm">
                  No users found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
