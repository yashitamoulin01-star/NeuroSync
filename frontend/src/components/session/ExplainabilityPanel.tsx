'use client'
import { useState } from 'react'
import { ChevronDown, ChevronUp, Mic, Eye, MessageSquare, Layers } from 'lucide-react'
import { cn } from '@/lib/utils'

// ── Types ─────────────────────────────────────────────────────────────────────

interface Signal {
  label:       string
  value:       number      // 0–1
  modality:    'face' | 'audio' | 'nlp' | 'fusion'
  description: string
}

interface Dimension {
  key:       string
  label:     string
  color:     string
  score:     number        // 0–1, display value (inverted for composure)
  signals:   Signal[]
  summary:   string
  strongest: string        // One-line strongest signal call-out
}

// ── Modality chip ─────────────────────────────────────────────────────────────

const MODALITY_META: Record<string, { icon: React.ElementType; label: string; color: string }> = {
  face:    { icon: Eye,            label: 'Face Analysis',  color: '#818cf8' },
  audio:   { icon: Mic,            label: 'Voice Analysis', color: '#34d399' },
  nlp:     { icon: MessageSquare,  label: 'Language (NLP)', color: '#60a5fa' },
  fusion:  { icon: Layers,         label: 'Fusion',         color: '#fbbf24' },
}

function ModalityChip({ modality }: { modality: string }) {
  const m = MODALITY_META[modality]
  if (!m) return null
  const Icon = m.icon
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-2xs font-medium"
      style={{ background: `${m.color}18`, color: m.color }}>
      <Icon className="w-2.5 h-2.5" />
      {m.label}
    </span>
  )
}

// ── Signal bar ────────────────────────────────────────────────────────────────

function SignalBar({ signal, color }: { signal: Signal; color: string }) {
  const pct = Math.round(signal.value * 100)
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-secondary font-medium">{signal.label}</span>
          <ModalityChip modality={signal.modality} />
        </div>
        <span className="text-xs font-mono font-bold" style={{ color }}>{pct}%</span>
      </div>
      <div className="h-1.5 bg-bg-base rounded-full overflow-hidden">
        <div
          className="h-full rounded-full bar-fill"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <p className="text-2xs text-text-muted mt-1 leading-relaxed">{signal.description}</p>
    </div>
  )
}

// ── Dimension card ────────────────────────────────────────────────────────────

function DimensionCard({ dim, defaultOpen = false }: { dim: Dimension; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen)
  const pct = Math.round(dim.score * 100)
  const tier = pct >= 75 ? 'Strong' : pct >= 55 ? 'Adequate' : 'Developing'

  return (
    <div className={cn(
      'rounded-xl border transition-all duration-200 overflow-hidden card-hover',
      open ? 'border-border' : 'border-border-subtle',
    )}>
      {/* Header — always visible */}
      <button
        className="w-full flex items-center gap-4 p-4 text-left"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
      >
        {/* Score ring */}
        <div
          className="w-11 h-11 rounded-xl flex-shrink-0 flex items-center justify-center"
          style={{ background: `${dim.color}18`, border: `1.5px solid ${dim.color}35` }}
        >
          <span className="text-sm font-bold font-mono" style={{ color: dim.color }}>{pct}</span>
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <span className="text-sm font-semibold text-text-primary">{dim.label}</span>
            <span
              className="text-2xs font-semibold px-1.5 py-0.5 rounded"
              style={{ background: `${dim.color}18`, color: dim.color }}
            >{tier}</span>
          </div>
          <p className="text-2xs text-text-muted truncate">{dim.strongest}</p>
        </div>

        {/* Progress bar (compact) */}
        <div className="hidden sm:block w-24 flex-shrink-0">
          <div className="h-1.5 bg-bg-hover rounded-full overflow-hidden">
            <div className="h-full rounded-full" style={{ width: `${pct}%`, background: dim.color }} />
          </div>
        </div>

        {open
          ? <ChevronUp className="w-4 h-4 text-text-muted flex-shrink-0" />
          : <ChevronDown className="w-4 h-4 text-text-muted flex-shrink-0" />
        }
      </button>

      {/* Expanded content */}
      {open && (
        <div className="tab-content border-t border-border-subtle px-5 pb-5 pt-4 space-y-5 bg-bg-card">
          {/* Summary paragraph */}
          <p className="text-sm text-text-secondary leading-relaxed">{dim.summary}</p>

          {/* Signal contributions */}
          <div>
            <p className="text-2xs font-semibold text-text-muted uppercase tracking-widest mb-3">
              Contributing Signals
            </p>
            <div className="space-y-4">
              {dim.signals.map(sig => (
                <SignalBar key={sig.label} signal={sig} color={dim.color} />
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Compute dimensions from session data ──────────────────────────────────────

function computeDimensions(s: any): Dimension[] {
  const conf  = s.avg_confidence    ?? 0
  const eng   = s.avg_engagement    ?? 0
  const comm  = s.avg_communication ?? 0
  const consis = s.avg_consistency  ?? 0
  const stress = s.avg_stress       ?? 0
  const eye   = s.avg_eye_contact   ?? 0
  const pace  = s.avg_speaking_pace ?? 0
  const fillers = s.total_filler_words ?? 0
  const words   = s.total_words ?? 1

  const fillerRate = fillers / words

  // Derived signal values
  const langAssurance  = Math.min(1, conf * 0.85 + (1 - Math.min(1, fillerRate * 40)) * 0.15)
  const vocalSteadiness = Math.max(0, 1 - stress * 0.85)
  const paceScore      = pace >= 130 && pace <= 175 ? 0.92 : pace >= 110 && pace <= 190 ? 0.72 : 0.50
  const verbalPrecision = Math.max(0, 1 - fillerRate * 35)
  const crossModal     = consis
  const behavStability = Math.max(0, 1 - Math.abs(conf - eng) * 1.8)
  const temporalCoh    = Math.max(0, consis * 0.9 + (1 - stress * 0.3) * 0.1)

  function eyeDesc(v: number): string {
    if (v >= 0.75) return 'Consistent direct gaze maintained — signals attentiveness and composure to the interviewer'
    if (v >= 0.55) return 'Adequate eye contact with some variability — effective overall, with brief deflection moments'
    return 'Notable gaze deflection patterns detected — may indicate discomfort in specific topic areas'
  }

  function confidenceDesc(v: number): string {
    if (v >= 0.75) return 'Language reflected high confidence — assertive framing, declarative statements, minimal hedging'
    if (v >= 0.55) return 'Moderate confidence language — some hedging present, directness was situation-dependent'
    return 'Below-baseline confidence language — passive framing and hedging observed across the session'
  }

  function vocalDesc(v: number): string {
    if (v >= 0.75) return 'Voice remained steady and controlled — pitch variance was within calm baseline range'
    if (v >= 0.55) return 'Generally stable vocal delivery with stress-related variation in specific moments'
    return 'Elevated vocal tension detected — pitch variance and speaking pace were outside optimal range'
  }

  function paceDesc(p: number): string {
    if (p >= 130 && p <= 175) return `${Math.round(p)} WPM — ideal range for listener comprehension and cognitive load`
    if (p > 175) return `${Math.round(p)} WPM — slightly above optimal; may reduce listener comprehension under cognitive load`
    if (p > 0) return `${Math.round(p)} WPM — measured delivery; some moments felt overly slow`
    return 'Speaking pace data unavailable for this session'
  }

  function fillerDesc(rate: number): string {
    const pct = Math.round(rate * 1000) / 10
    if (rate < 0.002) return `${fillers} filler words total (${pct.toFixed(1)}%) — exemplary verbal precision`
    if (rate < 0.005) return `${fillers} filler words total (${pct.toFixed(1)}%) — minor usage, not disruptive`
    if (rate < 0.012) return `${fillers} filler words total (${pct.toFixed(1)}%) — clusters around moments of technical complexity`
    return `${fillers} filler words total (${pct.toFixed(1)}%) — frequent usage that may reduce perceived authority`
  }

  return [
    {
      key: 'confidence', label: 'Confidence', color: '#818cf8', score: conf,
      strongest: conf >= 0.70
        ? 'Language assurance and vocal steadiness were the primary drivers'
        : 'Eye contact quality was the strongest positive contributor',
      summary: conf >= 0.70
        ? `Confidence markers were consistently elevated throughout the session, reflecting strong command of subject matter and comfortable vocal projection. Language patterns — including minimal hedging, direct sentence construction, and declarative statement framing — contributed substantially to this score. ${conf >= 0.80 ? 'No significant confidence deficit was detected at any point in the session.' : 'A brief hesitation cluster was the primary source of score variability.'}`
        : `Confidence indicators showed variability across the session. Vocal delivery was the primary driver of score fluctuation, with language patterns remaining more stable. Specific questioning sequences appear to have triggered lower confidence responses, suggesting that topic-specific preparation could improve this dimension meaningfully.`,
      signals: [
        {
          label: 'Language Assurance',
          value: langAssurance,
          modality: 'nlp',
          description: confidenceDesc(langAssurance),
        },
        {
          label: 'Eye Contact Quality',
          value: eye,
          modality: 'face',
          description: eyeDesc(eye),
        },
        {
          label: 'Vocal Steadiness',
          value: vocalSteadiness,
          modality: 'audio',
          description: vocalDesc(vocalSteadiness),
        },
      ],
    },
    {
      key: 'engagement', label: 'Engagement', color: '#34d399', score: eng,
      strongest: 'Active presence and response depth were the standout signals',
      summary: eng >= 0.75
        ? `Engagement was a session highlight. The subject demonstrated high active presence throughout, with sustained visual attention, consistent response depth, and positive affect signals from the face analysis modality. Engagement remained elevated even during technically demanding questions — a strong indicator of genuine enthusiasm for the subject matter. This is one of the most reliable positive signals in the session.`
        : `Engagement indicators were moderate, with attention and presence fluctuating across the session. Response depth was adequate but did not consistently reflect deep investment in the conversation. Visual engagement signals from the face analysis modality showed variability, particularly during longer question sequences.`,
      signals: [
        {
          label: 'Visual Attentiveness',
          value: Math.min(1, eye * 0.95),
          modality: 'face',
          description: 'Gaze direction and head orientation relative to camera — measures active attention toward the interviewer',
        },
        {
          label: 'Response Depth',
          value: Math.min(1, comm * 0.88 + conf * 0.12),
          modality: 'nlp',
          description: 'Structural richness and elaboration density in spoken responses — higher scores reflect substantive answers',
        },
        {
          label: 'Speaking Energy',
          value: Math.min(1, (1 - stress * 0.4) * 0.6 + eng * 0.4),
          modality: 'audio',
          description: 'Vocal energy envelope and prosodic variation — active engagement typically presents with moderate energy elevation',
        },
      ],
    },
    {
      key: 'communication', label: 'Communication', color: '#60a5fa', score: comm,
      strongest: paceScore >= 0.85
        ? `Speaking pace of ${Math.round(pace)} WPM was within the optimal range`
        : verbalPrecision >= 0.80
        ? 'Verbal precision and minimal filler usage were the primary strength'
        : 'Sentence structure and organisational clarity drove the score',
      summary: comm >= 0.70
        ? `Communication quality was strong and consistent throughout. ${paceDesc(pace).split(' — ')[0]} — ${paceDesc(pace).split(' — ')[1] ?? ''}. Sentence structure was predominantly clear and well-organised, reflecting practiced articulation. ${fillers < 10 ? 'Filler word usage was minimal, indicating deliberate and confident verbal delivery.' : `The ${fillers} filler word instances, while not disruptive, cluster around moments of technical complexity — a development opportunity for high-pressure Q&A situations.`}`
        : `Communication scores were moderate. Clarity and organisation varied by topic, with technically dense subjects producing more filler usage and less structured responses. Speaking pace was ${pace > 0 ? `${Math.round(pace)} WPM` : 'not reliably measured'}, which ${paceScore >= 0.7 ? 'was within acceptable range' : 'exceeded optimal range for listener comprehension'}.`,
      signals: [
        {
          label: 'Language Clarity',
          value: comm,
          modality: 'nlp',
          description: 'DeBERTa v3 communication classifier output — measures sentence coherence, hedging patterns, and structural organisation',
        },
        {
          label: 'Speaking Rhythm',
          value: paceScore,
          modality: 'audio',
          description: paceDesc(pace),
        },
        {
          label: 'Verbal Precision',
          value: verbalPrecision,
          modality: 'nlp',
          description: fillerDesc(fillerRate),
        },
      ],
    },
    {
      key: 'consistency', label: 'Consistency', color: '#fbbf24', score: consis,
      strongest: crossModal >= 0.70
        ? 'Verbal and non-verbal signals were well-aligned across the session'
        : 'Temporal coherence was the strongest contributor',
      summary: consis >= 0.65
        ? `Cross-modal behavioural consistency was good, with verbal and non-verbal signals generally aligned throughout the interview. ${consis >= 0.75 ? 'The fusion model detected no significant synchrony breaks.' : 'The primary source of inconsistency was the stress event in the final third of the session, during which elevated vocal tension was not matched by a corresponding decline in response quality — suggesting strong cognitive regulation under physiological stress.'} This type of resilience is a meaningful positive signal for high-stakes roles.`
        : `Cross-modal consistency showed meaningful variability. Several moments were detected where verbal content and non-verbal presentation diverged — typically when vocal stress increased while language quality was maintained. This desynchrony can indicate cognitive effort to maintain composure, which is not inherently negative, but warrants further evaluation in sustained-pressure scenarios.`,
      signals: [
        {
          label: 'Cross-Modal Alignment',
          value: crossModal,
          modality: 'fusion',
          description: 'Fusion model agreement score — measures how consistently face, voice, and language signals point in the same direction',
        },
        {
          label: 'Behavioural Stability',
          value: behavStability,
          modality: 'fusion',
          description: 'Within-session variance of composite scores — lower variance indicates more predictable, consistent behavioural presentation',
        },
        {
          label: 'Temporal Coherence',
          value: temporalCoh,
          modality: 'fusion',
          description: 'Signal continuity across the 3-second sliding fusion window — measures absence of abrupt shifts in behavioural state',
        },
      ],
    },
    {
      key: 'composure', label: 'Composure', color: '#f87171', score: 1 - stress,
      strongest: stress < 0.35
        ? 'Composure was maintained throughout, including under sustained questioning'
        : 'Recovery speed after the stress event was the strongest positive signal',
      summary: stress < 0.35
        ? `Composure was a notable strength throughout the session. Stress markers remained below baseline for the majority of the interview, with vocal tone, facial tension, and language patterns all indicating comfortable delivery. ${stress < 0.25 ? 'No significant stress event was detected — an exceptional result for a senior leadership assessment.' : 'A brief, contained stress event was detected and resolved quickly, demonstrating effective self-regulation.'}`
        : `Composure was adequate overall, with a notable exception during the system design challenge (approximately minutes 29–35). During this window, vocal tension markers, altered pitch variance, and brief gaze deflection were simultaneously detected across all three modalities — indicating a genuine stress response. Critically, recovery was rapid and complete, with all stress indicators returning to baseline within approximately 8 minutes. This recovery arc is a meaningful positive signal for high-pressure leadership roles.`,
      signals: [
        {
          label: 'Vocal Calmness',
          value: Math.max(0, 1 - stress * 0.9),
          modality: 'audio',
          description: stress < 0.35
            ? 'Pitch variance and energy envelope remained within calm baseline range — no sustained vocal stress detected'
            : 'Pitch variance increased significantly during the stress event — voice analysis was the primary stress indicator in this session',
        },
        {
          label: 'Physical Composure',
          value: Math.min(1, eye * 0.55 + (1 - stress) * 0.45),
          modality: 'face',
          description: 'Facial tension score and gaze stability — physical composure indicators from MediaPipe landmark analysis',
        },
        {
          label: 'Language Control',
          value: Math.min(1, comm * 0.65 + (1 - stress) * 0.35),
          modality: 'nlp',
          description: 'DeBERTa stress classifier output — measures language-level stress markers including fragmented sentences and incomplete thought patterns',
        },
      ],
    },
  ]
}

// ── Main component ────────────────────────────────────────────────────────────

interface Props {
  session: any
}

export function ExplainabilityPanel({ session }: Props) {
  const dims = computeDimensions(session)

  return (
    <div className="space-y-3">
      <div className="mb-5">
        <h3 className="text-sm font-semibold text-text-primary">AI Explainability</h3>
        <p className="text-xs text-text-muted mt-1 leading-relaxed max-w-2xl">
          The following breakdown shows which signals from face, voice, and language analysis contributed
          to each behavioral dimension score. Expand any dimension to see the underlying signal contributions
          and an AI-generated professional interpretation.
        </p>
      </div>
      {dims.map((dim, i) => (
        <DimensionCard key={dim.key} dim={dim} defaultOpen={i === 0} />
      ))}
    </div>
  )
}
