import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Settings',
  description: 'Adjust account details, API thresholds, models calibration, and system configurations.',
}

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
