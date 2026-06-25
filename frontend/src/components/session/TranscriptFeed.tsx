'use client'
import { useEffect, useRef } from 'react'
import { cn } from '@/lib/utils'

interface TranscriptEntry {
  timestamp: number
  text: string
  fillerWords?: string[]
}

interface Props {
  entries: TranscriptEntry[]
  live?: boolean
}

function highlight(text: string, fillers: string[]): React.ReactNode[] {
  if (!fillers.length) return [text]
  const pattern = new RegExp(`\\b(${fillers.map(w => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})\\b`, 'gi')
  const parts = text.split(pattern)
  return parts.map((p, i) =>
    fillers.some(f => f.toLowerCase() === p.toLowerCase())
      ? <mark key={i} className="bg-status-warning/20 text-status-warning rounded px-0.5 not-italic">{p}</mark>
      : p
  )
}

export function TranscriptFeed({ entries, live }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (live) bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [entries, live])

  if (!entries.length) {
    return (
      <div className="flex items-center justify-center h-24 text-xs text-text-muted">
        {live ? (
          <span className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-status-danger animate-pulse" />
            Listening for speech…
          </span>
        ) : 'No transcript available'}
      </div>
    )
  }

  return (
    <div className="space-y-3 text-sm text-text-secondary leading-relaxed">
      {entries.map((e, i) => (
        <div key={i} className="flex gap-3 group">
          <span className="text-2xs text-text-muted font-mono tabular-nums pt-0.5 flex-shrink-0 w-8">
            {Math.floor(e.timestamp / 60)}:{String(Math.floor(e.timestamp % 60)).padStart(2, '0')}
          </span>
          <p className="flex-1 text-text-secondary group-hover:text-text-primary transition-colors">
            {highlight(e.text, e.fillerWords ?? [])}
          </p>
        </div>
      ))}
      {live && (
        <div className="flex items-center gap-2 text-xs text-text-muted pl-11">
          <span className="w-1.5 h-1.5 rounded-full bg-status-danger animate-pulse" />
          Recording…
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  )
}
