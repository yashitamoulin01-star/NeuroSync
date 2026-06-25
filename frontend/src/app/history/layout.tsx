import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'History',
  description: 'Browse, search, sort, and review the history of all analyzed behavioral analysis sessions.',
}

export default function HistoryLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
