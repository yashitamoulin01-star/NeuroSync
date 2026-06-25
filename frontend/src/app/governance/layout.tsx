import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Governance & Compliance',
  description: 'Review policy validations, bias logs, human oversight checks, and compliance audits for enterprise AI behavioral evaluation.',
}

export default function GovernanceLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
