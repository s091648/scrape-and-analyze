'use client'
import { SettingsLayout } from '@/app/settings/layout'

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return <SettingsLayout>{children}</SettingsLayout>
}
