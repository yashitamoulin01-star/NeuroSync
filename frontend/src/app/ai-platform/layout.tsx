import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'AI Platform Diagnostics',
  description: 'Monitor fine-tuned DeBERTa metrics, Whisper model loads, real-time latency, and model transparency data.',
}

export default function AIPlatformLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
