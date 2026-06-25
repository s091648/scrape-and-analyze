import React, { useEffect } from 'react'

function DarkWrapper({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    document.documentElement.classList.add('dark')
    return () => document.documentElement.classList.remove('dark')
  }, [])
  return <>{children}</>
}

export const withDarkMode = (Story: React.ComponentType) => (
  <DarkWrapper>
    <Story />
  </DarkWrapper>
)
