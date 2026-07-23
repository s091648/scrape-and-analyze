'use client'
import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { useAuthToken } from './auth-token-provider'
import { apiFetch } from '@/lib/api/client'

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
  // 018-public-api-auth: /chat/quota now requires a token (guest tokens included) —
  // apiFetch() attaches whichever one AuthTokenProvider currently has.
  const { token, isLoading } = useAuthToken()

  const [quota, setQuota] = useState<Quota | null>(null)

  const refreshQuota = useCallback(async () => {
    try {
      const res = await apiFetch('/chat/quota')
      if (res.ok) {
        const data = await res.json()
        setQuota({ remaining: data.remaining, limit: data.limit, tier: data.tier })
      }
    } catch {}
  }, [])

  useEffect(() => {
    if (!isLoading && token) {
      refreshQuota()
    }
  }, [isLoading, token, refreshQuota])

  return (
    <ChatQuotaContext.Provider value={{ quota, refreshQuota }}>
      {children}
    </ChatQuotaContext.Provider>
  )
}

export function useChatQuota() {
  return useContext(ChatQuotaContext)
}
