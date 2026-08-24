import { create } from 'zustand'
import { fetchUsers, type AdminUser } from '@/lib/api/auth'

interface AdminUsersState {
  users: AdminUser[]
  loaded: boolean
  loading: boolean
  /** Fetches only if nothing's loaded yet — the shared cache both the User Management page
   * and Monitoring's Logs tab (caller-name resolution) read from, so visiting one after the
   * other doesn't re-hit GET /auth/users. */
  ensureLoaded: (token: string) => Promise<void>
  /** Force a refetch — used after the count of users could have changed server-side outside
   * of this store's own mutation methods (there isn't one today, but keeps parity with
   * ensureLoaded for whoever needs it next). */
  refresh: (token: string) => Promise<void>
  upsertUser: (user: AdminUser) => void
  removeUser: (id: string) => void
}

export const useAdminUsersStore = create<AdminUsersState>()((set, get) => ({
  users: [],
  loaded: false,
  loading: false,

  ensureLoaded: async token => {
    if (get().loaded || get().loading || !token) return
    set({ loading: true })
    try {
      const users = await fetchUsers(token)
      set({ users: Array.isArray(users) ? users : [], loaded: true, loading: false })
    } catch {
      set({ loading: false })
    }
  },

  refresh: async token => {
    if (!token) return
    set({ loading: true })
    try {
      const users = await fetchUsers(token)
      set({ users: Array.isArray(users) ? users : [], loaded: true, loading: false })
    } catch {
      set({ loading: false })
    }
  },

  upsertUser: user => set(state => {
    const exists = state.users.some(u => u.id === user.id)
    return {
      users: exists
        ? state.users.map(u => (u.id === user.id ? user : u))
        : [user, ...state.users],
    }
  }),

  removeUser: id => set(state => ({ users: state.users.filter(u => u.id !== id) })),
}))
