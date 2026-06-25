'use client'
import { useState, useEffect, useCallback } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { cbipApi, type BehavioralPatternItem, type PlatformKnowledgeStats } from '@/lib/api'
import {
  Network, RefreshCw, AlertCircle, ShieldCheck, Database,
  Users, CheckCircle2, TrendingUp, BarChart3, BookOpen,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { Skeleton } from '@/components/ui/Skeleton'


// ── Confidence badge ──────────────────────────────────────────────────────────

function ConfidenceBadge({ label }: { label: string }) {
  const map: Record<string, string> = {
    validated:        'text-metric-engagement bg-metric-engagement/10 border-metric-engagement/20',
    emerging:         'text-metric-consistency bg-metric-consistency/10 border-metric-consistency/20',
    provisional:      'text-status-warning bg-status-warning/10 border-status-warning/20',
    insufficient_data: 'text-text-muted bg-bg-hover border-border',
  }
  const labels: Record<string, string> = {
    validated:        'Validated',
    emerging:         'Emerging',
    provisional:      'Provisional',
    insufficient_data: 'Forming',
  }
  return (
    <span className={cn('text-2xs font-semibold px-2 py-0.5 rounded-full border', map[label] ?? map.insufficient_data)}>
      {labels[label] ?? label}
    </span>
  )
}

// ── Pattern card ──────────────────────────────────────────────────────────────

function PatternCard({ p }: { p: BehavioralPatternItem }) {
  const pct = Math.round(p.confidence * 100)
  const DIM_LABELS: Record<string, string> = {
    avg_confidence:    'Confidence',
    avg_engagement:    'Engagement',
    avg_communication: 'Communication',
    avg_stress:        'Composure',
    avg_consistency:   'Consistency',
  }
  return (
    <div className="rounded-xl border border-border bg-bg-card p-5 flex flex-col gap-3 hover:border-border-active transition-colors">
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-semibold text-text-primary leading-tight">{p.name}</h3>
        <ConfidenceBadge label={p.confidence_label} />
      </div>

      <p className="text-xs text-text-secondary leading-relaxed">{p.description}</p>

      {/* Dimension chips */}
      <div className="flex flex-wrap gap-1.5">
        {p.dimensions.map(d => (
          <span key={d} className="text-2xs px-2 py-0.5 rounded border border-border text-text-muted bg-bg-hover">
            {DIM_LABELS[d] ?? d}
          </span>
        ))}
      </div>

      {/* Confidence bar */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="text-2xs text-text-disabled">Knowledge confidence</span>
          <span className="text-2xs font-mono text-text-secondary">{pct}%</span>
        </div>
        <div className="h-1 bg-border rounded-none overflow-hidden">
          <div
            className="h-full transition-all duration-700"
            style={{
              width: `${pct}%`,
              background: pct >= 60 ? 'var(--color-metric-engagement)'
                : pct >= 30 ? 'var(--color-metric-consistency)'
                : 'var(--color-status-warning)',
            }}
          />
        </div>
      </div>

      {/* Footer stats */}
      <div className="flex items-center gap-4 pt-1 border-t border-border-subtle">
        <div className="text-center">
          <p className="text-sm font-bold text-text-primary">{p.observation_count}</p>
          <p className="text-2xs text-text-muted">Observed</p>
        </div>
        <div className="text-center">
          <p className="text-sm font-bold text-text-primary">{p.validated_count}</p>
          <p className="text-2xs text-text-muted">Validated</p>
        </div>
        <div className="text-center">
          <p className="text-sm font-mono text-text-secondary">≥{Math.round(p.threshold * 100)}%</p>
          <p className="text-2xs text-text-muted">Threshold</p>
        </div>
      </div>
    </div>
  )
}

// ── Stat card ─────────────────────────────────────────────────────────────────

function StatCard({
  label, value, sub, icon: Icon, highlight,
}: {
  label: string; value: string | number; sub?: string; icon: React.FC<any>; highlight?: boolean
}) {
  return (
    <div className={cn(
      'rounded-xl border bg-bg-card p-4 flex items-start gap-3',
      highlight ? 'border-accent/30 bg-accent-glow/30' : 'border-border',
    )}>
      <div className={cn(
        'w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5',
        highlight ? 'bg-accent/20' : 'bg-bg-hover',
      )}>
        <Icon className={cn('w-4 h-4', highlight ? 'text-accent' : 'text-text-muted')} />
      </div>
      <div>
        <p className="text-xl font-bold text-text-primary">{value}</p>
        <p className="text-xs text-text-muted">{label}</p>
        {sub && <p className="text-2xs text-text-disabled mt-0.5">{sub}</p>}
      </div>
    </div>
  )
}

// ── Architecture explanation ──────────────────────────────────────────────────

function ArchitectureNote() {
  return (
    <div className="rounded-xl border border-border bg-bg-card p-5">
      <div className="flex items-center gap-2 mb-3">
        <ShieldCheck className="w-4 h-4 text-text-muted" />
        <h3 className="text-xs font-semibold uppercase tracking-widest text-text-muted">
          How Platform Knowledge Works
        </h3>
      </div>
      <div className="grid md:grid-cols-3 gap-4 text-xs text-text-secondary">
        <div className="space-y-1">
          <p className="font-semibold text-text-primary">Layer 1 — Inference</p>
          <p>Whisper, DeBERTa, MediaPipe, Fusion Engine. These are immutable. Every production model passes golden tests, regression gates, calibration validation, and human approval before deployment.</p>
        </div>
        <div className="space-y-1">
          <p className="font-semibold text-text-primary">Layer 2 — Behavioral Memory</p>
          <p>Candidate-scoped EMA profiles. Personalisation. Each candidate&apos;s communication patterns learned over time. Candidate-controlled and privacy-aware.</p>
        </div>
        <div className="space-y-1">
          <p className="font-semibold text-text-primary">Layer 3 — Behavioral Knowledge</p>
          <p>This page. Cross-candidate validated knowledge. Behavioural archetypes, coaching effectiveness, org intelligence. Confidence grows through recruiter validation and hiring outcomes — not automatic retraining.</p>
        </div>
      </div>
      <p className="mt-3 text-2xs text-text-disabled border-t border-border-subtle pt-3">
        Production AI models are never modified by observed data. Knowledge confidence is always proportional to its validation level: automatic (0.20) → candidate feedback (0.45) → recruiter validation (0.70) → hiring decision (0.90) → long-term performance (1.00).
      </p>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function KnowledgePage() {
  const [stats,    setStats]    = useState<PlatformKnowledgeStats | null>(null)
  const [patterns, setPatterns] = useState<BehavioralPatternItem[]>([])
  const [loading,  setLoading]  = useState(true)
  const [error,    setError]    = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [s, p] = await Promise.all([
        cbipApi.getKnowledgeStats(),
        cbipApi.getPatterns(),
      ])
      setStats(s)
      setPatterns(p.patterns)
    } catch {
      setError('Could not load knowledge data. Check that the backend is running.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const confPct = stats ? Math.round(stats.knowledge_confidence * 100) : 0

  return (
    <AppShell title="Behavioral Knowledge">
      <div className="p-6 max-w-5xl mx-auto page-enter space-y-8">

        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Network className="w-5 h-5 text-text-primary" />
              <h1 className="text-2xl font-bold text-text-primary">Behavioral Knowledge</h1>
            </div>
            <p className="text-sm text-text-muted max-w-2xl">
              Validated behavioural intelligence accumulated across interviews.
              Confidence grows through recruiter feedback and hiring outcomes — not automatic model retraining.
            </p>
          </div>
          <Button
            variant="secondary" size="sm"
            icon={<RefreshCw className="w-3.5 h-3.5" />}
            onClick={load}
            loading={loading}
          >
            Refresh
          </Button>
        </div>

        {/* Error */}
        {error && (
          <div className="flex items-start gap-3 px-4 py-3 border border-border text-xs text-text-secondary">
            <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
            {error}
          </div>
        )}

        {/* Stats */}
        {loading && !stats ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-20" />)}
          </div>
        ) : stats && (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <StatCard
                label="Sessions Observed" value={stats.total_sessions_observed}
                icon={Database}
                sub="L1 automatic signals"
              />
              <StatCard
                label="Recruiter Validated" value={stats.recruiter_validated}
                icon={CheckCircle2}
                sub="L3 expert feedback"
                highlight={stats.recruiter_validated > 0}
              />
              <StatCard
                label="Hiring Decisions" value={stats.hiring_decisions}
                icon={Users}
                sub="L4 org ground truth"
                highlight={stats.hiring_decisions > 0}
              />
              <StatCard
                label="Long-term Outcomes" value={stats.long_term_outcomes}
                icon={TrendingUp}
                sub="L5 performance data"
                highlight={stats.long_term_outcomes > 0}
              />
              <StatCard
                label="Patterns Discovered" value={stats.patterns_discovered}
                icon={Network}
                sub={`${stats.patterns_validated} validated`}
              />
              <StatCard
                label="Orgs Tracked" value={stats.orgs_tracked}
                icon={BarChart3}
                sub="Organisation intelligence"
              />
              <StatCard
                label="Coaching Records" value={stats.coaching_records}
                icon={BookOpen}
                sub={stats.coaching_effectiveness_pct != null
                  ? `${stats.coaching_effectiveness_pct}% effective`
                  : 'Outcomes pending'}
              />
              <StatCard
                label="Knowledge Confidence" value={`${confPct}%`}
                icon={ShieldCheck}
                sub="Validation-weighted mean"
                highlight={confPct > 30}
              />
            </div>

            {/* Confidence explanation */}
            <div className="rounded-xl border border-border bg-bg-card p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-text-muted">Platform knowledge confidence</span>
                <span className="text-xs font-mono text-text-secondary">{confPct}%</span>
              </div>
              <div className="h-1.5 bg-border rounded-none overflow-hidden mb-2">
                <div
                  className="h-full transition-all duration-700"
                  style={{
                    width: `${confPct}%`,
                    background: confPct >= 50 ? 'var(--color-metric-engagement)'
                      : confPct >= 20 ? 'var(--color-status-warning)'
                      : 'var(--color-text-disabled)',
                  }}
                />
              </div>
              <p className="text-2xs text-text-disabled">
                Weighted mean of all validation events. Starts at 0.20 (automatic observations) and
                grows as recruiter feedback (0.70), hiring decisions (0.90), and long-term outcomes (1.00) accumulate.
              </p>
            </div>
          </>
        )}

        {/* Patterns */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-text-primary">Behavioural Archetypes</h2>
            <Badge variant="muted">{patterns.length} patterns</Badge>
          </div>

          {loading && !patterns.length ? (
            <div className="grid md:grid-cols-2 gap-4">
              {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-52" />)}
            </div>
          ) : patterns.length ? (
            <div className="grid md:grid-cols-2 gap-4">
              {patterns.map(p => <PatternCard key={p.pattern_id} p={p} />)}
            </div>
          ) : (
            <div className="flex flex-col items-center py-16 text-center space-y-3">
              <Network className="w-10 h-10 text-text-disabled" />
              <p className="text-sm text-text-primary font-medium">No patterns yet</p>
              <p className="text-xs text-text-muted max-w-sm">
                Behavioural archetypes form as sessions accumulate. Complete interviews with
                candidate IDs to begin building platform knowledge.
              </p>
            </div>
          )}
        </div>

        {/* Architecture note */}
        <ArchitectureNote />

      </div>
    </AppShell>
  )
}
