'use client'
import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { AppShell } from '@/components/layout/AppShell'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { ConfidenceBar } from '@/components/ui/ConfidenceBar'
import { cn } from '@/lib/utils'
import {
  Briefcase, Star, StarOff, Users,
  CheckCircle, Clock, TrendingUp, AlertTriangle, ArrowRight, RefreshCw,
  GitCompare, X, ChevronRight,
} from 'lucide-react'
import { api } from '@/lib/api'
import { formatDuration } from '@/lib/utils'
import type { SessionRow } from '@/lib/types'
import { Skeleton } from '@/components/ui/Skeleton'

// ── Derived types ─────────────────────────────────────────────────────────────

type Tier = 'proceed' | 'review' | 'hold'

interface Candidate {
  session: SessionRow
  overallScore: number
  tier: Tier
  tierConfidence: number
  topStrength: string
  topConcern: string | null
  shortlisted: boolean
}

// ── Scoring helpers ───────────────────────────────────────────────────────────

function computeTier(score: number, stress: number, words: number): Tier {
  if (words < 200)  return 'review'
  if (score >= 72 && stress < 0.45) return 'proceed'
  if (score >= 52 && stress < 0.60) return 'review'
  return 'hold'
}

function computeTierConfidence(score: number, consis: number, words: number, insights: any[]): number {
  const dataConf    = Math.min(1, words / 1500) * 0.25
  const consistConf = consis * 0.35
  const scoreConf   = (score >= 70 || score < 45) ? 0.30 : 0.18
  const sampleConf  = Math.min(1, (insights?.length ?? 0) / 5) * 0.10
  return Math.min(0.97, dataConf + consistConf + scoreConf + sampleConf)
}

function topStrength(s: SessionRow): string {
  const conf   = s.avg_confidence    ?? 0
  const eng    = s.avg_engagement    ?? 0
  const comm   = s.avg_communication ?? 0
  const consis = s.avg_consistency   ?? 0
  const comp   = 1 - (s.avg_stress   ?? 0)
  const dims   = [
    { l: 'Confidence',    v: conf },
    { l: 'Engagement',    v: eng  },
    { l: 'Communication', v: comm },
    { l: 'Consistency',   v: consis },
    { l: 'Composure',     v: comp },
  ]
  dims.sort((a, b) => b.v - a.v)
  const top = dims[0]
  return top.v >= 0.70
    ? `Strong ${top.l.toLowerCase()} (${Math.round(top.v * 100)}%)`
    : `Best in ${top.l.toLowerCase()} (${Math.round(top.v * 100)}%)`
}

function topConcern(s: SessionRow, insights: any[]): string | null {
  if ((s.avg_stress ?? 0) >= 0.50) return `Elevated stress (${Math.round((s.avg_stress ?? 0) * 100)}%)`
  if ((s.total_filler_words ?? 0) >= 20) return `High filler count (${s.total_filler_words})`
  if ((s.avg_confidence ?? 0) < 0.50) return `Low confidence (${Math.round((s.avg_confidence ?? 0) * 100)}%)`
  const stressEvents = insights?.filter((i: any) => i.type === 'stress_spike' || i.type === 'vocal_tension') ?? []
  if (stressEvents.length >= 2) return `${stressEvents.length} stress events detected`
  return null
}

function deriveCandidates(sessions: SessionRow[], shortlisted: Set<string>): Candidate[] {
  return sessions.map(s => {
    const conf   = s.avg_confidence    ?? 0
    const eng    = s.avg_engagement    ?? 0
    const comm   = s.avg_communication ?? 0
    const consis = s.avg_consistency   ?? 0
    const stress = s.avg_stress        ?? 0
    const score  = Math.round((conf + eng + comm + consis + (1 - stress)) / 5 * 100)
    const insights = (s as any).insights ?? []
    return {
      session:        s,
      overallScore:   score,
      tier:           computeTier(score, stress, s.total_words ?? 0),
      tierConfidence: computeTierConfidence(score, consis, s.total_words ?? 0, insights),
      topStrength:    topStrength(s),
      topConcern:     topConcern(s, insights),
      shortlisted:    shortlisted.has(s.id),
    }
  })
}

// ── Tier badge ────────────────────────────────────────────────────────────────

function TierBadge({ tier }: { tier: Tier }) {
  const styles = {
    proceed: 'text-metric-engagement bg-metric-engagement/10 border-metric-engagement/25',
    review:  'text-status-warning bg-status-warning/10 border-status-warning/25',
    hold:    'text-metric-stress bg-metric-stress/10 border-metric-stress/25',
  }
  const labels = { proceed: 'Proceed', review: 'Review', hold: 'Hold' }
  const icons  = { proceed: CheckCircle, review: AlertTriangle, hold: AlertTriangle }
  const Icon   = icons[tier]
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-semibold ${styles[tier]}`}>
      <Icon className="w-3 h-3" />
      {labels[tier]}
    </span>
  )
}

// ── Candidate card ────────────────────────────────────────────────────────────

function CandidateCard({
  candidate, onToggleShortlist, compareIds, onToggleCompare,
}: {
  candidate: Candidate
  onToggleShortlist: (id: string) => void
  compareIds: string[]
  onToggleCompare: (id: string) => void
}) {
  const { session: s, overallScore, tier, tierConfidence, topStrength: strength, topConcern: concern, shortlisted } = candidate
  const inCompare    = compareIds.includes(s.id)
  const compareMaxed = compareIds.length >= 2 && !inCompare

  const dateStr = s.started_at
    ? new Date(typeof s.started_at === 'string' ? s.started_at : (s.started_at as number) * 1000)
        .toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    : '—'

  const scoreColor = overallScore >= 72 ? '#34d399' : overallScore >= 52 ? '#fbbf24' : '#f87171'

  return (
    <div className={cn(
      'rounded-xl border bg-bg-card p-5 card-hover group transition-all',
      inCompare ? 'border-accent/40 shadow-glow-accent' : 'border-border',
    )}>
      <div className="flex items-start gap-4">

        {/* Compare checkbox */}
        <button
          onClick={() => onToggleCompare(s.id)}
          disabled={compareMaxed}
          title={inCompare ? 'Remove from comparison' : compareMaxed ? 'Max 2 candidates' : 'Add to comparison'}
          className={cn(
            'w-5 h-5 rounded border flex items-center justify-center flex-shrink-0 mt-0.5 transition-all',
            inCompare
              ? 'border-accent bg-accent text-white'
              : compareMaxed
              ? 'border-border opacity-40 cursor-not-allowed'
              : 'border-border text-text-disabled hover:border-accent/60',
          )}
        >
          {inCompare && <CheckCircle className="w-3 h-3" />}
        </button>

        {/* Score circle */}
        <div
          className="w-12 h-12 rounded-xl flex-shrink-0 flex items-center justify-center"
          style={{ background: `${scoreColor}15`, border: `1.5px solid ${scoreColor}35` }}
        >
          <span className="text-base font-bold font-mono" style={{ color: scoreColor }}>{overallScore}</span>
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2 mb-1.5">
            <div className="min-w-0">
              <h3 className="text-sm font-semibold text-text-primary truncate">{s.name}</h3>
              <p className="text-2xs text-text-muted mt-0.5">
                {s.mode ?? 'interview'} · {dateStr} · {formatDuration(s.duration ?? 0)}
              </p>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <TierBadge tier={tier} />
              <button
                onClick={() => onToggleShortlist(s.id)}
                className="text-text-muted hover:text-status-warning transition-colors"
                title={shortlisted ? 'Remove from shortlist' : 'Add to shortlist'}
              >
                {shortlisted
                  ? <Star className="w-4 h-4 fill-status-warning text-status-warning" />
                  : <StarOff className="w-4 h-4" />
                }
              </button>
            </div>
          </div>

          <div className="mb-3">
            <ConfidenceBar value={tierConfidence} label="Recommendation confidence" size="sm" />
          </div>

          <div className="flex flex-wrap gap-2 text-2xs">
            {strength && (
              <span className="flex items-center gap-1 text-metric-engagement">
                <CheckCircle className="w-3 h-3" />
                {strength}
              </span>
            )}
            {concern && (
              <span className="flex items-center gap-1 text-status-warning">
                <AlertTriangle className="w-3 h-3" />
                {concern}
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="mt-4 pt-3 border-t border-border-subtle flex items-center justify-between">
        <div className="flex gap-4 text-2xs text-text-muted">
          {[
            { label: 'Words',   value: (s.total_words ?? 0).toLocaleString() },
            { label: 'Fillers', value: String(s.total_filler_words ?? 0) },
            { label: 'Pace',    value: s.avg_speaking_pace ? `${Math.round(s.avg_speaking_pace)} wpm` : '—' },
          ].map(m => (
            <span key={m.label}>
              <span className="text-text-disabled">{m.label} </span>{m.value}
            </span>
          ))}
        </div>
        <Link href={`/workspace/${s.id}`}>
          <Button variant="ghost" size="xs" iconRight={<ArrowRight className="w-3 h-3" />}>
            Full Assessment
          </Button>
        </Link>
      </div>
    </div>
  )
}

// ── Priority candidate card (compact) ────────────────────────────────────────

function PriorityCard({ candidate }: { candidate: Candidate }) {
  const { session: s, overallScore } = candidate
  const scoreColor = overallScore >= 72 ? '#34d399' : overallScore >= 52 ? '#fbbf24' : '#f87171'
  return (
    <Link href={`/workspace/${s.id}`} className="block">
      <div className="rounded-xl border border-metric-engagement/20 bg-metric-engagement/[0.03] p-4 card-hover group">
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
            style={{ background: `${scoreColor}15`, border: `1.5px solid ${scoreColor}30` }}
          >
            <span className="text-sm font-bold font-mono" style={{ color: scoreColor }}>{overallScore}</span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-text-primary truncate">{s.name}</p>
            <p className="text-2xs text-text-muted mt-0.5">{candidate.topStrength}</p>
          </div>
          <ChevronRight className="w-3.5 h-3.5 text-text-disabled group-hover:text-text-muted transition-colors flex-shrink-0" />
        </div>
      </div>
    </Link>
  )
}

// ── Compare panel ─────────────────────────────────────────────────────────────

const COMPARE_DIMS = [
  { key: 'avg_confidence',    label: 'Confidence',    inverted: false },
  { key: 'avg_engagement',    label: 'Engagement',    inverted: false },
  { key: 'avg_communication', label: 'Communication', inverted: false },
  { key: 'avg_consistency',   label: 'Consistency',   inverted: false },
  { key: 'avg_stress',        label: 'Composure',     inverted: true  },
]

function ComparePanel({ a, b, onClose }: { a: Candidate; b: Candidate; onClose: () => void }) {
  const scoreColor = (v: number) => v >= 72 ? '#34d399' : v >= 52 ? '#fbbf24' : '#f87171'

  return (
    <div className="rounded-xl border border-accent/25 bg-bg-card overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-border bg-accent/[0.02]">
        <div className="flex items-center gap-2">
          <GitCompare className="w-4 h-4 text-accent" />
          <span className="label-xs text-text-secondary">Side-by-Side Comparison</span>
        </div>
        <button onClick={onClose} className="text-text-muted hover:text-text-primary transition-colors">
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Names row */}
      <div className="grid grid-cols-2 divide-x divide-border border-b border-border">
        {[a, b].map(c => (
          <div key={c.session.id} className="px-5 py-4 flex items-center gap-3">
            <div
              className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
              style={{ background: `${scoreColor(c.overallScore)}15`, border: `1.5px solid ${scoreColor(c.overallScore)}30` }}
            >
              <span className="text-sm font-bold font-mono" style={{ color: scoreColor(c.overallScore) }}>
                {c.overallScore}
              </span>
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-text-primary truncate">{c.session.name}</p>
              <div className="mt-1"><TierBadge tier={c.tier} /></div>
            </div>
          </div>
        ))}
      </div>

      {/* Dimension comparison */}
      <div className="divide-y divide-border">
        {COMPARE_DIMS.map(dim => {
          const rawA = (a.session as any)[dim.key] ?? 0
          const rawB = (b.session as any)[dim.key] ?? 0
          const vA   = dim.inverted ? 1 - rawA : rawA
          const vB   = dim.inverted ? 1 - rawB : rawB
          const winA = vA > vB
          const winB = vB > vA
          return (
            <div key={dim.key} className="grid grid-cols-[1fr_auto_1fr] items-center px-5 py-3">
              <div className="flex items-center gap-2">
                <span className={cn('text-sm font-bold font-mono', winA ? 'text-text-primary' : 'text-text-muted')}>
                  {Math.round(vA * 100)}%
                </span>
                {winA && <span className="w-1.5 h-1.5 rounded-full bg-status-success flex-shrink-0" />}
              </div>
              <span className="text-2xs text-text-disabled text-center px-4 min-w-[90px]">{dim.label}</span>
              <div className="flex items-center gap-2 justify-end">
                {winB && <span className="w-1.5 h-1.5 rounded-full bg-status-success flex-shrink-0" />}
                <span className={cn('text-sm font-bold font-mono', winB ? 'text-text-primary' : 'text-text-muted')}>
                  {Math.round(vB * 100)}%
                </span>
              </div>
            </div>
          )
        })}
      </div>

      {/* Footer */}
      <div className="grid grid-cols-2 divide-x divide-border border-t border-border">
        {[a, b].map(c => (
          <div key={c.session.id} className="px-5 py-3 flex justify-center">
            <Link href={`/workspace/${c.session.id}`}>
              <Button variant="ghost" size="xs" iconRight={<ArrowRight className="w-3 h-3" />}>
                Full report
              </Button>
            </Link>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

type FilterTier = 'all' | Tier | 'shortlisted'

export default function WorkspacePage() {
  const [sessions,    setSessions]    = useState<SessionRow[]>([])
  const [loading,     setLoading]     = useState(true)
  const [error,       setError]       = useState<string | null>(null)
  const [filter,      setFilter]      = useState<FilterTier>('all')
  const [shortlisted, setShortlisted] = useState<Set<string>>(new Set())
  const [lastRefresh, setLastRefresh] = useState(Date.now())
  const [compareIds,  setCompareIds]  = useState<string[]>([])
  const [showCompare, setShowCompare] = useState(false)

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('nuanceai_shortlist') ?? '[]')
      setShortlisted(new Set(saved))
    } catch { /* ignore */ }
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const { sessions: rows } = await api.getSessions({ limit: 100 })
      setSessions(rows)
      setLastRefresh(Date.now())
    } catch {
      setError('Could not load candidate assessments. Ensure the backend is running.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  function toggleShortlist(id: string) {
    setShortlisted(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      try { localStorage.setItem('nuanceai_shortlist', JSON.stringify([...next])) }
      catch { /* ignore */ }
      return next
    })
  }

  function toggleCompare(id: string) {
    setCompareIds(prev => {
      const next = prev.includes(id) ? prev.filter(x => x !== id) : prev.length >= 2 ? [prev[1], id] : [...prev, id]
      return next
    })
    setShowCompare(false)
  }

  const candidates = deriveCandidates(sessions, shortlisted)

  const counts = {
    all:         candidates.length,
    proceed:     candidates.filter(c => c.tier === 'proceed').length,
    review:      candidates.filter(c => c.tier === 'review').length,
    hold:        candidates.filter(c => c.tier === 'hold').length,
    shortlisted: candidates.filter(c => c.shortlisted).length,
  }

  const filtered = candidates.filter(c => {
    if (filter === 'all')         return true
    if (filter === 'shortlisted') return c.shortlisted
    return c.tier === filter
  })

  const avgScore = candidates.length
    ? Math.round(candidates.reduce((s, c) => s + c.overallScore, 0) / candidates.length)
    : 0

  const priorityCandidates = candidates
    .filter(c => c.tier === 'proceed')
    .sort((a, b) => b.overallScore - a.overallScore)
    .slice(0, 3)

  const compareA = compareIds[0] ? candidates.find(c => c.session.id === compareIds[0]) : null
  const compareB = compareIds[1] ? candidates.find(c => c.session.id === compareIds[1]) : null

  const FILTER_TABS: Array<{ key: FilterTier; label: string; count: number }> = [
    { key: 'all',         label: 'All',        count: counts.all },
    { key: 'proceed',     label: 'Proceed',    count: counts.proceed },
    { key: 'review',      label: 'Review',     count: counts.review },
    { key: 'hold',        label: 'Hold',       count: counts.hold },
    { key: 'shortlisted', label: 'Shortlisted', count: counts.shortlisted },
  ]

  return (
    <AppShell
      title="Recruiter Workspace"
      actions={
        <div className="flex items-center gap-2">
          {compareIds.length > 0 && (
            <Button
              variant={compareIds.length >= 2 ? 'primary' : 'secondary'}
              size="sm"
              icon={<GitCompare className="w-3.5 h-3.5" />}
              onClick={() => compareIds.length >= 2 && setShowCompare(v => !v)}
            >
              {compareIds.length >= 2 ? 'Compare' : `Compare (${compareIds.length}/2)`}
            </Button>
          )}
          <Button variant="ghost" size="sm" icon={<RefreshCw className="w-3.5 h-3.5" />} onClick={load}>
            Refresh
          </Button>
        </div>
      }
    >
      <div className="p-6 space-y-6 max-w-5xl page-enter">

        {/* ── Priority Queue ────────────────────────────────────────────────── */}
        {!loading && priorityCandidates.length > 0 && (
          <div>
            <div className="flex items-center justify-between mb-3">
              <div>
                <p className="label-xs text-text-disabled mb-1">Priority Queue</p>
                <h3 className="text-base font-bold text-text-primary">Top Candidates</h3>
              </div>
              <Badge variant="success" dot>{counts.proceed} proceed</Badge>
            </div>
            <div className="grid sm:grid-cols-3 gap-3">
              {priorityCandidates.map(c => (
                <PriorityCard key={c.session.id} candidate={c} />
              ))}
            </div>
          </div>
        )}

        {/* ── Pipeline KPIs ─────────────────────────────────────────────────── */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            { icon: Users,         label: 'Total assessed',  value: String(counts.all),                  color: '#818cf8' },
            { icon: CheckCircle,   label: 'Proceed',          value: String(counts.proceed),              color: '#34d399' },
            { icon: AlertTriangle, label: 'Needs review',     value: String(counts.review + counts.hold), color: '#fbbf24' },
            { icon: TrendingUp,    label: 'Avg. score',       value: counts.all ? String(avgScore) : '—', color: '#60a5fa' },
          ].map(({ icon: Icon, label, value, color }) => (
            <div key={label} className="rounded-xl border border-border bg-bg-card p-4 card-hover">
              <div className="flex items-center gap-2 mb-2">
                <Icon className="w-3.5 h-3.5" style={{ color }} />
                <span className="label-xs text-text-muted">{label}</span>
              </div>
              <span className="text-2xl font-bold font-mono text-text-primary">{value}</span>
            </div>
          ))}
        </div>

        {/* ── Compare hint ──────────────────────────────────────────────────── */}
        {compareIds.length === 0 && candidates.length >= 2 && (
          <div className="flex items-center gap-3 rounded-xl border border-border-subtle bg-bg-hover px-4 py-2.5">
            <GitCompare className="w-3.5 h-3.5 text-text-disabled flex-shrink-0" />
            <p className="text-xs text-text-muted">
              Select two candidates using the checkboxes to compare them side-by-side.
            </p>
          </div>
        )}

        {/* ── Compare panel ─────────────────────────────────────────────────── */}
        {showCompare && compareA && compareB && (
          <ComparePanel a={compareA} b={compareB} onClose={() => setShowCompare(false)} />
        )}

        {/* ── Filter tabs ───────────────────────────────────────────────────── */}
        <div className="flex items-center justify-between">
          <div className="flex gap-1 p-1 rounded-lg bg-bg-hover border border-border-subtle overflow-x-auto">
            {FILTER_TABS.map(t => (
              <button
                key={t.key}
                onClick={() => setFilter(t.key)}
                className={cn(
                  'px-3 py-1.5 rounded-md text-xs font-medium transition-all whitespace-nowrap flex items-center gap-1.5',
                  filter === t.key
                    ? 'bg-bg-card text-text-primary shadow-sm'
                    : 'text-text-muted hover:text-text-secondary',
                )}
              >
                {t.key === 'shortlisted' && <Star className="w-3 h-3" />}
                {t.label}
                <span className={cn('text-2xs font-mono', filter === t.key ? 'text-accent' : 'text-text-disabled')}>
                  {t.count}
                </span>
              </button>
            ))}
          </div>
          <p className="text-2xs text-text-muted hidden sm:block">
            Last refreshed {new Date(lastRefresh).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })}
          </p>
        </div>

        {/* ── Candidate list ────────────────────────────────────────────────── */}
        {error && (
          <div className="rounded-xl border border-status-danger/30 bg-status-danger/5 p-4 text-sm text-status-danger">
            {error}
          </div>
        )}

        {loading ? (
          <div className="space-y-4">
            {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-40" />)}
          </div>
        ) : filtered.length > 0 ? (
          <div className="space-y-4 stagger-children">
            {filtered.map(c => (
              <CandidateCard
                key={c.session.id}
                candidate={c}
                onToggleShortlist={toggleShortlist}
                compareIds={compareIds}
                onToggleCompare={toggleCompare}
              />
            ))}
          </div>
        ) : (
          <div className="rounded-xl border border-border bg-bg-card p-16 text-center">
            <Briefcase className="w-10 h-10 text-text-disabled mx-auto mb-4" />
            <p className="text-sm font-semibold text-text-primary mb-1">
              {filter === 'shortlisted' ? 'No shortlisted candidates' : 'No candidates in this tier'}
            </p>
            <p className="text-xs text-text-muted mb-6">
              {filter === 'shortlisted'
                ? 'Star a candidate to add them to your shortlist.'
                : candidates.length === 0
                ? 'Complete a session to see candidates here.'
                : `No candidates currently in the "${filter}" tier.`}
            </p>
            {candidates.length === 0 && (
              <Link href="/session/new">
                <Button variant="primary" size="sm">Start a session</Button>
              </Link>
            )}
          </div>
        )}

        {/* ── Governance notice ─────────────────────────────────────────────── */}
        <div className="rounded-xl border border-border-subtle bg-bg-hover px-5 py-4 flex items-start gap-3">
          <Clock className="w-4 h-4 text-text-muted flex-shrink-0 mt-0.5" />
          <p className="text-2xs text-text-muted leading-relaxed">
            <strong className="text-text-secondary">AI Governance notice: </strong>
            NeuroSync recommendations are probabilistic estimates intended to support, not replace, human judgement.
            All final hiring decisions must be validated by a qualified human reviewer.{' '}
            <Link href="/governance" className="text-accent underline underline-offset-2">
              View governance policy →
            </Link>
          </p>
        </div>

      </div>
    </AppShell>
  )
}
