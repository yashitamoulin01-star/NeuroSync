'use client'
import { useState, useEffect, useCallback, useRef } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { AppShell } from '@/components/layout/AppShell'
import { KPICard } from '@/components/dashboard/KPICard'
import { Button } from '@/components/ui/Button'
import dynamic from 'next/dynamic'
import { Badge } from '@/components/ui/Badge'
import { InsightCard } from '@/components/session/InsightCard'
import { useAuth } from '@/lib/auth'
import { EmptyState } from '@/components/ui/EmptyState'
import { BackendOffline } from '@/components/ui/BackendOffline'
import { UpcomingInterviews } from '@/components/dashboard/UpcomingInterviews'
import { cn } from '@/lib/utils'

const BehavioralFingerprint = dynamic(
  () => import('@/components/charts/BehavioralFingerprint').then((mod) => mod.BehavioralFingerprint),
  { ssr: false, loading: () => <div className="w-[200px] h-[200px] rounded-full skeleton" /> }
)
const SessionTable = dynamic(
  () => import('@/components/dashboard/SessionTable').then((mod) => mod.SessionTable),
  { ssr: false, loading: () => <div className="h-40 w-full rounded skeleton" /> }
)
import {
  Zap, TrendingUp, Brain, Activity,
  ArrowRight, AlertCircle, RefreshCw, CheckCircle,
  AlertTriangle, Cpu, BarChart3, Users, Shield,
} from 'lucide-react'
import { api } from '@/lib/api'
import type { DashboardStats, SessionRow, BehavioralInsight } from '@/lib/types'
import type { SessionRow as TableRow } from '@/components/dashboard/SessionTable'
import { Skeleton } from '@/components/ui/Skeleton'

// ── Tier computation ──────────────────────────────────────────────────────────

function tierFromRow(s: TableRow): 'proceed' | 'review' | 'hold' {
  const score = Math.round((s.confidence + s.engagement + s.communication + (1 - s.stress)) / 4 * 100)
  if (s.wordsSpoken < 200) return 'review'
  if (score >= 72 && s.stress < 0.45) return 'proceed'
  if (score >= 52 && s.stress < 0.60) return 'review'
  return 'hold'
}

function scoreFromRow(s: TableRow): number {
  return Math.round((s.confidence + s.engagement + s.communication + (1 - s.stress)) / 4 * 100)
}

// ── Skeletons ─────────────────────────────────────────────────────────────────

function KPISkeleton() {
  return (
    <div className="flex flex-col gap-2 border-l border-border pl-4 py-1">
      <div className="flex items-center gap-1.5">
        <Skeleton className="h-3.5 w-3.5 rounded-full" />
        <Skeleton className="h-3 w-20" />
      </div>
      <Skeleton className="h-8 w-16 mt-1" />
    </div>
  )
}

function EmptySessions() {
  const router = useRouter()
  return (
    <EmptyState
      icon={Activity}
      title="No sessions yet"
      description="Start your first behavioral analysis session to see data here."
      actionLabel="Start a session"
      onAction={() => router.push('/session/new')}
    />
  )
}

function normalizeRows(sessions: SessionRow[]): TableRow[] {
  return sessions.map(s => ({
    id:            s.id,
    name:          s.name,
    mode:          s.mode as TableRow['mode'],
    startedAt:     s.started_at ?? s.startedAt ?? new Date().toISOString(),
    duration:      s.duration,
    confidence:    s.avg_confidence    ?? s.confidence    ?? 0,
    stress:        s.avg_stress        ?? s.stress        ?? 0,
    communication: s.avg_communication ?? s.communication ?? 0,
    engagement:    s.avg_engagement    ?? s.engagement    ?? 0,
    fillerWords:   s.total_filler_words ?? s.fillerWords  ?? 0,
    wordsSpoken:   s.total_words        ?? s.wordsSpoken  ?? 0,
  }))
}

// ── Main ─────────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const { user } = useAuth()
  const retryRef  = useRef<ReturnType<typeof setTimeout>>()
  const mountedRef = useRef(true)
  const [stats,    setStats]    = useState<DashboardStats | null>(null)
  const [sessions, setSessions] = useState<TableRow[]>([])
  const [filter,   setFilter]   = useState<'all' | 'interview' | 'coaching' | 'presentation'>('all')
  const [loading,  setLoading]  = useState(true)
  const [error,    setError]    = useState<string | null>(null)
  const [online,   setOnline]   = useState<boolean | null>(null)

  const load = useCallback(async () => {
    if (!mountedRef.current) return
    setLoading(true)
    setError(null)
    try {
      const [statsRes, sessRes, health] = await Promise.all([
        api.dashboardStats(),
        api.getSessions({ limit: 50 }),
        api.healthDetailed().catch(() => null),
      ])
      if (!mountedRef.current) return
      setStats(statsRes)
      setSessions(normalizeRows(sessRes.sessions))
      setOnline(health != null ? (health as any).status === 'ok' : true)
    } catch {
      if (!mountedRef.current) return
      setError('Backend unavailable. Retrying...')
      setOnline(false)
      retryRef.current = setTimeout(load, 5000)
    } finally {
      if (mountedRef.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    mountedRef.current = true
    load()
    return () => {
      mountedRef.current = false
      clearTimeout(retryRef.current)
    }
  }, [load])

  const filtered: TableRow[] = filter === 'all'
    ? sessions
    : sessions.filter(s => s.mode === filter)

  // Pipeline distribution
  const pipeline = {
    proceed: sessions.filter(s => tierFromRow(s) === 'proceed').length,
    review:  sessions.filter(s => tierFromRow(s) === 'review').length,
    hold:    sessions.filter(s => tierFromRow(s) === 'hold').length,
  }
  const proceedRate = sessions.length
    ? Math.round(pipeline.proceed / sessions.length * 100)
    : 0
  const avgOverallScore = sessions.length
    ? Math.round(sessions.reduce((sum, s) => sum + scoreFromRow(s), 0) / sessions.length)
    : 0

  // Sessions in last 24h
  const oneDayAgo = Date.now() - 24 * 60 * 60 * 1000
  const todaySessions = sessions.filter(s => {
    const ts = typeof s.startedAt === 'number'
      ? (s.startedAt as number) * 1000
      : new Date(s.startedAt as string).getTime()
    return ts > oneDayAgo
  })

  // Last session
  const lastSession = sessions[0] ?? null
  const lastTier    = lastSession ? tierFromRow(lastSession) : null

  // Critical flags (high stress in last 10)
  const criticalSessions = sessions.slice(0, 10).filter(s => s.stress > 0.50).length

  // Insights from recent sessions
  const recentInsights: BehavioralInsight[] = []
  if (stats?.recent_sessions) {
    for (const s of stats.recent_sessions) {
      const arr = (s as any).insights
      if (Array.isArray(arr)) recentInsights.push(...arr)
    }
  }
  const criticalInsights = recentInsights.filter(i => i.severity >= 0.5).length
  const totalFlags = criticalInsights + criticalSessions

  const fingerprintData = stats ? {
    confidence:    stats.avg_confidence,
    communication: stats.avg_communication,
    engagement:    stats.avg_engagement,
    stress:        stats.avg_stress,
    consistency:   stats.avg_consistency ?? 0,
  } : { confidence: 0, communication: 0, engagement: 0, stress: 0, consistency: 0 }

  const displayName = user?.display_name || (user?.email ? user.email.split('@')[0] : 'Recruiter')

  const TIER_COLOR = { proceed: '#34d399', review: '#fbbf24', hold: '#f87171' } as const

  if (error && !loading && sessions.length === 0) {
    return (
      <AppShell title="Dashboard">
        <div className="p-6 max-w-3xl mx-auto mt-12">
          <BackendOffline onRetry={load} />
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell
      title="Dashboard"
      actions={
        <div className="flex items-center gap-2">
          {error && (
            <button
              onClick={load}
              className="flex items-center gap-1.5 text-xs text-status-warning hover:text-text-primary transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Reconnect
            </button>
          )}
          <Link href="/session/new">
            <Button variant="primary" size="sm" icon={<Zap className="w-3.5 h-3.5" />}>
              New Session
            </Button>
          </Link>
        </div>
      }
    >
      <div className="p-6 space-y-8 max-w-7xl page-enter">

        {/* ── Backend unavailable banner ───────────────────────────────────── */}
        {error && !loading && sessions.length > 0 && (
          <div className="flex items-center gap-3 rounded-xl border border-status-warning/30 bg-status-warning/5 px-4 py-3">
            <AlertCircle className="w-4 h-4 text-status-warning flex-shrink-0" />
            <p className="text-xs text-status-warning">
              NeuroSync backend is unreachable. Reconnecting automatically...
            </p>
            <button onClick={load} className="ml-auto text-xs text-status-warning underline">
              Retry now
            </button>
          </div>
        )}

        {/* ── Section 1: Executive Summary Banner ──────────────────────────── */}
        <div className="rounded-xl border border-border bg-bg-card overflow-hidden">
          <div className="flex items-center justify-between px-5 py-3 border-b border-border">
            <div className="flex items-center gap-2.5">
              <span className="label-xs text-text-disabled">Operational Status</span>
              {loading && (
                <div className="w-3 h-3 rounded-full border-2 border-border border-t-accent/60 animate-spin" />
              )}
            </div>
            <span className="text-2xs text-text-disabled">
              {new Date().toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}
              {displayName ? ` · ${displayName}` : ''}
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 divide-x divide-y sm:divide-y-0 lg:divide-y-0 divide-border">

            {/* 1. Platform status */}
            <div className="px-5 py-4">
              <p className="label-xs text-text-disabled mb-2">Platform</p>
              {loading ? <Skeleton className="h-5 w-16" /> : (
                <div className="flex items-center gap-1.5">
                  <span className={cn('w-1.5 h-1.5 rounded-full flex-shrink-0',
                    online ? 'bg-status-success' : 'bg-status-danger'
                  )} />
                  <span className={cn('text-sm font-semibold',
                    online ? 'text-status-success' : 'text-status-danger'
                  )}>
                    {online === null ? '…' : online ? 'Active' : 'Offline'}
                  </span>
                </div>
              )}
            </div>

            {/* 2. Sessions today */}
            <div className="px-5 py-4">
              <p className="label-xs text-text-disabled mb-2">Today</p>
              {loading ? <Skeleton className="h-5 w-16" /> : (
                <span className="text-sm font-bold font-mono text-text-primary">
                  {todaySessions.length} <span className="font-normal text-text-muted text-xs">sessions</span>
                </span>
              )}
            </div>

            {/* 3. Pipeline distribution */}
            <div className="px-5 py-4">
              <p className="label-xs text-text-disabled mb-2">Pipeline</p>
              {loading ? <Skeleton className="h-5 w-28" /> : sessions.length ? (
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold font-mono text-status-success">{pipeline.proceed}</span>
                  <span className="text-border text-xs">·</span>
                  <span className="text-sm font-bold font-mono text-status-warning">{pipeline.review}</span>
                  <span className="text-border text-xs">·</span>
                  <span className="text-sm font-bold font-mono text-status-danger">{pipeline.hold}</span>
                  <span className="text-2xs text-text-disabled ml-0.5">P·R·H</span>
                </div>
              ) : (
                <span className="text-sm text-text-disabled">—</span>
              )}
            </div>

            {/* 4. Critical flags */}
            <div className="px-5 py-4">
              <p className="label-xs text-text-disabled mb-2">Flags</p>
              {loading ? <Skeleton className="h-5 w-10" /> : (
                <div className="flex items-center gap-1.5">
                  {totalFlags > 0
                    ? <AlertTriangle className="w-3.5 h-3.5 text-status-warning flex-shrink-0" />
                    : <CheckCircle className="w-3.5 h-3.5 text-status-success flex-shrink-0" />
                  }
                  <span className={cn('text-sm font-bold font-mono',
                    totalFlags > 0 ? 'text-status-warning' : 'text-status-success'
                  )}>
                    {totalFlags === 0 ? 'None' : totalFlags}
                  </span>
                </div>
              )}
            </div>

            {/* 5. Last session verdict */}
            <div className="px-5 py-4">
              <p className="label-xs text-text-disabled mb-2">Last Session</p>
              {loading ? <Skeleton className="h-5 w-20" /> : lastSession ? (
                <div className="flex items-center gap-1.5">
                  <span
                    className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                    style={{ background: TIER_COLOR[lastTier!] }}
                  />
                  <span className="text-sm font-semibold text-text-primary capitalize">{lastTier}</span>
                </div>
              ) : (
                <span className="text-sm text-text-disabled">—</span>
              )}
            </div>

            {/* 6. Proceed rate */}
            <div className="px-5 py-4">
              <p className="label-xs text-text-disabled mb-2">Proceed Rate</p>
              {loading ? <Skeleton className="h-5 w-14" /> : (
                <span className="text-sm font-bold font-mono text-text-primary">
                  {sessions.length ? `${proceedRate}%` : '—'}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* ── Upcoming Interviews (renders only when connectors are set up) ── */}
        <UpcomingInterviews />

        {/* ── Section 2: KPI Row ────────────────────────────────────────────── */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {loading ? (
            Array.from({ length: 4 }).map((_, i) => <KPISkeleton key={i} />)
          ) : (
            <>
              <KPICard
                label="Avg behavioral score"
                value={sessions.length ? `${avgOverallScore}` : '—'}
                color="#818cf8"
                history={[]}
                icon={<BarChart3 className="w-3.5 h-3.5" />}
              />
              <KPICard
                label="Proceed rate"
                value={sessions.length ? `${proceedRate}%` : '—'}
                color="#34d399"
                history={[]}
                icon={<TrendingUp className="w-3.5 h-3.5" />}
              />
              <KPICard
                label="Avg confidence"
                value={stats ? `${Math.round(stats.avg_confidence * 100)}%` : '—'}
                color="#818cf8"
                history={[]}
                icon={<Activity className="w-3.5 h-3.5" />}
              />
              <KPICard
                label="Total sessions"
                value={stats?.total_sessions ?? 0}
                color="#60a5fa"
                history={[]}
                icon={<Users className="w-3.5 h-3.5" />}
              />
            </>
          )}
        </div>

        {/* ── Section 3: Live Activity ──────────────────────────────────────── */}
        <div>
          <div className="flex items-center justify-between mb-5">
            <div>
              <p className="label-xs text-text-disabled mb-1">Live Activity</p>
              <h3 className="text-base font-bold text-text-primary">Recent Sessions</h3>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex rounded-lg border border-border overflow-hidden">
                {(['all', 'interview', 'coaching', 'presentation'] as const).map(f => (
                  <button
                    key={f}
                    onClick={() => setFilter(f)}
                    className={cn(
                      'px-3 py-1.5 text-xs font-medium transition-colors border-r border-border last:border-0',
                      filter === f
                        ? 'bg-bg-hover text-text-primary'
                        : 'text-text-muted hover:text-text-secondary',
                    )}
                  >
                    {f === 'all' ? 'All' : f.charAt(0).toUpperCase() + f.slice(1)}
                  </button>
                ))}
              </div>
              <Link href="/history">
                <Button variant="ghost" size="sm" iconRight={<ArrowRight className="w-3.5 h-3.5" />}>
                  All sessions
                </Button>
              </Link>
            </div>
          </div>

          {loading ? (
            <div className="space-y-3">
              {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
            </div>
          ) : filtered.length > 0 ? (
            <SessionTable rows={filtered.slice(0, 10)} />
          ) : (
            <EmptySessions />
          )}
        </div>

        {/* ── Section 4: Behavioral Intelligence ───────────────────────────── */}
        <div className="grid lg:grid-cols-3 gap-8 pt-6 border-t border-border">

          {/* Cohort fingerprint */}
          <div>
            <p className="label-xs text-text-disabled mb-1">Behavioral Intelligence</p>
            <h3 className="text-base font-bold text-text-primary mb-5">Cohort Average</h3>
            {loading ? (
              <div className="flex flex-col items-center gap-4">
                <Skeleton className="w-[200px] h-[200px] rounded-full" />
                <div className="w-full space-y-2">
                  {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-3 w-full" />)}
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-4">
                <BehavioralFingerprint data={fingerprintData} size={200} animated />
                <div className="w-full grid grid-cols-2 gap-x-6 gap-y-1.5">
                  {[
                    { label: 'Confidence',  value: fingerprintData.confidence },
                    { label: 'Engagement',  value: fingerprintData.engagement },
                    { label: 'Comm.',       value: fingerprintData.communication },
                    { label: 'Consistency', value: fingerprintData.consistency },
                    { label: 'Composure',   value: 1 - fingerprintData.stress },
                  ].map(d => (
                    <div key={d.label} className="flex items-center justify-between border-b border-border-subtle py-1">
                      <span className="text-xs text-text-muted">{d.label}</span>
                      <span className="text-2xs font-mono font-medium text-text-secondary">
                        {Math.round(d.value * 100)}%
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Signal insights */}
          <div className="lg:col-span-2">
            <div className="flex items-center justify-between mb-5">
              <div>
                <p className="label-xs text-text-disabled mb-1">Signal Analysis</p>
                <h3 className="text-base font-bold text-text-primary">Recent Insights</h3>
              </div>
              {criticalInsights > 0 && (
                <Badge variant="warning" dot>{criticalInsights} critical</Badge>
              )}
            </div>

            {loading ? (
              <div className="space-y-3">
                {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-14 w-full" />)}
              </div>
            ) : recentInsights.length > 0 ? (
              <div>
                {recentInsights.slice(0, 5).map((ins, i) => (
                  <InsightCard key={i} insight={ins} compact />
                ))}
              </div>
            ) : (
              <div className="rounded-xl border border-border bg-bg-card py-10 flex flex-col items-center">
                <Brain className="w-8 h-8 text-text-disabled mb-3" />
                <p className="text-xs text-text-muted">
                  {stats?.total_sessions
                    ? 'No behavioral insights in recent sessions.'
                    : 'Complete a session to see behavioral insights.'}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* ── Section 5: Platform Operations ───────────────────────────────── */}
        <div className="rounded-xl border border-border bg-bg-card px-5 py-3.5 flex flex-wrap items-center gap-x-6 gap-y-2">
          <p className="label-xs text-text-disabled">Platform Operations</p>

          <div className="flex items-center gap-1.5">
            <Cpu className="w-3.5 h-3.5 text-text-muted" />
            <span className="text-xs text-text-secondary">MBA Engine</span>
            <span className={cn('text-2xs font-medium ml-1',
              online ? 'text-status-success' : 'text-text-disabled'
            )}>
              · {online === null ? '…' : online ? 'Active' : 'Offline'}
            </span>
          </div>

          <div className="flex items-center gap-1.5">
            <Brain className="w-3.5 h-3.5 text-text-muted" />
            <span className="text-xs text-text-secondary">DeBERTa v3</span>
            <span className="text-2xs text-text-disabled ml-1">· F1 82.4%</span>
          </div>

          <div className="flex items-center gap-1.5">
            <Shield className="w-3.5 h-3.5 text-text-muted" />
            <span className="text-xs text-text-secondary">AI Governance</span>
            <span className="text-2xs text-status-success ml-1">· Compliant</span>
          </div>

          <div className="ml-auto">
            <Link href="/operations">
              <Button variant="ghost" size="xs" iconRight={<ArrowRight className="w-3 h-3" />}>
                Full status
              </Button>
            </Link>
          </div>
        </div>

      </div>
    </AppShell>
  )
}
