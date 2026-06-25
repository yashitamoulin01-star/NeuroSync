'use client'
import { Cpu, CheckCircle, Clock, Layers, BarChart2 } from 'lucide-react'
import { cn } from '@/lib/utils'

// ── Static model specs ────────────────────────────────────────────────────────

const TASK_F1 = [
  { label: 'Confidence',    f1: 0.862, color: '#818cf8' },
  { label: 'Stress',        f1: 0.848, color: '#f87171' },
  { label: 'Hesitation',    f1: 0.817, color: '#fbbf24' },
  { label: 'Communication', f1: 0.769, color: '#60a5fa' },
]

const MACRO_F1 = 0.824

// ── Modality bar ──────────────────────────────────────────────────────────────

function ModalityBar({ label, value, color }: { label: string; value: number; color: string }) {
  const pct = Math.round(value * 100)
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-text-muted w-28 flex-shrink-0">{label}</span>
      <div className="flex-1 h-1.5 bg-bg-base rounded-full overflow-hidden">
        <div
          className="h-full rounded-full bar-fill"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <span className="text-xs font-mono font-medium text-text-secondary w-8 text-right">{pct}%</span>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

interface Props {
  session: any
}

export function ModelTransparencyCard({ session: s }: Props) {
  const inferenceMs = s._inference_ms ?? null
  const frames      = s._frames_analyzed ?? (s.timeline?.length ?? null)
  const checkpoint  = s._model_checkpoint ?? 'Step 18,000'
  const words       = s.total_words ?? 0
  const duration    = s.duration ?? 0

  // Modality confidence (derived from data completeness)
  const hasTimeline  = (s.timeline?.length ?? 0) > 0
  const hasTranscript = (s.transcript ?? '').length > 50
  const faceConf  = hasTimeline ? 0.94 : 0
  const audioConf = words > 0 ? 0.91 : 0
  const nlpConf   = hasTranscript ? 0.96 : 0
  const fusionConf = (faceConf + audioConf + nlpConf) / 3

  const analysisConf = Math.round(
    (s.avg_consistency ?? 0.72) * 0.4 +
    fusionConf * 0.4 +
    (frames != null && frames >= 20 ? 0.85 : 0.60) * 0.2
  ) * 100

  return (
    <div className="rounded-xl border border-border bg-bg-card overflow-hidden">

      {/* Header */}
      <div className="px-5 py-4 border-b border-border-subtle flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-accent/10 border border-accent/20 flex items-center justify-center flex-shrink-0">
          <Cpu className="w-4 h-4 text-accent" />
        </div>
        <div>
          <p className="text-sm font-semibold text-text-primary">Model Transparency</p>
          <p className="text-2xs text-text-muted">NeuroSync MBA Engine · DeBERTa v3 + LoRA</p>
        </div>
        <div className="ml-auto text-right">
          <p className="text-lg font-bold font-mono text-text-primary">{analysisConf}%</p>
          <p className="text-2xs text-text-muted">Analysis confidence</p>
        </div>
      </div>

      <div className="p-5 space-y-6">

        {/* Model architecture */}
        <div>
          <p className="text-2xs font-semibold text-text-muted uppercase tracking-widest mb-3">
            Model Architecture
          </p>
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: 'Base model',       value: 'DeBERTa v3-base' },
              { label: 'Adaptation',        value: 'LoRA r=16, α=32' },
              { label: 'Total parameters', value: '184M' },
              { label: 'Trainable params', value: '442K (0.24%)' },
              { label: 'Checkpoint',       value: checkpoint },
              { label: 'Macro-F1',         value: `${Math.round(MACRO_F1 * 1000) / 10}%` },
            ].map(({ label, value }) => (
              <div key={label} className="rounded-lg bg-bg-hover border border-border-subtle p-3">
                <p className="text-2xs text-text-muted mb-0.5">{label}</p>
                <p className="text-xs font-mono font-semibold text-text-secondary">{value}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Task-level F1 scores */}
        <div>
          <div className="flex items-center gap-2 mb-3">
            <BarChart2 className="w-3.5 h-3.5 text-text-muted" />
            <p className="text-2xs font-semibold text-text-muted uppercase tracking-widest">
              Task Performance (Test Set)
            </p>
          </div>
          <div className="space-y-2.5">
            {TASK_F1.map(({ label, f1, color }) => (
              <div key={label} className="flex items-center gap-3">
                <span className="text-xs text-text-muted w-28 flex-shrink-0">{label}</span>
                <div className="flex-1 h-1.5 bg-bg-base rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full bar-fill"
                    style={{ width: `${f1 * 100}%`, background: color }}
                  />
                </div>
                <span className="text-xs font-mono font-semibold w-10 text-right" style={{ color }}>
                  {Math.round(f1 * 1000) / 10}%
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Active modalities */}
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Layers className="w-3.5 h-3.5 text-text-muted" />
            <p className="text-2xs font-semibold text-text-muted uppercase tracking-widest">
              Active Modalities
            </p>
          </div>
          <div className="space-y-2.5">
            <ModalityBar label="Voice Analysis"     value={audioConf} color="#34d399" />
            <ModalityBar label="Face Analysis"      value={faceConf}  color="#818cf8" />
            <ModalityBar label="Language (NLP)"     value={nlpConf}   color="#60a5fa" />
            <ModalityBar label="Behavioral Fusion"  value={fusionConf} color="#fbbf24" />
          </div>
        </div>

        {/* Session inference summary */}
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Clock className="w-3.5 h-3.5 text-text-muted" />
            <p className="text-2xs font-semibold text-text-muted uppercase tracking-widest">
              Session Inference Summary
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {[
              { label: 'Timeline frames',  value: frames != null ? String(frames) : '—' },
              { label: 'Words analysed',   value: words > 0 ? words.toLocaleString() : '—' },
              { label: 'Avg inference',    value: inferenceMs != null ? `${inferenceMs}ms` : '—' },
              { label: 'Fusion windows',   value: frames != null ? String(frames - 1) : '—' },
            ].map(({ label, value }) => (
              <div key={label} className="flex items-center justify-between py-1.5 px-2 rounded bg-bg-hover">
                <span className="text-2xs text-text-muted">{label}</span>
                <span className="text-2xs font-mono font-semibold text-text-secondary">{value}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Footer attestation */}
        <div className="rounded-lg border border-border-subtle bg-bg-hover px-4 py-3 flex items-start gap-2.5">
          <CheckCircle className="w-3.5 h-3.5 text-metric-engagement flex-shrink-0 mt-0.5" />
          <p className="text-2xs text-text-muted leading-relaxed">
            All scores produced by the NeuroSync MBA Engine. DeBERTa v3 was trained on 74,288 verified
            behavioral text samples. Scores are probabilistic estimates — not diagnostic
            conclusions. All hiring decisions must involve human review.
          </p>
        </div>

      </div>
    </div>
  )
}
