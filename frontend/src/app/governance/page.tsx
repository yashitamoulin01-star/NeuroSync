'use client'
import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { AppShell } from '@/components/layout/AppShell'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import {
  Shield, BookOpen, AlertTriangle, Lock, Scale,
  CheckCircle, XCircle, Info, ExternalLink, ChevronRight,
  ClipboardList, FileCheck, Database, RefreshCw, Filter,
  AlertCircle, User, Clock, Server, FileText,
} from 'lucide-react'
import { useAuth } from '@/lib/auth'
import { enterpriseApi, setEnterpriseToken } from '@/lib/api'
import type { AuditEvent } from '@/lib/api'
import { cn } from '@/lib/utils'

// ── Shared primitives ─────────────────────────────────────────────────────────

function Section({
  id, icon: Icon, title, badge, children,
}: {
  id: string; icon: React.ElementType; title: string; badge?: string; children: React.ReactNode
}) {
  return (
    <section id={id} className="scroll-mt-6">
      <div className="flex items-center gap-3 mb-5">
        <div className="w-8 h-8 rounded-lg bg-accent/10 border border-accent/20 flex items-center justify-center flex-shrink-0">
          <Icon className="w-4 h-4 text-accent" />
        </div>
        <h2 className="text-base font-bold text-text-primary">{title}</h2>
        {badge && <Badge variant="muted">{badge}</Badge>}
      </div>
      <div className="space-y-4 pl-11">{children}</div>
    </section>
  )
}

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-border bg-bg-card p-5">
      {title && <p className="text-xs font-semibold text-text-muted uppercase tracking-widest mb-4">{title}</p>}
      {children}
    </div>
  )
}

function Row({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-6 py-2 border-b border-border-subtle last:border-0">
      <span className="text-xs text-text-muted flex-shrink-0 w-44">{label}</span>
      <span className={`text-xs text-right ${mono ? 'font-mono text-text-secondary' : 'text-text-secondary'}`}>
        {value}
      </span>
    </div>
  )
}

function ReviewTrigger({ text, severity }: { text: string; severity: 'mandatory' | 'recommended' }) {
  return (
    <div className={`flex items-start gap-3 py-2.5 px-3 rounded-lg ${
      severity === 'mandatory'
        ? 'bg-metric-stress/8 border border-metric-stress/20'
        : 'bg-status-warning/8 border border-status-warning/20'
    }`}>
      <AlertTriangle className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 ${
        severity === 'mandatory' ? 'text-metric-stress' : 'text-status-warning'
      }`} />
      <div>
        <span className={`text-2xs font-semibold uppercase tracking-wider ${
          severity === 'mandatory' ? 'text-metric-stress' : 'text-status-warning'
        }`}>
          {severity === 'mandatory' ? 'Mandatory' : 'Recommended'}
        </span>
        <p className="text-xs text-text-secondary mt-0.5">{text}</p>
      </div>
    </div>
  )
}

function FairnessItem({ assessed, text }: { assessed: boolean; text: string }) {
  const Icon = assessed ? CheckCircle : XCircle
  return (
    <div className="flex items-start gap-2.5 py-2">
      <Icon className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 ${assessed ? 'text-metric-engagement' : 'text-text-disabled'}`} />
      <p className="text-xs text-text-secondary leading-relaxed">{text}</p>
    </div>
  )
}

// ── Table of contents ─────────────────────────────────────────────────────────

const TOC = [
  { id: 'model-registry',      label: 'Model Registry',                icon: BookOpen },
  { id: 'calibration',         label: 'Confidence Calibration',        icon: Scale },
  { id: 'human-review',        label: 'Human Review Policy',           icon: AlertTriangle },
  { id: 'fairness',            label: 'Fairness & Bias',               icon: Scale },
  { id: 'privacy',             label: 'Data Privacy Controls',         icon: Lock },
  { id: 'limitations',         label: 'Known Limitations',             icon: Info },
  { id: 'audit',               label: 'Audit & Record-keeping',        icon: Shield },
]

// ── Audit Log panel ───────────────────────────────────────────────────────────

const SEVERITY_COLORS: Record<string, string> = {
  info:     'text-accent     bg-accent/10     border-accent/20',
  warning:  'text-status-warning bg-status-warning/10 border-status-warning/20',
  error:    'text-metric-stress bg-metric-stress/10 border-metric-stress/20',
  critical: 'text-metric-stress bg-metric-stress/15 border-metric-stress/30',
}

function AuditLogPanel() {
  const { token } = useAuth()
  const [events,   setEvents]   = useState<AuditEvent[]>([])
  const [total,    setTotal]    = useState(0)
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState<string | null>(null)
  const [severity, setSeverity] = useState('')
  const [action,   setAction]   = useState('')
  const [offset,   setOffset]   = useState(0)
  const LIMIT = 25

  const load = useCallback(async () => {
    if (!token) return
    setEnterpriseToken(token)
    setLoading(true)
    setError(null)
    try {
      const res = await enterpriseApi.getAuditEvents({
        severity: severity || undefined,
        action:   action   || undefined,
        limit:    LIMIT,
        offset,
      })
      setEvents(res.events)
      setTotal(res.total)
    } catch (e: any) {
      setError(e.message ?? 'Failed to load audit log')
    } finally {
      setLoading(false)
    }
  }, [token, severity, action, offset])

  useEffect(() => { load() }, [load])

  function formatTs(ts: number) {
    return new Date(ts * 1000).toLocaleString('en-US', {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
    })
  }

  if (!token) {
    return (
      <div className="rounded-xl border border-border bg-bg-card p-10 text-center">
        <Shield className="w-8 h-8 text-text-muted mx-auto mb-3" />
        <p className="text-sm font-medium text-text-primary mb-1">Authentication required</p>
        <p className="text-xs text-text-muted mb-4">Sign in to access the live audit log.</p>
        <Link href="/login">
          <Button variant="primary" size="sm">Sign in</Button>
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <select value={severity} onChange={e => { setSeverity(e.target.value); setOffset(0) }}
          className="h-8 rounded-lg border border-border bg-bg-card px-3 text-xs text-text-primary focus:outline-none focus:ring-2 focus:ring-accent">
          <option value="">All severities</option>
          <option value="info">Info</option>
          <option value="warning">Warning</option>
          <option value="error">Error</option>
          <option value="critical">Critical</option>
        </select>
        <input
          value={action}
          onChange={e => { setAction(e.target.value); setOffset(0) }}
          placeholder="Filter by action (e.g. auth.login)"
          className="h-8 rounded-lg border border-border bg-bg-card px-3 text-xs text-text-primary w-56
            placeholder:text-text-disabled focus:outline-none focus:ring-2 focus:ring-accent"
        />
        <button onClick={load}
          className="flex items-center gap-1.5 text-xs text-text-muted hover:text-text-primary transition-colors ml-auto">
          <RefreshCw className={cn('w-3.5 h-3.5', loading && 'animate-spin')} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-metric-stress/25 bg-metric-stress/8 px-3 py-2.5">
          <AlertCircle className="w-3.5 h-3.5 text-metric-stress" />
          <p className="text-xs text-metric-stress">{error}</p>
        </div>
      )}

      {/* Summary */}
      {total > 0 && (
        <p className="text-xs text-text-muted">
          Showing {offset + 1}–{Math.min(offset + events.length, total)} of {total} events
        </p>
      )}

      {/* Event list */}
      <div className="rounded-xl border border-border bg-bg-card overflow-hidden">
        {loading && events.length === 0 ? (
          <div className="p-8 text-center">
            <RefreshCw className="w-5 h-5 text-text-muted animate-spin mx-auto" />
          </div>
        ) : events.length === 0 ? (
          <div className="p-10 text-center">
            <ClipboardList className="w-8 h-8 text-text-disabled mx-auto mb-3" />
            <p className="text-sm text-text-muted">No audit events found</p>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {events.map(ev => (
              <div key={ev.event_id} className="flex items-start gap-4 px-4 py-3 hover:bg-bg-hover transition-colors">
                {/* Severity badge */}
                <span className={cn(
                  'text-2xs font-bold px-2 py-0.5 rounded border flex-shrink-0 mt-0.5 capitalize',
                  SEVERITY_COLORS[ev.severity] ?? 'text-text-muted bg-bg-hover border-border',
                )}>
                  {ev.severity}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-mono font-semibold text-text-primary">{ev.action}</span>
                    {ev.resource_type && (
                      <span className="text-2xs text-text-muted">on {ev.resource_type}</span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 mt-1 flex-wrap">
                    <span className="flex items-center gap-1 text-2xs text-text-muted">
                      <User className="w-2.5 h-2.5" />
                      {ev.actor_id}
                    </span>
                    {ev.ip_address && (
                      <span className="flex items-center gap-1 text-2xs text-text-muted">
                        <Server className="w-2.5 h-2.5" />
                        {ev.ip_address}
                      </span>
                    )}
                    <span className="flex items-center gap-1 text-2xs text-text-muted ml-auto">
                      <Clock className="w-2.5 h-2.5" />
                      {formatTs(ev.timestamp)}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Pagination */}
      {total > LIMIT && (
        <div className="flex items-center justify-between">
          <Button variant="ghost" size="sm" disabled={offset === 0}
            onClick={() => setOffset(o => Math.max(0, o - LIMIT))}>
            Previous
          </Button>
          <span className="text-xs text-text-muted">
            Page {Math.floor(offset / LIMIT) + 1} of {Math.ceil(total / LIMIT)}
          </span>
          <Button variant="ghost" size="sm" disabled={offset + LIMIT >= total}
            onClick={() => setOffset(o => o + LIMIT)}>
            Next
          </Button>
        </div>
      )}
    </div>
  )
}

// ── Compliance panel ──────────────────────────────────────────────────────────

function CompliancePanel() {
  const { token } = useAuth()
  const [summary,  setSummary]  = useState<any>(null)
  const [requests, setRequests] = useState<any[]>([])
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!token) return
    setEnterpriseToken(token)
    setLoading(true)
    setError(null)
    try {
      const [s, r] = await Promise.all([
        enterpriseApi.getComplianceSummary(),
        enterpriseApi.getDataRequests(),
      ])
      setSummary(s)
      setRequests(r.requests ?? [])
    } catch (e: any) {
      setError(e.message ?? 'Failed to load compliance data')
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { load() }, [load])

  if (!token) {
    return (
      <div className="rounded-xl border border-border bg-bg-card p-10 text-center">
        <Shield className="w-8 h-8 text-text-muted mx-auto mb-3" />
        <p className="text-sm font-medium text-text-primary mb-1">Authentication required</p>
        <p className="text-xs text-text-muted mb-4">Sign in to view compliance status.</p>
        <Link href="/login"><Button variant="primary" size="sm">Sign in</Button></Link>
      </div>
    )
  }

  if (loading) return (
    <div className="flex items-center justify-center py-20">
      <RefreshCw className="w-5 h-5 text-text-muted animate-spin" />
    </div>
  )

  if (error) return (
    <div className="rounded-xl border border-metric-stress/25 bg-metric-stress/8 px-4 py-3">
      <p className="text-xs text-metric-stress">{error}</p>
    </div>
  )

  const postureColor = summary?.posture === 'compliant'   ? 'text-metric-engagement' :
                       summary?.posture === 'warning'     ? 'text-status-warning'   :
                                                            'text-metric-stress'

  return (
    <div className="space-y-5">
      {/* Posture summary */}
      {summary && (
        <div className="rounded-xl border border-border bg-bg-card p-5">
          <div className="flex items-center gap-3 mb-5">
            <FileCheck className="w-5 h-5 text-accent" />
            <h3 className="text-sm font-semibold text-text-primary">Compliance Posture</h3>
            <span className={cn('ml-auto text-xs font-bold capitalize', postureColor)}>
              {summary.posture ?? '—'}
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[
              { label: 'Total consents',    value: summary.total_consents   ?? 0, color: '#818cf8' },
              { label: 'Active consents',   value: summary.active_consents  ?? 0, color: '#34d399' },
              { label: 'Pending requests',  value: summary.pending_requests ?? 0, color: '#f59e0b' },
              { label: 'Retention policies',value: summary.policies_count   ?? 0, color: '#60a5fa' },
            ].map(m => (
              <div key={m.label} className="rounded-lg bg-bg-hover border border-border-subtle p-3">
                <p className="text-2xs text-text-muted">{m.label}</p>
                <p className="text-xl font-bold font-mono mt-1" style={{ color: m.color }}>{m.value}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Data Subject Requests */}
      <div className="rounded-xl border border-border bg-bg-card overflow-hidden">
        <div className="px-5 py-4 border-b border-border flex items-center justify-between">
          <h3 className="text-sm font-semibold text-text-primary">Data Subject Requests (DSAR)</h3>
          <Badge variant="muted">{requests.length} total</Badge>
        </div>
        {requests.length === 0 ? (
          <div className="p-10 text-center">
            <Database className="w-8 h-8 text-text-disabled mx-auto mb-3" />
            <p className="text-sm text-text-muted">No data subject requests</p>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {requests.map((r: any) => (
              <div key={r.request_id} className="flex items-center gap-4 px-5 py-3 hover:bg-bg-hover transition-colors">
                <div className="flex-1">
                  <p className="text-xs font-medium text-text-primary capitalize">{r.request_type}</p>
                  <p className="text-2xs text-text-muted mt-0.5">Subject: {r.subject_id}</p>
                </div>
                <span className={cn(
                  'text-2xs font-semibold px-2 py-0.5 rounded border capitalize',
                  r.status === 'completed' ? 'text-metric-engagement bg-metric-engagement/10 border-metric-engagement/20' :
                  r.status === 'pending'   ? 'text-status-warning bg-status-warning/10 border-status-warning/20' :
                                             'text-text-muted bg-bg-hover border-border',
                )}>
                  {r.status}
                </span>
                <span className="text-2xs text-text-muted">
                  {new Date(r.created_at * 1000).toLocaleDateString()}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* GDPR reference */}
      <div className="rounded-xl border border-border-subtle bg-bg-hover p-5 text-xs text-text-muted leading-relaxed">
        <p className="font-semibold text-text-secondary mb-2">Supported DSAR types</p>
        <ul className="space-y-1.5">
          {['export — Right to data portability (GDPR Art. 20)',
            'erasure — Right to erasure / "right to be forgotten" (GDPR Art. 17)',
            'portability — Structured, machine-readable data export',
            'rectification — Request correction of inaccurate personal data'].map(t => (
            <li key={t} className="flex items-start gap-2">
              <ChevronRight className="w-3 h-3 text-accent mt-0.5 flex-shrink-0" />
              <span>{t}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

// ── Reports panel ─────────────────────────────────────────────────────────────

function ReportsPanel() {
  const { token } = useAuth()

  if (!token) {
    return (
      <div className="rounded-xl border border-border bg-bg-card p-10 text-center">
        <Shield className="w-8 h-8 text-text-muted mx-auto mb-3" />
        <p className="text-sm font-medium text-text-primary mb-1">Authentication required</p>
        <p className="text-xs text-text-muted mb-4">Sign in to manage immutable session reports.</p>
        <Link href="/login"><Button variant="primary" size="sm">Sign in</Button></Link>
      </div>
    )
  }

  return (
    <div className="space-y-5">
      <div className="rounded-xl border border-border bg-bg-card p-6">
        <div className="flex items-center gap-3 mb-5">
          <FileText className="w-5 h-5 text-accent" />
          <h3 className="text-sm font-semibold text-text-primary">Immutable Session Reports</h3>
          <Badge variant="accent">SHA-256 verified</Badge>
        </div>
        <p className="text-xs text-text-secondary leading-relaxed mb-5">
          Reports are generated as immutable snapshots of session data and locked with a SHA-256
          integrity hash. Corrections create new versions — the original is never overwritten.
          Each report requires approval before being finalized.
        </p>
        <div className="grid sm:grid-cols-3 gap-3 mb-5">
          {[
            { icon: Shield,   title: 'Tamper-proof',   desc: 'SHA-256 hash computed at creation. Verify integrity at any time.' },
            { icon: FileText, title: 'Versioned',       desc: 'Every correction creates a new version. Full history preserved.' },
            { icon: CheckCircle, title: 'Approval flow', desc: 'Reports require explicit approval before being marked final.' },
          ].map(f => (
            <div key={f.title} className="rounded-lg border border-border bg-bg-hover p-4">
              <f.icon className="w-4 h-4 text-accent mb-2" />
              <p className="text-xs font-semibold text-text-primary mb-1">{f.title}</p>
              <p className="text-2xs text-text-muted leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
        <div className="rounded-lg border border-border-subtle bg-bg-card p-4 text-xs text-text-secondary">
          <p className="font-semibold text-text-primary mb-2">Generate a report</p>
          <ol className="space-y-1.5 list-decimal list-inside text-text-muted">
            <li>Open a completed session from <Link href="/history" className="text-accent hover:underline">Session History</Link></li>
            <li>Click <span className="font-mono text-text-secondary">Generate Report</span> in the session results page</li>
            <li>The report is locked with a SHA-256 hash and queued for approval</li>
            <li>Use the verify endpoint to confirm integrity at any future time</li>
          </ol>
        </div>
      </div>

      <div className="rounded-xl border border-border-subtle bg-bg-hover p-5 text-xs text-text-muted">
        <p className="font-semibold text-text-secondary mb-2">API endpoints</p>
        <div className="space-y-1.5 font-mono text-text-muted">
          <p><span className="text-metric-engagement">POST</span>   /api/v1/reports/{'{session_id}'}          — generate</p>
          <p><span className="text-accent">GET</span>    /api/v1/reports/{'{session_id}'}          — latest version</p>
          <p><span className="text-accent">GET</span>    /api/v1/reports/{'{session_id}'}/versions — all versions</p>
          <p><span className="text-accent">GET</span>    /api/v1/reports/{'{report_id}'}/verify    — verify hash</p>
          <p><span className="text-metric-engagement">POST</span>   /api/v1/reports/{'{report_id}'}/approve   — approve</p>
        </div>
      </div>
    </div>
  )
}

// ── Tab bar ───────────────────────────────────────────────────────────────────

const TABS = [
  { id: 'policy',     label: 'AI Policy',   icon: Shield },
  { id: 'audit',      label: 'Audit Log',   icon: ClipboardList },
  { id: 'compliance', label: 'Compliance',  icon: FileCheck },
  { id: 'reports',    label: 'Reports',     icon: Database },
]

// ── Page ──────────────────────────────────────────────────────────────────────

export default function GovernancePage() {
  const [tab, setTab] = useState('policy')

  return (
    <AppShell title="AI Governance">
      <div className="p-6 max-w-5xl page-enter">

        {/* Header */}
        <div className="rounded-xl border border-accent/20 bg-accent/5 p-6 mb-6">
          <div className="flex items-start gap-4">
            <div className="w-10 h-10 rounded-xl bg-accent/15 border border-accent/25 flex items-center justify-center flex-shrink-0">
              <Shield className="w-5 h-5 text-accent" />
            </div>
            <div>
              <p className="text-2xs text-accent/70 uppercase tracking-widest font-semibold mb-1">
                NeuroSync Platform · AI Governance Documentation
              </p>
              <h1 className="text-xl font-bold text-text-primary mb-2">
                Responsible AI Policy v1.2
              </h1>
              <p className="text-sm text-text-secondary leading-relaxed max-w-2xl">
                This document governs all AI-generated assessments produced by the NeuroSync
                MBA Engine. It specifies model versioning standards, confidence requirements,
                mandatory human review triggers, fairness obligations, privacy controls, and
                known limitations. All operators deploying NeuroSync must comply with this policy.
              </p>
              <div className="flex flex-wrap gap-3 mt-4 text-2xs text-text-muted">
                <span>Effective date: 2026-06-20</span>
                <span>·</span>
                <span>Revision cycle: quarterly</span>
                <span>·</span>
                <span>Owner: Engineering &amp; Ethics Review Board</span>
              </div>
            </div>
          </div>
        </div>

        {/* Tab bar */}
        <div className="flex gap-1 rounded-xl border border-border bg-bg-card p-1 mb-6 overflow-x-auto">
          {TABS.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={cn(
                'flex items-center gap-1.5 flex-shrink-0 px-3 py-2 rounded-lg text-xs font-medium transition-all duration-150',
                tab === t.id
                  ? 'bg-bg-selected text-text-primary shadow-sm'
                  : 'text-text-muted hover:text-text-secondary',
              )}>
              <t.icon className="w-3.5 h-3.5" />
              <span>{t.label}</span>
            </button>
          ))}
        </div>

        {/* ── AI Policy tab ─────────────────────────────────────────────────── */}
        {tab === 'policy' && (
          <div className="grid lg:grid-cols-4 gap-6">

            {/* Table of contents */}
            <aside className="lg:col-span-1">
              <div className="rounded-xl border border-border bg-bg-card p-4 sticky top-6">
                <p className="text-2xs font-semibold text-text-muted uppercase tracking-widest mb-3">On this page</p>
                <nav className="space-y-0.5">
                  {TOC.map(({ id, label, icon: Icon }) => (
                    <a key={id} href={`#${id}`}
                      className="flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs text-text-muted hover:text-text-primary hover:bg-bg-hover transition-colors group">
                      <Icon className="w-3 h-3 group-hover:text-accent transition-colors flex-shrink-0" />
                      {label}
                    </a>
                  ))}
                </nav>
              </div>
            </aside>

            {/* Main content */}
            <main className="lg:col-span-3 space-y-10">

              {/* 1. Model Registry */}
              <Section id="model-registry" icon={BookOpen} title="Model Registry" badge="Current production">
                <Block title="Active model versions">
                  <Row label="Platform version"         value="NeuroSync Platform 1.2.0-rc1" />
                  <Row label="MBA Engine"               value="DeBERTa v3-base + LoRA (r=16, α=32)" />
                  <Row label="NLP checkpoint"            value="Step 18,000 · Macro-F1 82.4%" mono />
                  <Row label="Total parameters"          value="184,000,000" mono />
                  <Row label="Trainable parameters"      value="442,000 (0.24%)" mono />
                  <Row label="Speech-to-text"            value="OpenAI Whisper base · 74M params" />
                  <Row label="Face analysis"             value="MediaPipe Face Mesh · 468 landmarks" />
                  <Row label="Fusion architecture"       value="MLP meta-learner · 3s sliding window" />
                  <Row label="Training data"             value="74,288 behavioural text samples" mono />
                  <Row label="Evaluation protocol"       value="5-fold cross-validation · held-out 15%" />
                </Block>
                <Block title="Task-level performance (test set)">
                  {[
                    { task: 'Confidence classification', f1: '86.2%', classes: '3-class (low / moderate / high)' },
                    { task: 'Stress detection',          f1: '84.8%', classes: '3-class (low / moderate / high)' },
                    { task: 'Hesitation detection',      f1: '81.7%', classes: '3-class (none / mild / burst)' },
                    { task: 'Communication quality',     f1: '76.9%', classes: '4-class (low / moderate / good / excellent)' },
                    { task: 'Macro-F1 (average)',        f1: '82.4%', classes: '' },
                  ].map(r => (
                    <div key={r.task} className="flex items-start justify-between py-2 border-b border-border-subtle last:border-0 gap-4">
                      <div>
                        <p className="text-xs font-medium text-text-primary">{r.task}</p>
                        {r.classes && <p className="text-2xs text-text-muted mt-0.5">{r.classes}</p>}
                      </div>
                      <span className="text-xs font-mono font-bold text-accent flex-shrink-0">{r.f1}</span>
                    </div>
                  ))}
                </Block>
              </Section>

              {/* 2. Calibration */}
              <Section id="calibration" icon={Scale} title="Confidence Calibration">
                <Block title="Calibration methodology">
                  <p className="text-xs text-text-secondary leading-relaxed mb-4">
                    Model confidence scores are derived from softmax probability outputs of the DeBERTa
                    multi-task classifier. Raw probabilities are over-confident on out-of-distribution inputs.
                    The following calibration approach is applied:
                  </p>
                  {[
                    { step: '1', title: 'Cross-modal weighting',      desc: 'Face, voice, and NLP scores are combined via the Behavioural Fusion MLP. Each modality weight is calibrated against session-level labels.' },
                    { step: '2', title: 'Consistency-adjusted conf.',  desc: 'The consistency dimension scales the reported confidence: low consistency → wider uncertainty bounds.' },
                    { step: '3', title: 'Sample size correction',      desc: 'Sessions under 5 minutes or 500 words trigger an automatic confidence penalty.' },
                    { step: '4', title: 'Explicit uncertainty floor',  desc: 'No dimension score is reported with confidence above 97%.' },
                  ].map(s => (
                    <div key={s.step} className="flex gap-3 py-2.5 border-b border-border-subtle last:border-0">
                      <span className="w-5 h-5 rounded-full bg-accent/15 text-accent text-2xs font-bold flex items-center justify-center flex-shrink-0 mt-0.5">{s.step}</span>
                      <div>
                        <p className="text-xs font-semibold text-text-primary">{s.title}</p>
                        <p className="text-xs text-text-secondary mt-0.5 leading-relaxed">{s.desc}</p>
                      </div>
                    </div>
                  ))}
                </Block>
              </Section>

              {/* 3. Human Review Policy */}
              <Section id="human-review" icon={AlertTriangle} title="Human Review Policy" badge="Mandatory">
                <Block title="Mandatory review triggers">
                  <div className="space-y-2">
                    <ReviewTrigger severity="mandatory" text="Overall composite score below 40: insufficient positive signal for any adverse action without independent review" />
                    <ReviewTrigger severity="mandatory" text="Sustained stress (avg_stress > 0.65) for more than 5 consecutive minutes: may indicate distress, not representative performance" />
                    <ReviewTrigger severity="mandatory" text="Consistency score below 0.35: cross-modal signal divergence suggests data quality issues or atypical conditions" />
                    <ReviewTrigger severity="mandatory" text="Session duration under 5 minutes or total words below 200: insufficient behavioural data for reliable scoring" />
                    <ReviewTrigger severity="mandatory" text="Any single dimension score below 0.25: extreme outlier requiring human interpretation" />
                  </div>
                </Block>
                <Block title="Recommended review triggers">
                  <div className="space-y-2">
                    <ReviewTrigger severity="recommended" text="Two or more stress_spike or vocal_tension events in a single session" />
                    <ReviewTrigger severity="recommended" text="Proceed recommendation with tier confidence below 60%" />
                    <ReviewTrigger severity="recommended" text="Large discrepancy between language confidence score and face/voice scores (|NLP − face| > 0.30)" />
                  </div>
                </Block>
              </Section>

              {/* 4. Fairness */}
              <Section id="fairness" icon={Scale} title="Fairness & Bias">
                <Block title="What is currently monitored">
                  <div className="divide-y divide-border-subtle">
                    <FairnessItem assessed={true} text="Behavioural consistency is reported per session and inconsistent results are flagged for human review." />
                    <FairnessItem assessed={true} text="Confidence intervals are widened for short sessions." />
                    <FairnessItem assessed={true} text="Human review is mandatory for the lowest-scoring sessions." />
                    <FairnessItem assessed={true} text="Whisper WER acknowledgement: model accuracy degrades on accented speech." />
                  </div>
                </Block>
                <Block title="Known gaps">
                  <div className="divide-y divide-border-subtle">
                    <FairnessItem assessed={false} text="Demographic parity testing across protected groups. Training labels do not contain demographic metadata." />
                    <FairnessItem assessed={false} text="Cross-accent Whisper accuracy benchmarking." />
                    <FairnessItem assessed={false} text="Lighting condition robustness for face analysis." />
                    <FairnessItem assessed={false} text="Neurodivergence accommodation in scoring models." />
                  </div>
                </Block>
                <div className="rounded-xl border border-status-warning/25 bg-status-warning/8 px-5 py-4 flex gap-3">
                  <AlertTriangle className="w-4 h-4 text-status-warning flex-shrink-0 mt-0.5" />
                  <p className="text-xs text-text-secondary leading-relaxed">
                    <strong className="text-status-warning">Important: </strong>
                    NeuroSync must not be the sole criterion for any adverse employment decision.
                    Assessment results should always be combined with structured interviews and validated against role-specific criteria.
                  </p>
                </div>
              </Section>

              {/* 5. Privacy */}
              <Section id="privacy" icon={Lock} title="Data Privacy Controls">
                <Block title="Data storage and residency">
                  <Row label="Session data"        value="Local SQLite WAL at data/nuanceai.db" mono />
                  <Row label="Video frames"        value="Local disk. Not transmitted externally." />
                  <Row label="Audio chunks"        value="Processed in-memory. Not persisted unless DATASET_AUTO_SAVE=True." />
                  <Row label="External API calls"  value="None. All inference is local, no cloud AI calls." />
                  <Row label="Telemetry"           value="None. No usage data is sent to external servers." />
                </Block>
              </Section>

              {/* 6. Limitations */}
              <Section id="limitations" icon={Info} title="Known Limitations">
                <div className="space-y-3">
                  {[
                    { severity: 'High',   title: 'getUserMedia requires HTTPS',    desc: 'Webcam and microphone capture fail silently on plain HTTP outside localhost.' },
                    { severity: 'Medium', title: 'Whisper base model accuracy',    desc: '~85% word accuracy on clear English speech. Degrades with accents, background noise.' },
                    { severity: 'Medium', title: 'DeBERTa checkpoint dependency',  desc: 'Full NLP scoring requires models/deberta/best/model.pt.' },
                    { severity: 'Low',    title: 'Single-server SQLite storage',   desc: 'Not suitable for multi-process or multi-server deployment.' },
                  ].map(l => (
                    <div key={l.title} className="rounded-xl border border-border bg-bg-card p-4 flex gap-3">
                      <span className={`text-2xs font-bold px-2 py-0.5 rounded self-start flex-shrink-0 mt-0.5 ${
                        l.severity === 'High'   ? 'bg-metric-stress/15 text-metric-stress' :
                        l.severity === 'Medium' ? 'bg-status-warning/15 text-status-warning' :
                                                  'bg-bg-hover text-text-muted border border-border'
                      }`}>{l.severity}</span>
                      <div>
                        <p className="text-xs font-semibold text-text-primary mb-0.5">{l.title}</p>
                        <p className="text-xs text-text-secondary leading-relaxed">{l.desc}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </Section>

              {/* 7. Audit */}
              <Section id="audit" icon={Shield} title="Audit & Record-keeping">
                <Block title="What is recorded per session">
                  {[
                    ['Session ID',             'UUID, immutable. Links all session records.'],
                    ['Start / end timestamps', 'UTC unix seconds, stored in sessions table.'],
                    ['All derived scores',     'avg_confidence, avg_stress, avg_engagement, avg_communication, avg_consistency'],
                    ['All detected insights',  'type, severity, timestamp, modalities_involved'],
                    ['Transcript',             'Full session transcript.'],
                    ['Timeline frames',        'Sampled every ~2s, stored in session_frames table.'],
                  ].map(([label, desc]) => (
                    <div key={label as string} className="flex items-start gap-4 py-2 border-b border-border-subtle last:border-0">
                      <span className="text-xs font-medium text-text-primary w-44 flex-shrink-0">{label}</span>
                      <span className="text-xs text-text-muted">{desc}</span>
                    </div>
                  ))}
                </Block>
                <p className="text-xs text-text-muted">
                  Switch to the <button onClick={() => setTab('audit')}
                    className="text-accent hover:underline">Audit Log</button> tab to view live enterprise audit events.
                </p>
              </Section>

              {/* Footer */}
              <div className="rounded-xl border border-border-subtle bg-bg-hover px-6 py-5 flex items-start gap-3">
                <Shield className="w-4 h-4 text-accent flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-xs font-semibold text-text-secondary mb-1">Policy review schedule</p>
                  <p className="text-xs text-text-muted leading-relaxed">
                    Reviewed quarterly or when a major model update is deployed.
                    All changes must be version-controlled and communicated to all operators before taking effect.
                  </p>
                  <p className="text-2xs text-text-disabled mt-3">
                    NeuroSync Governance Policy v1.2 · Effective 2026-06-24 · NeuroSync Platform
                  </p>
                </div>
              </div>
            </main>
          </div>
        )}

        {/* ── Audit Log tab ─────────────────────────────────────────────────── */}
        {tab === 'audit' && <AuditLogPanel />}

        {/* ── Compliance tab ────────────────────────────────────────────────── */}
        {tab === 'compliance' && <CompliancePanel />}

        {/* ── Reports tab ───────────────────────────────────────────────────── */}
        {tab === 'reports' && <ReportsPanel />}

      </div>
    </AppShell>
  )
}
