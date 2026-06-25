import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Session Report',
  description: 'Examine detailed multi-modal behavioral results, confidence scores, stress metrics, timeline analysis, and suggested follow-up questions.',
}

export default function SessionResultsLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
