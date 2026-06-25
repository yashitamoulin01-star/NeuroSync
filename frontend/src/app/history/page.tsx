'use client'
import { useState, useMemo, useEffect, useCallback } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import Link from 'next/link'
import {
  Search, SlidersHorizontal, ArrowUpRight, TrendingUp,
  Clock, X, AlertCircle, RefreshCw, FileText,
} from 'lucide-react'
import { formatDuration, formatScore, cn } from '@/lib/utils'
import { api } from '@/lib/api'
import type { SessionRow } from '@/lib/types'
import { Skeleton } from '@/components/ui/Skeleton'

type SortKey = 'date' | 'confidence' | 'stress' | 'duration'
type SortDir = 'asc' | 'desc'

const MODE_BADGE: Record<string, 'accent' | 'success' | 'warning'> = {
  interview: 'accent', coaching: 'success', presentation: 'warning',
}

function ScoreBar({ value, color, invert }: { value: number; color: string; invert?: boolean }) {
  const v = Math.min(1, Math.max(0, invert ? 1 - value : value))
  return (
    <div className="flex items-center gap-2 w-24">
      <div className="flex-1 h-1 bg-bg-hover rounded-full overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${v * 100}%`, background: color }} />
      </div>
      <span className="text-2xs font-mono text-text-muted w-7 text-right">{Math.round(v * 100)}%</span>
    </div>
  )
}


function EmptyState({ filtered }: { filtered: boolean }) {
  return (
    <tr>
      <td colSpan={8} className="py-20 text-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-bg-hover flex items-center justify-center">
            <FileText className="w-5 h-5 text-text-muted" />
          </div>
          <p className="text-sm text-text-primary font-medium">
            {filtered ? 'No sessions match your filters' : 'No sessions yet'}
          </p>
          <p className="text-xs text-text-muted">
            {filtered ? 'Try adjusting your search or filter.' : 'Start a session to see history here.'}
          </p>
          {!filtered && (
            <Link href="/session/new">
              <Button variant="primary" size="sm" className="mt-1">Start a session</Button>
            </Link>
          )}
        </div>
      </td>
    </tr>
  )
}

function normalizeDate(s: SessionRow): string {
  return (s as any).started_at ?? (s as any).startedAt ?? new Date().toISOString()
}

function normalizeRow(s: SessionRow) {
  return {
    ...s,
    startedAt:     normalizeDate(s),
    confidence:    s.avg_confidence    ?? (s as any).confidence    ?? 0,
    stress:        s.avg_stress        ?? (s as any).stress        ?? 0,
    communication: s.avg_communication ?? (s as any).communication ?? 0,
    engagement:    s.avg_engagement    ?? (s as any).engagement    ?? 0,
    fillerWords:   s.total_filler_words ?? (s as any).fillerWords  ?? 0,
    wordsSpoken:   s.total_words       ?? (s as any).wordsSpoken   ?? 0,
  }
}

export default function HistoryPage() {
  const [allRows, setAllRows] = useState<ReturnType<typeof normalizeRow>[]>([])
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState<string | null>(null)
  const [total,   setTotal]   = useState(0)

  const [query,       setQuery]       = useState('')
  const [modeF,       setModeF]       = useState<string>('all')
  const [sortKey,     setSortKey]     = useState<SortKey>('date')
  const [sortDir,     setSortDir]     = useState<SortDir>('desc')
  const [showFilters, setShowFilters] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.getSessions({ limit: 200 })
      setAllRows(res.sessions.map(normalizeRow))
      setTotal(res.count)
    } catch {
      setError('Could not load session history.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const rows = useMemo(() => {
    let list = [...allRows]
    if (query)           list = list.filter(s => s.name.toLowerCase().includes(query.toLowerCase()))
    if (modeF !== 'all') list = list.filter(s => s.mode === modeF)
    list.sort((a, b) => {
      const val = {
        date:       [new Date(a.startedAt).getTime(), new Date(b.startedAt).getTime()],
        confidence: [a.confidence, b.confidence],
        stress:     [a.stress, b.stress],
        duration:   [a.duration, b.duration],
      }[sortKey]
      return sortDir === 'asc' ? val[0] - val[1] : val[1] - val[0]
    })
    return list
  }, [allRows, query, modeF, sortKey, sortDir])

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  function SortButton({ k, label }: { k: SortKey; label: string }) {
    const active = sortKey === k
    return (
      <button
        onClick={() => toggleSort(k)}
        className={cn(
          'flex items-center gap-1 text-2xs font-semibold uppercase tracking-widest transition-colors',
          active ? 'text-accent' : 'text-text-muted hover:text-text-secondary',
        )}
      >
        {label}
        {active && <span className="text-accent">{sortDir === 'desc' ? '↓' : '↑'}</span>}
      </button>
    )
  }

  const hasFilters  = modeF !== 'all' || !!query
  const avgConf     = rows.length ? rows.reduce((a, r) => a + r.confidence, 0) / rows.length : 0

  return (
    <AppShell
      title="History"
      actions={
        <div className="flex items-center gap-2">
          {error && (
            <button onClick={load}
              className="flex items-center gap-1.5 text-xs text-status-warning hover:text-text-primary transition-colors">
              <RefreshCw className="w-3.5 h-3.5" /> Retry
            </button>
          )}
          <Button
            variant="ghost" size="sm"
            icon={<SlidersHorizontal className="w-3.5 h-3.5" />}
            onClick={() => setShowFilters(!showFilters)}
            className={showFilters ? 'text-accent' : ''}
          >
            Filters {hasFilters && <span className="ml-1 w-1.5 h-1.5 rounded-full bg-accent inline-block" />}
          </Button>
        </div>
      }
    >
      <div className="p-6 space-y-5 max-w-7xl">

        {/* Error banner */}
        {error && (
          <div className="flex items-center gap-3 rounded-xl border border-status-danger/30 bg-status-danger/5 px-4 py-3">
            <AlertCircle className="w-4 h-4 text-status-danger flex-shrink-0" />
            <p className="text-xs text-status-danger">{error}</p>
            <button onClick={load} className="ml-auto text-xs text-status-danger underline">Retry</button>
          </div>
        )}

        {/* Header */}
        <div>
          <h2 className="text-xl font-bold text-text-primary">Session history</h2>
          <p className="text-sm text-text-muted mt-0.5">
            {loading ? 'Loading...' : `${total} session${total !== 1 ? 's' : ''} total`}
          </p>
        </div>

        {/* Search + filter */}
        <div className="space-y-3">
          <div className="flex gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted pointer-events-none" />
              <input
                type="text"
                placeholder="Search sessions…"
                value={query}
                onChange={e => setQuery(e.target.value)}
                className="w-full h-9 rounded-lg border border-border bg-bg-card pl-9 pr-3 text-sm text-text-primary placeholder:text-text-disabled focus:outline-none focus:ring-2 focus:ring-accent-bright focus:ring-offset-1 focus:ring-offset-bg-base hover:border-border-strong transition-colors"
              />
              {query && (
                <button onClick={() => setQuery('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary">
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>

          {showFilters && (
            <div className="flex flex-wrap gap-3 p-4 rounded-lg border border-border bg-bg-card">
              <div>
                <p className="text-2xs text-text-muted font-semibold uppercase tracking-widest mb-2">Mode</p>
                <div className="flex gap-2 flex-wrap">
                  {(['all', 'interview', 'coaching', 'presentation'] as const).map(m => (
                    <button key={m} onClick={() => setModeF(m)}
                      className={cn(
                        'px-3 py-1 rounded-full text-xs font-medium border transition-colors',
                        modeF === m
                          ? 'border-accent bg-accent-glow text-accent'
                          : 'border-border text-text-muted hover:border-border-strong hover:text-text-secondary',
                      )}
                    >
                      {m === 'all' ? 'All' : m.charAt(0).toUpperCase() + m.slice(1)}
                    </button>
                  ))}
                </div>
              </div>
              {hasFilters && (
                <button
                  onClick={() => { setQuery(''); setModeF('all') }}
                  className="ml-auto text-xs text-text-muted hover:text-text-primary flex items-center gap-1.5 transition-colors"
                >
                  <X className="w-3 h-3" /> Clear all
                </button>
              )}
            </div>
          )}
        </div>

        {/* Table */}
        <div className="rounded-xl border border-border bg-bg-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-bg-hover/50">
                  <th className="px-5 py-3 text-left w-64">
                    <span className="label-xs text-text-muted">Session</span>
                  </th>
                  <th className="px-3 py-3 text-left">
                    <span className="label-xs text-text-muted">Mode</span>
                  </th>
                  <th className="px-3 py-3 text-left"><SortButton k="duration" label="Duration" /></th>
                  <th className="px-3 py-3 text-left"><SortButton k="confidence" label="Confidence" /></th>
                  <th className="px-3 py-3 text-left hidden lg:table-cell">
                    <span className="label-xs text-text-muted">Comm.</span>
                  </th>
                  <th className="px-3 py-3 text-left"><SortButton k="stress" label="Stress" /></th>
                  <th className="px-3 py-3 text-left hidden md:table-cell">
                    <span className="label-xs text-text-muted">Words</span>
                  </th>
                  <th className="px-5 py-3 text-right w-16" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {loading ? (
                  Array.from({ length: 5 }).map((_, i) => (
                    <tr key={i}>
                      <td colSpan={8} className="px-5 py-4">
                        <div className="h-8 skeleton rounded-lg" />
                      </td>
                    </tr>
                  ))
                ) : rows.length === 0 ? (
                  <EmptyState filtered={hasFilters} />
                ) : rows.map(r => (
                  <tr key={r.id} className="group hover:bg-bg-hover/60 transition-colors">
                    <td className="px-5 py-3.5">
                      <div>
                        <p className="font-medium text-text-primary group-hover:text-accent transition-colors line-clamp-1">
                          {r.name}
                        </p>
                        <p className="text-2xs text-text-muted mt-0.5 flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {new Date(r.startedAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                          {' · '}
                          {new Date(r.startedAt).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })}
                        </p>
                      </div>
                    </td>
                    <td className="px-3 py-3.5">
                      <Badge variant={MODE_BADGE[r.mode] ?? 'default'} dot>{r.mode}</Badge>
                    </td>
                    <td className="px-3 py-3.5">
                      <span className="text-xs font-mono text-text-secondary">{formatDuration(r.duration)}</span>
                    </td>
                    <td className="px-3 py-3.5">
                      <ScoreBar value={r.confidence} color="#818cf8" />
                    </td>
                    <td className="px-3 py-3.5 hidden lg:table-cell">
                      <ScoreBar value={r.communication} color="#60a5fa" />
                    </td>
                    <td className="px-3 py-3.5">
                      <ScoreBar value={r.stress} color="#f87171" invert />
                    </td>
                    <td className="px-3 py-3.5 hidden md:table-cell">
                      <span className="text-xs text-text-muted font-mono">
                        {(r.wordsSpoken ?? 0).toLocaleString()}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      <Link href={`/session/${r.id}/results`}>
                        <Button variant="ghost" size="xs" iconRight={<ArrowUpRight className="w-3 h-3" />}>
                          View
                        </Button>
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {rows.length > 0 && (
            <div className="px-5 py-3 border-t border-border-subtle bg-bg-hover/30 flex items-center justify-between">
              <span className="text-xs text-text-muted">{rows.length} result{rows.length !== 1 ? 's' : ''}</span>
              <div className="flex items-center gap-3 text-xs text-text-muted">
                <TrendingUp className="w-3.5 h-3.5" />
                Avg confidence: {formatScore(avgConf)}
              </div>
            </div>
          )}
        </div>
      </div>
    </AppShell>
  )
}
