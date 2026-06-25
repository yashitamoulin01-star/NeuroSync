import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Start Session',
  description: 'Initiate a new real-time behavioral analysis session for interview, coaching, or presentation mode.',
}

export default function NewSessionLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
