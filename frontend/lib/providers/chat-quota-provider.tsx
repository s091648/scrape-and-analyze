'use client'
import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { useSession } from 'next-auth/react'

const QUOTA_ENDPOINT = '/api/proxy/chat/quota'

export interface Quota {
  remaining: number
  limit: number
  tier: string
}

interface ChatQuotaContextType {
  quota: Quota | null
  refreshQuota: () => Promise<void>
}

const ChatQuotaContext = createContext<ChatQuotaContextType>({
  quota: null,
  refreshQuota: async () => {},
})

export function ChatQuotaProvider({ children }: { children: React.ReactNode }) {
  const { data: session, status } = useSession()
  const [quota, setQuota] = useState<Quota | null>(null)

  const token = (session as any)?.accessToken as string | undefined

  const refreshQuota = useCallback(async () => {
    try {
      const res = await fetch(QUOTA_ENDPOINT, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (res.ok) {
        const data = await res.json()
        setQuota({ remaining: data.remaining, limit: data.limit, tier: data.tier })
      }
    } catch {}
  }, [token])

  useEffect(() => {
    if (status !== 'loading') {
      refreshQuota()
    }
  }, [status, refreshQuota])

  return (
    <ChatQuotaContext.Provider value={{ quota, refreshQuota }}>
      {children}
    </ChatQuotaContext.Provider>
  )
}

export function useChatQuota() {
  return useContext(ChatQuotaContext)
}
