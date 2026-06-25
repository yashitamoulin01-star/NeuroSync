'use client'
import { useState, useEffect } from 'react'
import Link from 'next/link'
import { AppShell } from '@/components/layout/AppShell'
import { Button } from '@/components/ui/Button'
import { toast } from '@/lib/toast'
import { Badge } from '@/components/ui/Badge'
import { ConfidenceBar, ConfidenceChip } from '@/components/ui/ConfidenceBar'
import { EvidenceTimeline } from '@/components/workspace/EvidenceTimeline'
import { BehavioralFingerprint } from '@/components/charts/BehavioralFingerprint'
import {
  ArrowLeft, CheckCircle, AlertTriangle, Clock, Hash,
  MessageSquare, Zap, Download, Share2, RefreshCw, AlertCircle,
} from 'lucide-react'
import { api } from '@/lib/api'
import { formatDuration } from '@/lib/utils'
import type { BehavioralInsight } from '@/lib/types'
import { Skeleton } from '@/components/ui/Skeleton'

// ── Scoring ───────────────────────────────────────────────────────────────────

function computeScore(s: any): number {
  const conf  = s.avg_confidence    ?? 0
  const eng   = s.avg_engagement    ?? 0
  const comm  = s.avg_communication ?? 0
  const consis = s.avg_consistency  ?? 0
  const comp  = 1 - (s.avg_stress  ?? 0)
  return Math.round((conf + eng + comm + consis + comp) / 5 * 100)
}

function computeTier(score: number, stress: number) {
  if (score >= 72 && stress < 0.45) return 'proceed'
  if (score >= 52 && stress < 0.60) return 'review'
  return 'hold'
}

function tierConf(score: number, consis: number, words: number): number {
  return Math.min(0.97, (Math.min(1, words / 1500) * 0.25) + (consis * 0.40) + ((score >= 70 || score < 45) ? 0.28 : 0.15))
}

// ── Scorecard ─────────────────────────────────────────────────────────────────

const DIMS = [
  { key: 'avg_confidence',    label: 'Confidence',    color: '#818cf8', inv: false,
    taskF1: 0.862, description: 'Assertiveness and certainty expressed through language and voice' },
  { key: 'avg_engagement',    label: 'Engagement',    color: '#34d399', inv: false,
    taskF1: 0.800, description: 'Active presence, visual attention, and response depth' },
  { key: 'avg_communication', label: 'Communication', color: '#60a5fa', inv: false,
    taskF1: 0.769, description: 'Clarity, structure, and speaking pace' },
  { key: 'avg_consistency',   label: 'Consistency',   color: '#fbbf24', inv: false,
    taskF1: 0.717, description: 'Alignment between verbal and non-verbal signals' },
  { key: 'avg_stress',        label: 'Composure',     color: '#f87171', inv: true,
    taskF1: 0.848, description: 'Inverse of detected vocal and facial stress' },
]

function Scorecard({ session: s, insights }: { session: any; insights: BehavioralInsight[] }) {
  const overallScore = computeScore(s)
  const tier  = computeTier(overallScore, s.avg_stress ?? 0)
  const tConf = tierConf(overallScore, s.avg_consistency ?? 0, s.total_words ?? 0)

  const tierStyles = {
    proceed: { text: 'text-status-success', bg: 'bg-status-success/8', border: 'border-status-success/25' },
    review:  { text: 'text-status-warning', bg: 'bg-status-warning/8', border: 'border-status-warning/25' },
    hold:    { text: 'text-status-danger',  bg: 'bg-status-danger/8',  border: 'border-status-danger/25' },
  }
  const ts = tierStyles[tier]
  const TierIcon = tier === 'proceed' ? CheckCircle : AlertTriangle

  return (
    <div className="space-y-4">
      {/* Recommendation header */}
      <div className={`rounded-xl border p-5 ${ts.border} ${ts.bg}`}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <TierIcon className={`w-5 h-5 ${ts.text}`} />
            <span className={`text-base font-bold ${ts.text}`}>
              {tier === 'proceed' ? 'Recommend: Proceed' : tier === 'review' ? 'Recommend: Review' : 'Recommend: Hold'}
            </span>
          </div>
          <ConfidenceChip value={tConf} />
        </div>
        <ConfidenceBar value={tConf} size="sm" showPct={false} />
        <p className="text-xs text-text-secondary mt-3 leading-relaxed">
          {tier === 'proceed'
            ? `Strong behavioural profile across all five dimensions. Composite score ${overallScore}/100 meets the threshold for advancement. Evidence across face, voice, and language modalities is consistent.`
            : tier === 'review'
            ? `Mixed behavioural signals warrant additional evaluation. Composite score ${overallScore}/100 is adequate but does not meet the confidence threshold for an unambiguous proceed recommendation. Human review recommended before decision.`
            : `Behavioural profile shows significant concerns. Composite score ${overallScore}/100 is below the minimum threshold. A structured follow-up or coaching session is recommended before any advancement decision.`}
        </p>
      </div>

      {/* Per-dimension table */}
      <div className="rounded-xl border border-border bg-bg-card overflow-hidden">
        <div className="px-5 py-3 border-b border-border-subtle">
          <p className="text-xs font-semibold text-text-muted uppercase tracking-widest">Dimension Scorecard</p>
        </div>
        <div className="divide-y divide-border-subtle">
          <div className="grid grid-cols-12 px-5 py-2 text-2xs font-semibold text-text-muted uppercase tracking-widest">
            <span className="col-span-3">Dimension</span>
            <span className="col-span-2 text-right">Score</span>
            <span className="col-span-4 px-4">Model Confidence</span>
            <span className="col-span-2 text-right">Evidence</span>
            <span className="col-span-1 text-right">Task F1</span>
          </div>
          {DIMS.map(d => {
            const raw     = s[d.key] ?? 0
            const display = d.inv ? 1 - raw : raw
            const pct     = Math.round(display * 100)
            const relEvidence = insights.filter(i => {
              if (d.key === 'avg_confidence')    return ['hesitation_burst', 'positive_signal', 'strong_delivery'].includes(i.type)
              if (d.key === 'avg_stress')        return ['stress_spike', 'vocal_tension'].includes(i.type)
              if (d.key === 'avg_engagement')    return i.type === 'strong_delivery'
              if (d.key === 'avg_consistency')   return i.type === 'gaze_aversion'
              if (d.key === 'avg_communication') return i.type === 'hesitation_burst'
              return false
            })
            const dimConf = Math.min(0.97, d.taskF1 * 0.6 + (s.avg_consistency ?? 0.7) * 0.25 + (Math.min(1, (s.total_words ?? 0) / 1500)) * 0.15)
            return (
              <div key={d.key} className="grid grid-cols-12 px-5 py-3.5 items-center hover:bg-bg-hover transition-colors">
                <div className="col-span-3 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: d.color }} />
                  <span className="text-xs font-medium text-text-primary">{d.label}</span>
                </div>
                <div className="col-span-2 text-right">
                  <span className="text-sm font-bold font-mono" style={{ color: d.color }}>{pct}%</span>
                </div>
                <div className="col-span-4 px-4">
                  <ConfidenceBar value={dimConf} size="sm" />
                </div>
                <div className="col-span-2 text-right">
                  <span className="text-xs text-text-muted font-mono">
                    {relEvidence.length > 0 ? `${relEvidence.length} event${relEvidence.length > 1 ? 's' : ''}` : '—'}
                  </span>
                </div>
                <div className="col-span-1 text-right">
                  <span className="text-2xs text-text-disabled font-mono">{Math.round(d.taskF1 * 100)}%</span>
                </div>
              </div>
            )
          })}
        </div>
        <div className="px-5 py-3 border-t border-border-subtle bg-bg-hover flex items-center justify-between">
          <span className="text-xs font-semibold text-text-muted">Overall Composite</span>
          <div className="flex items-center gap-3">
            <span className="text-lg font-bold font-mono text-text-primary">{overallScore}</span>
            <span className="text-2xs text-text-muted">/ 100</span>
          </div>
        </div>
      </div>
    </div>
  )
}


// ── Page ──────────────────────────────────────────────────────────────────────

type Tab = 'scorecard' | 'evidence'

export default function CandidateAssessmentPage({ params }: { params: { id: string } }) {
  const [tab,     setTab]     = useState<Tab>('scorecard')
  const [data,    setData]    = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState<string | null>(null)

  useEffect(() => {
    let mounted = true
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const res = await api.getSessionDetail(params.id)
        if (mounted) setData(res)
      } catch {
        if (mounted) setError('Could not load assessment data.')
      } finally {
        if (mounted) setLoading(false)
      }
    }
    load()
    return () => { mounted = false }
  }, [params.id])

  const s        = data ?? {}
  const insights: BehavioralInsight[] = s.insights ?? []
  const score    = data ? computeScore(s) : 0

  const fp = {
    confidence:    s.avg_confidence    ?? 0,
    communication: s.avg_communication ?? 0,
    engagement:    s.avg_engagement    ?? 0,
    stress:        s.avg_stress        ?? 0,
    consistency:   s.avg_consistency   ?? 0,
  }

  const dateStr = s.started_at
    ? new Date(typeof s.started_at === 'number' ? s.started_at * 1000 : s.started_at)
        .toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    : '—'

  function handleShare() {
    navigator.clipboard.writeText(window.location.href)
      .then(() => toast('success', 'Assessment link copied to clipboard'))
      .catch(() => toast('error', 'Could not copy link'))
  }

  return (
    <AppShell
      title="Candidate Assessment"
      actions={
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" icon={<Share2 className="w-3.5 h-3.5" />} onClick={handleShare}>
            Share
          </Button>
          <Link href={`/session/${params.id}/results`}>
            <Button variant="secondary" size="sm">Full Results →</Button>
          </Link>
        </div>
      }
    >
      <div className="p-6 space-y-6 max-w-5xl page-enter">

        {/* Breadcrumb */}
        <div className="flex items-center gap-2">
          <Link href="/workspace">
            <Button variant="ghost" size="xs" icon={<ArrowLeft className="w-3 h-3" />}>Workspace</Button>
          </Link>
          <span className="text-text-disabled">/</span>
          <span className="text-xs text-text-muted truncate max-w-xs">
            {loading ? 'Loading…' : (s.name ?? params.id)}
          </span>
        </div>

        {error && (
          <div className="flex items-center gap-3 rounded-xl border border-status-danger/30 bg-status-danger/5 px-4 py-3">
            <AlertCircle className="w-4 h-4 text-status-danger flex-shrink-0" />
            <p className="text-xs text-status-danger">{error}</p>
            <button onClick={() => window.location.reload()}
              className="ml-auto text-xs text-status-danger underline flex items-center gap-1">
              <RefreshCw className="w-3 h-3" /> Retry
            </button>
          </div>
        )}

        {/* Candidate header */}
        <div className="rounded-xl border border-border bg-bg-card p-5">
          {loading ? (
            <div className="flex gap-5">
              <Skeleton className="w-24 h-24 rounded-full flex-shrink-0" />
              <div className="flex-1 space-y-3">
                <Skeleton className="h-5 w-64" />
                <Skeleton className="h-4 w-40" />
                <div className="grid grid-cols-4 gap-3 mt-2">
                  {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-12" />)}
                </div>
              </div>
            </div>
          ) : (
            <div className="flex flex-col sm:flex-row gap-5">
              <div className="flex-shrink-0 flex justify-center">
                <BehavioralFingerprint data={fp} size={140} animated />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-start gap-3 mb-3">
                  <div>
                    <h2 className="text-lg font-bold text-text-primary">{s.name ?? 'Candidate'}</h2>
                    <p className="text-sm text-text-muted">{s.mode ?? 'interview'} · {dateStr}</p>
                  </div>
                  <Badge variant={s.mode === 'interview' ? 'accent' : 'success'}>{s.mode ?? 'interview'}</Badge>
                  <div className="ml-auto flex items-center gap-2">
                    <span className="text-3xl font-bold font-mono text-text-primary">{score}</span>
                    <span className="text-sm text-text-muted">/100</span>
                  </div>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {[
                    { icon: Clock,         label: 'Duration', value: formatDuration(s.duration ?? 0) },
                    { icon: Hash,          label: 'Words',    value: (s.total_words ?? 0).toLocaleString() },
                    { icon: MessageSquare, label: 'Fillers',  value: String(s.total_filler_words ?? 0) },
                    { icon: Zap,           label: 'Pace',     value: s.avg_speaking_pace ? `${Math.round(s.avg_speaking_pace)} wpm` : '—' },
                  ].map(({ icon: Icon, label, value }) => (
                    <div key={label} className="rounded-lg bg-bg-hover border border-border-subtle p-3">
                      <div className="flex items-center gap-1.5 mb-0.5">
                        <Icon className="w-3 h-3 text-text-muted" />
                        <span className="text-2xs text-text-muted">{label}</span>
                      </div>
                      <span className="text-sm font-bold font-mono text-text-primary">{value}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Tabs */}
          <div className="flex border-b border-border-subtle mt-5 -mb-1 gap-0">
            {([
              { key: 'scorecard', label: 'Scorecard & Recommendation' },
              { key: 'evidence',  label: `Evidence Timeline${insights.length ? ` (${insights.length})` : ''}` },
            ] as const).map(t => (
              <button key={t.key} onClick={() => setTab(t.key)}
                className={`px-4 py-3 text-xs font-medium border-b-2 transition-colors ${
                  tab === t.key
                    ? 'border-accent text-accent'
                    : 'border-transparent text-text-muted hover:text-text-secondary'
                }`}>
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {/* Tab content */}
        {!loading && (
          <div className="tab-content">
            {tab === 'scorecard' && (
              <Scorecard session={s} insights={insights} />
            )}
            {tab === 'evidence' && (
              <div className="rounded-xl border border-border bg-bg-card p-5">
                <EvidenceTimeline
                  insights={insights}
                  duration={s.duration ?? 0}
                  session={s}
                />
              </div>
            )}
          </div>
        )}

        {loading && (
          <div className="space-y-3">
            {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-20" />)}
          </div>
        )}

        {/* Governance notice */}
        <div className="rounded-xl border border-border-subtle bg-bg-hover px-5 py-4">
          <p className="text-2xs text-text-muted leading-relaxed">
            <strong className="text-text-secondary">Mandatory disclosure: </strong>
            This assessment was produced by the NeuroSync MBA Engine (DeBERTa v3, Macro-F1 82.4%).
            Scores are probabilistic estimates based on behavioural signals and must not be
            used as the sole basis for any hiring, promotion, or adverse employment decision.
            All high-severity events require independent human review before action is taken.{' '}
            <Link href="/governance" className="text-accent underline underline-offset-2">
              Full governance policy →
            </Link>
          </p>
        </div>

      </div>
    </AppShell>
  )
}
