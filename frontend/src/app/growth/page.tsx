'use client'
import { useState, useEffect, useCallback } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { behaviorApi, cbipApi, type BehavioralGrowth, type GrowthForecastResponse } from '@/lib/api'
import {
  TrendingUp, TrendingDown, Minus, Brain, Search,
  AlertCircle, RefreshCw, Users, Target, Award,
  ThumbsUp, ThumbsDown, ArrowRight,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { Skeleton } from '@/components/ui/Skeleton'

// ── Helpers ───────────────────────────────────────────────────────────────────


const DIM_COLORS: Record<string, string> = {
  confidence:    '#818cf8',
  engagement:    '#34d399',
  communication: '#60a5fa',
  composure:     '#f87171',
  consistency:   '#fbbf24',
}

const DIM_LABELS: Record<string, string> = {
  confidence:    'Confidence',
  engagement:    'Engagement',
  communication: 'Communication',
  composure:     'Composure',
  consistency:   'Consistency',
}

function TrendIcon({ trend }: { trend: string }) {
  if (trend === 'improving') return <TrendingUp  className="w-3.5 h-3.5 text-metric-engagement" />
  if (trend === 'declining') return <TrendingDown className="w-3.5 h-3.5 text-metric-stress" />
  return <Minus className="w-3.5 h-3.5 text-text-disabled" />
}

function ConfidencePill({ level }: { level: string }) {
  const cls = level === 'high'
    ? 'text-metric-engagement bg-metric-engagement/10 border-metric-engagement/20'
    : level === 'medium'
    ? 'text-status-warning bg-status-warning/10 border-status-warning/20'
    : 'text-text-muted bg-bg-hover border-border'
  return (
    <span className={`text-2xs font-semibold px-2 py-0.5 rounded-full border ${cls}`}>
      {level}
    </span>
  )
}

// ── Growth charts ─────────────────────────────────────────────────────────────

function BaselineRadar({ baseline }: { baseline: Record<string, number> }) {
  const dims = Object.entries(baseline)
  if (!dims.length) return null

  const cx = 100, cy = 100, r = 75
  const n = dims.length

  const toXY = (idx: number, val: number) => {
    const angle = (idx / n) * 2 * Math.PI - Math.PI / 2
    return {
      x: cx + r * val * Math.cos(angle),
      y: cy + r * val * Math.sin(angle),
    }
  }

  const gridPoints = (val: number) =>
    Array.from({ length: n }, (_, i) => toXY(i, val))
      .map(p => `${p.x},${p.y}`)
      .join(' ')

  const fillPoints = dims
    .map(([ , v], i) => { const p = toXY(i, v); return `${p.x},${p.y}` })
    .join(' ')

  return (
    <svg viewBox="0 0 200 200" className="w-full max-w-[200px] mx-auto">
      {[0.25, 0.5, 0.75, 1].map(g => (
        <polygon key={g} points={gridPoints(g)} fill="none" stroke="var(--color-border)" strokeWidth="0.5" />
      ))}
      {dims.map(([, ], i) => {
        const outer = toXY(i, 1)
        return <line key={i} x1={cx} y1={cy} x2={outer.x} y2={outer.y} stroke="var(--color-border)" strokeWidth="0.5" />
      })}
      <polygon points={fillPoints} fill="#818cf8" fillOpacity="0.2" stroke="#818cf8" strokeWidth="1.5" />
      {dims.map(([key, val], i) => {
        const p = toXY(i, val)
        return <circle key={key} cx={p.x} cy={p.y} r="3" fill={DIM_COLORS[key] ?? '#818cf8'} />
      })}
      {dims.map(([key], i) => {
        const p = toXY(i, 1.18)
        return (
          <text key={key} x={p.x} y={p.y} textAnchor="middle" dominantBaseline="middle"
            fontSize="8" fill="var(--color-text-muted)">
            {DIM_LABELS[key] ?? key}
          </text>
        )
      })}
    </svg>
  )
}

function HistoryTimeline({ history }: {
  history: Array<{ session_id: string; conducted_at: number; overall_score: number; recommendation: string }>
}) {
  if (!history.length) return (
    <p className="text-xs text-text-muted py-4">No interviews recorded yet.</p>
  )

  return (
    <div className="space-y-2">
      {history.map((h, i) => {
        const date = new Date(h.conducted_at * 1000)
        const dateStr = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
        const score = Math.round(h.overall_score * 100)
        const recColor = h.recommendation === 'Proceed'
          ? 'text-metric-engagement'
          : h.recommendation === 'Review'
          ? 'text-status-warning'
          : 'text-metric-stress'
        return (
          <div key={h.session_id} className="flex items-center gap-3 py-2 border-b border-border-subtle last:border-0">
            <span className="text-2xs font-mono text-text-disabled w-4">{i + 1}</span>
            <div className="flex-1 min-w-0">
              <p className="text-xs text-text-secondary">{dateStr}</p>
              <p className="text-2xs text-text-muted font-mono truncate">{h.session_id.slice(0, 12)}…</p>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-16 h-1 bg-border rounded-none overflow-hidden">
                <div className="h-full bg-text-primary" style={{ width: `${score}%` }} />
              </div>
              <span className="text-xs font-mono text-text-secondary w-8 text-right">{score}</span>
              <span className={cn('text-2xs font-semibold w-14 text-right', recColor)}>
                {h.recommendation}
              </span>
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ── Forecasting section ───────────────────────────────────────────────────────

const FORECAST_COLORS: Record<string, string> = {
  confidence:    '#818cf8',
  engagement:    '#34d399',
  communication: '#60a5fa',
  composure:     '#f87171',
  consistency:   '#fbbf24',
}

function ForecastSection({ candidateId }: { candidateId: string }) {
  const [forecast, setForecast] = useState<GrowthForecastResponse | null>(null)
  const [loading,  setLoading]  = useState(true)

  useEffect(() => {
    let mounted = true
    cbipApi.getGrowthForecast(candidateId).then(d => {
      if (mounted) { setForecast(d); setLoading(false) }
    }).catch(() => { if (mounted) setLoading(false) })
    return () => { mounted = false }
  }, [candidateId])

  if (loading) return <Skeleton className="h-32 w-full" />
  if (!forecast?.forecast) return null

  const { forecasts, overall_trajectory, confidence_note } = forecast.forecast
  const trajColor = overall_trajectory === 'positive' ? 'text-metric-engagement'
    : overall_trajectory === 'negative' ? 'text-metric-stress'
    : 'text-text-muted'

  return (
    <div className="rounded-xl border border-border bg-bg-card p-5">
      <div className="flex items-center justify-between mb-1">
        <h3 className="text-xs font-semibold uppercase tracking-widest text-text-muted">
          Growth Forecast
        </h3>
        <span className={cn('text-xs font-semibold capitalize', trajColor)}>
          {overall_trajectory} trajectory
        </span>
      </div>
      <p className="text-2xs text-text-disabled mb-4">{confidence_note}</p>

      <div className="space-y-3">
        {forecasts.map(f => {
          const color = FORECAST_COLORS[f.dimension] ?? '#818cf8'
          const curr  = Math.round(f.current_value      * 100)
          const pred  = Math.round(f.predicted_value    * 100)
          const lo    = Math.round(f.confidence_low     * 100)
          const hi    = Math.round(f.confidence_high    * 100)
          const delta = pred - curr

          return (
            <div key={f.dimension}>
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full" style={{ background: color }} />
                  <span className="text-xs font-medium text-text-primary capitalize">{f.dimension}</span>
                  <span className={cn(
                    'text-2xs font-mono',
                    delta > 0 ? 'text-metric-engagement' : delta < 0 ? 'text-metric-stress' : 'text-text-muted',
                  )}>
                    {delta > 0 ? '+' : ''}{delta}%
                  </span>
                </div>
                <div className="flex items-center gap-1.5 text-2xs text-text-muted">
                  <span className="font-mono">{curr}%</span>
                  <ArrowRight className="w-2.5 h-2.5" />
                  <span className="font-mono font-semibold text-text-secondary">{pred}%</span>
                  <span className="text-text-disabled">({lo}–{hi}%)</span>
                </div>
              </div>
              <div className="h-1 bg-border rounded-none overflow-hidden">
                <div className="h-full transition-all duration-700" style={{ width: `${pred}%`, background: color }} />
              </div>
            </div>
          )
        })}
      </div>
      <p className="text-2xs text-text-disabled mt-3">
        Forecasts predict behavioural growth over the next {forecasts[0]?.horizon_interviews ?? 3} interviews.
        They do not predict hiring outcomes. Ranges reflect historical variance.
      </p>
    </div>
  )
}

// ── Candidate feedback (L2) ───────────────────────────────────────────────────

function CandidateFeedbackPanel({
  candidateId,
  latestSessionId,
}: {
  candidateId: string
  latestSessionId: string
}) {
  const [submitted, setSubmitted] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  async function submit(helpful: boolean) {
    if (!latestSessionId || submitting || submitted) return
    setSubmitting(true)
    try {
      await cbipApi.candidateFeedback(latestSessionId, candidateId, helpful)
      setSubmitted(true)
    } catch {
      // silently ignore — feedback is optional
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="rounded-xl border border-border bg-bg-card p-4 flex items-center justify-between gap-4">
      <div>
        <p className="text-xs font-medium text-text-primary">Was this analysis helpful?</p>
        <p className="text-2xs text-text-muted mt-0.5">
          Your feedback helps improve platform coaching quality.
        </p>
      </div>
      {submitted ? (
        <span className="text-xs text-metric-engagement font-medium">Thanks for the feedback.</span>
      ) : (
        <div className="flex gap-2">
          <button
            onClick={() => submit(true)}
            disabled={submitting}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded border border-border
                       text-text-muted hover:text-metric-engagement hover:border-metric-engagement/40 transition-colors"
          >
            <ThumbsUp className="w-3.5 h-3.5" /> Yes
          </button>
          <button
            onClick={() => submit(false)}
            disabled={submitting}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded border border-border
                       text-text-muted hover:text-metric-stress hover:border-metric-stress/40 transition-colors"
          >
            <ThumbsDown className="w-3.5 h-3.5" /> No
          </button>
        </div>
      )}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function GrowthPage() {
  const [candidateId, setCandidateId] = useState('')
  const [inputVal,    setInputVal]    = useState('')
  const [growth,      setGrowth]      = useState<BehavioralGrowth | null>(null)
  const [loading,     setLoading]     = useState(false)
  const [error,       setError]       = useState<string | null>(null)

  const load = useCallback(async (id: string) => {
    if (!id.trim()) return
    setLoading(true)
    setError(null)
    setGrowth(null)
    try {
      const data = await behaviorApi.getGrowth(id.trim())
      setGrowth(data)
      setCandidateId(id.trim())
    } catch (e: any) {
      if (e?.message?.startsWith('404')) {
        setError('No behavioral profile found for this candidate ID. Complete at least one interview with this user ID to create a profile.')
      } else {
        setError('Could not load profile. Check that the backend is running.')
      }
    } finally {
      setLoading(false)
    }
  }, [])

  function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    load(inputVal)
  }

  const overallPct = growth ? Math.round(growth.overall_growth_score * 100) : 0

  return (
    <AppShell title="Behavioral Growth">
      <div className="p-6 max-w-4xl mx-auto page-enter space-y-8">

        {/* Hero */}
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Brain className="w-5 h-5 text-text-primary" />
            <h1 className="text-2xl font-bold text-text-primary">Behavioral Growth</h1>
          </div>
          <p className="text-sm text-text-muted">
            Privacy-aware behavioral memory — each candidate&apos;s communication patterns
            learned over time via exponential moving averages.
          </p>
        </div>

        {/* Candidate search */}
        <form onSubmit={handleSearch} className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-muted" />
            <input
              value={inputVal}
              onChange={e => setInputVal(e.target.value)}
              placeholder="Enter candidate ID (user_id from session)"
              className="w-full pl-9 pr-4 py-2 text-sm bg-bg-input border border-border rounded-none
                         text-text-primary placeholder:text-text-muted
                         focus:outline-none focus:ring-1 focus:ring-text-primary"
            />
          </div>
          <Button type="submit" variant="secondary" size="sm" loading={loading}
            icon={<Search className="w-3.5 h-3.5" />}>
            Load Profile
          </Button>
        </form>

        {/* Error */}
        {error && (
          <div className="flex items-start gap-3 px-4 py-3 border border-border text-xs text-text-secondary">
            <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
            {error}
          </div>
        )}

        {/* Loading skeletons */}
        {loading && (
          <div className="space-y-4">
            <Skeleton className="h-28 w-full" />
            <div className="grid md:grid-cols-2 gap-4">
              <Skeleton className="h-48" />
              <Skeleton className="h-48" />
            </div>
          </div>
        )}

        {/* Profile loaded */}
        {growth && !loading && (
          <>
            {/* Summary row */}
            <div className="grid grid-cols-3 gap-4">
              <div className="rounded-xl border border-border bg-bg-card p-5 text-center">
                <div className="flex justify-center mb-2">
                  <Users className="w-5 h-5 text-text-muted" />
                </div>
                <p className="text-3xl font-bold text-text-primary">{growth.total_interviews}</p>
                <p className="text-xs text-text-muted mt-1">Interviews</p>
              </div>

              <div className="rounded-xl border border-border bg-bg-card p-5 text-center">
                <div className="flex justify-center mb-2">
                  <Target className="w-5 h-5 text-text-muted" />
                </div>
                <p className="text-3xl font-bold text-text-primary">{overallPct}</p>
                <p className="text-xs text-text-muted mt-1">Growth Score</p>
              </div>

              <div className="rounded-xl border border-border bg-bg-card p-5 text-center">
                <div className="flex justify-center mb-2">
                  <Award className="w-5 h-5 text-text-muted" />
                </div>
                <p className="text-3xl font-bold text-text-primary">
                  {Object.values(growth.trend_direction).filter(t => t === 'improving').length}
                </p>
                <p className="text-xs text-text-muted mt-1">Improving Dims</p>
              </div>
            </div>

            {/* Radar + Dimensions */}
            <div className="grid md:grid-cols-2 gap-6">

              {/* Radar */}
              <div className="rounded-xl border border-border bg-bg-card p-5">
                <h3 className="text-xs font-semibold uppercase tracking-widest text-text-muted mb-4">
                  Behavioral Baseline
                </h3>
                <BaselineRadar baseline={growth.baseline} />
                <p className="text-2xs text-text-disabled text-center mt-2">
                  Based on {growth.total_interviews} interview{growth.total_interviews !== 1 ? 's' : ''}
                </p>
              </div>

              {/* Dimension breakdown */}
              <div className="rounded-xl border border-border bg-bg-card p-5">
                <h3 className="text-xs font-semibold uppercase tracking-widest text-text-muted mb-4">
                  Dimension Trends
                </h3>
                <div className="space-y-4">
                  {Object.entries(growth.baseline).map(([dim, val]) => (
                    <div key={dim}>
                      <div className="flex items-center justify-between mb-1.5">
                        <div className="flex items-center gap-1.5">
                          <span className="w-2 h-2 rounded-full" style={{ background: DIM_COLORS[dim] ?? '#818cf8' }} />
                          <span className="text-xs font-medium text-text-primary">
                            {DIM_LABELS[dim] ?? dim}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <TrendIcon trend={growth.trend_direction[dim] ?? 'stable'} />
                          <ConfidencePill level={growth.confidence_levels[dim] ?? 'insufficient'} />
                          <span className="text-xs font-mono text-text-secondary w-8 text-right">
                            {Math.round(val * 100)}%
                          </span>
                        </div>
                      </div>
                      <div className="h-1 bg-border rounded-none overflow-hidden">
                        <div
                          className="h-full transition-all duration-700"
                          style={{ width: `${val * 100}%`, background: DIM_COLORS[dim] ?? '#818cf8' }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Coaching focus */}
            {growth.coaching_focus.length > 0 && (
              <div className="rounded-xl border border-border bg-bg-card p-5">
                <h3 className="text-xs font-semibold uppercase tracking-widest text-text-muted mb-4">
                  Personalized Coaching Focus
                </h3>
                <ul className="space-y-3">
                  {growth.coaching_focus.map((tip, i) => (
                    <li key={i} className="flex items-start gap-3">
                      <span className="text-xs font-mono text-text-disabled mt-0.5">{i + 1}.</span>
                      <p className="text-sm text-text-secondary leading-relaxed">{tip}</p>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Interview history */}
            <div className="rounded-xl border border-border bg-bg-card p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-xs font-semibold uppercase tracking-widest text-text-muted">
                  Interview History
                </h3>
                <Badge variant="muted">{growth.history_summary.length} shown</Badge>
              </div>
              <HistoryTimeline history={growth.history_summary} />
            </div>

            {/* Growth Forecast */}
            <ForecastSection candidateId={candidateId} />

            {/* Candidate feedback (L2 validation) */}
            {growth.history_summary.length > 0 && (
              <CandidateFeedbackPanel
                candidateId={candidateId}
                latestSessionId={growth.history_summary[0]?.session_id ?? ''}
              />
            )}

            {/* Privacy note */}
            <p className="text-2xs text-text-disabled text-center">
              Behavioral memory is candidate-controlled. All learned baselines use exponential moving averages —
              individual sessions are never stored verbatim. Production AI models remain immutable.
              Platform knowledge grows through a validated Behavioral Knowledge Layer, not through model retraining.
            </p>
          </>
        )}

        {/* Empty state when no profile loaded */}
        {!growth && !loading && !error && (
          <div className="flex flex-col items-center justify-center py-24 text-center space-y-4">
            <Brain className="w-12 h-12 text-text-disabled" />
            <div>
              <p className="text-sm font-semibold text-text-primary">Enter a candidate ID to view their growth profile</p>
              <p className="text-xs text-text-muted mt-1 max-w-sm">
                Profiles are created automatically when a session is completed with a user_id set.
                Growth intelligence accumulates across interviews.
              </p>
            </div>
          </div>
        )}

      </div>
    </AppShell>
  )
}
