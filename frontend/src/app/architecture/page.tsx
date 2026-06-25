'use client'
import { useState, type ElementType } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { cn } from '@/lib/utils'
import {
  Brain, Database, Layers, Radio,
  Shield, Zap, Eye, Mic, FileText, BarChart3, GitMerge,
  CheckCircle, AlertCircle, ArrowRight, ChevronDown, ChevronUp,
  Network, Activity, FlaskConical,
} from 'lucide-react'

// ── Types ─────────────────────────────────────────────────────────────────────

interface ComponentDetail {
  id: string
  label: string
  icon: ElementType
  tech: string[]
  desc: string
  latency?: string
  accuracy?: string
  notes?: string
}

// ── Component catalogue ────────────────────────────────────────────────────────

const COMPONENTS: ComponentDetail[] = [
  {
    id: 'face',
    label: 'Face Analysis',
    icon: Eye,
    tech: ['MediaPipe Face Mesh', 'OpenCV'],
    desc: 'Extracts 468 facial landmarks per frame at 5fps. Computes eye contact ratio, blink cadence (blinks/min), head pose (yaw/pitch/roll), and facial tension from AU-adjacent landmark distances.',
    latency: '~12ms per frame',
    accuracy: 'Landmark error <2px at 320×240',
    notes: 'Runs client-side via WASM in future roadmap; currently server-side.',
  },
  {
    id: 'audio',
    label: 'Audio Analysis',
    icon: Mic,
    tech: ['LibROSA', 'SciPy', 'NumPy'],
    desc: 'Processes 500ms PCM chunks. Extracts: RMS energy, pitch (YIN algorithm), speech/silence ratio, speaking rate estimate from syllable energy peaks, and vocal jitter.',
    latency: '~8ms per chunk',
    notes: 'Audio captured via ScriptProcessor (AudioWorklet migration pending).',
  },
  {
    id: 'nlp',
    label: 'Language Analysis',
    icon: FileText,
    tech: ['faster-Whisper (CTranslate2)', 'DeBERTa v3-base', 'LoRA (r=16 α=32)', 'PEFT'],
    desc: 'Whisper transcribes 3-second audio windows. DeBERTa v3 (fine-tuned on 74,288 behavioral text samples) classifies confidence, hesitation, and communication structure. Filler words detected by regex over transcript.',
    latency: '~180ms per window (base model, CPU)',
    accuracy: 'Macro-F1 82.4% across 4 behavioral dimensions',
  },
  {
    id: 'fusion',
    label: 'Behavioral Fusion',
    icon: GitMerge,
    tech: ['3-second sliding window', 'Evidence Graph', 'Weighted averaging'],
    desc: 'Temporal synchronization layer. Collects face, audio, and NLP signals within a 3-second window. Computes cross-modal consistency and produces 5 composite dimensions: Confidence, Engagement, Communication, Consistency, Composure.',
    latency: '~5ms',
    notes: 'Window overlap = 500ms. Updates pushed to client via WebSocket on each new fusion frame.',
  },
  {
    id: 'reasoning',
    label: 'Reasoning Engine',
    icon: Brain,
    tech: ['Evidence Graph', 'Behavioral State Machine', 'Asymptotic Scorer', 'ECE Calibration'],
    desc: 'Nine-stage pipeline: evidence extraction → evidence graph → contradiction detection → asymptotic scoring → temporal arc analysis → state machine transitions → context rules → calibration → decision trace. Every output is reconstructable from its inputs.',
    latency: '~15ms',
    notes: 'Contradiction detection flags cross-modal conflicts (e.g. confident language + physiological stress). State machine tracks: settled, stressed, recovering, degrading, inconsistent.',
  },
  {
    id: 'calibration',
    label: 'Calibration',
    icon: BarChart3,
    tech: ['ECE (Expected Calibration Error)', 'Platt Scaling', 'Temperature Scaling'],
    desc: 'Post-hoc confidence calibration. Model probability outputs are calibrated so that a stated 80% confidence corresponds to approximately 80% empirical accuracy. Produces reliability tiers: insufficient / low / medium / high.',
    notes: 'Calibration is static — computed offline against validation set. Never adjusted at runtime.',
  },
  {
    id: 'abme',
    label: 'ABME',
    icon: Activity,
    tech: ['EMA (α=0.15)', 'SQLite behavioral_memory schema'],
    desc: 'Adaptive Behavioral Memory Engine. Per-candidate EMA-based profiles accumulate across sessions. Tracks baseline confidence, stress reactivity, communication style, and coaching delivery outcomes. Enables session-to-session delta comparison.',
    notes: 'ABME never modifies model weights. It updates candidate knowledge state only.',
  },
  {
    id: 'cbip',
    label: 'CBIP',
    icon: Network,
    tech: ['5-Level Validation Pyramid', 'OLS regression', 'SQLite behavioral_knowledge schema'],
    desc: 'Continual Behavioral Intelligence Platform. Cross-candidate knowledge layer. Accumulates validated behavioral observations, ranked by source reliability (L1 0.20 → L5 1.00). Powers: coaching effectiveness ranking, behavioral archetype tracking, org intelligence, OLS growth forecasting.',
    notes: 'Hard constraint: CBIP never modifies model weights. Production models evolve only through the MLOps pipeline.',
  },
  {
    id: 'db',
    label: 'Database',
    icon: Database,
    tech: ['SQLite (WAL mode)', 'stdlib sqlite3 (no ORM)'],
    desc: 'Four logical schemas: core (sessions, frames, insights), enterprise (audit, rbac, compliance), behavioral_memory (ABME profiles), behavioral_knowledge (CBIP patterns). WAL mode enables concurrent reads during write.',
    notes: 'Designed for single-node deployment. PostgreSQL migration path is modelled via DATABASE_URL config.',
  },
  {
    id: 'enterprise',
    label: 'Enterprise Layer',
    icon: Shield,
    tech: ['JWT auth', 'RBAC (8 roles, 50+ permissions)', 'SHA-256 audit chain', 'GDPR endpoints'],
    desc: 'Multi-tenant platform with per-org signal isolation. Immutable audit log uses SHA-256 chaining — each entry hashes the previous. Compliance endpoints support GDPR right-to-erasure and data retention policies.',
  },
  {
    id: 'aiplatform',
    label: 'AI Platform',
    icon: FlaskConical,
    tech: ['Model Registry', 'Experiment Tracker', 'Drift Detector (PSI/KL)', 'ECE Calibration', 'Replay Engine'],
    desc: 'Internal MLOps tooling. Tracks model versions, experiment results, golden test suite (10 scenarios), regression gates, and input drift. PSI and KL-divergence metrics detect when live inputs deviate from training distribution.',
    notes: 'Production models must pass regression gate before promotion.',
  },
]

// ── Signal flow nodes ─────────────────────────────────────────────────────────

const FLOW_STAGES = [
  {
    label: 'Signal Acquisition',
    sublabel: 'WebSocket',
    icon: Radio,
    color: '#6366f1',
    items: ['Video 5fps (320×240)', 'Audio 500ms PCM chunks', 'Session metadata'],
  },
  {
    label: 'Modality Analysis',
    sublabel: 'Parallel',
    icon: Layers,
    color: '#818cf8',
    items: ['Face: 468 landmarks', 'Audio: LibROSA features', 'Language: Whisper → DeBERTa'],
  },
  {
    label: 'Behavioral Fusion',
    sublabel: '3s window',
    icon: GitMerge,
    color: '#a78bfa',
    items: ['Temporal sync', 'Evidence graph', 'Cross-modal weighting'],
  },
  {
    label: 'Reasoning Pipeline',
    sublabel: '9 stages',
    icon: Brain,
    color: '#c4b5fd',
    items: ['Contradiction detection', 'State machine', 'Calibration'],
  },
  {
    label: 'Output',
    sublabel: '500ms WS push',
    icon: Zap,
    color: '#e0d7ff',
    items: ['5 behavioral dimensions', 'Narrative + evidence', 'Decision support'],
  },
]

const PIPELINE_STAGES = [
  { n: 1, label: 'Evidence Extraction', desc: 'Per-modality feature vectors with quality weights' },
  { n: 2, label: 'Evidence Graph', desc: 'Cross-modal consistency check and inter-signal correlation' },
  { n: 3, label: 'Contradiction Detection', desc: 'Flags when face, voice, and language signals conflict' },
  { n: 4, label: 'Asymptotic Scoring', desc: 'Score approaches limits, never clamps — preserves information' },
  { n: 5, label: 'Arc Analysis', desc: 'Session trajectory: early vs late behavioral state comparison' },
  { n: 6, label: 'State Machine', desc: 'Behavioral state transitions: settled / stressed / recovering / degrading' },
  { n: 7, label: 'Context Rules', desc: 'Mode-specific adjustments (interview vs coaching vs presentation)' },
  { n: 8, label: 'Confidence Calibration', desc: 'ECE-calibrated reliability: insufficient / low / medium / high' },
  { n: 9, label: 'Decision Trace', desc: 'Every conclusion is reconstructable from inputs — full auditability' },
]

const VALIDATION_PYRAMID = [
  { level: 'L5', label: 'Performance outcome', weight: 1.00, color: '#818cf8' },
  { level: 'L4', label: 'Hiring decision',      weight: 0.90, color: '#a78bfa' },
  { level: 'L3', label: 'Recruiter rating',     weight: 0.70, color: '#c4b5fd' },
  { level: 'L2', label: 'Candidate feedback',   weight: 0.45, color: '#ddd6fe' },
  { level: 'L1', label: 'Session observation',  weight: 0.20, color: '#ede9fe' },
]

// ── Component card ─────────────────────────────────────────────────────────────

function ComponentCard({
  comp, selected, onClick,
}: { comp: ComponentDetail; selected: boolean; onClick: () => void }) {
  const Icon = comp.icon
  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full text-left rounded-xl border p-4 transition-all duration-150',
        selected
          ? 'border-accent bg-accent-glow'
          : 'border-border bg-bg-card hover:border-border-active hover:bg-bg-hover',
      )}
    >
      <div className="flex items-center gap-2.5 mb-2">
        <Icon className={cn('w-4 h-4 flex-shrink-0', selected ? 'text-accent' : 'text-text-muted')} />
        <span className={cn('text-sm font-semibold', selected ? 'text-accent' : 'text-text-primary')}>
          {comp.label}
        </span>
      </div>
      <div className="flex flex-wrap gap-1">
        {comp.tech.slice(0, 2).map(t => (
          <span key={t} className="text-2xs font-mono text-text-disabled bg-bg-hover px-1.5 py-0.5 rounded">
            {t}
          </span>
        ))}
        {comp.tech.length > 2 && (
          <span className="text-2xs text-text-disabled">+{comp.tech.length - 2}</span>
        )}
      </div>
    </button>
  )
}

// ── Detail panel ───────────────────────────────────────────────────────────────

function DetailPanel({ comp }: { comp: ComponentDetail }) {
  const Icon = comp.icon
  return (
    <div className="rounded-xl border border-border bg-bg-card p-6 h-full">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-9 h-9 rounded-lg bg-accent-glow border border-accent/20 flex items-center justify-center">
          <Icon className="w-5 h-5 text-accent" />
        </div>
        <div>
          <h3 className="text-base font-bold text-text-primary">{comp.label}</h3>
          {(comp.latency || comp.accuracy) && (
            <p className="text-xs text-text-muted mt-0.5">
              {[comp.latency, comp.accuracy].filter(Boolean).join(' · ')}
            </p>
          )}
        </div>
      </div>

      <p className="text-sm text-text-secondary leading-relaxed mb-5">{comp.desc}</p>

      <div className="mb-4">
        <p className="text-2xs font-semibold uppercase tracking-widest text-text-disabled mb-2">Stack</p>
        <div className="flex flex-wrap gap-1.5">
          {comp.tech.map(t => (
            <span key={t} className="text-xs font-mono text-text-secondary bg-bg-hover border border-border-subtle px-2 py-0.5 rounded-md">
              {t}
            </span>
          ))}
        </div>
      </div>

      {comp.notes && (
        <div className="flex items-start gap-2 mt-4 p-3 rounded-lg bg-bg-hover border border-border-subtle">
          <AlertCircle className="w-3.5 h-3.5 text-text-muted flex-shrink-0 mt-0.5" />
          <p className="text-xs text-text-muted leading-relaxed">{comp.notes}</p>
        </div>
      )}
    </div>
  )
}

// ── Signal flow ───────────────────────────────────────────────────────────────

function SignalFlow() {
  const [expanded, setExpanded] = useState(false)

  return (
    <section>
      <button
        onClick={() => setExpanded(v => !v)}
        className="w-full flex items-center justify-between mb-4"
      >
        <h2 className="text-lg font-bold text-text-primary">Signal Flow</h2>
        {expanded
          ? <ChevronUp className="w-4 h-4 text-text-muted" />
          : <ChevronDown className="w-4 h-4 text-text-muted" />}
      </button>

      <div className="flex items-stretch gap-0 overflow-x-auto pb-2">
        {FLOW_STAGES.map((stage, i) => {
          const Icon = stage.icon
          return (
            <div key={stage.label} className="flex items-center flex-shrink-0">
              <div className="rounded-xl border border-border bg-bg-card p-4 min-w-[160px]">
                <div className="flex items-center gap-2 mb-2">
                  <div
                    className="w-7 h-7 rounded-lg flex items-center justify-center"
                    style={{ backgroundColor: `${stage.color}20`, border: `1px solid ${stage.color}30` }}
                  >
                    <Icon className="w-3.5 h-3.5" style={{ color: stage.color }} />
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-text-primary leading-tight">{stage.label}</p>
                    <p className="text-2xs text-text-disabled">{stage.sublabel}</p>
                  </div>
                </div>
                {expanded && (
                  <ul className="space-y-1 mt-2">
                    {stage.items.map(item => (
                      <li key={item} className="flex items-center gap-1.5 text-2xs text-text-muted">
                        <CheckCircle className="w-2.5 h-2.5 text-text-disabled flex-shrink-0" />
                        {item}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              {i < FLOW_STAGES.length - 1 && (
                <ArrowRight className="w-5 h-5 text-text-disabled mx-2 flex-shrink-0" />
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}

// ── Reasoning pipeline ────────────────────────────────────────────────────────

function ReasoningPipeline() {
  return (
    <section>
      <h2 className="text-lg font-bold text-text-primary mb-4">Reasoning Pipeline</h2>
      <p className="text-sm text-text-muted mb-5 max-w-2xl">
        Every analytical conclusion passes through nine deterministic stages.
        The output of each stage is the input to the next — making every conclusion reconstructable.
      </p>
      <div className="grid gap-2">
        {PIPELINE_STAGES.map(stage => (
          <div
            key={stage.n}
            className="flex items-start gap-4 rounded-xl border border-border bg-bg-card px-4 py-3 hover:border-border-active transition-colors"
          >
            <div className="w-6 h-6 rounded-full bg-accent-glow border border-accent/20 flex items-center justify-center flex-shrink-0 mt-0.5">
              <span className="text-2xs font-mono font-bold text-accent">{stage.n}</span>
            </div>
            <div>
              <p className="text-sm font-semibold text-text-primary">{stage.label}</p>
              <p className="text-xs text-text-muted mt-0.5">{stage.desc}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

// ── Validation pyramid ────────────────────────────────────────────────────────

function ValidationPyramid() {
  return (
    <section>
      <h2 className="text-lg font-bold text-text-primary mb-1">CBIP Validation Pyramid</h2>
      <p className="text-sm text-text-muted mb-5 max-w-2xl">
        Platform knowledge is weighted by source reliability. Automatic observations (L1) carry minimal weight.
        Long-term performance outcomes (L5) are treated as ground truth.
      </p>
      <div className="space-y-2 max-w-lg">
        {VALIDATION_PYRAMID.map((tier, i) => (
          <div key={tier.level} className="flex items-center gap-3">
            <span className="text-xs font-mono font-bold text-text-disabled w-6">{tier.level}</span>
            <div
              className="h-8 rounded-lg flex items-center px-3 transition-all"
              style={{
                backgroundColor: `${tier.color}15`,
                border: `1px solid ${tier.color}30`,
                width: `${(1 - i * 0.15) * 100}%`,
              }}
            >
              <span className="text-xs font-medium text-text-primary flex-1">{tier.label}</span>
              <span className="text-xs font-mono text-text-muted ml-2">{tier.weight.toFixed(2)}</span>
            </div>
          </div>
        ))}
      </div>
      <p className="text-xs text-text-muted mt-4">
        CBIP never modifies model weights. Knowledge accumulates in the Behavioral Knowledge Layer only.
      </p>
    </section>
  )
}

// ── AI Trust block ────────────────────────────────────────────────────────────

const TRUST_SIX = [
  { q: 'What happened?',            a: 'Behavioral arc, per-dimension scores, and signal timeline' },
  { q: 'Why do we believe this?',   a: 'Evidence graph with per-modality source attribution' },
  { q: 'How confident are we?',     a: 'ECE-calibrated tier: insufficient / low / medium / high' },
  { q: 'What evidence supports it?',a: 'Critical, supporting, and contextual evidence ranking' },
  { q: 'What contradicts it?',      a: 'Cross-signal contradiction detection with interpretation' },
  { q: 'What should happen next?',  a: 'Recruiter decision support: strengths, concerns, review triggers' },
]

function TrustBlock() {
  return (
    <section>
      <h2 className="text-lg font-bold text-text-primary mb-1">AI Trust — Six Questions</h2>
      <p className="text-sm text-text-muted mb-5 max-w-2xl">
        Every NeuroSync output must answer six questions. If the system cannot answer all six, the output is marked incomplete.
      </p>
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {TRUST_SIX.map(({ q, a }, i) => (
          <div key={i} className="rounded-xl border border-border bg-bg-card p-4">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-5 h-5 rounded-full bg-accent-glow flex items-center justify-center flex-shrink-0">
                <span className="text-2xs font-bold text-accent">{i + 1}</span>
              </div>
              <p className="text-xs font-semibold text-text-primary">{q}</p>
            </div>
            <p className="text-xs text-text-muted leading-relaxed">{a}</p>
          </div>
        ))}
      </div>
    </section>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ArchitecturePage() {
  const [selected, setSelected] = useState<string>('reasoning')
  const selectedComp = COMPONENTS.find(c => c.id === selected)!

  return (
    <AppShell title="Architecture">
      <div className="p-6 max-w-7xl space-y-12">

        {/* Header */}
        <div className="max-w-2xl">
          <h1 className="text-2xl font-bold text-text-primary tracking-tight mb-2">Inside NeuroSync</h1>
          <p className="text-sm text-text-secondary leading-relaxed">
            Three independent signal streams — face, voice, language — synchronized by a time-windowed
            fusion layer and interpreted by a nine-stage reasoning pipeline. Every output is calibrated,
            evidence-ranked, and reconstructable.
          </p>
        </div>

        {/* Signal flow */}
        <SignalFlow />

        {/* Component explorer */}
        <section>
          <h2 className="text-lg font-bold text-text-primary mb-1">Component Explorer</h2>
          <p className="text-sm text-text-muted mb-5">
            Select a component to see technical details, stack, and design decisions.
          </p>
          <div className="grid lg:grid-cols-3 gap-6">
            <div className="lg:col-span-1 grid grid-cols-1 gap-2">
              {COMPONENTS.map(comp => (
                <ComponentCard
                  key={comp.id}
                  comp={comp}
                  selected={selected === comp.id}
                  onClick={() => setSelected(comp.id)}
                />
              ))}
            </div>
            <div className="lg:col-span-2">
              <DetailPanel comp={selectedComp} />
            </div>
          </div>
        </section>

        {/* Reasoning pipeline */}
        <ReasoningPipeline />

        {/* Validation pyramid */}
        <ValidationPyramid />

        {/* AI Trust */}
        <TrustBlock />

        {/* Constraints block */}
        <section>
          <h2 className="text-lg font-bold text-text-primary mb-4">Production Constraints</h2>
          <div className="grid sm:grid-cols-2 gap-3 max-w-3xl">
            {[
              'Production model weights are never fine-tuned at runtime',
              'Calibration is static — computed offline, never adjusted dynamically',
              'No continuous retraining from user session data',
              'Every model promotion requires passing the 10-scenario regression gate',
              'Behavioral forecasts predict growth only — never hiring outcomes',
              'Every forecast includes ±1.5σ confidence intervals',
            ].map(c => (
              <div key={c} className="flex items-start gap-2.5 rounded-lg border border-border bg-bg-card px-3 py-2.5">
                <CheckCircle className="w-3.5 h-3.5 text-status-success flex-shrink-0 mt-0.5" />
                <span className="text-xs text-text-secondary leading-relaxed">{c}</span>
              </div>
            ))}
          </div>
        </section>

      </div>
    </AppShell>
  )
}
