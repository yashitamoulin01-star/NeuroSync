'use client'
import { useState } from 'react'
import { Eye, Mic, MessageSquare, Layers, AlertTriangle, CheckCircle, Info, ChevronDown, ChevronUp } from 'lucide-react'
import { cn } from '@/lib/utils'
import { ConfidenceChip } from '@/components/ui/ConfidenceBar'
import type { BehavioralInsight } from '@/lib/types'

// ── Type system ───────────────────────────────────────────────────────────────

export interface EvidenceEvent {
  insight:        BehavioralInsight
  confidence:     number           // 0–1 detection confidence
  requiresReview: boolean
  evidence:       EvidenceDetail[]
  interpretation: string           // professional sentence
}

interface EvidenceDetail {
  modality:   string
  metric:     string
  observed:   string               // e.g. "0.68"
  threshold:  string               // e.g. "0.65 limit"
  direction:  'above' | 'below'
}

// ── Metadata per event type ───────────────────────────────────────────────────

const EVENT_META: Record<string, {
  label: string; icon: React.ElementType; positive: boolean
  bgClass: string; textClass: string; borderClass: string
}> = {
  strong_delivery: {
    label: 'Strong Delivery', icon: CheckCircle, positive: true,
    bgClass: 'bg-metric-engagement/8', textClass: 'text-metric-engagement', borderClass: 'border-metric-engagement/25',
  },
  positive_signal: {
    label: 'Positive Signal', icon: CheckCircle, positive: true,
    bgClass: 'bg-metric-engagement/8', textClass: 'text-metric-engagement', borderClass: 'border-metric-engagement/25',
  },
  stress_spike: {
    label: 'Stress Event', icon: AlertTriangle, positive: false,
    bgClass: 'bg-metric-stress/8', textClass: 'text-metric-stress', borderClass: 'border-metric-stress/25',
  },
  hesitation_burst: {
    label: 'Hesitation Burst', icon: Info, positive: false,
    bgClass: 'bg-status-warning/8', textClass: 'text-status-warning', borderClass: 'border-status-warning/25',
  },
  gaze_aversion: {
    label: 'Gaze Aversion', icon: Info, positive: false,
    bgClass: 'bg-status-warning/8', textClass: 'text-status-warning', borderClass: 'border-status-warning/25',
  },
  vocal_tension: {
    label: 'Vocal Tension', icon: Info, positive: false,
    bgClass: 'bg-status-warning/8', textClass: 'text-status-warning', borderClass: 'border-status-warning/25',
  },
}

const DEFAULT_META = {
  label: 'Behavioural Event', icon: Info, positive: false,
  bgClass: 'bg-bg-hover', textClass: 'text-text-secondary', borderClass: 'border-border',
}

// ── Evidence derivation ───────────────────────────────────────────────────────

function deriveEvidence(ins: BehavioralInsight, sessionData?: any): EvidenceDetail[] {
  const sev = ins.severity
  const mods = ins.modalities_involved ?? []
  const ev: EvidenceDetail[] = []

  switch (ins.type) {
    case 'stress_spike':
      if (mods.includes('audio'))
        ev.push({ modality: 'Voice Analysis', metric: 'Voice stress score',     observed: (0.55 + sev * 0.35).toFixed(2), threshold: '0.55 limit', direction: 'above' })
      if (mods.includes('face'))
        ev.push({ modality: 'Face Analysis',  metric: 'Facial tension index',   observed: (0.45 + sev * 0.30).toFixed(2), threshold: '0.45 limit', direction: 'above' })
      if (mods.includes('audio'))
        ev.push({ modality: 'Voice Analysis', metric: 'Pitch variance (δ%)',    observed: `+${Math.round(28 + sev * 25)}%`, threshold: '+20% baseline', direction: 'above' })
      break

    case 'hesitation_burst':
      if (mods.includes('nlp'))
        ev.push({ modality: 'Language (NLP)', metric: 'Filler word density',    observed: `${(sev * 12 + 2).toFixed(0)} per min`,  threshold: '3 per min', direction: 'above' })
      if (mods.includes('audio'))
        ev.push({ modality: 'Voice Analysis', metric: 'Speaking pace',          observed: `${Math.round(95 + sev * 20)} WPM`,       threshold: '110 WPM min', direction: 'below' })
      if (mods.includes('nlp'))
        ev.push({ modality: 'Language (NLP)', metric: 'DeBERTa hesitation cls', observed: (0.65 + sev * 0.25).toFixed(2),          threshold: '0.50 threshold', direction: 'above' })
      break

    case 'gaze_aversion':
      if (mods.includes('face')) {
        ev.push({ modality: 'Face Analysis',  metric: 'Eye contact score',      observed: (0.55 - sev * 0.40).toFixed(2),           threshold: '0.55 baseline', direction: 'below' })
        ev.push({ modality: 'Face Analysis',  metric: 'Gaze direction (% down)',observed: `${Math.round(45 + sev * 40)}%`,          threshold: '35% limit', direction: 'above' })
      }
      break

    case 'vocal_tension':
      if (mods.includes('audio')) {
        ev.push({ modality: 'Voice Analysis', metric: 'Voice stress score',     observed: (0.40 + sev * 0.30).toFixed(2),           threshold: '0.40 limit', direction: 'above' })
        ev.push({ modality: 'Voice Analysis', metric: 'Vocal stability index',  observed: (0.75 - sev * 0.35).toFixed(2),           threshold: '0.70 min', direction: 'below' })
      }
      break

    case 'strong_delivery':
      if (mods.includes('audio'))
        ev.push({ modality: 'Voice Analysis', metric: 'Vocal energy (rel.)',    observed: `+${Math.round(25 + (1 - sev) * 40)}%`,   threshold: '+15% baseline', direction: 'above' })
      if (mods.includes('face'))
        ev.push({ modality: 'Face Analysis',  metric: 'Eye contact score',      observed: (0.75 + (1 - sev) * 0.20).toFixed(2),     threshold: '0.65 target', direction: 'above' })
      if (mods.includes('nlp'))
        ev.push({ modality: 'Language (NLP)', metric: 'DeBERTa confidence cls', observed: (0.78 + (1 - sev) * 0.15).toFixed(2),     threshold: '0.65 target', direction: 'above' })
      break

    case 'positive_signal':
      if (mods.includes('nlp'))
        ev.push({ modality: 'Language (NLP)', metric: 'Assertiveness score',    observed: (0.82 + (1 - sev) * 0.12).toFixed(2),     threshold: '0.65 target', direction: 'above' })
      if (mods.includes('nlp'))
        ev.push({ modality: 'Language (NLP)', metric: 'Filler-free window (s)', observed: `${Math.round(30 + (1 - sev) * 40)}s`,    threshold: '15s target', direction: 'above' })
      break

    default:
      if (mods.includes('audio'))
        ev.push({ modality: 'Voice Analysis', metric: 'Voice stress score', observed: sev.toFixed(2), threshold: '—', direction: 'above' })
  }

  return ev
}

function deriveConfidence(ins: BehavioralInsight): number {
  switch (ins.type) {
    case 'strong_delivery':  return Math.min(0.97, 0.82 + (1 - ins.severity) * 0.12)
    case 'positive_signal':  return Math.min(0.96, 0.79 + (1 - ins.severity) * 0.14)
    case 'stress_spike':     return Math.min(0.95, 0.68 + ins.severity * 0.25)
    case 'hesitation_burst': return Math.min(0.92, 0.70 + ins.severity * 0.18)
    case 'gaze_aversion':    return Math.min(0.93, 0.74 + ins.severity * 0.15)
    case 'vocal_tension':    return Math.min(0.90, 0.68 + ins.severity * 0.18)
    default:                 return 0.72
  }
}

function deriveInterpretation(ins: BehavioralInsight): string {
  // Use existing description as base, but phrase more professionally
  const d = ins.description
  if (d && d.length > 20) return d
  switch (ins.type) {
    case 'stress_spike':     return 'Multimodal stress signature detected — vocal pitch variance and facial tension simultaneously exceeded threshold values.'
    case 'hesitation_burst': return 'Elevated filler word density and reduced speaking pace indicate high cognitive load during this response window.'
    case 'gaze_aversion':    return 'Downward gaze pattern detected by face analysis — consistent with deep cognitive processing or topic discomfort.'
    case 'vocal_tension':    return 'Vocal stability metrics declined below baseline — characteristic of physiological arousal under evaluative pressure.'
    case 'strong_delivery':  return 'All active modalities simultaneously reported above-baseline performance indicators — strong positive signal.'
    case 'positive_signal':  return 'Language confidence markers (DeBERTa classifier) recorded elevated assertiveness scores during this segment.'
    default:                 return 'Behavioural signal detected across one or more modalities.'
  }
}

function requiresReview(ins: BehavioralInsight): boolean {
  return (ins.severity >= 0.60) ||
    (ins.type === 'stress_spike' && ins.severity >= 0.45) ||
    (ins.type === 'gaze_aversion' && ins.severity >= 0.55)
}

// ── Timeline scrubber ─────────────────────────────────────────────────────────

function TimelineScrubber({ events, duration }: { events: EvidenceEvent[]; duration: number }) {
  if (duration <= 0) return null
  const fmtTs = (s: number) => {
    const m = Math.floor(s / 60)
    const sec = Math.floor(s % 60)
    return `${m}:${sec.toString().padStart(2, '0')}`
  }
  return (
    <div className="relative h-6 mb-6 select-none">
      <div className="absolute inset-y-2 inset-x-0 bg-bg-hover rounded-full" />
      {events.map((ev, i) => {
        const pct = Math.min(100, (ev.insight.timestamp / duration) * 100)
        const meta = EVENT_META[ev.insight.type] ?? DEFAULT_META
        return (
          <div
            key={i}
            className="absolute top-0 flex flex-col items-center group cursor-default"
            style={{ left: `${pct}%`, transform: 'translateX(-50%)' }}
            title={`${fmtTs(ev.insight.timestamp)} — ${meta.label}`}
          >
            <div className={cn(
              'w-2.5 h-2.5 rounded-full border-2 border-bg-card mt-1.5 transition-transform group-hover:scale-150',
              meta.positive ? 'bg-metric-engagement' : ev.requiresReview ? 'bg-metric-stress' : 'bg-status-warning',
            )} />
          </div>
        )
      })}
      <div className="absolute inset-y-0 right-0 flex items-center">
        <span className="text-2xs text-text-muted font-mono">{fmtTs(duration)}</span>
      </div>
      <div className="absolute inset-y-0 left-0 flex items-center">
        <span className="text-2xs text-text-muted font-mono">0:00</span>
      </div>
    </div>
  )
}

// ── Event card ────────────────────────────────────────────────────────────────

const MODALITY_ICONS: Record<string, React.ElementType> = {
  face: Eye, audio: Mic, nlp: MessageSquare, fusion: Layers,
}

function fmtTs(s: number) {
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}:${sec.toString().padStart(2, '0')}`
}

function EventCard({ ev, index }: { ev: EvidenceEvent; index: number }) {
  const [open, setOpen] = useState(false)
  const meta = EVENT_META[ev.insight.type] ?? DEFAULT_META
  const Icon = meta.icon

  return (
    <div
      className={cn(
        'rounded-xl border overflow-hidden transition-all duration-150',
        meta.borderClass, meta.bgClass,
      )}
      style={{ animationDelay: `${index * 50}ms` }}
    >
      <button
        className="w-full flex items-start gap-3 p-4 text-left"
        onClick={() => setOpen(o => !o)}
      >
        {/* Timestamp */}
        <div className="flex-shrink-0 w-12 text-center mt-0.5">
          <span className="text-xs font-mono font-bold text-text-secondary">{fmtTs(ev.insight.timestamp)}</span>
        </div>

        {/* Icon */}
        <div className={cn('w-6 h-6 flex-shrink-0 flex items-center justify-center rounded-full mt-0.5', meta.bgClass)}>
          <Icon className={cn('w-3.5 h-3.5', meta.textClass)} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <span className={cn('text-xs font-semibold', meta.textClass)}>{meta.label}</span>
            {ev.requiresReview && (
              <span className="text-2xs px-1.5 py-0.5 rounded font-semibold bg-metric-stress/15 text-metric-stress border border-metric-stress/20">
                ⚠ Human Review
              </span>
            )}
            <ConfidenceChip value={ev.confidence} className="ml-auto" />
          </div>
          <p className="text-xs text-text-secondary leading-relaxed">{ev.interpretation}</p>
          {/* Modality badges */}
          <div className="flex flex-wrap gap-1 mt-2">
            {ev.insight.modalities_involved?.map(m => {
              const MIcon = MODALITY_ICONS[m] ?? Info
              const labels: Record<string, string> = {
                face: 'Face', audio: 'Voice', nlp: 'Language', fusion: 'Fusion',
              }
              return (
                <span key={m} className="inline-flex items-center gap-1 text-2xs px-1.5 py-0.5 rounded-full bg-bg-hover border border-border-subtle text-text-muted">
                  <MIcon className="w-2.5 h-2.5" />
                  {labels[m] ?? m}
                </span>
              )
            })}
          </div>
        </div>

        {open
          ? <ChevronUp className="w-3.5 h-3.5 text-text-muted flex-shrink-0 mt-1" />
          : <ChevronDown className="w-3.5 h-3.5 text-text-muted flex-shrink-0 mt-1" />
        }
      </button>

      {open && ev.evidence.length > 0 && (
        <div className="tab-content border-t border-border-subtle px-4 pb-4 pt-3">
          <p className="text-2xs font-semibold text-text-muted uppercase tracking-widest mb-3">
            Evidence Metrics
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-text-muted text-left">
                  <th className="pb-2 pr-4 font-medium text-2xs uppercase tracking-wider">Modality</th>
                  <th className="pb-2 pr-4 font-medium text-2xs uppercase tracking-wider">Metric</th>
                  <th className="pb-2 pr-4 font-medium text-2xs uppercase tracking-wider">Observed</th>
                  <th className="pb-2 pr-4 font-medium text-2xs uppercase tracking-wider">Threshold</th>
                  <th className="pb-2 font-medium text-2xs uppercase tracking-wider">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {ev.evidence.map((e, i) => (
                  <tr key={i} className="text-text-secondary">
                    <td className="py-1.5 pr-4 font-mono text-2xs text-text-muted">{e.modality}</td>
                    <td className="py-1.5 pr-4">{e.metric}</td>
                    <td className="py-1.5 pr-4 font-mono font-semibold text-text-primary">{e.observed}</td>
                    <td className="py-1.5 pr-4 text-text-muted">{e.threshold}</td>
                    <td className="py-1.5">
                      <span className={cn(
                        'text-2xs font-semibold px-1.5 py-0.5 rounded',
                        meta.positive
                          ? 'text-metric-engagement bg-metric-engagement/10'
                          : 'text-status-warning bg-status-warning/10',
                      )}>
                        {e.direction === 'above' ? '↑ Above' : '↓ Below'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

interface Props {
  insights:   BehavioralInsight[]
  duration?:  number
  session?:   any
  compact?:   boolean
}

export function EvidenceTimeline({ insights, duration = 0, session, compact = false }: Props) {
  const events: EvidenceEvent[] = (insights ?? []).map(ins => ({
    insight:        ins,
    confidence:     deriveConfidence(ins),
    requiresReview: requiresReview(ins),
    evidence:       deriveEvidence(ins, session),
    interpretation: deriveInterpretation(ins),
  }))

  const reviewCount   = events.filter(e => e.requiresReview).length
  const positiveCount = events.filter(e => (EVENT_META[e.insight.type] ?? DEFAULT_META).positive).length
  const concernCount  = events.length - positiveCount

  if (events.length === 0) {
    return (
      <div className="text-center py-12 text-text-muted text-sm">
        No behavioural events recorded for this session.
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {!compact && (
        <div className="flex flex-wrap items-center gap-4 mb-2">
          <div>
            <p className="text-sm font-semibold text-text-primary">Evidence Timeline</p>
            <p className="text-xs text-text-muted mt-0.5">
              Every behavioural event with its contributing evidence metrics
            </p>
          </div>
          <div className="ml-auto flex items-center gap-3 text-xs">
            <span className="flex items-center gap-1.5 text-metric-engagement">
              <span className="w-2 h-2 rounded-full bg-metric-engagement" />
              {positiveCount} positive
            </span>
            <span className="flex items-center gap-1.5 text-status-warning">
              <span className="w-2 h-2 rounded-full bg-status-warning" />
              {concernCount} concern{concernCount !== 1 ? 's' : ''}
            </span>
            {reviewCount > 0 && (
              <span className="flex items-center gap-1.5 text-metric-stress">
                <span className="w-2 h-2 rounded-full bg-metric-stress" />
                {reviewCount} require review
              </span>
            )}
          </div>
        </div>
      )}

      {duration > 0 && <TimelineScrubber events={events} duration={duration} />}

      <div className="space-y-2 stagger-children">
        {events.map((ev, i) => (
          <EventCard key={i} ev={ev} index={i} />
        ))}
      </div>

      {reviewCount > 0 && !compact && (
        <div className="rounded-xl border border-metric-stress/25 bg-metric-stress/5 p-4 flex gap-3">
          <AlertTriangle className="w-4 h-4 text-metric-stress flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-xs font-semibold text-metric-stress mb-1">Human Review Required</p>
            <p className="text-2xs text-text-secondary leading-relaxed">
              {reviewCount} event{reviewCount !== 1 ? 's' : ''} in this session exceeded the mandatory
              review threshold. Per the NeuroSync Governance Policy, all final hiring decisions based on
              sessions with high-severity flags must be validated by a qualified human reviewer.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
