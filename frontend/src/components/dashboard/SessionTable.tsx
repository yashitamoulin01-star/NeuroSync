'use client'
import Link from 'next/link'
import { formatDuration, formatScore, cn } from '@/lib/utils'
import { Badge } from '@/components/ui/Badge'
import { ArrowUpRight, Clock, Brain, BarChart2 } from 'lucide-react'
import { memo } from 'react'
import { motion } from 'framer-motion'

export interface SessionRow {
  id:         string
  name:       string
  mode:       string
  startedAt:  string
  duration:   number
  confidence: number
  stress:     number
  communication: number
  engagement: number
  fillerWords: number
  wordsSpoken: number
}

interface Props {
  rows: SessionRow[]
  loading?: boolean
}

function ScoreCell({ value, invert }: { value: number; invert?: boolean }) {
  const v = invert ? 1 - value : value
  const color =
    v >= 0.75 ? 'text-metric-engagement' :
    v >= 0.50 ? 'text-metric-consistency' :
    v >= 0.25 ? 'text-status-warning' :
                'text-metric-stress'
  return (
    <span className={cn('font-mono text-xs font-medium tabular-nums', color)}>
      {formatScore(value)}
    </span>
  )
}

const MODE_BADGE: Record<string, 'accent' | 'success' | 'warning'> = {
  interview:    'accent',
  coaching:     'success',
  presentation: 'warning',
}

export const SessionTable = memo(function SessionTable({ rows, loading }: Props) {
  if (loading) {
    return (
      <div className="space-y-2">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-12 rounded-lg bg-bg-hover animate-pulse" />
        ))}
      </div>
    )
  }

  if (!rows.length) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <Brain className="w-10 h-10 text-text-disabled mb-3" />
        <p className="text-sm text-text-secondary font-medium">No sessions yet</p>
        <p className="text-xs text-text-muted mt-1">Start your first session to see analysis here.</p>
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border">
            {['Session', 'Mode', 'Duration', 'Confidence', 'Comm.', 'Stress', 'Engagement', ''].map(h => (
              <th key={h} className="pb-2 pt-1 text-left text-2xs font-semibold text-text-muted uppercase tracking-widest first:pl-0 px-3">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border-subtle">
          {rows.map((r, i) => (
            <motion.tr 
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2, delay: i * 0.05 }}
              key={r.id} 
              className="group hover:bg-bg-hover transition-colors"
            >
              <td className="py-3 pl-0 pr-3">
                <div>
                  <p className="text-sm text-text-primary font-medium group-hover:text-accent transition-colors">{r.name}</p>
                  <p className="text-2xs text-text-muted mt-0.5 flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {new Date(r.startedAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                  </p>
                </div>
              </td>
              <td className="px-3 py-3">
                <Badge variant={MODE_BADGE[r.mode] ?? 'default'} dot>
                  {r.mode}
                </Badge>
              </td>
              <td className="px-3 py-3 text-xs text-text-secondary font-mono">
                {formatDuration(r.duration)}
              </td>
              <td className="px-3 py-3"><ScoreCell value={r.confidence} /></td>
              <td className="px-3 py-3"><ScoreCell value={r.communication} /></td>
              <td className="px-3 py-3"><ScoreCell value={r.stress} invert /></td>
              <td className="px-3 py-3"><ScoreCell value={r.engagement} /></td>
              <td className="px-3 py-3 text-right">
                <Link href={`/session/${r.id}/results`}>
                  <span className="inline-flex items-center gap-1 text-xs text-text-muted hover:text-accent transition-colors">
                    View <ArrowUpRight className="w-3 h-3" />
                  </span>
                </Link>
              </td>
            </motion.tr>
          ))}
        </tbody>
      </table>
    </div>
  )
})
