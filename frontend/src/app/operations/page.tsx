'use client'
import { useState, useEffect, useCallback } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { Button } from '@/components/ui/Button'
import {
  Activity, RefreshCw, AlertTriangle, CheckCircle, XCircle, HelpCircle,
  Server, Database, Cpu, HardDrive, Zap, BrainCircuit, Layers, BarChart3,
  Clock, Shield, ShieldAlert,
} from 'lucide-react'
import { observabilityApi } from '@/lib/api'
import type { HealthReport, AlertsReport, ResourceSnapshot, HealthComponent } from '@/lib/api'
import { cn } from '@/lib/utils'
import { Skeleton } from '@/components/ui/Skeleton'

// ── Status helpers ────────────────────────────────────────────────────────────

function statusColor(status: string): string {
  if (status === 'healthy')   return '#34d399'
  if (status === 'degraded')  return '#fbbf24'
  if (status === 'unhealthy') return '#f87171'
  return '#6b7280'
}

function alertColor(level: string): string {
  if (level === 'critical') return '#f87171'
  if (level === 'warning')  return '#fbbf24'
  return '#60a5fa'
}

function ageStr(seconds: number): string {
  if (seconds < 60)   return `${seconds}s ago`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  return `${Math.floor(seconds / 3600)}h ago`
}

// ── Status icon ───────────────────────────────────────────────────────────────

function StatusIcon({ status, size = 'sm' }: { status: string; size?: 'sm' | 'md' }) {
  const cls = size === 'md' ? 'w-5 h-5' : 'w-4 h-4'
  if (status === 'healthy')   return <CheckCircle  className={cn(cls, 'text-status-success')} />
  if (status === 'degraded')  return <AlertTriangle className={cn(cls, 'text-status-warning')} />
  if (status === 'unhealthy') return <XCircle      className={cn(cls, 'text-status-danger')} />
  return <HelpCircle className={cn(cls, 'text-text-muted')} />
}

// ── Resource gauge (arc SVG) ──────────────────────────────────────────────────

function ResourceGauge({
  label, pct, value, sub, color, icon: Icon,
}: {
  label: string; pct: number; value: string; sub?: string; color: string; icon: React.ElementType
}) {
  return (
    <div className="rounded-xl border border-border bg-bg-card p-5 card-hover">
      <div className="flex items-center gap-2 mb-4">
        <Icon className="w-4 h-4 text-text-muted" />
        <span className="text-xs font-semibold text-text-muted uppercase tracking-widest">{label}</span>
      </div>
      <div className="flex items-center justify-center mb-4">
        <svg viewBox="0 0 100 60" width="140" height="84" className="overflow-visible">
          <path d="M 10 55 A 40 40 0 0 1 90 55"
            fill="none" stroke="#27272a" strokeWidth="8" strokeLinecap="round" />
          {pct > 0 && (
            <path d="M 10 55 A 40 40 0 0 1 90 55"
              fill="none" stroke={color} strokeWidth="8" strokeLinecap="round"
              strokeDasharray={`${pct * 1.257} 999`}
            />
          )}
          <text x="50" y="52" textAnchor="middle" fill="#f4f4f5" fontSize="14"
            fontWeight="700" fontFamily="'JetBrains Mono', monospace">
            {value}
          </text>
        </svg>
      </div>
      <div className="h-1.5 bg-bg-hover rounded-full overflow-hidden">
        <div className="h-full rounded-full bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      {sub && <p className="text-2xs text-text-muted mt-2 text-center">{sub}</p>}
    </div>
  )
}

// ── Component health card ─────────────────────────────────────────────────────

const COMPONENT_ICONS: Record<string, React.ElementType> = {
  database:              Database,
  reasoning_engine:      BrainCircuit,
  model_registry:        Layers,
  session_manager:       Activity,
  event_bus:             Zap,
  feature_store:         BarChart3,
  ai_lifecycle_registry: Server,
  memory:                Cpu,
  storage:               HardDrive,
}

function ComponentCard({ component }: { component: HealthComponent }) {
  const color = statusColor(component.status)
  const Icon  = COMPONENT_ICONS[component.name] ?? Server
  const details = Object.entries(component.details ?? {}).slice(0, 3)

  return (
    <div className="rounded-xl border bg-bg-card p-4 card-hover"
      style={{ borderColor: `${color}28` }}>
      <div className="flex items-center gap-2 mb-3">
        <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
          style={{ background: `${color}15` }}>
          <Icon className="w-4 h-4" style={{ color }} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs font-semibold text-text-primary capitalize">
            {component.name.replace(/_/g, ' ')}
          </p>
          {component.latency_ms != null && (
            <p className="text-2xs text-text-muted">{component.latency_ms.toFixed(1)} ms</p>
          )}
        </div>
        <StatusIcon status={component.status} />
      </div>

      {component.error && (
        <p className="text-2xs text-metric-stress bg-metric-stress/5 rounded px-2 py-1 mb-2 truncate">
          {component.error}
        </p>
      )}

      {details.length > 0 && (
        <div className="space-y-1">
          {details.map(([k, v]) => (
            <div key={k} className="flex items-center justify-between text-2xs">
              <span className="text-text-disabled capitalize">{k.replace(/_/g, ' ')}</span>
              <span className="font-mono text-text-muted">{String(v)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Stat mini card ────────────────────────────────────────────────────────────

function StatCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-bg-hover border border-border-subtle p-3">
      <p className="text-2xs text-text-muted uppercase tracking-widest mb-1">{label}</p>
      <p className="text-sm font-bold font-mono text-text-primary">{value}</p>
    </div>
  )
}


// ── Page ──────────────────────────────────────────────────────────────────────

export default function OperationsPage() {
  const [health,    setHealth]    = useState<HealthReport | null>(null)
  const [alerts,    setAlerts]    = useState<AlertsReport | null>(null)
  const [resources, setResources] = useState<ResourceSnapshot | null>(null)
  const [loading,   setLoading]   = useState(true)
  const [error,     setError]     = useState<string | null>(null)
  const [checkedAt, setCheckedAt] = useState<Date | null>(null)

  const load = useCallback(async () => {
    setError(null)
    try {
      const [h, a, r] = await Promise.allSettled([
        observabilityApi.getHealthFull(),
        observabilityApi.getAlerts(),
        observabilityApi.getResources(),
      ])
      if (h.status === 'fulfilled') setHealth(h.value)
      else setError('Health check failed. Verify the backend is running.')
      if (a.status === 'fulfilled') setAlerts(a.value)
      if (r.status === 'fulfilled') setResources(r.value)
      setCheckedAt(new Date())
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const id = setInterval(load, 15_000)
    return () => clearInterval(id)
  }, [load])

  const overallStatus    = health?.status ?? 'unknown'
  const firingCritical   = alerts?.alerts.filter(a => a.level === 'critical') ?? []
  const firingWarning    = alerts?.alerts.filter(a => a.level === 'warning') ?? []
  const sys              = resources?.system
  const proc             = resources?.process

  const statusBannerCls  = overallStatus === 'healthy'
    ? 'border-metric-engagement/30 bg-metric-engagement/5'
    : overallStatus === 'degraded'
    ? 'border-status-warning/30 bg-status-warning/5'
    : 'border-metric-stress/30 bg-metric-stress/5'

  const statusTextCls = overallStatus === 'healthy'
    ? 'text-metric-engagement'
    : overallStatus === 'degraded'
    ? 'text-status-warning'
    : 'text-metric-stress'

  return (
    <AppShell
      title="Operations"
      actions={
        <div className="flex items-center gap-3">
          {checkedAt && (
            <span className="text-2xs text-text-muted hidden sm:block">
              Checked {checkedAt.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}
            </span>
          )}
          <Button variant="ghost" size="sm" icon={<RefreshCw className="w-3.5 h-3.5" />} onClick={load}>
            Refresh
          </Button>
        </div>
      }
    >
      <div className="p-6 space-y-8 max-w-6xl page-enter">

        {error && (
          <div className="rounded-xl border border-status-warning/30 bg-status-warning/5 px-4 py-3 text-xs text-status-warning">
            {error}
          </div>
        )}

        {/* ── Overall status banner ── */}
        {!loading && health && (
          <div className={`rounded-xl border p-4 flex items-center gap-4 ${statusBannerCls}`}>
            <StatusIcon status={overallStatus} size="md" />
            <div className="flex-1">
              <p className={`text-sm font-bold capitalize ${statusTextCls}`}>
                Platform {overallStatus}
              </p>
              <p className="text-2xs text-text-muted">
                {health.summary.healthy} healthy · {health.summary.degraded} degraded ·{' '}
                {health.summary.unhealthy} unhealthy ·{' '}
                v{health.version} · {health.environment} · checked in {health.duration_ms.toFixed(0)} ms
              </p>
            </div>
            {alerts && (
              <div className="flex items-center gap-4 text-xs">
                <span className={cn(
                  'flex items-center gap-1.5',
                  firingCritical.length ? 'text-metric-stress' : 'text-text-disabled',
                )}>
                  <ShieldAlert className="w-3.5 h-3.5" />
                  {firingCritical.length} critical
                </span>
                <span className={cn(
                  'flex items-center gap-1.5',
                  firingWarning.length ? 'text-status-warning' : 'text-text-disabled',
                )}>
                  <AlertTriangle className="w-3.5 h-3.5" />
                  {firingWarning.length} warning
                </span>
              </div>
            )}
          </div>
        )}

        {loading && <Skeleton className="h-20 rounded-xl" />}

        {/* ── Active alerts ── */}
        {!loading && alerts && alerts.alerts.length > 0 && (
          <section>
            <div className="flex items-center gap-2 mb-4">
              <ShieldAlert className="w-4 h-4 text-metric-stress" />
              <h2 className="text-sm font-semibold text-text-primary">Active Alerts</h2>
              <span className="text-2xs font-mono text-metric-stress ml-1">
                {alerts.firing} firing / {alerts.total_rules} rules
              </span>
            </div>
            <div className="space-y-2">
              {alerts.alerts.map(alert => {
                const color = alertColor(alert.level)
                return (
                  <div key={alert.name}
                    className="rounded-xl border px-4 py-3 flex items-start gap-3"
                    style={{ borderColor: `${color}30`, background: `${color}08` }}>
                    <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" style={{ color }} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-xs font-semibold text-text-primary capitalize">
                          {alert.name.replace(/_/g, ' ')}
                        </span>
                        <span className="text-2xs px-1.5 py-0.5 rounded font-semibold uppercase"
                          style={{ color, background: `${color}18` }}>
                          {alert.level}
                        </span>
                        <span className="text-2xs text-text-disabled ml-auto flex items-center gap-1 flex-shrink-0">
                          <Clock className="w-3 h-3" />
                          {ageStr(alert.age_seconds)}
                        </span>
                      </div>
                      <p className="text-2xs text-text-muted">{alert.message}</p>
                    </div>
                  </div>
                )
              })}
            </div>
          </section>
        )}

        {/* ── All-clear notice ── */}
        {!loading && alerts && alerts.alerts.length === 0 && (
          <div className="rounded-xl border border-metric-engagement/20 bg-metric-engagement/5 px-4 py-3 flex items-center gap-3">
            <CheckCircle className="w-4 h-4 text-metric-engagement flex-shrink-0" />
            <p className="text-xs text-metric-engagement">
              All {alerts.total_rules} alert rules passing — no active alerts
            </p>
            {checkedAt && (
              <span className="text-2xs text-text-muted ml-auto">
                as of {checkedAt.toLocaleTimeString()}
              </span>
            )}
          </div>
        )}

        {/* ── Live resources ── */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <Cpu className="w-4 h-4 text-accent" />
            <h2 className="text-sm font-semibold text-text-primary">Live Resources</h2>
            <span className="ml-auto text-2xs text-metric-engagement flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-metric-engagement animate-pulse" />
              15s refresh
            </span>
          </div>

          {loading ? (
            <div className="grid sm:grid-cols-3 gap-4">
              {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-48" />)}
            </div>
          ) : sys ? (
            <>
              <div className="grid sm:grid-cols-3 gap-4">
                <ResourceGauge
                  label="CPU Utilization"
                  icon={Cpu}
                  color="#818cf8"
                  pct={sys.cpu_percent}
                  value={`${Math.round(sys.cpu_percent)}%`}
                  sub={`${sys.cpu_count} logical cores`}
                />
                <ResourceGauge
                  label="Memory Usage"
                  icon={Server}
                  color="#60a5fa"
                  pct={sys.memory_percent}
                  value={`${Math.round(sys.memory_percent)}%`}
                  sub={`${(sys.memory_available_mb / 1024).toFixed(1)} GB free of ${(sys.memory_total_mb / 1024).toFixed(1)} GB`}
                />
                <ResourceGauge
                  label="Disk Usage"
                  icon={HardDrive}
                  color={sys.disk_percent > 85 ? '#f87171' : '#34d399'}
                  pct={sys.disk_percent}
                  value={`${Math.round(sys.disk_percent)}%`}
                  sub={`${sys.disk_free_gb.toFixed(1)} GB free of ${sys.disk_total_gb.toFixed(1)} GB`}
                />
              </div>

              {proc && (
                <div className="mt-4 grid grid-cols-2 sm:grid-cols-5 gap-3">
                  <StatCell label="Process RSS"  value={`${proc.memory_rss_mb.toFixed(0)} MB`} />
                  <StatCell label="Process CPU"  value={`${proc.cpu_percent.toFixed(1)}%`} />
                  <StatCell label="Threads"      value={String(proc.threads)} />
                  <StatCell label="Open files"   value={String(proc.open_files)} />
                  <StatCell label="PID"          value={String(proc.pid)} />
                </div>
              )}
            </>
          ) : (
            <div className="rounded-xl border border-border-subtle bg-bg-card p-8 text-center">
              <p className="text-xs text-text-muted">
                Resource data unavailable
                {resources?.error ? ` — ${resources.error}` : ' (psutil may not be installed)'}
              </p>
            </div>
          )}
        </section>

        {/* ── Component health grid ── */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <Activity className="w-4 h-4 text-accent" />
            <h2 className="text-sm font-semibold text-text-primary">Component Health</h2>
            {health && (
              <span className="text-2xs text-text-muted ml-1">
                {health.components.length} components · {health.duration_ms.toFixed(0)} ms total
              </span>
            )}
          </div>

          {loading ? (
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-28" />)}
            </div>
          ) : health && health.components.length > 0 ? (
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {health.components.map(c => (
                <ComponentCard key={c.name} component={c} />
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-border-subtle bg-bg-card p-8 text-center">
              <p className="text-xs text-text-muted">No component data — start the backend to see health checks.</p>
            </div>
          )}
        </section>

        {/* ── Prometheus notice ── */}
        <div className="rounded-xl border border-border-subtle bg-bg-hover px-5 py-4 flex items-start gap-3">
          <Shield className="w-4 h-4 text-text-muted flex-shrink-0 mt-0.5" />
          <p className="text-2xs text-text-muted leading-relaxed">
            <strong className="text-text-secondary">Prometheus scrape endpoint: </strong>
            <code className="font-mono text-accent text-2xs">GET /metrics</code>
            {' '}exposes all platform metrics in text exposition format (v0.0.4).
            Add it as a scrape target in <code className="font-mono">prometheus.yml</code> to enable Grafana dashboards.
            JSON metrics also available at <code className="font-mono text-accent text-2xs">GET /metrics/json</code>.
          </p>
        </div>

      </div>
    </AppShell>
  )
}
