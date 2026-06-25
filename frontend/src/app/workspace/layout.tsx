import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Workspace',
  description: 'Manage interview workspace, active candidate workflows, team collaborations, and recruiter actions.',
}

export default function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
