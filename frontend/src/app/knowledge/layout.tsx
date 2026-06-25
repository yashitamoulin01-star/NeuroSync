import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Behavioral Knowledge Base',
  description: 'Access the knowledge base of research-backed behavioral indicators, training checksheets, and signal references.',
}

export default function KnowledgeLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
