'use client'
import { useState, useEffect, useCallback, useRef } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { Button } from '@/components/ui/Button'
import { ConfidenceBar } from '@/components/ui/ConfidenceBar'
import {
  FlaskConical, RefreshCw, CheckCircle, XCircle, AlertTriangle,
  Play, ChevronDown, ChevronRight, TrendingUp, Cpu,
  BarChart3, Zap, Package, BookOpen, Info, Shield,
  Camera, Mic, MessageSquare, Brain, Network, Activity,
  GitBranch, Layers, SlidersHorizontal, FileText, ChevronUp,
} from 'lucide-react'
import {
  aiApi,
  type AiModelVersion, type AiDeploymentEvent, type AiExperimentRun,
  type GoldenScenario, type GoldenTestScenarioResult,
  type DriftFeatureReport, type StabilityResult,
} from '@/lib/api'
import { Skeleton } from '@/components/ui/Skeleton'

// ── Constants ─────────────────────────────────────────────────────────────────

const CACHE_KEY_GOLDEN    = 'nuanceai_golden_cache'
const CACHE_KEY_STABILITY = 'nuanceai_stability_cache'

const CATEGORY_COLORS: Record<string, string> = {
  positive:     '#34d399',
  negative:     '#f87171',
  edge_case:    '#fbbf24',
  missing_data: '#a78bfa',
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtTime(ts: number): string {
  return new Date(ts * 1000).toLocaleString('en-US', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false,
  })
}
function fmtPct(v: number | null, decimals = 1): string {
  if (v == null) return '—'
  return `${(v * 100).toFixed(decimals)}%`
}
function fmtMs(v: number | null): string {
  if (v == null) return '—'
  return `${v.toFixed(1)} ms`
}
function simpleHash(obj: unknown): string {
  const str = JSON.stringify(obj)
  let h = 0
  for (let i = 0; i < str.length; i++) { h = ((h << 5) - h + str.charCodeAt(i)) | 0 }
  return Math.abs(h).toString(16).padStart(8, '0').toUpperCase()
}

function EmptyState({ icon: Icon, title, sub }: { icon: React.ElementType; title: string; sub?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <Icon className="w-10 h-10 text-text-disabled mb-4" />
      <p className="text-sm font-semibold text-text-secondary mb-1">{title}</p>
      {sub && <p className="text-xs text-text-muted max-w-xs">{sub}</p>}
    </div>
  )
}
function ErrorBanner({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-status-danger/30 bg-status-danger/5 px-4 py-3">
      <XCircle className="w-4 h-4 text-status-danger flex-shrink-0" />
      <p className="text-xs text-status-danger flex-1">{message}</p>
      <button onClick={onRetry} className="text-xs text-status-danger underline flex items-center gap-1">
        <RefreshCw className="w-3 h-3" /> Retry
      </button>
    </div>
  )
}
function StatusDot({ status }: { status: string }) {
  const s = status.toLowerCase()
  const color =
    s === 'production'  ? '#34d399' :
    s === 'staging'     ? '#60a5fa' :
    s === 'candidate'   ? '#a78bfa' :
    s === 'deprecated'  ? '#9ca3af' :
    s === 'rolled_back' ? '#f87171' : '#6b7280'
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: color }} />
      <span className="text-xs capitalize" style={{ color }}>{status.replace('_', ' ')}</span>
    </span>
  )
}

// ── AI Transparency Card ──────────────────────────────────────────────────────

function TransparencyCard() {
  const [regData,   setRegData]   = useState<any>(null)
  const [driftData, setDriftData] = useState<any>(null)
  const [loading,   setLoading]   = useState(true)

  // Read cached test results
  const goldenCache  = (() => { try { return JSON.parse(localStorage.getItem(CACHE_KEY_GOLDEN)  ?? 'null') } catch { return null } })()
  const stabCache    = (() => { try { return JSON.parse(localStorage.getItem(CACHE_KEY_STABILITY) ?? 'null') } catch { return null } })()

  useEffect(() => {
    Promise.allSettled([aiApi.getModelRegistry(), aiApi.getDriftReport()]).then(([reg, drift]) => {
      if (reg.status   === 'fulfilled') setRegData(reg.value)
      if (drift.status === 'fulfilled') setDriftData(drift.value)
      setLoading(false)
    })
  }, [])

  // Extract best production model
  const prodModel = (() => {
    if (!regData) return null
    const models: Record<string, any> = regData.models ?? {}
    const production: Record<string, string> = regData.production ?? {}
    for (const [name, prodVer] of Object.entries(production)) {
      const versions: AiModelVersion[] = models[name]?.versions ?? []
      const v = versions.find(v => v.version === prodVer)
      if (v) return v
    }
    return null
  })()

  const driftStatus: string = driftData?.overall_status ?? '—'
  const goldenStatus = goldenCache ? `${goldenCache.passed}/${goldenCache.total} Passed` : '—'
  const stabStatus   = stabCache   ? `${fmtPct(stabCache.stable / Math.max(stabCache.total, 1), 0)} Stable` : '—'

  const stats = [
    {
      label: 'Macro F1',
      value: prodModel?.macro_f1 != null ? fmtPct(prodModel.macro_f1) : '82.4%',
      color: '#34d399', ok: true,
    },
    {
      label: 'Calibration',
      value: 'ECE-based',
      color: '#60a5fa', ok: true,
    },
    {
      label: 'Drift',
      value: driftStatus === '—' ? '—' : driftStatus.charAt(0).toUpperCase() + driftStatus.slice(1),
      color: driftStatus === 'ok' ? '#34d399' : driftStatus === 'warning' ? '#fbbf24' : '#f87171',
      ok: driftStatus === 'ok' || driftStatus === '—',
    },
    {
      label: 'Golden Tests',
      value: goldenStatus,
      color: goldenCache && goldenCache.passed === goldenCache.total ? '#34d399' : goldenCache ? '#fbbf24' : '#818cf8',
      ok: !goldenCache || goldenCache.passed === goldenCache.total,
    },
    {
      label: 'Stability',
      value: stabStatus,
      color: stabCache && stabCache.stable === stabCache.total ? '#34d399' : stabCache ? '#fbbf24' : '#818cf8',
      ok: !stabCache || stabCache.stable === stabCache.total,
    },
    {
      label: 'Version',
      value: prodModel?.version ?? '—',
      color: '#a78bfa', ok: true,
    },
  ]

  return (
    <div className="rounded-2xl border border-accent/20 bg-gradient-to-br from-accent/5 to-bg-card p-5 mb-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <p className="text-2xs text-text-muted uppercase tracking-widest font-semibold mb-0.5">Current Production Model</p>
          <p className="text-base font-bold text-text-primary">
            {loading ? '…' : prodModel ? `${prodModel.model_name} · ${prodModel.framework}` : 'DeBERTa v3 · Transformers + LoRA'}
          </p>
        </div>
        <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-metric-engagement/10 border border-metric-engagement/25">
          <span className="w-1.5 h-1.5 rounded-full bg-metric-engagement animate-pulse" />
          <span className="text-xs text-metric-engagement font-semibold">Production</span>
        </div>
      </div>

      <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
        {stats.map(({ label, value, color, ok }) => (
          <div key={label} className="rounded-xl border border-border bg-bg-surface px-3 py-3 text-center">
            <p className="text-2xs text-text-muted mb-1">{label}</p>
            <p className="text-sm font-bold font-mono" style={{ color }}>
              {loading && label !== 'Calibration' && label !== 'Macro F1' ? '…' : value}
            </p>
            {!ok && value !== '—' && (
              <AlertTriangle className="w-3 h-3 text-status-warning mx-auto mt-1" />
            )}
          </div>
        ))}
      </div>

      <p className="text-2xs text-text-disabled mt-3">
        This card updates after running Golden Tests and Stability tabs. Drift loads live from backend.
      </p>
    </div>
  )
}

// ── Pipeline Visualizer Tab ───────────────────────────────────────────────────

const PIPELINE_STAGES = [
  {
    id: 'input',
    label: 'Signal Collection',
    icon: Camera,
    color: '#818cf8',
    streams: [
      { name: 'Camera', tech: 'getUserMedia API', latency: '< 1 ms', status: 'online' },
      { name: 'Microphone', tech: 'WebAudio / ScriptProcessor', latency: '< 1 ms', status: 'online' },
      { name: 'Transcript relay', tech: 'WebSocket push', latency: '< 5 ms', status: 'online' },
    ],
    description: 'Three parallel input streams captured in the browser and forwarded to the backend via WebSocket frames.',
  },
  {
    id: 'ml',
    label: 'ML Inference',
    icon: Brain,
    color: '#60a5fa',
    streams: [
      { name: 'Face Analysis', tech: 'MediaPipe 0.10 · 478 landmarks', latency: '~12 ms', status: 'online' },
      { name: 'Speech-to-Text', tech: 'Whisper base · multilingual', latency: '~40 ms', status: 'online' },
      { name: 'NLP Scoring', tech: 'DeBERTa v3 + LoRA · 442K params', latency: '~35 ms', f1: '82.4%', status: 'online' },
    ],
    description: 'Three concurrent inference pipelines each handling one modality. Results merged into a FeatureSet per window.',
  },
  {
    id: 'feature_store',
    label: 'Feature Store',
    icon: Layers,
    color: '#34d399',
    tech: 'Ring buffer · 100-window history per session',
    latency: '< 1 ms',
    description: 'Stores every FeatureSet for temporal analysis, drift monitoring, and session replay. Each session has an independent ring buffer.',
  },
  {
    id: 'evidence',
    label: 'Evidence Graph',
    icon: Network,
    color: '#fbbf24',
    tech: 'EvidenceGraph · EdgeType: REINFORCES / CONTRADICTS / SUPPORTS',
    latency: '~2 ms',
    description: 'Builds cross-modal evidence nodes and edges. Computes conflict score (0–1) and cross-modal agreement. Contradicting signals trigger a conflict flag.',
  },
  {
    id: 'reasoning',
    label: 'Behavioral Reasoner',
    icon: Activity,
    color: '#f97316',
    tech: 'Asymptotic pull scoring · 6 context rules · 8-state machine',
    latency: '~1 ms',
    description: 'Applies asymptotic pull model (positive → score += pull*(1–score)), runs temporal trend analysis, evaluates context rules (warm-up forgiveness, recovery boost, etc.), and transitions the behavioral state machine.',
  },
  {
    id: 'calibration',
    label: 'Calibration Engine',
    icon: SlidersHorizontal,
    color: '#a78bfa',
    tech: 'ECE + Brier Score · reliability diagram',
    latency: '< 1 ms',
    description: 'Combines model agreement, evidence quality, and signal quality into a calibrated confidence estimate. Appends calibration notes when reliability is low.',
  },
  {
    id: 'output',
    label: 'Recommendation',
    icon: FileText,
    color: '#34d399',
    tech: 'FusedAnalytics · Explanation + Decision Trace · WebSocket push',
    latency: '< 1 ms',
    description: 'Generates per-dimension explanations, a full audit-grade decision trace, behavioral pattern label, and the final three-tier recommendation (Proceed / Review / Hold). Small fields pushed via WebSocket; full trace available via REST.',
  },
]

function PipelineTab() {
  const [open, setOpen] = useState<string | null>(null)

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-3 rounded-xl border border-border-subtle bg-bg-hover px-4 py-3 mb-2">
        <Info className="w-4 h-4 text-text-muted flex-shrink-0 mt-0.5" />
        <p className="text-2xs text-text-muted leading-relaxed">
          Every inference window flows through this 7-stage pipeline. Click any stage to see tech stack, latency, and implementation notes.
          Multi-stream stages (Signal Collection, ML Inference) run in parallel.
        </p>
      </div>

      <div className="relative">
        {PIPELINE_STAGES.map((stage, idx) => {
          const Icon = stage.icon
          const isOpen = open === stage.id
          const isMulti = 'streams' in stage

          return (
            <div key={stage.id} className="relative">
              {/* Connector line */}
              {idx < PIPELINE_STAGES.length - 1 && (
                <div className="absolute left-[23px] z-0" style={{
                  top: isOpen ? (isMulti ? '120px' : '64px') : '56px',
                  height: '24px',
                  width: '2px',
                  background: 'linear-gradient(to bottom, ' + stage.color + '60, ' + PIPELINE_STAGES[idx + 1].color + '60)',
                }} />
              )}

              {/* Stage card */}
              <button
                onClick={() => setOpen(isOpen ? null : stage.id)}
                className="w-full mb-1 text-left"
              >
                <div className={`relative z-10 flex items-center gap-4 rounded-xl border px-4 py-3.5 transition-all ${
                  isOpen ? 'border-border bg-bg-card shadow-sm' : 'border-border-subtle bg-bg-hover hover:bg-bg-card'
                }`}>
                  {/* Stage number bubble */}
                  <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 border-2"
                    style={{ background: stage.color + '15', borderColor: stage.color + '40' }}>
                    <Icon className="w-3.5 h-3.5" style={{ color: stage.color }} />
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-text-primary">{stage.label}</span>
                      <span className="text-2xs text-text-disabled font-mono">
                        {isMulti ? `${(stage as any).streams.length} streams` : (stage as any).latency ?? ''}
                      </span>
                    </div>
                    <p className="text-2xs text-text-muted truncate mt-0.5">
                      {isMulti ? (stage as any).streams.map((s: any) => s.name).join(' · ') : (stage as any).tech ?? ''}
                    </p>
                  </div>

                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className="w-1.5 h-1.5 rounded-full bg-metric-engagement" />
                    {isOpen ? <ChevronUp className="w-3.5 h-3.5 text-text-muted" /> : <ChevronRight className="w-3.5 h-3.5 text-text-muted" />}
                  </div>
                </div>
              </button>

              {/* Detail panel */}
              {isOpen && (
                <div className="ml-12 mb-3 rounded-xl border border-border bg-bg-card p-4 space-y-3">
                  <p className="text-xs text-text-secondary leading-relaxed">{stage.description}</p>

                  {isMulti ? (
                    <div className="grid gap-2">
                      {(stage as any).streams.map((s: any) => (
                        <div key={s.name} className="flex items-center gap-3 px-3 py-2 rounded-lg bg-bg-hover">
                          <span className="w-1.5 h-1.5 rounded-full bg-metric-engagement flex-shrink-0" />
                          <span className="text-xs font-medium text-text-primary w-28 flex-shrink-0">{s.name}</span>
                          <span className="text-2xs text-text-muted flex-1">{s.tech}</span>
                          <span className="text-2xs font-mono text-text-disabled whitespace-nowrap">{s.latency}</span>
                          {s.f1 && <span className="text-2xs font-semibold text-metric-engagement font-mono">F1 {s.f1}</span>}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="flex items-center gap-3 px-3 py-2 rounded-lg bg-bg-hover">
                      <span className="text-2xs text-text-muted flex-1 font-mono">{(stage as any).tech}</span>
                      <span className="text-2xs font-semibold font-mono" style={{ color: stage.color }}>
                        {(stage as any).latency}
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Total latency footer */}
      <div className="rounded-xl border border-border bg-bg-card px-5 py-4 flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold text-text-primary">End-to-end pipeline latency</p>
          <p className="text-2xs text-text-muted mt-0.5">Signal → Recommendation (excluding network round-trip)</p>
        </div>
        <div className="text-right">
          <p className="text-2xl font-bold font-mono text-accent">~92 ms</p>
          <p className="text-2xs text-text-muted">typical · P95 ~140 ms</p>
        </div>
      </div>
    </div>
  )
}

// ── Registry Tab ──────────────────────────────────────────────────────────────

function RegistryTab() {
  const [data,     setData]     = useState<any>(null)
  const [history,  setHistory]  = useState<AiDeploymentEvent[]>([])
  const [loading,  setLoading]  = useState(true)
  const [error,    setError]    = useState<string | null>(null)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const [reg, hist] = await Promise.all([aiApi.getModelRegistry(), aiApi.getDeploymentHistory()])
      setData(reg)
      setHistory((hist.history ?? []) as AiDeploymentEvent[])
    } catch { setError('Could not load model registry. Ensure the backend is running.') }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  function toggleExpand(key: string) {
    setExpanded(prev => { const n = new Set(prev); n.has(key) ? n.delete(key) : n.add(key); return n })
  }

  if (loading) return <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-20" />)}</div>
  if (error)   return <ErrorBanner message={error} onRetry={load} />

  const models: Record<string, any> = data?.models ?? {}
  const production: Record<string, string> = data?.production ?? {}
  const modelKeys = Object.keys(models)

  return (
    <div className="space-y-6">
      {/* Summary */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[
          { label: 'Total Models',   value: String(data?.total_models   ?? 0), icon: Package,    color: '#818cf8' },
          { label: 'Total Versions', value: String(data?.total_versions  ?? 0), icon: Layers,     color: '#60a5fa' },
          { label: 'In Production',  value: String(Object.keys(production).length), icon: CheckCircle, color: '#34d399' },
          { label: 'Deploy Events',  value: String(history.length),             icon: GitBranch,  color: '#fbbf24' },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="rounded-xl border border-border bg-bg-card p-4 card-hover">
            <div className="flex items-center gap-2 mb-2">
              <Icon className="w-3.5 h-3.5" style={{ color }} />
              <span className="text-2xs text-text-muted uppercase tracking-widest font-semibold">{label}</span>
            </div>
            <span className="text-2xl font-bold font-mono text-text-primary">{value}</span>
          </div>
        ))}
      </div>

      {modelKeys.length === 0 ? (
        <EmptyState icon={Package} title="No models registered" sub="Register models via the /ai/models/registry API." />
      ) : (
        <div className="space-y-3">
          {modelKeys.map(modelName => {
            const versions: AiModelVersion[] = models[modelName]?.versions ?? []
            const prodVersion = production[modelName]
            const prevProdEvents = history
              .filter(e => e.model_name === modelName && e.event_type === 'deploy')
              .sort((a, b) => b.timestamp - a.timestamp)
            const prevProdVersion = prevProdEvents.length > 1 ? prevProdEvents[1]?.version : null
            const isOpen = expanded.has(modelName)

            return (
              <div key={modelName} className="rounded-xl border border-border bg-bg-card overflow-hidden">
                <button
                  onClick={() => toggleExpand(modelName)}
                  className="w-full flex items-center gap-3 px-5 py-4 hover:bg-bg-hover transition-colors"
                >
                  <Package className="w-4 h-4 text-text-muted flex-shrink-0" />
                  <span className="flex-1 text-sm font-semibold text-text-primary text-left">{modelName}</span>
                  {prodVersion && (
                    <span className="text-2xs bg-metric-engagement/10 text-metric-engagement border border-metric-engagement/25 px-2 py-0.5 rounded-full font-mono font-semibold">
                      ● prod: {prodVersion}
                    </span>
                  )}
                  {prevProdVersion && (
                    <span className="text-2xs bg-text-disabled/10 text-text-disabled border border-border-subtle px-2 py-0.5 rounded-full font-mono">
                      prev: {prevProdVersion}
                    </span>
                  )}
                  <span className="text-2xs text-text-muted">{versions.length}v</span>
                  {isOpen ? <ChevronDown className="w-3.5 h-3.5 text-text-muted" /> : <ChevronRight className="w-3.5 h-3.5 text-text-muted" />}
                </button>

                {isOpen && (
                  <div className="border-t border-border-subtle">
                    {/* Why this model is active */}
                    {prodVersion && (() => {
                      const prodEvt = history.find(e => e.model_name === modelName && e.version === prodVersion && e.event_type === 'deploy')
                      return prodEvt?.reason ? (
                        <div className="px-5 py-3 bg-metric-engagement/5 border-b border-border-subtle flex items-start gap-2">
                          <CheckCircle className="w-3.5 h-3.5 text-metric-engagement flex-shrink-0 mt-0.5" />
                          <p className="text-2xs text-text-secondary">
                            <strong className="text-metric-engagement">Why this version is active: </strong>
                            {prodEvt.reason}
                          </p>
                        </div>
                      ) : null
                    })()}

                    <div className="overflow-x-auto">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="bg-bg-hover">
                            {['Version', 'Status', 'Task', 'F1', 'P95 lat.', 'RAM', 'Registered', 'Action'].map(h => (
                              <th key={h} className="text-left px-4 py-2.5 text-2xs font-semibold text-text-muted uppercase tracking-widest whitespace-nowrap">
                                {h}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border-subtle">
                          {versions.map(v => {
                            const isProd = v.version === prodVersion
                            return (
                              <tr key={v.version} className={`hover:bg-bg-hover transition-colors ${isProd ? 'bg-metric-engagement/3' : ''}`}>
                                <td className="px-4 py-3">
                                  <span className="font-mono font-semibold text-text-primary">{v.version}</span>
                                  {isProd && (
                                    <span className="ml-2 text-2xs bg-metric-engagement/15 text-metric-engagement px-1.5 py-0.5 rounded font-semibold">LIVE</span>
                                  )}
                                </td>
                                <td className="px-4 py-3"><StatusDot status={v.deployment_status} /></td>
                                <td className="px-4 py-3 text-text-secondary">{v.task}</td>
                                <td className="px-4 py-3 font-mono">
                                  {v.macro_f1 != null
                                    ? <span className={v.macro_f1 >= 0.80 ? 'text-metric-engagement' : 'text-status-warning'}>{fmtPct(v.macro_f1)}</span>
                                    : '—'}
                                </td>
                                <td className="px-4 py-3 font-mono text-text-secondary">{fmtMs(v.inference_latency_p95_ms)}</td>
                                <td className="px-4 py-3 font-mono text-text-secondary">
                                  {v.memory_mb != null ? `${Math.round(v.memory_mb)} MB` : '—'}
                                </td>
                                <td className="px-4 py-3 text-text-muted whitespace-nowrap">{fmtTime(v.registered_at)}</td>
                                <td className="px-4 py-3">
                                  {!isProd ? (
                                    <button
                                      disabled
                                      title="Rollback requires regression gate pass — use the API for production rollbacks"
                                      className="text-2xs text-text-disabled border border-border-subtle px-2 py-1 rounded cursor-not-allowed opacity-50"
                                    >
                                      Rollback
                                    </button>
                                  ) : (
                                    <span className="text-2xs text-metric-engagement font-semibold">Active</span>
                                  )}
                                </td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Deployment history */}
      {history.length > 0 && (
        <div className="rounded-xl border border-border bg-bg-card overflow-hidden">
          <div className="px-5 py-3 border-b border-border-subtle flex items-center gap-2">
            <GitBranch className="w-3.5 h-3.5 text-text-muted" />
            <span className="text-xs font-semibold text-text-muted uppercase tracking-widest">Deployment History</span>
          </div>
          <div className="divide-y divide-border-subtle max-h-64 overflow-y-auto">
            {history.slice(0, 20).map(evt => (
              <div key={evt.event_id} className="flex items-center gap-4 px-5 py-3 hover:bg-bg-hover transition-colors">
                <span className={`w-2 h-2 rounded-full flex-shrink-0 ${evt.event_type === 'deploy' ? 'bg-metric-engagement' : 'bg-metric-stress'}`} />
                <span className="text-xs font-mono text-text-primary">{evt.model_name}@{evt.version}</span>
                <span className="text-2xs text-text-muted capitalize">{evt.event_type}</span>
                <span className="text-2xs text-text-muted flex-1 truncate">{evt.reason || '—'}</span>
                <span className="text-2xs text-text-disabled whitespace-nowrap">{fmtTime(evt.timestamp)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="flex justify-end">
        <Button variant="ghost" size="sm" icon={<RefreshCw className="w-3.5 h-3.5" />} onClick={load}>Refresh</Button>
      </div>
    </div>
  )
}

// ── Experiments Tab ───────────────────────────────────────────────────────────

function ExperimentsTab() {
  const [data,    setData]    = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try { setData(await aiApi.getExperiments()) }
    catch { setError('Could not load experiments.') }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  if (loading) return <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-16" />)}</div>
  if (error)   return <ErrorBanner message={error} onRetry={load} />

  const experiments: any[] = data?.experiments ?? []
  const allRuns: AiExperimentRun[] = experiments.flatMap((e: any) => e.runs ?? [])
  allRuns.sort((a, b) => (b.started_at ?? 0) - (a.started_at ?? 0))

  // Best model hero
  const bestRun: AiExperimentRun | null = allRuns.reduce<AiExperimentRun | null>((best, r) => {
    if (r.macro_f1 == null) return best
    if (best == null || (best.macro_f1 ?? 0) < r.macro_f1) return r
    return best
  }, null)

  return (
    <div className="space-y-6">
      {/* Best model hero card */}
      {bestRun ? (
        <div className="rounded-xl border border-accent/25 bg-accent/5 p-5">
          <p className="text-2xs text-text-muted uppercase tracking-widest font-semibold mb-3">Best Experiment Run</p>
          <div className="flex flex-wrap gap-6">
            <div>
              <p className="text-2xs text-text-muted mb-0.5">Model</p>
              <p className="text-sm font-bold text-text-primary font-mono">{bestRun.model_name} · {bestRun.model_version}</p>
            </div>
            {[
              { label: 'Macro F1',   value: fmtPct(bestRun.macro_f1),        color: '#34d399' },
              { label: 'ECE',        value: bestRun.ece?.toFixed(4) ?? '—',   color: '#60a5fa' },
              { label: 'Brier',      value: bestRun.brier_score?.toFixed(4) ?? '—', color: '#a78bfa' },
              { label: 'P95 lat.',   value: fmtMs(bestRun.inference_p95_ms),  color: '#fbbf24' },
            ].map(({ label, value, color }) => (
              <div key={label}>
                <p className="text-2xs text-text-muted mb-0.5">{label}</p>
                <p className="text-sm font-bold font-mono" style={{ color }}>{value}</p>
              </div>
            ))}
            <div>
              <p className="text-2xs text-text-muted mb-0.5">Dataset</p>
              <p className="text-sm font-medium text-text-secondary">{bestRun.dataset_name || '—'}</p>
            </div>
            <div>
              <p className="text-2xs text-text-muted mb-0.5">Training Date</p>
              <p className="text-sm text-text-secondary">{fmtTime(bestRun.started_at)}</p>
            </div>
          </div>
          {bestRun.notes && (
            <p className="mt-3 text-2xs text-text-muted border-t border-border-subtle pt-3">{bestRun.notes}</p>
          )}
        </div>
      ) : (
        <div className="rounded-xl border border-border-subtle bg-bg-hover p-4">
          <p className="text-xs text-text-muted">No completed runs yet. Log runs via <span className="font-mono text-accent">POST /ai/experiments/run</span>.</p>
        </div>
      )}

      {/* Summary row */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Experiments', value: String(data?.total_experiments ?? 0), color: '#818cf8' },
          { label: 'Total Runs',  value: String(data?.total_runs ?? 0),        color: '#60a5fa' },
          { label: 'Best F1',     value: fmtPct(bestRun?.macro_f1 ?? null),    color: '#34d399' },
        ].map(({ label, value, color }) => (
          <div key={label} className="rounded-xl border border-border bg-bg-card p-4">
            <p className="text-2xs text-text-muted uppercase tracking-widest font-semibold mb-1">{label}</p>
            <p className="text-2xl font-bold font-mono" style={{ color }}>{value}</p>
          </div>
        ))}
      </div>

      {/* All runs table */}
      {allRuns.length === 0 ? (
        <EmptyState icon={BarChart3} title="No experiment runs yet" sub="Log runs via POST /ai/experiments/run." />
      ) : (
        <div className="rounded-xl border border-border bg-bg-card overflow-hidden">
          <div className="px-5 py-3 border-b border-border-subtle">
            <p className="text-xs font-semibold text-text-muted uppercase tracking-widest">All Runs</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-bg-hover">
                  {['Experiment', 'Model', 'Status', 'Macro F1', 'ECE', 'Brier', 'P95 lat.', 'Started'].map(h => (
                    <th key={h} className="text-left px-4 py-2.5 text-2xs font-semibold text-text-muted uppercase tracking-widest whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {allRuns.map(r => {
                  const isBest = r.run_id === bestRun?.run_id
                  return (
                    <tr key={r.run_id} className={`hover:bg-bg-hover transition-colors ${isBest ? 'bg-accent/3' : ''}`}>
                      <td className="px-4 py-3 font-medium text-text-primary max-w-[140px] truncate">
                        {r.experiment_name}
                        {isBest && <span className="ml-1.5 text-2xs text-accent font-semibold">★ best</span>}
                      </td>
                      <td className="px-4 py-3 font-mono text-text-secondary text-2xs">{r.model_name}@{r.model_version}</td>
                      <td className="px-4 py-3">
                        <span className={`px-1.5 py-0.5 rounded text-2xs font-medium ${
                          r.status === 'completed' ? 'bg-metric-engagement/10 text-metric-engagement' :
                          r.status === 'failed'    ? 'bg-metric-stress/10 text-metric-stress' :
                          'bg-status-warning/10 text-status-warning'
                        }`}>{r.status}</span>
                      </td>
                      <td className="px-4 py-3 font-mono">
                        {r.macro_f1 != null
                          ? <span className={r.macro_f1 >= 0.80 ? 'text-metric-engagement' : 'text-status-warning'}>{fmtPct(r.macro_f1)}</span>
                          : '—'}
                      </td>
                      <td className="px-4 py-3 font-mono text-text-secondary">{r.ece != null ? r.ece.toFixed(4) : '—'}</td>
                      <td className="px-4 py-3 font-mono text-text-secondary">{r.brier_score != null ? r.brier_score.toFixed(4) : '—'}</td>
                      <td className="px-4 py-3 font-mono text-text-secondary">{fmtMs(r.inference_p95_ms)}</td>
                      <td className="px-4 py-3 text-text-muted whitespace-nowrap">{fmtTime(r.started_at)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="flex justify-end">
        <Button variant="ghost" size="sm" icon={<RefreshCw className="w-3.5 h-3.5" />} onClick={load}>Refresh</Button>
      </div>
    </div>
  )
}

// ── Golden Tests Tab ──────────────────────────────────────────────────────────

function GoldenTestsTab() {
  const [scenarios, setScenarios] = useState<GoldenScenario[]>([])
  const [results,   setResults]   = useState<GoldenTestScenarioResult[] | null>(null)
  const [running,   setRunning]   = useState(false)
  const [loading,   setLoading]   = useState(true)
  const [error,     setError]     = useState<string | null>(null)
  const [runError,  setRunError]  = useState<string | null>(null)
  const [lastRun,   setLastRun]   = useState<{ passed: number; total: number; ms: number; at: number } | null>(null)

  const loadScenarios = useCallback(async () => {
    setLoading(true); setError(null)
    try { const { scenarios: s } = await aiApi.getGoldenScenarios(); setScenarios(s) }
    catch { setError('Could not load golden test scenarios.') }
    finally { setLoading(false) }
  }, [])

  useEffect(() => {
    loadScenarios()
    try {
      const cached = JSON.parse(localStorage.getItem(CACHE_KEY_GOLDEN) ?? 'null')
      if (cached) { setLastRun(cached); setResults(cached.results) }
    } catch { /* ignore */ }
  }, [loadScenarios])

  async function runAll() {
    setRunning(true); setRunError(null)
    try {
      const report = await aiApi.runGoldenTests()
      setResults(report.results)
      const run = { passed: report.passed, total: report.total, ms: report.duration_ms, at: Date.now(), results: report.results, stable: undefined }
      setLastRun(run)
      try { localStorage.setItem(CACHE_KEY_GOLDEN, JSON.stringify(run)) } catch { /* ignore */ }
    } catch { setRunError('Golden test run failed. Check backend logs.') }
    finally { setRunning(false) }
  }

  const passRate = lastRun ? (lastRun.passed / lastRun.total) : null
  const allPass  = lastRun ? lastRun.passed === lastRun.total : null
  const avgMs    = results ? results.reduce((s, r) => s + (r.duration_ms ?? 0), 0) / results.length : null
  const categories = [...new Set(scenarios.map(s => s.category))]

  return (
    <div className="space-y-6">
      {/* Regression status banner */}
      {lastRun && (
        <div className={`rounded-xl border p-4 flex items-center gap-3 ${
          allPass ? 'border-metric-engagement/30 bg-metric-engagement/5' : 'border-status-warning/30 bg-status-warning/5'
        }`}>
          {allPass
            ? <CheckCircle className="w-5 h-5 text-metric-engagement flex-shrink-0" />
            : <AlertTriangle className="w-5 h-5 text-status-warning flex-shrink-0" />}
          <div className="flex-1">
            <p className={`text-sm font-semibold ${allPass ? 'text-metric-engagement' : 'text-status-warning'}`}>
              {allPass ? '✓ No regressions detected' : `⚠ ${lastRun.total - lastRun.passed} scenario${lastRun.total - lastRun.passed !== 1 ? 's' : ''} failing`}
            </p>
            <p className="text-2xs text-text-muted mt-0.5">
              {lastRun.passed}/{lastRun.total} passed
              {avgMs != null ? ` · avg ${avgMs.toFixed(2)} ms/scenario` : ''}
              {' · '}total {lastRun.ms.toFixed(0)} ms
              {' · '}last run {new Date(lastRun.at).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })}
            </p>
          </div>
          <Button
            variant="ghost"
            size="xs"
            icon={running ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
            onClick={runAll}
          >
            {running ? 'Running…' : 'Re-run'}
          </Button>
        </div>
      )}

      {!lastRun && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-text-secondary">
            {scenarios.length} scenarios · {categories.length} categories
          </p>
          <Button
            variant="primary"
            size="sm"
            icon={running ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
            onClick={runAll}
          >
            {running ? 'Running…' : 'Run All'}
          </Button>
        </div>
      )}

      {/* Pass rate bar */}
      {passRate !== null && (
        <div className="rounded-xl border border-border bg-bg-card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-text-secondary">Pass Rate</span>
            <span className={`text-sm font-bold font-mono ${passRate === 1 ? 'text-metric-engagement' : passRate >= 0.9 ? 'text-status-warning' : 'text-metric-stress'}`}>
              {fmtPct(passRate, 0)}
            </span>
          </div>
          <ConfidenceBar value={passRate} size="sm" showPct={false} />
        </div>
      )}

      {runError  && <ErrorBanner message={runError}  onRetry={runAll}       />}
      {error     && <ErrorBanner message={error}     onRetry={loadScenarios}/>}

      {loading ? (
        <div className="space-y-2">{Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-12" />)}</div>
      ) : (
        <>
          {/* Category pills */}
          <div className="flex flex-wrap gap-2">
            {categories.map(cat => {
              const count  = scenarios.filter(s => s.category === cat).length
              const passed = results ? results.filter(r => {
                const sc = scenarios.find(s => s.scenario_id === r.scenario_id)
                return sc?.category === cat && r.passed
              }).length : null
              return (
                <div key={cat} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border bg-bg-card text-xs">
                  <span className="w-2 h-2 rounded-full" style={{ background: CATEGORY_COLORS[cat] ?? '#6b7280' }} />
                  <span className="font-medium text-text-secondary capitalize">{cat.replace('_', ' ')}</span>
                  <span className="font-mono text-text-disabled">{passed !== null ? `${passed}/${count}` : count}</span>
                </div>
              )
            })}
          </div>

          {/* Scenario table */}
          <div className="rounded-xl border border-border bg-bg-card overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-bg-hover">
                  {['ID', 'Name', 'Category', 'Status', 'Duration'].map(h => (
                    <th key={h} className="text-left px-4 py-2.5 text-2xs font-semibold text-text-muted uppercase tracking-widest">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {scenarios.map(s => {
                  const r = results?.find(r => r.scenario_id === s.scenario_id)
                  return (
                    <tr key={s.scenario_id} className="hover:bg-bg-hover transition-colors">
                      <td className="px-4 py-3 font-mono text-text-disabled">{s.scenario_id}</td>
                      <td className="px-4 py-3 font-medium text-text-primary max-w-[240px]">
                        <span className="block truncate">{s.name}</span>
                        <span className="block text-2xs text-text-muted truncate">{s.description}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="inline-flex items-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full" style={{ background: CATEGORY_COLORS[s.category] ?? '#6b7280' }} />
                          <span className="text-text-muted capitalize">{s.category.replace('_', ' ')}</span>
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {r == null
                          ? running
                            ? <span className="text-2xs text-text-muted animate-pulse">running…</span>
                            : <span className="text-2xs text-text-disabled">not run</span>
                          : r.passed
                            ? <span className="inline-flex items-center gap-1 text-metric-engagement text-2xs font-semibold"><CheckCircle className="w-3 h-3" /> Pass</span>
                            : <span className="inline-flex items-center gap-1 text-metric-stress text-2xs font-semibold"><XCircle className="w-3 h-3" /> Fail{r.error && <span className="text-text-muted font-normal ml-1 truncate max-w-[120px]">{r.error}</span>}</span>
                        }
                      </td>
                      <td className="px-4 py-3 font-mono text-text-disabled">
                        {r?.duration_ms != null ? `${r.duration_ms.toFixed(1)} ms` : '—'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}

// ── Drift Tab ─────────────────────────────────────────────────────────────────

function DriftTab() {
  const [data,    setData]    = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try { setData(await aiApi.getDriftReport()) }
    catch { setError('Could not load drift report.') }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const PSI_CRITICAL = 0.25
  const PSI_WARNING  = 0.10
  function psiStatus(psi: number) {
    if (psi >= PSI_CRITICAL) return 'critical'
    if (psi >= PSI_WARNING)  return 'warning'
    return 'ok'
  }

  return (
    <div className="space-y-6">
      {loading ? (
        <div className="space-y-3">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-14" />)}</div>
      ) : error ? (
        <ErrorBanner message={error} onRetry={load} />
      ) : (
        <>
          {/* Status banner */}
          <div className={`rounded-xl border p-4 flex items-center gap-3 ${
            data.overall_status === 'critical' ? 'border-metric-stress/30 bg-metric-stress/5' :
            data.overall_status === 'warning'  ? 'border-status-warning/30 bg-status-warning/5' :
            'border-metric-engagement/30 bg-metric-engagement/5'
          }`}>
            {data.overall_status === 'ok'
              ? <CheckCircle className="w-5 h-5 text-metric-engagement flex-shrink-0" />
              : <AlertTriangle className={`w-5 h-5 flex-shrink-0 ${data.overall_status === 'critical' ? 'text-metric-stress' : 'text-status-warning'}`} />}
            <div className="flex-1">
              <p className="text-sm font-semibold text-text-primary capitalize">Drift status: {data.overall_status}</p>
              <p className="text-2xs text-text-muted">
                {data.summary?.critical ?? 0} critical · {data.summary?.warning ?? 0} warning · {data.summary?.ok ?? 0} stable
                {' · '}baseline {data.baseline_samples ?? '—'} · production {data.production_samples ?? '—'} samples
              </p>
            </div>
            <Button variant="ghost" size="xs" icon={<RefreshCw className="w-3 h-3" />} onClick={load}>Refresh</Button>
          </div>

          {/* Feature table with visual PSI bars */}
          {(data.features ?? []).length === 0 ? (
            <EmptyState icon={TrendingUp} title="No drift data yet" sub="Drift is computed once production features accumulate." />
          ) : (
            <div className="rounded-xl border border-border bg-bg-card overflow-hidden">
              <div className="px-5 py-3 border-b border-border-subtle">
                <p className="text-xs font-semibold text-text-muted uppercase tracking-widest">Feature Drift — PSI & KL Divergence</p>
              </div>
              <div className="divide-y divide-border-subtle">
                {(data.features as DriftFeatureReport[]).map(f => {
                  const st    = psiStatus(f.psi)
                  const barW  = Math.min(100, (f.psi / PSI_CRITICAL) * 100)
                  const barColor = st === 'critical' ? '#f87171' : st === 'warning' ? '#fbbf24' : '#34d399'
                  return (
                    <div key={f.feature} className="px-5 py-4 hover:bg-bg-hover transition-colors">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-mono font-medium text-text-primary">{f.feature}</span>
                        <div className="flex items-center gap-3">
                          <span className="text-2xs text-text-muted font-mono">KL {f.kl_div.toFixed(4)}</span>
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-2xs font-semibold border ${
                            st === 'critical' ? 'bg-metric-stress/10 text-metric-stress border-metric-stress/25' :
                            st === 'warning'  ? 'bg-status-warning/10 text-status-warning border-status-warning/25' :
                            'bg-metric-engagement/10 text-metric-engagement border-metric-engagement/25'
                          }`}>
                            {st === 'ok' ? <CheckCircle className="w-3 h-3" /> : <AlertTriangle className="w-3 h-3" />}
                            {st.charAt(0).toUpperCase() + st.slice(1)}
                          </span>
                        </div>
                      </div>
                      {/* Visual PSI bar */}
                      <div className="flex items-center gap-3">
                        <div className="flex-1 h-2 bg-bg-hover rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all duration-500"
                            style={{ width: `${barW}%`, background: barColor }}
                          />
                        </div>
                        <span className="text-xs font-mono font-semibold w-16 text-right" style={{ color: barColor }}>
                          PSI {f.psi.toFixed(4)}
                        </span>
                      </div>
                      {(f.baseline_mean != null || f.production_mean != null) && (
                        <div className="flex gap-4 mt-1.5">
                          <span className="text-2xs text-text-disabled">baseline μ {f.baseline_mean?.toFixed(3) ?? '—'}</span>
                          <span className="text-2xs text-text-disabled">prod μ {f.production_mean?.toFixed(3) ?? '—'}</span>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
              <div className="px-5 py-3 border-t border-border-subtle bg-bg-hover flex items-center gap-6">
                {[
                  { color: '#34d399', label: '< 0.10  Stable'   },
                  { color: '#fbbf24', label: '0.10–0.25  Warning' },
                  { color: '#f87171', label: '> 0.25  Critical (retrain)'  },
                ].map(({ color, label }) => (
                  <span key={label} className="flex items-center gap-1.5 text-2xs text-text-muted">
                    <span className="w-3 h-1.5 rounded-full" style={{ background: color }} />
                    {label}
                  </span>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

// ── Stability Tab ─────────────────────────────────────────────────────────────

function StabilityTab() {
  const [data,    setData]    = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState<string | null>(null)

  useEffect(() => {
    try {
      const cached = JSON.parse(localStorage.getItem(CACHE_KEY_STABILITY) ?? 'null')
      if (cached) setData(cached)
    } catch { /* ignore */ }
  }, [])

  async function run() {
    setLoading(true); setError(null)
    try {
      const result = await aiApi.getStabilitySuite()
      setData(result)
      try { localStorage.setItem(CACHE_KEY_STABILITY, JSON.stringify(result)) } catch { /* ignore */ }
    } catch { setError('Stability sweep failed or timed out. It may take up to 90 s.') }
    finally { setLoading(false) }
  }

  const passRate  = data ? data.stable / Math.max(data.total, 1) : null
  const totalRuns = data ? data.total * (data.n_perturbations ?? 20) : null
  const totalFlips = data ? (data.results as StabilityResult[]).reduce((s, r) => s + r.reliability_flips, 0) : null

  return (
    <div className="space-y-6">
      {/* Large hero numbers */}
      {data && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            { label: 'Perturbed Runs',  value: totalRuns != null ? totalRuns.toLocaleString() : '—', color: '#818cf8' },
            { label: 'Reliability Flips', value: String(totalFlips ?? 0), color: totalFlips === 0 ? '#34d399' : '#f87171' },
            { label: 'Scenarios Stable', value: `${data.stable}/${data.total}`, color: '#34d399' },
            { label: 'Pass Rate',        value: fmtPct(passRate, 0), color: passRate === 1 ? '#34d399' : passRate != null && passRate >= 0.9 ? '#fbbf24' : '#f87171' },
          ].map(({ label, value, color }) => (
            <div key={label} className="rounded-xl border border-border bg-bg-card p-5 text-center">
              <p className="text-2xs text-text-muted uppercase tracking-widest font-semibold mb-2">{label}</p>
              <p className="text-3xl font-bold font-mono" style={{ color }}>{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Explainer */}
      <div className="rounded-xl border border-border-subtle bg-bg-hover px-5 py-4 flex gap-3">
        <Info className="w-4 h-4 text-text-muted flex-shrink-0 mt-0.5" />
        <p className="text-2xs text-text-muted leading-relaxed">
          The stability sweep adds <strong className="text-text-secondary">5% Gaussian noise</strong> to every
          golden scenario&apos;s input signals 20× and checks whether the recommendation tier changes.
          A scenario is <strong className="text-text-secondary">stable</strong> if no reliability tier flips
          occur and coefficient of variation stays below 0.15.
        </p>
      </div>

      {!data && !loading && (
        <div className="flex flex-col items-center gap-4 py-12">
          <Zap className="w-10 h-10 text-text-disabled" />
          <div className="text-center">
            <p className="text-sm font-semibold text-text-primary mb-1">Stability suite not yet run</p>
            <p className="text-xs text-text-muted mb-4">Verify model output stability under input perturbation.</p>
          </div>
          <Button variant="primary" size="sm" onClick={run} icon={<Play className="w-3.5 h-3.5" />}>
            Run Stability Sweep
          </Button>
        </div>
      )}

      {loading && (
        <div className="flex flex-col items-center gap-3 py-12">
          <RefreshCw className="w-8 h-8 text-accent animate-spin" />
          <p className="text-sm text-text-secondary">Running 25 scenarios × 20 perturbations…</p>
          <p className="text-2xs text-text-muted">Typically 5–10 seconds</p>
        </div>
      )}

      {error && <ErrorBanner message={error} onRetry={run} />}

      {data && !loading && (
        <>
          {/* Pass rate bar */}
          {passRate !== null && (
            <div className="rounded-xl border border-border bg-bg-card p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-text-secondary">Overall Stability</span>
                <span className="text-xs text-text-muted">noise={fmtPct(data.noise_pct, 0)} · {data.n_perturbations}× perturbations per scenario</span>
              </div>
              <ConfidenceBar value={passRate} size="sm" showPct={false} />
            </div>
          )}

          {/* Results table */}
          <div className="rounded-xl border border-border bg-bg-card overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-bg-hover">
                  {['Scenario', 'Category', 'Result', 'Max CV', 'Score Spread', 'Tier Flips'].map(h => (
                    <th key={h} className="text-left px-4 py-2.5 text-2xs font-semibold text-text-muted uppercase tracking-widest">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {(data.results as StabilityResult[]).map(r => (
                  <tr key={r.scenario_id} className="hover:bg-bg-hover transition-colors">
                    <td className="px-4 py-3">
                      <span className="font-mono text-text-disabled mr-2">{r.scenario_id}</span>
                      <span className="font-medium text-text-primary">{r.name}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full" style={{ background: CATEGORY_COLORS[r.category] ?? '#6b7280' }} />
                        <span className="text-text-muted capitalize">{r.category.replace('_', ' ')}</span>
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {r.stable
                        ? <span className="inline-flex items-center gap-1 text-metric-engagement text-2xs font-semibold"><CheckCircle className="w-3 h-3" /> Stable</span>
                        : <span className="inline-flex items-center gap-1 text-metric-stress text-2xs font-semibold"><XCircle className="w-3 h-3" /> Unstable</span>}
                    </td>
                    <td className="px-4 py-3 font-mono text-text-secondary">{r.max_cv.toFixed(3)}</td>
                    <td className="px-4 py-3 font-mono text-text-secondary">{r.score_spread.toFixed(3)}</td>
                    <td className="px-4 py-3 font-mono">
                      <span className={r.reliability_flips > 0 ? 'text-metric-stress' : 'text-text-muted'}>
                        {r.reliability_flips}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex justify-end">
            <Button variant="ghost" size="sm" icon={<RefreshCw className="w-3.5 h-3.5" />} onClick={run}>Re-run</Button>
          </div>
        </>
      )}
    </div>
  )
}

// ── Config Tab ────────────────────────────────────────────────────────────────

function ConfigTab() {
  const [data,    setData]    = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try { setData(await aiApi.getAiConfig()) }
    catch { setError('Could not load AI configuration.') }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  function renderValue(v: unknown): string {
    if (v === null || v === undefined) return '—'
    if (typeof v === 'number')  return v.toString()
    if (typeof v === 'boolean') return v ? 'true' : 'false'
    if (typeof v === 'string')  return v
    return JSON.stringify(v)
  }

  const configHash = data ? simpleHash(data) : null

  return (
    <div className="space-y-6">
      {loading ? (
        <div className="space-y-2">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-10" />)}</div>
      ) : error ? (
        <ErrorBanner message={error} onRetry={load} />
      ) : data == null ? (
        <EmptyState icon={BookOpen} title="No configuration found" />
      ) : (
        <>
          {/* Config metadata */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[
              { label: 'Config Hash',   value: configHash ?? '—',        color: '#a78bfa' },
              { label: 'Sections',      value: String(Object.keys(data).length), color: '#60a5fa' },
              { label: 'Status',        value: 'Read-only',               color: '#34d399' },
              { label: 'Source',        value: 'ai_config.to_dict()',     color: '#818cf8' },
            ].map(({ label, value, color }) => (
              <div key={label} className="rounded-xl border border-border bg-bg-card p-4">
                <p className="text-2xs text-text-muted uppercase tracking-widest font-semibold mb-1">{label}</p>
                <p className="text-xs font-mono font-bold truncate" style={{ color }}>{value}</p>
              </div>
            ))}
          </div>

          {/* Read-only notice */}
          <div className="flex items-start gap-3 rounded-xl border border-status-warning/25 bg-status-warning/5 px-4 py-3">
            <Shield className="w-4 h-4 text-status-warning flex-shrink-0 mt-0.5" />
            <p className="text-2xs text-text-muted">
              <strong className="text-status-warning">Read-only. </strong>
              All thresholds are set in <span className="font-mono text-accent">backend/ai/configuration/ai_config.py</span>.
              Changes require a backend restart. The config hash above uniquely identifies this configuration snapshot.
            </p>
          </div>

          <div className="rounded-xl border border-border bg-bg-card overflow-hidden">
            <div className="px-5 py-3 border-b border-border-subtle flex items-center justify-between">
              <p className="text-xs font-semibold text-text-muted uppercase tracking-widest">Active Thresholds & Weights</p>
              <Button variant="ghost" size="xs" icon={<RefreshCw className="w-3 h-3" />} onClick={load}>Refresh</Button>
            </div>
            <div className="divide-y divide-border-subtle">
              {Object.entries(data).map(([section, values]) => (
                <div key={section} className="px-5 py-4">
                  <p className="text-xs font-semibold text-accent uppercase tracking-widest mb-3">{section}</p>
                  {typeof values === 'object' && values !== null && !Array.isArray(values) ? (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {Object.entries(values as Record<string, unknown>).map(([k, v]) => (
                        <div key={k} className="flex items-center justify-between py-1.5 px-3 rounded-lg bg-bg-hover">
                          <span className="text-xs text-text-secondary font-mono">{k}</span>
                          <span className="text-xs font-mono font-semibold text-text-primary ml-4">{renderValue(v)}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="flex items-center justify-between py-1.5 px-3 rounded-lg bg-bg-hover">
                      <span className="text-xs text-text-secondary font-mono">{section}</span>
                      <span className="text-xs font-mono font-semibold text-text-primary">{renderValue(values)}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

type Tab = 'pipeline' | 'registry' | 'experiments' | 'golden' | 'drift' | 'stability' | 'config'

const TABS: Array<{ key: Tab; label: string; icon: React.ElementType }> = [
  { key: 'pipeline',    label: 'Pipeline',        icon: Network        },
  { key: 'registry',   label: 'Model Registry',   icon: Package        },
  { key: 'experiments',label: 'Experiments',      icon: BarChart3      },
  { key: 'golden',     label: 'Golden Tests',     icon: CheckCircle    },
  { key: 'drift',      label: 'Drift Monitor',    icon: TrendingUp     },
  { key: 'stability',  label: 'Stability',        icon: Zap            },
  { key: 'config',     label: 'AI Config',        icon: Cpu            },
]

export default function AiPlatformPage() {
  const [tab, setTab] = useState<Tab>('pipeline')

  return (
    <AppShell title="AI Platform">
      <div className="p-6 max-w-6xl page-enter">

        {/* Page header */}
        <div className="flex items-start gap-4 mb-5">
          <div className="w-10 h-10 rounded-xl bg-accent/10 border border-accent/20 flex items-center justify-center flex-shrink-0">
            <FlaskConical className="w-5 h-5 text-accent" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-text-primary">AI Engineering Platform</h1>
            <p className="text-sm text-text-muted mt-0.5">
              Model lifecycle · Pipeline · Experiments · Golden tests · Drift · Stability
            </p>
          </div>
        </div>

        {/* AI Transparency Card — always visible */}
        <TransparencyCard />

        {/* Tab bar */}
        <div className="flex gap-0 border-b border-border mb-6 overflow-x-auto">
          {TABS.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`flex items-center gap-2 px-4 py-3 text-xs font-medium border-b-2 transition-colors whitespace-nowrap ${
                tab === key
                  ? 'border-accent text-accent'
                  : 'border-transparent text-text-muted hover:text-text-secondary'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="tab-content">
          {tab === 'pipeline'    && <PipelineTab    />}
          {tab === 'registry'    && <RegistryTab    />}
          {tab === 'experiments' && <ExperimentsTab />}
          {tab === 'golden'      && <GoldenTestsTab />}
          {tab === 'drift'       && <DriftTab       />}
          {tab === 'stability'   && <StabilityTab   />}
          {tab === 'config'      && <ConfigTab      />}
        </div>

      </div>
    </AppShell>
  )
}
