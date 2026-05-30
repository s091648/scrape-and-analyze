'use client'
import { createContext, useContext, useEffect, useState } from 'react'
import { useSession } from 'next-auth/react'

const STORAGE_KEY = 'guest_mode'

interface GuestModeContextType {
  isGuestMode: boolean
  enterGuestMode: () => void
  exitGuestMode: () => void
}

const GuestModeContext = createContext<GuestModeContextType>({
  isGuestMode: false,
  enterGuestMode: () => {},
  exitGuestMode: () => {},
})

export function GuestModeProvider({ children }: { children: React.ReactNode }) {
  const { status } = useSession()
  const [isGuestMode, setIsGuestMode] = useState(() => {
    if (typeof window === 'undefined') return false
    return sessionStorage.getItem(STORAGE_KEY) === 'true'
  })

  useEffect(() => {
    if (status === 'authenticated') exitGuestMode()
  }, [status])

  function enterGuestMode() {
    sessionStorage.setItem(STORAGE_KEY, 'true')
    setIsGuestMode(true)
  }

  function exitGuestMode() {
    sessionStorage.removeItem(STORAGE_KEY)
    setIsGuestMode(false)
  }

  return (
    <GuestModeContext.Provider value={{ isGuestMode, enterGuestMode, exitGuestMode }}>
      {children}
    </GuestModeContext.Provider>
  )
}

export function useGuestMode() {
  return useContext(GuestModeContext)
}
