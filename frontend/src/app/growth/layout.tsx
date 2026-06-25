import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Growth Analytics',
  description: 'Track candidate progression, skill evaluation metrics, and professional growth feedback trends.',
}

export default function GrowthLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
