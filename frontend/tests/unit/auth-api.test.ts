import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockApiFetch = vi.fn()
vi.mock('@/lib/api/client', () => ({ apiFetch: mockApiFetch }))

beforeEach(() => vi.clearAllMocks())

describe('auth API', () => {
  const token = 'test-token'

  function mockOk(data: any) {
    mockApiFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve(data) })
  }

  function mockFail(status = 500) {
    mockApiFetch.mockResolvedValue({ ok: false, status })
  }

  describe('fetchMe', () => {
    it('returns user profile when response is ok', async () => {
      const profile = { id: 'u1', username: 'alice', name: 'Alice', email: 'alice@example.com', icon: null, role: 'admin', google_id: null }
      mockOk(profile)
      const { fetchMe } = await import('@/lib/api/auth')
      const result = await fetchMe(token)
      expect(mockApiFetch).toHaveBeenCalledWith(
        '/auth/me',
        expect.objectContaining({ headers: { Authorization: `Bearer ${token}` } }),
        undefined,
        { silent: true },
      )
      expect(result).toEqual(profile)
    })

    it('returns null when response is not ok', async () => {
      mockFail(401)
      const { fetchMe } = await import('@/lib/api/auth')
      const result = await fetchMe(token)
      expect(result).toBeNull()
    })

    it('passes locale to apiFetch', async () => {
      mockOk({})
      const { fetchMe } = await import('@/lib/api/auth')
      await fetchMe(token, 'zh-TW')
      expect(mockApiFetch).toHaveBeenCalledWith(expect.any(String), expect.any(Object), 'zh-TW', { silent: true })
    })
  })

  describe('updateMe', () => {
    it('patches /auth/me with body and auth header', async () => {
      mockOk({})
      const { updateMe } = await import('@/lib/api/auth')
      await updateMe(token, { name: 'Bob' })
      expect(mockApiFetch).toHaveBeenCalledWith('/auth/me', expect.objectContaining({
        method: 'PATCH',
        headers: expect.objectContaining({ Authorization: `Bearer ${token}` }),
        body: JSON.stringify({ name: 'Bob' }),
      }), undefined, { silent: true })
    })
  })

  describe('changePassword', () => {
    it('posts to /auth/me/password with credentials', async () => {
      mockOk({})
      const { changePassword } = await import('@/lib/api/auth')
      await changePassword(token, { current_password: 'old', new_password: 'new123' })
      expect(mockApiFetch).toHaveBeenCalledWith('/auth/me/password', expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: `Bearer ${token}` }),
        body: JSON.stringify({ current_password: 'old', new_password: 'new123' }),
      }), undefined, { silent: true })
    })
  })

  describe('deleteMe', () => {
    it('sends DELETE to /auth/me with auth header', async () => {
      mockApiFetch.mockResolvedValue({ ok: true })
      const { deleteMe } = await import('@/lib/api/auth')
      await deleteMe(token)
      expect(mockApiFetch).toHaveBeenCalledWith('/auth/me', expect.objectContaining({
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      }), undefined, { silent: true })
    })
  })

  describe('unlinkGoogle', () => {
    it('sends DELETE to /auth/me/link-google', async () => {
      mockApiFetch.mockResolvedValue({ ok: true })
      const { unlinkGoogle } = await import('@/lib/api/auth')
      await unlinkGoogle(token)
      expect(mockApiFetch).toHaveBeenCalledWith('/auth/me/link-google', expect.objectContaining({
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      }), undefined, { silent: true })
    })
  })

  describe('registerUser', () => {
    it('posts to /auth/register without auth header', async () => {
      mockOk({})
      const { registerUser } = await import('@/lib/api/auth')
      const body = { username: 'alice', password: 'pass123', email: 'alice@example.com', name: 'Alice' }
      await registerUser(body)
      expect(mockApiFetch).toHaveBeenCalledWith('/auth/register', expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }), undefined, { silent: true })
    })

    it('works without optional name field', async () => {
      mockOk({})
      const { registerUser } = await import('@/lib/api/auth')
      await registerUser({ username: 'bob', password: 'pass', email: 'bob@example.com' })
      expect(mockApiFetch).toHaveBeenCalled()
    })
  })

  describe('fetchUsers', () => {
    it('fetches user list with auth header', async () => {
      const users = [{ id: 'u1', email: 'a@example.com', name: 'Alice', username: 'alice', role: 'admin' as const, is_allowed: true, icon: null, google_id: null, created_at: null }]
      mockOk(users)
      const { fetchUsers } = await import('@/lib/api/auth')
      const result = await fetchUsers(token)
      expect(mockApiFetch).toHaveBeenCalledWith('/auth/users', expect.objectContaining({
        headers: { Authorization: `Bearer ${token}` },
      }), undefined)
      expect(result).toEqual(users)
    })
  })

  describe('updateUser', () => {
    it('patches user by id with body and auth header', async () => {
      mockOk({})
      const { updateUser } = await import('@/lib/api/auth')
      await updateUser(token, 'u1', { role: 'admin' })
      expect(mockApiFetch).toHaveBeenCalledWith('/auth/users/u1', expect.objectContaining({
        method: 'PATCH',
        headers: expect.objectContaining({ Authorization: `Bearer ${token}` }),
        body: JSON.stringify({ role: 'admin' }),
      }), undefined)
    })

    it('can update is_allowed flag', async () => {
      mockOk({})
      const { updateUser } = await import('@/lib/api/auth')
      await updateUser(token, 'u2', { is_allowed: false })
      expect(mockApiFetch).toHaveBeenCalledWith('/auth/users/u2', expect.objectContaining({
        body: JSON.stringify({ is_allowed: false }),
      }), undefined)
    })
  })

  describe('deleteUser', () => {
    it('sends DELETE to /auth/users/:id with auth header', async () => {
      mockApiFetch.mockResolvedValue({ ok: true })
      const { deleteUser } = await import('@/lib/api/auth')
      await deleteUser(token, 'u1')
      expect(mockApiFetch).toHaveBeenCalledWith('/auth/users/u1', expect.objectContaining({
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      }), undefined)
    })
  })

  describe('createUser', () => {
    it('posts to /auth/users with body and auth header', async () => {
      mockOk({ id: 'u3' })
      const { createUser } = await import('@/lib/api/auth')
      await createUser(token, { email: 'bob@example.com', role: 'user' })
      expect(mockApiFetch).toHaveBeenCalledWith('/auth/users', expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: `Bearer ${token}` }),
        body: JSON.stringify({ email: 'bob@example.com', role: 'user' }),
      }), undefined)
    })

    it('supports username and password fields', async () => {
      mockOk({})
      const { createUser } = await import('@/lib/api/auth')
      await createUser(token, { username: 'charlie', password: 'secret', role: 'user' })
      expect(mockApiFetch).toHaveBeenCalledWith('/auth/users', expect.objectContaining({
        body: JSON.stringify({ username: 'charlie', password: 'secret', role: 'user' }),
      }), undefined)
    })
  })
})
