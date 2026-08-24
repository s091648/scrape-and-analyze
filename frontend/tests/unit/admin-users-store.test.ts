import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { AdminUser } from '@/lib/api/auth'

vi.mock('@/lib/api/auth', () => ({
  fetchUsers: vi.fn(),
}))

function makeUser(overrides: Partial<AdminUser> = {}): AdminUser {
  return {
    id: 'u1',
    email: 'a@example.com',
    name: 'Alice',
    username: 'alice',
    role: 'user',
    is_allowed: true,
    icon: null,
    google_id: null,
    created_at: null,
    ...overrides,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
})

async function freshStore() {
  vi.resetModules()
  const { useAdminUsersStore } = await import('@/lib/stores/admin-users-store')
  const { fetchUsers } = await import('@/lib/api/auth') as unknown as { fetchUsers: ReturnType<typeof vi.fn> }
  return { useAdminUsersStore, fetchUsers }
}

describe('useAdminUsersStore.ensureLoaded', () => {
  it('fetches and stores users on first call', async () => {
    const { useAdminUsersStore, fetchUsers } = await freshStore()
    const users = [makeUser({ id: 'u1' }), makeUser({ id: 'u2' })]
    fetchUsers.mockResolvedValueOnce(users)

    await useAdminUsersStore.getState().ensureLoaded('token-1')

    expect(fetchUsers).toHaveBeenCalledWith('token-1')
    const state = useAdminUsersStore.getState()
    expect(state.users).toEqual(users)
    expect(state.loaded).toBe(true)
    expect(state.loading).toBe(false)
  })

  it('does not fetch again once already loaded', async () => {
    const { useAdminUsersStore, fetchUsers } = await freshStore()
    fetchUsers.mockResolvedValueOnce([makeUser()])
    await useAdminUsersStore.getState().ensureLoaded('token-1')

    await useAdminUsersStore.getState().ensureLoaded('token-1')

    expect(fetchUsers).toHaveBeenCalledTimes(1)
  })

  it('does not fetch when a load is already in flight', async () => {
    const { useAdminUsersStore, fetchUsers } = await freshStore()
    let resolveFetch: (users: AdminUser[]) => void = () => {}
    fetchUsers.mockReturnValueOnce(new Promise(resolve => { resolveFetch = resolve }))

    const firstCall = useAdminUsersStore.getState().ensureLoaded('token-1')
    await useAdminUsersStore.getState().ensureLoaded('token-1')

    expect(fetchUsers).toHaveBeenCalledTimes(1)
    resolveFetch([makeUser()])
    await firstCall
  })

  it('does not fetch when token is empty', async () => {
    const { useAdminUsersStore, fetchUsers } = await freshStore()

    await useAdminUsersStore.getState().ensureLoaded('')

    expect(fetchUsers).not.toHaveBeenCalled()
    expect(useAdminUsersStore.getState().loaded).toBe(false)
  })

  it('sets loading back to false without marking loaded when the API rejects', async () => {
    const { useAdminUsersStore, fetchUsers } = await freshStore()
    fetchUsers.mockRejectedValueOnce(new Error('network error'))

    await useAdminUsersStore.getState().ensureLoaded('token-1')

    const state = useAdminUsersStore.getState()
    expect(state.loading).toBe(false)
    expect(state.loaded).toBe(false)
    expect(state.users).toEqual([])
  })

  it('normalizes a non-array response to an empty user list', async () => {
    const { useAdminUsersStore, fetchUsers } = await freshStore()
    fetchUsers.mockResolvedValueOnce(null as unknown as AdminUser[])

    await useAdminUsersStore.getState().ensureLoaded('token-1')

    const state = useAdminUsersStore.getState()
    expect(state.users).toEqual([])
    expect(state.loaded).toBe(true)
  })
})

describe('useAdminUsersStore.refresh', () => {
  it('re-fetches even when already loaded', async () => {
    const { useAdminUsersStore, fetchUsers } = await freshStore()
    fetchUsers.mockResolvedValueOnce([makeUser({ id: 'u1' })])
    await useAdminUsersStore.getState().ensureLoaded('token-1')

    fetchUsers.mockResolvedValueOnce([makeUser({ id: 'u1' }), makeUser({ id: 'u2' })])
    await useAdminUsersStore.getState().refresh('token-1')

    expect(fetchUsers).toHaveBeenCalledTimes(2)
    expect(useAdminUsersStore.getState().users).toHaveLength(2)
  })

  it('does nothing when token is empty', async () => {
    const { useAdminUsersStore, fetchUsers } = await freshStore()

    await useAdminUsersStore.getState().refresh('')

    expect(fetchUsers).not.toHaveBeenCalled()
  })

  it('sets loading back to false when the API rejects', async () => {
    const { useAdminUsersStore, fetchUsers } = await freshStore()
    fetchUsers.mockRejectedValueOnce(new Error('boom'))

    await useAdminUsersStore.getState().refresh('token-1')

    expect(useAdminUsersStore.getState().loading).toBe(false)
  })
})

describe('useAdminUsersStore.upsertUser', () => {
  it('prepends a new user', async () => {
    const { useAdminUsersStore } = await freshStore()
    useAdminUsersStore.setState({ users: [makeUser({ id: 'existing' })] })

    useAdminUsersStore.getState().upsertUser(makeUser({ id: 'new' }))

    const ids = useAdminUsersStore.getState().users.map(u => u.id)
    expect(ids).toEqual(['new', 'existing'])
  })

  it('replaces an existing user in place', async () => {
    const { useAdminUsersStore } = await freshStore()
    useAdminUsersStore.setState({ users: [makeUser({ id: 'u1', name: 'Old Name' })] })

    useAdminUsersStore.getState().upsertUser(makeUser({ id: 'u1', name: 'New Name' }))

    const state = useAdminUsersStore.getState()
    expect(state.users).toHaveLength(1)
    expect(state.users[0].name).toBe('New Name')
  })
})

describe('useAdminUsersStore.removeUser', () => {
  it('removes the matching user by id', async () => {
    const { useAdminUsersStore } = await freshStore()
    useAdminUsersStore.setState({ users: [makeUser({ id: 'u1' }), makeUser({ id: 'u2' })] })

    useAdminUsersStore.getState().removeUser('u1')

    expect(useAdminUsersStore.getState().users.map(u => u.id)).toEqual(['u2'])
  })
})
