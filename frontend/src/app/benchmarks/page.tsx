'use client'
import { useState, useEffect, useCallback } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { Button } from '@/components/ui/Button'
import { ConfidenceBar } from '@/components/ui/ConfidenceBar'
import {
  Cpu, Activity, Zap, Database, RefreshCw, Wifi,
  BrainCircuit, Mic, Eye, Layers,
} from 'lucide-react'
import { api } from '@/lib/api'
import type { BenchmarkData, InferenceStats } from '@/lib/api'
import { Skeleton } from '@/components/ui/Skeleton'

// ── Gauge component ───────────────────────────────────────────────────────────

function SystemGauge({
  label, pct, value, sub, color, icon: Icon,
}: {
  label: string; pct: number | null; value: string; sub?: string; color: string; icon: React.ElementType
}) {
  const p = pct ?? 0
  return (
    <div className="rounded-xl border border-border bg-bg-card p-5 card-hover">
      <div className="flex items-center gap-2 mb-4">
        <Icon className="w-4 h-4 text-text-muted" />
        <span className="text-xs font-semibold text-text-muted uppercase tracking-widest">{label}</span>
      </div>
      {/* Arc gauge (SVG) */}
      <div className="flex items-center justify-center mb-4">
        <svg viewBox="0 0 100 60" width="140" height="84" className="overflow-visible">
          {/* Track */}
          <path d="M 10 55 A 40 40 0 0 1 90 55"
            fill="none" stroke="#27272a" strokeWidth="8" strokeLinecap="round" />
          {/* Fill */}
          {p > 0 && (
            <path d="M 10 55 A 40 40 0 0 1 90 55"
              fill="none"
              stroke={color}
              strokeWidth="8"
              strokeLinecap="round"
              strokeDasharray={`${p * 1.257} 999`}
            />
          )}
          <text x="50" y="52" textAnchor="middle" fill="#f4f4f5" fontSize="14"
            fontWeight="700" fontFamily="'JetBrains Mono', monospace">
            {value}
          </text>
        </svg>
      </div>
      {pct !== null && (
        <div className="h-1.5 bg-bg-hover rounded-full overflow-hidden">
          <div className="h-full rounded-full bar-fill" style={{ width: `${p}%`, background: color }} />
        </div>
      )}
      {sub && <p className="text-2xs text-text-muted mt-2 text-center">{sub}</p>}
    </div>
  )
}

// ── Latency row ───────────────────────────────────────────────────────────────

function LatencyRow({
  label, stats, color, icon: Icon, note,
}: {
  label: string; stats: InferenceStats | undefined; color: string; icon: React.ElementType; note: string
}) {
  const fmt = (v: number | null) => v != null ? `${Math.round(v)}ms` : '—'
  const hasData = stats?.n && stats.n > 0

  return (
    <div className="flex items-center gap-4 py-3 border-b border-border-subtle last:border-0">
      <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
        style={{ background: `${color}18` }}>
        <Icon className="w-3.5 h-3.5" style={{ color }} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-xs font-medium text-text-primary">{label}</span>
          <span className="text-2xs text-text-muted">{note}</span>
          {hasData && (
            <span className="ml-auto text-2xs text-text-disabled font-mono">{stats!.n} samples</span>
          )}
        </div>
        {hasData ? (
          <div className="flex items-center gap-4 text-xs font-mono">
            <span className="text-text-secondary">
              <span className="text-text-muted mr-1">p50</span>
              <span className="font-bold" style={{ color }}>{fmt(stats!.p50)}</span>
            </span>
            <span className="text-text-secondary">
              <span className="text-text-muted mr-1">p95</span>
              {fmt(stats!.p95)}
            </span>
            <span className="text-text-secondary">
              <span className="text-text-muted mr-1">p99</span>
              {fmt(stats!.p99)}
            </span>
          </div>
        ) : (
          <p className="text-2xs text-text-disabled italic">No samples yet. Run a live session to record latency.</p>
        )}
      </div>
    </div>
  )
}

// ── F1 table row ──────────────────────────────────────────────────────────────

function F1Row({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="flex items-center gap-3 py-2">
      <span className="text-xs text-text-muted w-32 flex-shrink-0">{label}</span>
      <div className="flex-1">
        <ConfidenceBar value={value} size="sm" />
      </div>
      <span className="text-xs font-mono font-bold w-10 text-right" style={{ color }}>
        {Math.round(value * 1000) / 10}%
      </span>
    </div>
  )
}

// ── Stat card ─────────────────────────────────────────────────────────────────

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg bg-bg-hover border border-border-subtle p-3">
      <p className="text-2xs text-text-muted uppercase tracking-widest mb-1">{label}</p>
      <p className="text-sm font-bold font-mono text-text-primary">{value}</p>
      {sub && <p className="text-2xs text-text-muted mt-0.5">{sub}</p>}
    </div>
  )
}


// ── Page ──────────────────────────────────────────────────────────────────────

export default function BenchmarksPage() {
  const [data,      setData]      = useState<BenchmarkData | null>(null)
  const [loading,   setLoading]   = useState(true)
  const [error,     setError]     = useState<string | null>(null)
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null)

  const load = useCallback(async () => {
    setError(null)
    try {
      const res = await api.getBenchmarks()
      setData(res)
      setUpdatedAt(new Date())
    } catch {
      setError('Backend unreachable. Showing last known data.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const id = setInterval(load, 8_000)
    return () => clearInterval(id)
  }, [load])

  const sys = data?.system
  const inf = data?.inference ?? {}
  const ws  = data?.websocket
  const mdl = data?.models
  const ses = data?.sessions

  return (
    <AppShell
      title="System Benchmarks"
      actions={
        <div className="flex items-center gap-3">
          {updatedAt && (
            <span className="text-2xs text-text-muted hidden sm:block">
              Updated {updatedAt.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}
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

        {/* ── Live System Metrics ── */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <Activity className="w-4 h-4 text-accent" />
            <h2 className="text-sm font-semibold text-text-primary">Live System Metrics</h2>
            <span className="ml-auto flex items-center gap-1.5 text-2xs text-status-success">
              <span className="w-1.5 h-1.5 rounded-full bg-status-success animate-pulse" />
              Live · 8s refresh
            </span>
          </div>
          {loading ? (
            <div className="grid sm:grid-cols-3 gap-4">
              {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-48" />)}
            </div>
          ) : (
            <div className="grid sm:grid-cols-3 gap-4">
              <SystemGauge
                label="CPU Utilization"
                icon={Cpu}
                color="#818cf8"
                pct={sys?.cpu_pct ?? null}
                value={sys?.cpu_pct != null ? `${Math.round(sys.cpu_pct)}%` : '—'}
                sub={`${sys?.ram?.used_mb != null ? Math.round(sys.ram.used_mb / 1024 * 10) / 10 : '—'} / ${sys?.ram?.total_mb != null ? Math.round(sys.ram.total_mb / 1024 * 10) / 10 : '—'} GB RAM`}
              />
              <SystemGauge
                label="RAM Usage"
                icon={Database}
                color="#60a5fa"
                pct={sys?.ram?.pct ?? null}
                value={sys?.ram?.pct != null ? `${Math.round(sys.ram.pct)}%` : '—'}
                sub={`${sys?.ram?.free_mb != null ? Math.round(sys.ram.free_mb / 1024 * 10) / 10 : '—'} GB free`}
              />
              {sys?.gpu?.available ? (
                <SystemGauge
                  label="GPU / VRAM"
                  icon={Zap}
                  color="#34d399"
                  pct={sys.gpu.vram_used_mb != null && sys.gpu.vram_total_mb
                    ? Math.round(sys.gpu.vram_used_mb / sys.gpu.vram_total_mb * 100) : null}
                  value={sys.gpu.vram_used_mb != null ? `${sys.gpu.vram_used_mb}MB` : '—'}
                  sub={sys.gpu.name ?? 'GPU'}
                />
              ) : (
                <SystemGauge
                  label="GPU / VRAM"
                  icon={Zap}
                  color="#f87171"
                  pct={0}
                  value="CPU"
                  sub="No CUDA GPU detected"
                />
              )}
            </div>
          )}
        </section>

        {/* ── Inference Latency ── */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <Zap className="w-4 h-4 text-accent" />
            <h2 className="text-sm font-semibold text-text-primary">Inference Latency</h2>
            <span className="text-2xs text-text-muted ml-1">P50 / P95 / P99 across live sessions</span>
          </div>
          <div className="rounded-xl border border-border bg-bg-card p-5">
            <LatencyRow label="Face Analysis"     stats={inf.face}   color="#818cf8" icon={Eye}           note="MediaPipe Face Mesh · 468 landmarks" />
            <LatencyRow label="Voice Analysis"    stats={inf.audio}  color="#34d399" icon={Mic}           note={`Whisper ${mdl?.whisper.version ?? 'base'} · CPU inference`} />
            <LatencyRow label="Language (NLP)"    stats={inf.nlp}    color="#60a5fa" icon={BrainCircuit}  note="DeBERTa v3 + LoRA · 4-task classifier" />
            <LatencyRow label="Behavioural Fusion" stats={inf.fusion} color="#fbbf24" icon={Layers}       note="MLP meta-learner · 3s sliding window" />
          </div>
          <p className="text-2xs text-text-muted mt-2 px-1">
            Latencies are recorded per inference call during live sessions and computed as a rolling window of the last 300 samples. Run one or more live sessions to populate this data.
          </p>
        </section>

        {/* ── Model Performance ── */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <BrainCircuit className="w-4 h-4 text-accent" />
            <h2 className="text-sm font-semibold text-text-primary">Model Performance (Test Set)</h2>
          </div>
          <div className="grid lg:grid-cols-2 gap-6">

            {/* DeBERTa card */}
            <div className="rounded-xl border border-border bg-bg-card p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <p className="text-xs font-semibold text-text-primary">MBA Engine · DeBERTa v3-base</p>
                  <p className="text-2xs text-text-muted mt-0.5">
                    {mdl?.deberta.adaptation ?? 'LoRA r=16, α=32'} · Checkpoint {mdl?.deberta.checkpoint ?? 'step_18000'}
                  </p>
                </div>
                <span className={`text-2xs px-2 py-1 rounded-full font-semibold ${
                  mdl?.deberta.available
                    ? 'bg-status-success/10 text-status-success border border-status-success/25'
                    : 'bg-bg-hover text-text-muted border border-border'
                }`}>
                  {mdl?.deberta.available ? '● Online' : '○ Not loaded'}
                </span>
              </div>
              <div className="space-y-1 mb-5">
                <F1Row label="Macro-F1 (avg)"   value={mdl?.deberta.f1.macro        ?? 0.824} color="#818cf8" />
                <F1Row label="Confidence class" value={mdl?.deberta.f1.confidence    ?? 0.862} color="#818cf8" />
                <F1Row label="Stress detection" value={mdl?.deberta.f1.stress        ?? 0.848} color="#f87171" />
                <F1Row label="Hesitation class" value={mdl?.deberta.f1.hesitation    ?? 0.817} color="#fbbf24" />
                <F1Row label="Communication"    value={mdl?.deberta.f1.communication ?? 0.769} color="#60a5fa" />
              </div>
              <div className="grid grid-cols-3 gap-2">
                <StatCard label="Total params"     value={`${Math.round((mdl?.deberta.params_total ?? 184_000_000) / 1e6)}M`} />
                <StatCard label="Trainable params" value={`${Math.round((mdl?.deberta.params_trainable ?? 442_000) / 1e3)}K`} sub="(0.24%)" />
                <StatCard label="Training samples" value={`${Math.round((mdl?.deberta.training_samples ?? 74_288) / 1e3)}K`} />
              </div>
            </div>

            {/* Other models */}
            <div className="space-y-4">
              {/* Whisper */}
              <div className="rounded-xl border border-border bg-bg-card p-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Mic className="w-4 h-4 text-accent" />
                    <p className="text-xs font-semibold text-text-primary">Whisper {mdl?.whisper.version ?? 'base'}</p>
                  </div>
                  <span className="text-2xs text-status-success bg-status-success/10 border border-status-success/25 px-2 py-0.5 rounded-full font-semibold">
                    ● {mdl?.whisper.available ? 'Available' : 'Missing'}
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <StatCard label="Parameters" value={`${Math.round((mdl?.whisper.params ?? 74_000_000) / 1e6)}M`} />
                  <StatCard label="WER (en)"   value={`${Math.round((mdl?.whisper.wer_english ?? 0.148) * 1000) / 10}%`} sub="~85% accuracy" />
                  <StatCard label="Languages"  value={String(mdl?.whisper.languages ?? 99)} />
                </div>
              </div>

              {/* MediaPipe */}
              <div className="rounded-xl border border-border bg-bg-card p-4">
                <div className="flex items-center gap-2 mb-3">
                  <Eye className="w-4 h-4 text-accent" />
                  <p className="text-xs font-semibold text-text-primary">MediaPipe Face Mesh</p>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <StatCard label="Landmarks"   value={String(mdl?.mediapipe.landmarks ?? 468)} />
                  <StatCard label="Target FPS"  value={`${mdl?.mediapipe.fps_target ?? 30} fps`} />
                  <StatCard label="Min conf."   value={`${Math.round((mdl?.mediapipe.detection_confidence ?? 0.7) * 100)}%`} />
                </div>
              </div>

              {/* Fusion */}
              <div className="rounded-xl border border-border bg-bg-card p-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Layers className="w-4 h-4 text-metric-consistency" />
                    <p className="text-xs font-semibold text-text-primary">Behavioural Fusion</p>
                  </div>
                  <span className={`text-2xs px-2 py-0.5 rounded-full font-semibold border ${
                    mdl?.fusion.available
                      ? 'bg-status-success/10 text-status-success border-status-success/25'
                      : 'bg-bg-hover text-text-muted border-border'
                  }`}>
                    {mdl?.fusion.available ? '● MLP loaded' : '○ Weighted fallback'}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <StatCard label="Architecture"  value={mdl?.fusion.architecture ?? 'MLP meta-learner'} />
                  <StatCard label="Window size"   value={`${mdl?.fusion.window_s ?? 3.0}s`} sub="sliding" />
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ── WebSocket + Session Stats ── */}
        <section className="grid sm:grid-cols-2 gap-6">
          {/* WebSocket */}
          <div className="rounded-xl border border-border bg-bg-card p-5">
            <div className="flex items-center gap-2 mb-4">
              <Wifi className="w-4 h-4 text-accent" />
              <h2 className="text-xs font-semibold text-text-muted uppercase tracking-widest">WebSocket Throughput</h2>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <StatCard label="Active connections" value={String(ws?.active_connections ?? 0)} />
              <StatCard label="Msg/s (lifetime)"  value={`${ws?.messages_per_sec?.toFixed(2) ?? '0.00'}`} />
              <StatCard label="Analytics interval" value={`${ws?.analytics_push_interval_ms ?? 500}ms`} sub="2/sec" />
              <StatCard label="Frame rate target"  value={`${ws?.target_frame_rate_fps ?? 5} fps`} sub="200ms capture" />
              <StatCard label="Total messages"     value={(ws?.total_messages ?? 0).toLocaleString()} />
              <StatCard label="Total frames"       value={(ws?.total_frames   ?? 0).toLocaleString()} />
            </div>
            <p className="text-2xs text-text-muted mt-3">
              Uptime {ws?.uptime_seconds != null ? `${Math.floor(ws.uptime_seconds / 60)}m ${ws.uptime_seconds % 60}s` : '—'}
            </p>
          </div>

          {/* Session stats */}
          <div className="rounded-xl border border-border bg-bg-card p-5">
            <div className="flex items-center gap-2 mb-4">
              <Database className="w-4 h-4 text-accent" />
              <h2 className="text-xs font-semibold text-text-muted uppercase tracking-widest">Session Statistics</h2>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <StatCard label="Total sessions"   value={String(ses?.total ?? 0)} />
              <StatCard label="Avg. duration"    value={ses?.avg_duration_s ? `${Math.round(ses.avg_duration_s / 60)}m` : '—'} />
              <StatCard label="Avg. confidence"  value={ses?.avg_confidence ? `${Math.round(ses.avg_confidence * 100)}%` : '—'} />
              <StatCard label="Avg. stress"      value={ses?.avg_stress ? `${Math.round(ses.avg_stress * 100)}%` : '—'} />
            </div>
          </div>
        </section>

      </div>
    </AppShell>
  )
}
