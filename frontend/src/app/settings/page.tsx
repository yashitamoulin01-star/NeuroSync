'use client'
import { useState, useEffect, useCallback } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { cn } from '@/lib/utils'
import {
  Settings, Brain, Bell, Cpu, CheckCircle2, AlertCircle,
  ExternalLink, RefreshCw, Activity, Database, Zap,
  HardDrive, Wifi, Layers, Mic2, Eye, Server, Clock,
  Users, Key, Plus, Trash2, Copy, ShieldCheck, Shield,
  UserX, ChevronDown, AlertTriangle, Check, Plug, Power, Briefcase,
} from 'lucide-react'
import { api, WS_URL, enterpriseApi, setEnterpriseToken, connectorApi, atsApi } from '@/lib/api'
import type { TrainingStatus, HealthDetailed } from '@/lib/types'
import type { OrgUser, ApiKey, AvailableConnector, ConnectorRecord, AvailableATS, ATSConnection } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { Skeleton } from '@/components/ui/Skeleton'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

// ── Shared primitives ─────────────────────────────────────────────────────────

type StatusLevel = 'online' | 'idle' | 'warning' | 'offline' | 'missing' | 'error' | 'checking'

const STATUS_COLOR: Record<StatusLevel, string> = {
  online:   '#34d399',
  idle:     '#818cf8',
  warning:  '#f59e0b',
  offline:  '#ef4444',
  missing:  '#71717a',
  error:    '#ef4444',
  checking: '#71717a',
}

const STATUS_LABEL: Record<StatusLevel, string> = {
  online:   'Online',
  idle:     'Idle',
  warning:  'Warning',
  offline:  'Offline',
  missing:  'Not found',
  error:    'Error',
  checking: 'Checking…',
}

function StatusDot({ status }: { status: StatusLevel }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className={cn('w-2 h-2 rounded-full flex-shrink-0', status === 'online' && 'animate-pulse')}
        style={{ background: STATUS_COLOR[status] }}
      />
      <span className="text-xs font-medium" style={{ color: STATUS_COLOR[status] }}>
        {STATUS_LABEL[status]}
      </span>
    </span>
  )
}

function ComponentRow({
  icon: Icon, label, status, detail,
}: {
  icon: React.ElementType
  label: string
  status: StatusLevel
  detail?: string
}) {
  return (
    <div className="flex items-center gap-3 py-2.5 border-b border-border-subtle last:border-0">
      <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
        style={{ background: `${STATUS_COLOR[status]}12` }}>
        <Icon className="w-3.5 h-3.5" style={{ color: STATUS_COLOR[status] }} />
      </div>
      <span className="text-sm text-text-primary flex-1 font-medium">{label}</span>
      {detail && <span className="text-xs text-text-muted mr-3 hidden sm:block">{detail}</span>}
      <StatusDot status={status} />
    </div>
  )
}

function GaugeBar({
  value, max, color, label, unit,
}: {
  value: number; max: number; color: string; label: string; unit?: string
}) {
  const pct = Math.min(100, Math.round((value / max) * 100))
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-2xs text-text-muted">{label}</span>
        <span className="text-2xs font-mono text-text-secondary">
          {value.toLocaleString()}{unit} / {max.toLocaleString()}{unit}
        </span>
      </div>
      <div className="h-1.5 bg-bg-hover rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: pct > 85 ? '#ef4444' : pct > 65 ? '#f59e0b' : color }} />
      </div>
    </div>
  )
}


function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button role="switch" aria-checked={checked} onClick={() => onChange(!checked)}
      className={cn(
        'relative inline-flex h-5 w-9 items-center rounded-full transition-colors',
        'focus:outline-none focus:ring-2 focus:ring-accent-bright focus:ring-offset-1 focus:ring-offset-bg-base',
        checked ? 'bg-accent-bright' : 'bg-bg-hover border border-border-strong',
      )}>
      <span className={cn(
        'inline-block h-3.5 w-3.5 rounded-full bg-white shadow transition-transform',
        checked ? 'translate-x-4' : 'translate-x-1',
      )} />
    </button>
  )
}

function SelectInput({ options, value, onChange }: {
  options: { value: string; label: string }[]
  value: string
  onChange: (v: string) => void
}) {
  return (
    <select value={value} onChange={e => onChange(e.target.value)}
      className="h-8 rounded-lg border border-border bg-bg-card px-3 text-xs text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-bright hover:border-border-strong transition-colors appearance-none pr-6">
      {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  )
}

function SettingRow({ label, desc, children }: {
  label: string; desc?: string; children: React.ReactNode
}) {
  return (
    <div className="flex items-start justify-between gap-6 py-4 border-b border-border-subtle last:border-0">
      <div className="min-w-0">
        <p className="text-sm text-text-primary font-medium">{label}</p>
        {desc && <p className="text-xs text-text-muted mt-0.5 leading-relaxed max-w-sm">{desc}</p>}
      </div>
      <div className="flex-shrink-0">{children}</div>
    </div>
  )
}

function formatUptime(s: number | null): string {
  if (s == null) return '—'
  if (s < 60)   return `${s}s`
  if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60)
  return `${h}h ${m}m`
}

// ── Tabs ─────────────────────────────────────────────────────────────────────

const TABS = [
  { id: 'status',  label: 'System Status', icon: Activity },
  { id: 'general', label: 'General',       icon: Settings },
  { id: 'models',  label: 'AI Models',     icon: Brain },
  { id: 'alerts',  label: 'Alerts',        icon: Bell },
  { id: 'api',     label: 'API',           icon: Cpu },
  { id: 'users',      label: 'Users',      icon: Users },
  { id: 'keys',       label: 'API Keys',   icon: Key },
  { id: 'connectors', label: 'Connectors', icon: Plug },
  { id: 'ats',        label: 'ATS',        icon: Briefcase },
]

// ── Users panel ────────────────────────────────────────────────────────────────

const ROLE_LABELS: Record<string, string> = {
  platform_admin: 'Platform Admin',
  tenant_admin:   'Tenant Admin',
  org_admin:      'Org Admin',
  hr_manager:     'HR Manager',
  interviewer:    'Interviewer',
  analyst:        'Analyst',
  reviewer:       'Reviewer',
  candidate:      'Candidate',
}

function UsersPanel({ token }: { token: string | null }) {
  const [users,   setUsers]   = useState<OrgUser[]>([])
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState<string | null>(null)
  const [busy,    setBusy]    = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!token) return
    setEnterpriseToken(token)
    setLoading(true)
    setError(null)
    try {
      const res = await enterpriseApi.listUsers()
      setUsers(res.users)
    } catch (e: any) {
      setError(e.message ?? 'Failed to load users')
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { load() }, [load])

  async function handleSuspend(userId: string) {
    setBusy(userId)
    try {
      await enterpriseApi.suspendUser(userId)
      await load()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setBusy(null)
    }
  }

  if (!token) {
    return (
      <div className="rounded-xl border border-border bg-bg-card p-10 text-center">
        <Shield className="w-8 h-8 text-text-muted mx-auto mb-3" />
        <p className="text-sm font-medium text-text-primary mb-1">Authentication required</p>
        <p className="text-xs text-text-muted">Sign in to manage users.</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">Organization Users</h3>
          <p className="text-xs text-text-muted mt-0.5">Manage user accounts, roles, and access.</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={load} className="flex items-center gap-1.5 text-xs text-text-muted hover:text-text-primary transition-colors">
            <RefreshCw className={cn('w-3.5 h-3.5', loading && 'animate-spin')} />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-metric-stress/25 bg-metric-stress/8 px-3 py-2.5">
          <AlertCircle className="w-3.5 h-3.5 text-metric-stress" />
          <p className="text-xs text-metric-stress">{error}</p>
        </div>
      )}

      <div className="rounded-xl border border-border bg-bg-card overflow-hidden">
        {loading && users.length === 0 ? (
          <div className="p-8 text-center">
            <RefreshCw className="w-5 h-5 text-text-muted animate-spin mx-auto" />
          </div>
        ) : users.length === 0 ? (
          <div className="p-10 text-center">
            <Users className="w-8 h-8 text-text-disabled mx-auto mb-3" />
            <p className="text-sm text-text-muted">No users in this organization</p>
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-border bg-bg-hover">
                <th className="text-left px-4 py-2.5 text-2xs font-semibold text-text-muted uppercase tracking-widest">User</th>
                <th className="text-left px-4 py-2.5 text-2xs font-semibold text-text-muted uppercase tracking-widest hidden sm:table-cell">Roles</th>
                <th className="text-left px-4 py-2.5 text-2xs font-semibold text-text-muted uppercase tracking-widest hidden md:table-cell">Status</th>
                <th className="text-left px-4 py-2.5 text-2xs font-semibold text-text-muted uppercase tracking-widest hidden lg:table-cell">Last login</th>
                <th className="px-4 py-2.5" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {users.map(u => (
                <tr key={u.user_id} className="hover:bg-bg-hover transition-colors">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2.5">
                      <div className="w-7 h-7 rounded-full bg-accent/15 border border-accent/25 flex items-center justify-center flex-shrink-0">
                        <span className="text-2xs font-bold text-accent">
                          {(u.display_name || u.email).slice(0, 2).toUpperCase()}
                        </span>
                      </div>
                      <div>
                        <p className="text-xs font-medium text-text-primary">{u.display_name || u.email}</p>
                        <p className="text-2xs text-text-muted">{u.email}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 hidden sm:table-cell">
                    <div className="flex flex-wrap gap-1">
                      {(u.roles ?? []).slice(0, 2).map(r => (
                        <span key={r} className="text-2xs font-medium px-1.5 py-0.5 rounded bg-accent/10 text-accent border border-accent/20">
                          {ROLE_LABELS[r] ?? r}
                        </span>
                      ))}
                      {(u.roles ?? []).length > 2 && (
                        <span className="text-2xs text-text-muted">+{(u.roles ?? []).length - 2}</span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 hidden md:table-cell">
                    <span className={cn(
                      'text-2xs font-semibold px-2 py-0.5 rounded border capitalize',
                      u.status === 'active'    ? 'text-metric-engagement bg-metric-engagement/10 border-metric-engagement/20' :
                      u.status === 'suspended' ? 'text-metric-stress bg-metric-stress/10 border-metric-stress/20' :
                                                 'text-text-muted bg-bg-hover border-border',
                    )}>
                      {u.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 hidden lg:table-cell">
                    <span className="text-2xs text-text-muted">
                      {u.last_login ? new Date(u.last_login * 1000).toLocaleDateString() : 'Never'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    {u.status === 'active' && (
                      <button
                        onClick={() => handleSuspend(u.user_id)}
                        disabled={busy === u.user_id}
                        className="flex items-center gap-1 text-2xs text-metric-stress hover:bg-metric-stress/10 px-2 py-1 rounded transition-colors disabled:opacity-50"
                      >
                        <UserX className="w-3 h-3" />
                        {busy === u.user_id ? 'Suspending…' : 'Suspend'}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

// ── API Keys panel ─────────────────────────────────────────────────────────────

const ALL_SCOPES = ['sessions:read', 'sessions:write', 'analytics:read', 'admin:read']

function ApiKeysPanel({ token }: { token: string | null }) {
  const [keys,      setKeys]      = useState<ApiKey[]>([])
  const [loading,   setLoading]   = useState(false)
  const [error,     setError]     = useState<string | null>(null)
  const [creating,  setCreating]  = useState(false)
  const [newName,   setNewName]   = useState('')
  const [newScopes, setNewScopes] = useState<string[]>(['sessions:read'])
  const [rawKey,    setRawKey]    = useState<string | null>(null)
  const [busy,      setBusy]      = useState<string | null>(null)
  const [copied,    setCopied]    = useState(false)

  const load = useCallback(async () => {
    if (!token) return
    setEnterpriseToken(token)
    setLoading(true)
    setError(null)
    try {
      const res = await enterpriseApi.listApiKeys()
      setKeys(res.api_keys)
    } catch (e: any) {
      setError(e.message ?? 'Failed to load API keys')
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { load() }, [load])

  async function handleCreate() {
    if (!newName.trim()) return
    setCreating(true)
    setError(null)
    try {
      const res = await enterpriseApi.createApiKey(newName.trim(), newScopes)
      setRawKey(res.raw_key)
      setNewName('')
      setNewScopes(['sessions:read'])
      await load()
    } catch (e: any) {
      setError(e.message ?? 'Failed to create API key')
    } finally {
      setCreating(false)
    }
  }

  async function handleRevoke(keyId: string) {
    setBusy(keyId)
    try {
      await enterpriseApi.revokeApiKey(keyId)
      await load()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setBusy(null)
    }
  }

  function copyKey() {
    if (!rawKey) return
    navigator.clipboard.writeText(rawKey)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  function toggleScope(s: string) {
    setNewScopes(prev => prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s])
  }

  if (!token) {
    return (
      <div className="rounded-xl border border-border bg-bg-card p-10 text-center">
        <Shield className="w-8 h-8 text-text-muted mx-auto mb-3" />
        <p className="text-sm font-medium text-text-primary mb-1">Authentication required</p>
        <p className="text-xs text-text-muted">Sign in to manage API keys.</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-text-primary">API Keys</h3>
        <p className="text-xs text-text-muted mt-0.5">
          API keys authenticate programmatic access to the NeuroSync API. The raw key is shown
          once at creation — store it securely.
        </p>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-metric-stress/25 bg-metric-stress/8 px-3 py-2.5">
          <AlertCircle className="w-3.5 h-3.5 text-metric-stress" />
          <p className="text-xs text-metric-stress">{error}</p>
        </div>
      )}

      {/* Raw key reveal */}
      {rawKey && (
        <div className="rounded-xl border border-metric-engagement/25 bg-metric-engagement/5 p-4">
          <div className="flex items-center gap-2 mb-2">
            <ShieldCheck className="w-4 h-4 text-metric-engagement" />
            <p className="text-xs font-semibold text-metric-engagement">API key created — save it now</p>
          </div>
          <p className="text-2xs text-text-muted mb-3">This key will not be shown again.</p>
          <div className="flex items-center gap-2">
            <code className="flex-1 text-2xs font-mono bg-bg-base border border-border rounded-lg px-3 py-2 text-text-secondary overflow-x-auto">
              {rawKey}
            </code>
            <button onClick={copyKey}
              className="flex items-center gap-1.5 text-xs px-3 py-2 rounded-lg border border-border bg-bg-card hover:bg-bg-hover transition-colors flex-shrink-0">
              {copied ? <Check className="w-3.5 h-3.5 text-metric-engagement" /> : <Copy className="w-3.5 h-3.5 text-text-muted" />}
              {copied ? 'Copied' : 'Copy'}
            </button>
          </div>
          <button onClick={() => setRawKey(null)} className="mt-2 text-2xs text-text-muted hover:text-text-secondary transition-colors">
            Dismiss
          </button>
        </div>
      )}

      {/* Create form */}
      <div className="rounded-xl border border-border bg-bg-card p-5">
        <h4 className="text-xs font-semibold text-text-primary mb-4">Create new API key</h4>
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-text-muted mb-1.5">Key name</label>
            <input
              value={newName}
              onChange={e => setNewName(e.target.value)}
              placeholder="e.g. CI/CD pipeline, data export"
              className="w-full h-8 rounded-lg border border-border bg-bg-base px-3 text-xs text-text-primary
                placeholder:text-text-disabled focus:outline-none focus:ring-2 focus:ring-accent"
            />
          </div>
          <div>
            <label className="block text-xs text-text-muted mb-2">Scopes</label>
            <div className="flex flex-wrap gap-2">
              {ALL_SCOPES.map(s => (
                <button key={s} onClick={() => toggleScope(s)}
                  className={cn(
                    'text-2xs px-2.5 py-1 rounded-full border font-medium transition-colors',
                    newScopes.includes(s)
                      ? 'bg-accent/15 text-accent border-accent/30'
                      : 'bg-bg-hover text-text-muted border-border hover:border-border-strong',
                  )}>
                  {s}
                </button>
              ))}
            </div>
          </div>
          <Button variant="primary" size="sm" icon={<Plus className="w-3.5 h-3.5" />}
            onClick={handleCreate} disabled={creating || !newName.trim()}>
            {creating ? 'Creating…' : 'Create API key'}
          </Button>
        </div>
      </div>

      {/* Key list */}
      <div className="rounded-xl border border-border bg-bg-card overflow-hidden">
        <div className="px-5 py-4 border-b border-border flex items-center justify-between">
          <h4 className="text-xs font-semibold text-text-primary">Active keys ({keys.filter(k => !k.revoked).length})</h4>
          <button onClick={load} className="text-xs text-text-muted hover:text-text-primary transition-colors flex items-center gap-1">
            <RefreshCw className={cn('w-3 h-3', loading && 'animate-spin')} />
          </button>
        </div>
        {loading && keys.length === 0 ? (
          <div className="p-8 text-center">
            <RefreshCw className="w-4 h-4 text-text-muted animate-spin mx-auto" />
          </div>
        ) : keys.filter(k => !k.revoked).length === 0 ? (
          <div className="p-8 text-center">
            <Key className="w-8 h-8 text-text-disabled mx-auto mb-3" />
            <p className="text-sm text-text-muted">No active API keys</p>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {keys.filter(k => !k.revoked).map(k => (
              <div key={k.key_id} className="flex items-center gap-4 px-5 py-3 hover:bg-bg-hover transition-colors">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-xs font-medium text-text-primary">{k.name}</p>
                    <span className="text-2xs font-mono text-text-muted">{k.prefix}…</span>
                  </div>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {k.scopes.map(s => (
                      <span key={s} className="text-2xs px-1.5 py-0.5 rounded bg-bg-hover border border-border text-text-muted">
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="text-right flex-shrink-0">
                  <p className="text-2xs text-text-muted">
                    Created {new Date(k.created_at * 1000).toLocaleDateString()}
                  </p>
                  {k.expires_at && (
                    <p className="text-2xs text-text-muted">
                      Expires {new Date(k.expires_at * 1000).toLocaleDateString()}
                    </p>
                  )}
                </div>
                <button
                  onClick={() => handleRevoke(k.key_id)}
                  disabled={busy === k.key_id}
                  className="flex items-center gap-1 text-2xs text-metric-stress hover:bg-metric-stress/10 px-2 py-1 rounded transition-colors disabled:opacity-50 flex-shrink-0"
                >
                  <Trash2 className="w-3 h-3" />
                  {busy === k.key_id ? 'Revoking…' : 'Revoke'}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Connectors panel ────────────────────────────────────────────────────────────

const CAP_LABELS: Array<{ key: keyof AvailableConnector['capabilities']; label: string }> = [
  { key: 'meeting_metadata',     label: 'Meetings' },
  { key: 'transcript_support',   label: 'Transcript' },
  { key: 'recording_support',    label: 'Recording' },
  { key: 'live_stream_support',  label: 'Live' },
  { key: 'participant_metadata', label: 'Participants' },
]

const CONNECTOR_STATUS: Record<string, { label: string; color: string }> = {
  connected:    { label: 'Connected',    color: 'text-metric-engagement' },
  disconnected: { label: 'Not connected', color: 'text-text-muted' },
  expired:      { label: 'Expired',      color: 'text-metric-stress' },
  error:        { label: 'Error',        color: 'text-metric-stress' },
}

function relTime(ts: number | null): string {
  if (!ts) return 'never'
  const s = Math.floor(Date.now() / 1000 - ts)
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}

function ConnectorsPanel({ token }: { token: string | null }) {
  const [available, setAvailable] = useState<AvailableConnector[]>([])
  const [records,   setRecords]   = useState<ConnectorRecord[]>([])
  const [loading,   setLoading]   = useState(false)
  const [error,     setError]     = useState<string | null>(null)
  const [notice,    setNotice]    = useState<string | null>(null)
  const [busy,      setBusy]      = useState<string | null>(null)
  const [showPerms, setShowPerms] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!token) return
    setEnterpriseToken(token)
    setLoading(true)
    setError(null)
    try {
      const [av, ls] = await Promise.all([connectorApi.available(), connectorApi.list()])
      setAvailable(av.providers)
      setRecords(ls.connectors)
    } catch (e: any) {
      setError(e.message ?? 'Failed to load connectors')
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { load() }, [load])

  const byProvider = new Map(records.map(r => [r.provider, r]))

  function flash(msg: string) {
    setNotice(msg)
    setTimeout(() => setNotice(n => (n === msg ? null : n)), 3000)
  }

  async function handleConnect(provider: string) {
    setBusy(provider)
    setError(null)
    try {
      const redirectUri = `${window.location.origin}/settings?connector_callback=1`
      const res = await connectorApi.connect(provider, redirectUri)
      // Real deployment: redirect to the provider consent screen.
      // window.location.assign(res.authorize_url)
      flash(`OAuth initiated for ${provider}. Authorize URL ready.`)
      await load()
    } catch (e: any) {
      setError(e.message ?? 'Connect failed')
    } finally {
      setBusy(null)
    }
  }

  async function handleAction(id: string, action: 'refresh' | 'test' | 'disconnect') {
    setBusy(id + action)
    setError(null)
    try {
      if (action === 'refresh') { await connectorApi.refresh(id); flash('Tokens refreshed.') }
      else if (action === 'test') {
        const r = await connectorApi.test(id)
        flash(r.ok ? `Connection OK: ${r.message}` : `Test failed: ${r.message}`)
      } else { await connectorApi.disconnect(id); flash('Disconnected. Tokens wiped.') }
      await load()
    } catch (e: any) {
      setError(e.message ?? `${action} failed`)
    } finally {
      setBusy(null)
    }
  }

  if (!token) {
    return (
      <div className="rounded-xl border border-border bg-bg-card p-10 text-center">
        <Shield className="w-8 h-8 text-text-muted mx-auto mb-3" />
        <p className="text-sm font-medium text-text-primary mb-1">Authentication required</p>
        <p className="text-xs text-text-muted">Sign in as an administrator to manage connectors.</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-text-primary">Meeting Connectors</h3>
        <p className="text-xs text-text-muted mt-0.5">
          Securely link external meeting providers. OAuth tokens are encrypted at rest and never
          leave your server. One connection per provider, per organization.
        </p>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-metric-stress/25 bg-metric-stress/8 px-3 py-2.5">
          <AlertCircle className="w-3.5 h-3.5 text-metric-stress flex-shrink-0" />
          <p className="text-xs text-metric-stress">{error}</p>
        </div>
      )}
      {notice && (
        <div className="flex items-center gap-2 rounded-lg border border-metric-engagement/25 bg-metric-engagement/5 px-3 py-2.5">
          <CheckCircle2 className="w-3.5 h-3.5 text-metric-engagement flex-shrink-0" />
          <p className="text-xs text-metric-engagement">{notice}</p>
        </div>
      )}

      {loading && available.length === 0 ? (
        <div className="grid sm:grid-cols-2 gap-3">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-36 w-full rounded-xl" />)}
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 gap-3">
          {available.map(prov => {
            const rec = byProvider.get(prov.provider)
            const status = rec ? rec.status : 'disconnected'
            const sm = CONNECTOR_STATUS[status] ?? CONNECTOR_STATUS.disconnected
            const isConnected = rec && (status === 'connected' || status === 'expired' || status === 'error')
            return (
              <div key={prov.provider} className="rounded-xl border border-border bg-bg-card p-4 flex flex-col gap-3">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2.5">
                    <div className="w-9 h-9 rounded-lg bg-bg-hover flex items-center justify-center flex-shrink-0">
                      <Plug className="w-4 h-4 text-text-secondary" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-text-primary">{prov.display_name}</p>
                      <div className="flex items-center gap-1.5">
                        <span className={cn('w-1.5 h-1.5 rounded-full',
                          status === 'connected' ? 'bg-metric-engagement'
                          : status === 'disconnected' ? 'bg-text-disabled' : 'bg-metric-stress')} />
                        <span className={cn('text-2xs font-medium', sm.color)}>{sm.label}</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Capability badges */}
                <div className="flex flex-wrap gap-1">
                  {CAP_LABELS.map(c => prov.capabilities[c.key] && (
                    <span key={c.key} className="text-2xs px-1.5 py-0.5 rounded bg-bg-hover text-text-muted border border-border">
                      {c.label}
                    </span>
                  ))}
                </div>

                {isConnected && (
                  <p className="text-2xs text-text-disabled flex items-center gap-1">
                    <Clock className="w-3 h-3" /> Last sync {relTime(rec!.last_sync)}
                  </p>
                )}
                {rec?.last_error && status === 'error' && (
                  <p className="text-2xs text-metric-stress truncate">{rec.last_error}</p>
                )}

                {/* Actions */}
                <div className="flex flex-wrap items-center gap-1.5 mt-auto pt-1">
                  {!isConnected ? (
                    <Button variant="primary" size="xs" icon={<Plug className="w-3 h-3" />}
                      loading={busy === prov.provider}
                      onClick={() => handleConnect(prov.provider)}>
                      Connect
                    </Button>
                  ) : (
                    <>
                      <Button variant="ghost" size="xs" icon={<Activity className="w-3 h-3" />}
                        loading={busy === rec!.connector_id + 'test'}
                        onClick={() => handleAction(rec!.connector_id, 'test')}>
                        Test
                      </Button>
                      <Button variant="ghost" size="xs" icon={<RefreshCw className="w-3 h-3" />}
                        loading={busy === rec!.connector_id + 'refresh'}
                        onClick={() => handleAction(rec!.connector_id, 'refresh')}>
                        Refresh
                      </Button>
                      <button onClick={() => setShowPerms(p => p === rec!.connector_id ? null : rec!.connector_id)}
                        className="text-2xs px-2 py-1 rounded-md text-text-muted hover:text-text-secondary transition-colors">
                        Permissions
                      </button>
                      <button onClick={() => handleAction(rec!.connector_id, 'disconnect')}
                        className="text-2xs px-2 py-1 rounded-md text-metric-stress hover:bg-metric-stress/10 transition-colors flex items-center gap-1">
                        <Power className="w-3 h-3" /> Disconnect
                      </button>
                    </>
                  )}
                </div>

                {/* Permissions drawer */}
                {showPerms === rec?.connector_id && (
                  <div className="rounded-lg border border-border bg-bg-base p-2.5">
                    <p className="text-2xs font-semibold text-text-muted uppercase tracking-widest mb-1.5">Granted scopes</p>
                    <div className="flex flex-col gap-1">
                      {(rec.scopes.length ? rec.scopes : prov.scopes).map(s => (
                        <code key={s} className="text-2xs font-mono text-text-secondary break-all">{s}</code>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ── ATS panel ───────────────────────────────────────────────────────────────

const ATS_CAP_LABELS: Array<{ key: keyof AvailableATS['capabilities']; label: string }> = [
  { key: 'push_report',      label: 'Push report' },
  { key: 'write_scorecard',  label: 'Scorecard' },
  { key: 'sync_candidates',  label: 'Sync candidates' },
  { key: 'write_back_stage', label: 'Stage write-back' },
]

function AtsPanel({ token }: { token: string | null }) {
  const [available, setAvailable] = useState<AvailableATS[]>([])
  const [records,   setRecords]   = useState<ATSConnection[]>([])
  const [loading,   setLoading]   = useState(false)
  const [error,     setError]     = useState<string | null>(null)
  const [notice,    setNotice]    = useState<string | null>(null)
  const [busy,      setBusy]      = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!token) return
    setEnterpriseToken(token)
    setLoading(true)
    setError(null)
    try {
      const [av, ls] = await Promise.all([atsApi.available(), atsApi.list()])
      setAvailable(av.providers)
      setRecords(ls.connections)
    } catch (e: any) {
      setError(e.message ?? 'Failed to load ATS integrations')
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { load() }, [load])

  const byProvider = new Map(records.map(r => [r.provider, r]))
  function flash(msg: string) { setNotice(msg); setTimeout(() => setNotice(n => (n === msg ? null : n)), 3000) }

  async function handleConnect(provider: string) {
    setBusy(provider); setError(null)
    try {
      const redirectUri = `${window.location.origin}/settings?ats_callback=1`
      await atsApi.connect(provider, redirectUri)
      flash(`OAuth initiated for ${provider}.`)
      await load()
    } catch (e: any) { setError(e.message ?? 'Connect failed') } finally { setBusy(null) }
  }

  async function handleAction(id: string, action: 'refresh' | 'test' | 'disconnect') {
    setBusy(id + action); setError(null)
    try {
      if (action === 'refresh') { await atsApi.refresh(id); flash('Tokens refreshed.') }
      else if (action === 'test') { const r = await atsApi.test(id); flash(r.ok ? `OK: ${r.message}` : `Failed: ${r.message}`) }
      else { await atsApi.disconnect(id); flash('Disconnected.') }
      await load()
    } catch (e: any) { setError(e.message ?? `${action} failed`) } finally { setBusy(null) }
  }

  if (!token) {
    return (
      <div className="rounded-xl border border-border bg-bg-card p-10 text-center">
        <Shield className="w-8 h-8 text-text-muted mx-auto mb-3" />
        <p className="text-sm font-medium text-text-primary mb-1">Authentication required</p>
        <p className="text-xs text-text-muted">Sign in as an administrator to manage ATS integrations.</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-text-primary">Applicant Tracking Systems</h3>
        <p className="text-xs text-text-muted mt-0.5">
          Export behavioral reports back into your ATS and sync candidate records. Interview results
          flow out; no ATS-specific logic touches the analysis engine.
        </p>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-metric-stress/25 bg-metric-stress/8 px-3 py-2.5">
          <AlertCircle className="w-3.5 h-3.5 text-metric-stress flex-shrink-0" />
          <p className="text-xs text-metric-stress">{error}</p>
        </div>
      )}
      {notice && (
        <div className="flex items-center gap-2 rounded-lg border border-metric-engagement/25 bg-metric-engagement/5 px-3 py-2.5">
          <CheckCircle2 className="w-3.5 h-3.5 text-metric-engagement flex-shrink-0" />
          <p className="text-xs text-metric-engagement">{notice}</p>
        </div>
      )}

      {loading && available.length === 0 ? (
        <div className="grid sm:grid-cols-2 gap-3">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-32 w-full rounded-xl" />)}
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 gap-3">
          {available.map(prov => {
            const rec = byProvider.get(prov.provider)
            const status = rec ? rec.status : 'disconnected'
            const sm = CONNECTOR_STATUS[status] ?? CONNECTOR_STATUS.disconnected
            const isConnected = rec && status !== 'disconnected'
            return (
              <div key={prov.provider} className="rounded-xl border border-border bg-bg-card p-4 flex flex-col gap-3">
                <div className="flex items-center gap-2.5">
                  <div className="w-9 h-9 rounded-lg bg-bg-hover flex items-center justify-center flex-shrink-0">
                    <Briefcase className="w-4 h-4 text-text-secondary" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-text-primary">{prov.display_name}</p>
                    <div className="flex items-center gap-1.5">
                      <span className={cn('w-1.5 h-1.5 rounded-full',
                        status === 'connected' ? 'bg-metric-engagement'
                        : status === 'disconnected' ? 'bg-text-disabled' : 'bg-metric-stress')} />
                      <span className={cn('text-2xs font-medium', sm.color)}>{sm.label}</span>
                    </div>
                  </div>
                </div>

                <div className="flex flex-wrap gap-1">
                  {ATS_CAP_LABELS.map(c => prov.capabilities[c.key] && (
                    <span key={c.key} className="text-2xs px-1.5 py-0.5 rounded bg-bg-hover text-text-muted border border-border">
                      {c.label}
                    </span>
                  ))}
                </div>

                {isConnected && rec && (
                  <p className="text-2xs text-text-disabled flex items-center gap-1">
                    <Clock className="w-3 h-3" /> Last sync {relTime(rec.last_sync)}
                  </p>
                )}

                <div className="flex flex-wrap items-center gap-1.5 mt-auto pt-1">
                  {!isConnected ? (
                    <Button variant="primary" size="xs" icon={<Plug className="w-3 h-3" />}
                      loading={busy === prov.provider} onClick={() => handleConnect(prov.provider)}>
                      Connect
                    </Button>
                  ) : (
                    <>
                      <Button variant="ghost" size="xs" icon={<Activity className="w-3 h-3" />}
                        loading={busy === rec!.connection_id + 'test'}
                        onClick={() => handleAction(rec!.connection_id, 'test')}>Test</Button>
                      <Button variant="ghost" size="xs" icon={<RefreshCw className="w-3 h-3" />}
                        loading={busy === rec!.connection_id + 'refresh'}
                        onClick={() => handleAction(rec!.connection_id, 'refresh')}>Refresh</Button>
                      <button onClick={() => handleAction(rec!.connection_id, 'disconnect')}
                        className="text-2xs px-2 py-1 rounded-md text-metric-stress hover:bg-metric-stress/10 transition-colors flex items-center gap-1">
                        <Power className="w-3 h-3" /> Disconnect
                      </button>
                    </>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function SettingsPage() {
  const [tab, setTab] = useState('status')
  const { token } = useAuth()

  const [health,   setHealth]   = useState<HealthDetailed | null>(null)
  const [training, setTraining] = useState<TrainingStatus | null>(null)
  const [loading,  setLoading]  = useState(false)
  const [lastPoll, setLastPoll] = useState<Date | null>(null)

  // General
  const [defaultMode,    setDefaultMode]    = useState('interview')
  const [autoExport,     setAutoExport]     = useState(false)
  const [sessionTimeout, setSessionTimeout] = useState('60')
  // Models
  const [textModel,    setTextModel]    = useState('deberta')
  const [whisperModel, setWhisperModel] = useState('base')
  const [gpuAccel,     setGpuAccel]     = useState(true)
  const [fp16,         setFp16]         = useState(true)
  // Alerts
  const [stressAlert,     setStressAlert]     = useState(true)
  const [stressThreshold, setStressThreshold] = useState('0.7')
  const [fillerAlert,     setFillerAlert]      = useState(false)
  const [confidenceAlert, setConfidenceAlert]  = useState(true)
  // Save feedback
  const [savedTab, setSavedTab] = useState<string | null>(null)

  // Load persisted settings on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem('nuanceai_settings')
      if (saved) {
        const p = JSON.parse(saved)
        if (p.defaultMode)    setDefaultMode(p.defaultMode)
        if (p.autoExport     != null) setAutoExport(p.autoExport)
        if (p.sessionTimeout) setSessionTimeout(p.sessionTimeout)
        if (p.textModel)      setTextModel(p.textModel)
        if (p.whisperModel)   setWhisperModel(p.whisperModel)
        if (p.gpuAccel       != null) setGpuAccel(p.gpuAccel)
        if (p.fp16           != null) setFp16(p.fp16)
        if (p.stressAlert    != null) setStressAlert(p.stressAlert)
        if (p.stressThreshold) setStressThreshold(p.stressThreshold)
        if (p.fillerAlert    != null) setFillerAlert(p.fillerAlert)
        if (p.confidenceAlert != null) setConfidenceAlert(p.confidenceAlert)
      }
    } catch { /* ignore corrupt localStorage */ }
  }, [])

  function saveSettings(section: string, patch: object) {
    try {
      const existing = JSON.parse(localStorage.getItem('nuanceai_settings') ?? '{}')
      localStorage.setItem('nuanceai_settings', JSON.stringify({ ...existing, ...patch }))
    } catch { /* localStorage unavailable */ }
    setSavedTab(section)
    setTimeout(() => setSavedTab(s => s === section ? null : s), 2000)
  }

  const poll = useCallback(async () => {
    setLoading(true)
    try {
      const [h, t] = await Promise.all([api.healthDetailed(), api.trainingStatus()])
      setHealth(h)
      setTraining(t)
      setLastPoll(new Date())
    } catch {
      // health endpoint unreachable — set offline placeholder
      setHealth(prev => prev ?? null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    poll()
    const id = setInterval(poll, 10_000)
    return () => clearInterval(id)
  }, [poll])

  const c    = health?.components
  const sys  = health?.system

  function resolveStatus(raw?: string): StatusLevel {
    if (!raw) return 'checking'
    return raw as StatusLevel
  }

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <AppShell title="Settings">
      <div className="p-6 max-w-4xl space-y-6">

        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-text-primary">Settings</h2>
            <p className="text-sm text-text-muted mt-0.5">
              NeuroSync system status and configuration
            </p>
          </div>
          <button onClick={poll}
            className="flex items-center gap-1.5 text-xs text-text-muted hover:text-text-primary transition-colors">
            <RefreshCw className={cn('w-3.5 h-3.5', loading && 'animate-spin')} />
            {lastPoll ? `Updated ${lastPoll.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}` : 'Refresh'}
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-0 rounded-xl border border-border bg-bg-card p-1 overflow-x-auto">
          {TABS.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={cn(
                'flex items-center gap-1.5 flex-shrink-0 px-3 py-2 rounded-lg text-xs font-medium transition-all duration-150',
                tab === t.id
                  ? 'bg-bg-selected text-text-primary shadow-sm'
                  : 'text-text-muted hover:text-text-secondary',
              )}>
              <t.icon className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">{t.label}</span>
            </button>
          ))}
        </div>

        {/* ── System Status tab ────────────────────────────────────────────── */}
        {tab === 'status' && (
          <div className="space-y-4">

            {/* Summary banner */}
            <div className={cn(
              'flex items-center gap-3 rounded-xl border px-5 py-4',
              health
                ? 'border-metric-engagement/30 bg-metric-engagement/5'
                : 'border-border bg-bg-card',
            )}>
              <div className={cn(
                'w-2.5 h-2.5 rounded-full flex-shrink-0',
                health ? 'bg-metric-engagement animate-pulse' : 'bg-text-disabled',
              )} />
              <div className="flex-1">
                <p className="text-sm font-semibold text-text-primary">
                  {health ? 'NeuroSync system operational' : 'Connecting to backend…'}
                </p>
                <p className="text-xs text-text-muted mt-0.5">
                  {health
                    ? `MBA Engine · Uptime ${formatUptime(health.uptime_seconds)} · ${sys?.active_sessions ?? 0} active session${(sys?.active_sessions ?? 0) !== 1 ? 's' : ''}`
                    : 'Start with: uvicorn backend.main:app --port 8000'}
                </p>
              </div>
              {health && (
                <div className="text-right hidden sm:block">
                  <p className="text-2xs text-text-muted">Backend version</p>
                  <p className="text-xs font-mono text-text-secondary">v1.2.0-rc1</p>
                </div>
              )}
            </div>

            {/* Component grid */}
            <div className="grid md:grid-cols-2 gap-4">

              {/* Services */}
              <div className="rounded-xl border border-border bg-bg-card p-5">
                <h3 className="text-xs font-semibold text-text-muted uppercase tracking-widest mb-4">Services</h3>
                {loading && !health ? (
                  <div className="space-y-3">
                    {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-10" />)}
                  </div>
                ) : (
                  <>
                    <ComponentRow icon={Server}    label="Backend API"    status={health ? 'online' : 'offline'} detail="FastAPI v0.115" />
                    <ComponentRow icon={Database}  label="Database"       status={resolveStatus(c?.database.status)} detail="SQLite WAL" />
                    <ComponentRow icon={Wifi}      label="WebSocket"      status={health ? 'online' : 'offline'} detail={WS_URL} />
                    <ComponentRow icon={HardDrive} label="Storage"        status={c?.storage.pct != null ? (c.storage.pct > 90 ? 'warning' : 'online') : 'checking'}
                      detail={c?.storage ? `${c.storage.free_gb}GB free` : undefined} />
                  </>
                )}
              </div>

              {/* AI Models */}
              <div className="rounded-xl border border-border bg-bg-card p-5">
                <h3 className="text-xs font-semibold text-text-muted uppercase tracking-widest mb-4">NeuroSync Platform</h3>
                {loading && !health ? (
                  <div className="space-y-3">
                    {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-10" />)}
                  </div>
                ) : (
                  <>
                    <ComponentRow icon={Brain}  label="MBA Engine"         status={resolveStatus(c?.deberta.status)}
                      detail={c?.deberta.best_f1 ? `DeBERTa v3 · F1 ${Math.round(c.deberta.best_f1 * 100)}%` : 'DeBERTa v3'} />
                    <ComponentRow icon={Mic2}   label="Whisper"            status={resolveStatus(c?.whisper.status)} detail="Speech transcription" />
                    <ComponentRow icon={Eye}    label="Face Analysis"      status={resolveStatus(c?.face_engine.status)} detail="MediaPipe" />
                    <ComponentRow icon={Zap}    label="Voice Analysis"     status={resolveStatus(c?.classifiers.status)}
                      detail={c?.classifiers.n_sessions ? `${c.classifiers.n_sessions} sessions trained` : 'Prosody & pace'} />
                    <ComponentRow icon={Layers} label="Behavioral Fusion"  status={resolveStatus(c?.fusion.status)} detail="Multimodal meta-learner" />
                  </>
                )}
              </div>
            </div>

            {/* Hardware metrics */}
            <div className="rounded-xl border border-border bg-bg-card p-5">
              <h3 className="text-xs font-semibold text-text-muted uppercase tracking-widest mb-5">Hardware</h3>
              <div className="grid md:grid-cols-3 gap-6">

                {/* GPU */}
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-6 h-6 rounded-md bg-accent/10 flex items-center justify-center">
                      <Zap className="w-3.5 h-3.5 text-accent" />
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-text-primary">GPU</p>
                      <p className="text-2xs text-text-muted">
                        {c?.gpu.available ? c.gpu.name ?? 'NVIDIA GPU' : 'CPU only'}
                      </p>
                    </div>
                  </div>
                  {c?.gpu.available ? (
                    <div className="space-y-2.5">
                      {c.gpu.vram_used_mb != null && c.gpu.vram_total_mb != null && (
                        <GaugeBar
                          label="VRAM" unit="MB"
                          value={c.gpu.vram_used_mb}
                          max={c.gpu.vram_total_mb}
                          color="#818cf8"
                        />
                      )}
                      {c.gpu.utilization_pct != null && (
                        <GaugeBar
                          label="GPU Utilization" unit="%"
                          value={c.gpu.utilization_pct}
                          max={100}
                          color="#34d399"
                        />
                      )}
                      {c.gpu.vram_free_mb != null && (
                        <p className="text-2xs text-text-muted">{c.gpu.vram_free_mb} MB VRAM free</p>
                      )}
                    </div>
                  ) : (
                    <p className="text-xs text-text-muted">No CUDA device detected. Models run on CPU.</p>
                  )}
                </div>

                {/* CPU */}
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-6 h-6 rounded-md bg-metric-engagement/10 flex items-center justify-center">
                      <Cpu className="w-3.5 h-3.5 text-metric-engagement" />
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-text-primary">CPU</p>
                      <p className="text-2xs text-text-muted">Processor utilization</p>
                    </div>
                  </div>
                  {sys?.cpu_pct != null ? (
                    <div className="space-y-2.5">
                      <GaugeBar label="CPU Usage" unit="%" value={sys.cpu_pct} max={100} color="#34d399" />
                    </div>
                  ) : (
                    <Skeleton className="h-5 w-full" />
                  )}
                </div>

                {/* RAM */}
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-6 h-6 rounded-md bg-metric-stress/10 flex items-center justify-center">
                      <Activity className="w-3.5 h-3.5 text-metric-stress" />
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-text-primary">Memory</p>
                      <p className="text-2xs text-text-muted">System RAM</p>
                    </div>
                  </div>
                  {sys?.ram?.total_mb ? (
                    <div className="space-y-2.5">
                      <GaugeBar
                        label="RAM" unit="MB"
                        value={sys.ram.used_mb}
                        max={sys.ram.total_mb}
                        color="#f87171"
                      />
                      <p className="text-2xs text-text-muted">
                        {Math.round(sys.ram.free_mb / 1024)}GB free of {Math.round(sys.ram.total_mb / 1024)}GB
                      </p>
                    </div>
                  ) : (
                    <Skeleton className="h-5 w-full" />
                  )}
                </div>
              </div>
            </div>

            {/* Session activity */}
            <div className="rounded-xl border border-border bg-bg-card p-5">
              <h3 className="text-xs font-semibold text-text-muted uppercase tracking-widest mb-4">Session Activity</h3>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                {[
                  { label: 'Active sessions',    value: sys?.active_sessions ?? 0,   icon: Activity, color: '#34d399' },
                  { label: 'Backend uptime',      value: formatUptime(health?.uptime_seconds ?? null), icon: Clock,    color: '#818cf8' },
                  { label: 'DeBERTa F1',          value: c?.deberta.best_f1 ? `${Math.round(c.deberta.best_f1 * 100)}%` : '—', icon: Brain, color: '#818cf8' },
                  { label: 'Classifiers trained', value: training?.classifiers.trained ? 'Yes' : 'No', icon: CheckCircle2, color: '#34d399' },
                ].map(m => (
                  <div key={m.label} className="rounded-lg bg-bg-hover border border-border-subtle p-3">
                    <div className="flex items-center gap-1.5 mb-1.5">
                      <m.icon className="w-3.5 h-3.5" style={{ color: m.color }} />
                      <p className="text-2xs text-text-muted">{m.label}</p>
                    </div>
                    <p className="text-lg font-bold font-mono text-text-primary">{String(m.value)}</p>
                  </div>
                ))}
              </div>
            </div>

          </div>
        )}

        {/* ── General tab ──────────────────────────────────────────────────── */}
        {tab === 'general' && (
          <div className="rounded-xl border border-border bg-bg-card p-5">
            <h3 className="text-sm font-semibold text-text-primary mb-1">General</h3>
            <p className="text-xs text-text-muted mb-5">Session defaults and workspace preferences.</p>
            <SettingRow label="Default session mode" desc="Pre-selects the mode when starting a new session.">
              <SelectInput value={defaultMode} onChange={setDefaultMode}
                options={[
                  { value: 'interview',    label: 'Interview' },
                  { value: 'coaching',     label: 'Coaching' },
                  { value: 'presentation', label: 'Presentation' },
                ]} />
            </SettingRow>
            <SettingRow label="Session timeout (minutes)" desc="Automatically end sessions after this duration.">
              <SelectInput value={sessionTimeout} onChange={setSessionTimeout}
                options={[
                  { value: '30', label: '30 min' },
                  { value: '60', label: '60 min' },
                  { value: '90', label: '90 min' },
                  { value: '0',  label: 'No limit' },
                ]} />
            </SettingRow>
            <SettingRow label="Auto-export results" desc="Automatically save a PDF report when a session ends.">
              <Toggle checked={autoExport} onChange={setAutoExport} />
            </SettingRow>
            <div className="pt-4 flex items-center gap-3">
              <Button variant="primary" size="sm"
                onClick={() => saveSettings('general', { defaultMode, autoExport, sessionTimeout })}>
                {savedTab === 'general' ? '✓ Saved' : 'Save general settings'}
              </Button>
              {savedTab === 'general' && <span className="text-xs text-status-success">Settings saved locally.</span>}
            </div>
          </div>
        )}

        {/* ── AI Models tab ─────────────────────────────────────────────────── */}
        {tab === 'models' && (
          <div className="space-y-4">
            <div className="rounded-xl border border-border bg-bg-card p-5">
              <h3 className="text-sm font-semibold text-text-primary mb-1">Language Model</h3>
              <p className="text-xs text-text-muted mb-5">Controls how speech transcripts are analyzed for behavioral signals.</p>
              <SettingRow label="NLP backbone"
                desc={`Fine-tuned DeBERTa v3 achieves ${c?.deberta.best_f1 ? `${Math.round(c.deberta.best_f1 * 100)}%` : '82.4%'} macro-F1.`}>
                <SelectInput value={textModel} onChange={setTextModel}
                  options={[
                    { value: 'deberta', label: 'DeBERTa v3 (trained)' },
                    { value: 'rules',   label: 'Rule-based (fallback)' },
                  ]} />
              </SettingRow>
              <SettingRow label="Whisper model" desc="Larger models are more accurate but slower on CPU.">
                <SelectInput value={whisperModel} onChange={setWhisperModel}
                  options={[
                    { value: 'tiny',   label: 'tiny' },
                    { value: 'base',   label: 'base' },
                    { value: 'small',  label: 'small' },
                    { value: 'medium', label: 'medium' },
                  ]} />
              </SettingRow>
            </div>

            <div className="rounded-xl border border-border bg-bg-card p-5">
              <h3 className="text-sm font-semibold text-text-primary mb-1">Compute</h3>
              <p className="text-xs text-text-muted mb-5">Inference acceleration settings.</p>
              <SettingRow label="GPU acceleration" desc="Use CUDA if available.">
                <Toggle checked={gpuAccel} onChange={setGpuAccel} />
              </SettingRow>
              <SettingRow label="FP16 precision" desc="Half-precision inference — faster on CUDA.">
                <Toggle checked={fp16} onChange={setFp16} />
              </SettingRow>
              <div className="pt-4 flex items-center gap-3">
                <Button variant="primary" size="sm"
                  onClick={() => saveSettings('models', { textModel, whisperModel, gpuAccel, fp16 })}>
                  {savedTab === 'models' ? '✓ Saved' : 'Save model settings'}
                </Button>
                {savedTab === 'models' && <span className="text-xs text-status-success">Settings saved locally.</span>}
              </div>
            </div>

            <div className="rounded-xl border border-accent/20 bg-accent-glow p-5">
              <div className="flex items-center gap-2 mb-4">
                <CheckCircle2 className="w-4 h-4 text-accent" />
                <span className="text-sm font-semibold text-text-primary">MBA Engine · DeBERTa v3-base · Step 18,000</span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {[
                  { label: 'Confidence', f1: '86.2%' },
                  { label: 'Stress',     f1: '84.8%' },
                  { label: 'Hesitation', f1: '81.7%' },
                  { label: 'Comm.',      f1: '76.9%' },
                ].map(m => (
                  <div key={m.label} className="rounded-lg bg-bg-card border border-border p-2.5">
                    <p className="text-2xs text-text-muted">{m.label}</p>
                    <p className="text-sm font-bold font-mono text-accent mt-0.5">{m.f1}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── Alerts tab ───────────────────────────────────────────────────── */}
        {tab === 'alerts' && (
          <div className="rounded-xl border border-border bg-bg-card p-5">
            <h3 className="text-sm font-semibold text-text-primary mb-1">Alert Thresholds</h3>
            <p className="text-xs text-text-muted mb-5">
              Define when behavioral signals should trigger alerts during live sessions.
            </p>
            <SettingRow label="Stress spike alerts"
              desc="Alert when stress exceeds threshold for 10+ consecutive seconds.">
              <div className="flex items-center gap-3">
                <SelectInput value={stressThreshold} onChange={setStressThreshold}
                  options={[
                    { value: '0.5', label: '> 50%' },
                    { value: '0.6', label: '> 60%' },
                    { value: '0.7', label: '> 70%' },
                    { value: '0.8', label: '> 80%' },
                  ]} />
                <Toggle checked={stressAlert} onChange={setStressAlert} />
              </div>
            </SettingRow>
            <SettingRow label="Confidence drop alerts"
              desc="Alert when confidence drops below 40% for more than 20 seconds.">
              <Toggle checked={confidenceAlert} onChange={setConfidenceAlert} />
            </SettingRow>
            <SettingRow label="Filler word bursts"
              desc="Alert when more than 5 filler words detected in 30 seconds.">
              <Toggle checked={fillerAlert} onChange={setFillerAlert} />
            </SettingRow>
            <div className="pt-4 flex items-center gap-3">
              <Button variant="primary" size="sm"
                onClick={() => saveSettings('alerts', { stressAlert, stressThreshold, fillerAlert, confidenceAlert })}>
                {savedTab === 'alerts' ? '✓ Saved' : 'Save alert settings'}
              </Button>
              {savedTab === 'alerts' && <span className="text-xs text-status-success">Settings saved locally.</span>}
            </div>
          </div>
        )}

        {/* ── API tab ──────────────────────────────────────────────────────── */}
        {tab === 'api' && (
          <div className="space-y-4">
            <div className="rounded-xl border border-border bg-bg-card p-5">
              <h3 className="text-sm font-semibold text-text-primary mb-1">Backend Connection</h3>
              <p className="text-xs text-text-muted mb-5">NeuroSync API and WebSocket endpoints.</p>
              <SettingRow label="API URL" desc="FastAPI backend server.">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono text-text-secondary bg-bg-hover border border-border rounded-lg px-3 py-1.5">
                    {API_BASE.replace(/^https?:\/\//, '')}
                  </span>
                  <span className={cn(
                    'px-2 py-0.5 rounded-full text-2xs font-medium border',
                    health ? 'bg-metric-engagement/10 text-metric-engagement border-metric-engagement/20' : 'bg-text-disabled/10 text-text-disabled border-text-disabled/20',
                  )}>
                    {health ? '● Connected' : '○ Offline'}
                  </span>
                </div>
              </SettingRow>
              <SettingRow label="WebSocket URL" desc="Real-time session stream.">
                <span className="text-xs font-mono text-text-secondary bg-bg-hover border border-border rounded-lg px-3 py-1.5">
                  {WS_URL.replace(/^wss?:\/\//, 'ws://')}
                </span>
              </SettingRow>
            </div>

            <div className="rounded-xl border border-border bg-bg-card p-5">
              <h3 className="text-sm font-semibold text-text-primary mb-4">API Documentation</h3>
              <div className="flex flex-wrap gap-3">
                <a href={`${API_BASE}/docs`} target="_blank" rel="noreferrer">
                  <Button variant="secondary" size="sm" iconRight={<ExternalLink className="w-3.5 h-3.5" />}>
                    Swagger UI
                  </Button>
                </a>
                <a href={`${API_BASE}/redoc`} target="_blank" rel="noreferrer">
                  <Button variant="secondary" size="sm" iconRight={<ExternalLink className="w-3.5 h-3.5" />}>
                    ReDoc
                  </Button>
                </a>
              </div>
            </div>
          </div>
        )}

        {/* ── Users tab ────────────────────────────────────────────────────── */}
        {tab === 'users' && <UsersPanel token={token} />}

        {/* ── API Keys tab ─────────────────────────────────────────────────── */}
        {tab === 'keys' && <ApiKeysPanel token={token} />}

        {/* ── Connectors tab ───────────────────────────────────────────────── */}
        {tab === 'connectors' && <ConnectorsPanel token={token} />}

        {/* ── ATS tab ──────────────────────────────────────────────────────── */}
        {tab === 'ats' && <AtsPanel token={token} />}

      </div>
    </AppShell>
  )
}
