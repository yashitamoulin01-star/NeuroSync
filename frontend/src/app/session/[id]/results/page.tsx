'use client'
import { useState, useEffect, memo } from 'react'
import Link from 'next/link'
import { AppShell } from '@/components/layout/AppShell'
import { Button } from '@/components/ui/Button'
import { BehavioralFingerprint } from '@/components/charts/BehavioralFingerprint'
import { TimelineChart } from '@/components/charts/TimelineChart'
import { InsightCard } from '@/components/session/InsightCard'
import { TranscriptFeed } from '@/components/session/TranscriptFeed'
import { ExplainabilityPanel } from '@/components/session/ExplainabilityPanel'
import { ModelTransparencyCard } from '@/components/session/ModelTransparencyCard'
import { AtsExportButton } from '@/components/session/AtsExportButton'
import { cn } from '@/lib/utils'
import {
  Download, Share2, AlertCircle, FlaskConical, BookOpen,
  ChevronDown, ChevronUp, ChevronRight, ArrowLeft, ArrowRight, Users,
  TrendingUp, TrendingDown, Minus, AlertTriangle, CheckCircle, XCircle,
  MessageSquare, Shield, Lightbulb, BarChart3, Brain, Zap,
  Target, Eye, Mic,
} from 'lucide-react'
import { formatDuration } from '@/lib/utils'
import { api, cbipApi } from '@/lib/api'
import { DEMO_SESSION } from '@/lib/demoData'
import { toast } from '@/lib/toast'
import type { BehavioralInsight } from '@/lib/types'
import type { TimelinePoint } from '@/lib/api'
import { Skeleton } from '@/components/ui/Skeleton'

// ── Dimension definitions ─────────────────────────────────────────────────────

const DIMS: Array<{ key: string; label: string; color: string; desc: string; inverted?: boolean }> = [
  { key: 'avg_confidence',    label: 'Confidence',    color: '#818cf8', desc: 'Language clarity and vocal energy' },
  { key: 'avg_engagement',    label: 'Engagement',    color: '#34d399', desc: 'Active presence and response depth' },
  { key: 'avg_communication', label: 'Communication', color: '#60a5fa', desc: 'Clarity, pace, and structure' },
  { key: 'avg_consistency',   label: 'Consistency',   color: '#fbbf24', desc: 'Cross-modal signal alignment' },
  { key: 'avg_stress',        label: 'Composure',     color: '#f87171', desc: 'Inverse vocal/facial stress', inverted: true },
]

function levelOf(v: number) { return v >= 0.75 ? 'High' : v >= 0.55 ? 'Moderate' : v >= 0.35 ? 'Developing' : 'Low' }

// ── Text generators ───────────────────────────────────────────────────────────

function buildExecSummary(s: any, overallScore: number): string {
  const name = s.name ? s.name.split(/[—,]/)[0].trim() : 'The candidate'
  const mode = s.mode === 'coaching' ? 'coaching session' : s.mode === 'presentation' ? 'presentation' : 'interview'
  const conf = s.avg_confidence ?? 0, stress = s.avg_stress ?? 0, comm = s.avg_communication ?? 0

  let primary = conf >= 0.70 && comm >= 0.70
    ? 'Vocal confidence and communication quality were both above baseline, with assertive language patterns and minimal hedging throughout.'
    : conf >= 0.70
    ? 'Vocal confidence was the primary strength, with assertive language patterns and low hesitation frequency contributing to above-baseline scores.'
    : comm >= 0.70
    ? 'Communication quality and structural clarity were the primary strengths, with well-organised responses across all question types.'
    : 'Behavioural signals were variable across modalities, with no single dimension consistently dominant.'

  const stressNote = stress >= 0.45
    ? ' Elevated stress markers were recorded during specific questioning sequences; follow-up evaluation under sustained pressure is advised.'
    : stress >= 0.30
    ? ' Minor stress events were detected and resolved quickly, indicating effective self-regulation under pressure.'
    : ' Composure was maintained throughout, including during technically demanding sequences.'

  const verdict = overallScore >= 75 ? 'supports advancing to the next evaluation stage'
    : overallScore >= 55 ? 'warrants standard due diligence before proceeding'
    : 'merits further evaluation before a determination is made'

  return `${name} demonstrated ${overallScore >= 75 ? 'strong' : overallScore >= 55 ? 'adequate' : 'mixed'} behavioural indicators across this ${mode}. ${primary}${stressNote} The overall profile ${verdict}.`
}

function buildRecommendation(overallScore: number, stress: number, conf: number): string {
  if (overallScore >= 75 && stress < 0.45)
    return 'Behavioural indicators were strong across all measured dimensions, with composure maintained throughout. Confidence and communication scores both exceeded the 70th percentile threshold. Recommend advancing to the next evaluation stage.'
  if (overallScore >= 60)
    return `Performance was adequate with notable consistency across modalities.${stress >= 0.55 ? ' Stress markers were elevated under pressure; a structured follow-up is recommended before final determination.' : ''} Recommend proceeding with standard due diligence.`
  if (conf < 0.40)
    return 'Confidence and communication scores were below the expected threshold. A structured coaching session focused on verbal delivery is recommended before re-evaluation.'
  return 'Behavioural signals were variable across modalities. A second structured interview with targeted probes on lower-scoring dimensions is recommended before a final determination.'
}

// ── Data helpers ──────────────────────────────────────────────────────────────

function toTimelineData(frames: TimelinePoint[]) {
  return frames.map(f => ({ t: Math.round(f.ts), confidence: f.confidence, stress: f.stress, engagement: f.engagement, communication: f.communication }))
}

function parseTranscript(raw: string) {
  if (!raw) return []
  return raw.split('. ').filter(Boolean).map((t, i) => ({ timestamp: i * 15, text: t.trim() + (t.endsWith('.') ? '' : '.'), fillerWords: [] as string[] }))
}

// ── Demo narrative data ───────────────────────────────────────────────────────

const DEMO_NARRATIVE = {
  overall_score: 74,
  recommendation: 'Proceed',
  follow_up_questions: [
    'Walk me through a decision you made that you were initially uncertain about. What gave you the confidence to commit?',
    'Describe a high-pressure situation you have navigated. How did you manage your communication under that pressure?',
  ],
  behavioral_arc: {
    label: 'improving',
    description: 'Behavioural signals improved consistently across the session. Confidence and engagement both increased from early to late segments, while stress indicators declined — suggesting interview nerves rather than a performance ceiling.',
    deltas: { confidence: 12.4, stress: -8.1, engagement: 9.7 },
  },
  contradictions: [{
    type: 'confident_language_under_stress',
    signal_a: 'Confidence 74% (verbal)',
    signal_b: 'Stress 32% (physiological)',
    interpretation: 'The candidate used assertive language while showing moderate stress markers in the early session. Stress dissipated as the session progressed — consistent with initial interview nerves rather than topic-driven anxiety.',
    review_required: false,
  }],
  evidence_quality: {
    confidence: 'supporting', stress: 'contextual', engagement: 'supporting',
    communication: 'supporting', consistency: 'supporting', composure: 'supporting',
    overall_reliability: 'high', data_quality: ['Session length and word count are sufficient for reliable scoring.'],
  },
  decision_support: {
    strengths: ['Confidence (74%) — assertive language and stable vocal delivery', 'Communication (71%) — clear and structured responses', 'Session arc improved across the interview'],
    concerns: ['Engagement (62%) — moderate variation in energy across topics'],
    missing_signals: [],
    recommendation_label: 'Proceed',
    recommendation_confidence: 'high',
    human_review_required: false,
    human_review_rationale: 'Standard review recommended — AI analysis is supplementary evidence only.',
  },
  narrative: {
    opening: 'The candidate demonstrated a strong behavioural profile across the 12-minute session. Multimodal signals aligned coherently, and performance improved consistently from early to late segments — suggesting initial interview nerves rather than a performance ceiling.',
    confidence: 'Confidence registered at 74%, supported by assertive language patterns, stable vocal projection, and minimal hedging. The candidate maintained directness across response types — consistent with genuine subject-matter familiarity.',
    composure: 'Moderate stress was detected (32%), within the expected range for structured interviews. Stress indicators declined across the session, suggesting effective self-regulation as familiarity with the format increased.',
    communication: 'Communication quality scored 71%, with well-structured responses and a natural speaking pace. Filler word frequency was low (12 instances across 847 words — 1.4% rate), indicating organised thinking under pressure.',
    engagement: 'Engagement was moderate (62%), with some variation in energy across topics. Behavioural consistency scored 68%, suggesting partial divergence between verbal and non-verbal signals at certain points.',
    recommendation: 'The multimodal behavioural profile supports advancement. Confidence, communication, and composure all exceeded expected thresholds, and the improving session arc is a positive indicator.',
  },
  dimensions: { confidence: 74, composure: 68, communication: 71, engagement: 62, consistency: 68 },
}

// ── Workflow Bar — contextual back nav + candidate context ────────────────────

function WorkflowBar({ candidateName, sessionId, tier, isDemo }: {
  candidateName?: string; sessionId: string; tier: string; isDemo: boolean
}) {
  const tierColor = tier === 'Proceed' ? 'text-status-success' : tier === 'Review' ? 'text-status-warning' : tier === 'Hold' ? 'text-status-danger' : 'text-text-disabled'
  return (
    <div className="sticky top-0 z-20 flex items-center gap-3 px-4 sm:px-6 py-2.5 bg-bg-surface/90 backdrop-blur-sm border-b border-border no-print">
      <Link
        href="/workspace"
        className="flex items-center gap-1.5 text-xs text-text-muted hover:text-text-primary transition-colors flex-shrink-0"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        <span className="hidden sm:inline">Workspace</span>
      </Link>

      <span className="text-border select-none">·</span>

      {candidateName ? (
        <span className="text-xs font-medium text-text-secondary truncate min-w-0 max-w-[140px] sm:max-w-[240px]">
          {candidateName}
        </span>
      ) : (
        <span className="text-xs text-text-disabled">Behavioral Report</span>
      )}

      {tier && tier !== '' && (
        <span className={cn('text-2xs font-semibold uppercase tracking-wide flex-shrink-0', tierColor)}>
          {tier}
        </span>
      )}

      <div className="flex-1" />

      {!isDemo && (
        <Link href="/workspace" className="flex-shrink-0">
          <Button variant="ghost" size="xs" icon={<Users className="w-3 h-3" />}>
            <span className="hidden sm:inline">View in Pipeline</span>
          </Button>
        </Link>
      )}
    </div>
  )
}

// ── Workflow Footer — "what's next?" navigation ───────────────────────────────

function WorkflowFooter({ isDemo, sessionId }: { isDemo: boolean; sessionId: string }) {
  return (
    <section className="pt-8 border-t border-border no-print">
      <p className="label-xs text-text-disabled mb-4">What&apos;s Next</p>
      <div className="flex flex-wrap gap-3">
        <Link href="/workspace">
          <Button variant="ghost" size="sm" icon={<ArrowLeft className="w-3.5 h-3.5" />}>
            All Candidates
          </Button>
        </Link>
        <Link href="/workspace">
          <Button variant="secondary" size="sm" icon={<Users className="w-3.5 h-3.5" />}>
            Compare in Pipeline
          </Button>
        </Link>
        {!isDemo && (
          <Link href="/session/new">
            <Button variant="outline" size="sm" icon={<ArrowRight className="w-3.5 h-3.5" />}>
              New Interview
            </Button>
          </Link>
        )}
      </div>
    </section>
  )
}

// ── 1. Executive Summary Card ─────────────────────────────────────────────────

function ExecutiveSummaryCard({
  s, overallScore, conf, eng, comm, consis, composure, stress, execSummary, rec, narrative,
}: {
  s: any; overallScore: number; conf: number; eng: number; comm: number
  consis: number; composure: number; stress: number; execSummary: string; rec: string; narrative: any
}) {
  const tier = overallScore >= 75 ? 'Proceed' : overallScore >= 55 ? 'Review' : 'Hold'
  const tierColor = { Proceed: '#34d399', Review: '#fbbf24', Hold: '#f87171' }[tier]
  const tierBorder = { Proceed: 'border-metric-engagement/30 bg-metric-engagement/[0.03]', Review: 'border-status-warning/30 bg-status-warning/[0.03]', Hold: 'border-metric-stress/30 bg-metric-stress/[0.03]' }[tier]

  const dims = [
    { l: 'Confidence', v: conf }, { l: 'Engagement', v: eng },
    { l: 'Communication', v: comm }, { l: 'Consistency', v: consis }, { l: 'Composure', v: composure },
  ].sort((a, b) => b.v - a.v)
  const strengths = dims.filter(d => d.v >= 0.65).slice(0, 3)
  const risks: string[] = []
  if (stress > 0.45) risks.push('Elevated stress')
  if (conf < 0.50) risks.push('Low confidence')
  dims.filter(d => d.v < 0.55 && d.l !== 'Composure').forEach(d => { if (!risks.includes(`Low ${d.l.toLowerCase()}`)) risks.push(`${d.l} ${Math.round(d.v * 100)}%`) })

  const wordCount = s.total_words ?? 0
  const reliability = narrative?.evidence_quality?.overall_reliability ?? (wordCount > 1000 ? 'high' : wordCount > 400 ? 'moderate' : 'limited')

  const sessionDate = s.started_at ? new Date(typeof s.started_at === 'number' ? s.started_at * 1000 : s.started_at) : null
  const dateStr = sessionDate?.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' }) ?? '—'
  const timeStr = sessionDate?.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }) ?? ''
  const modeLabel = s.mode ? s.mode.charAt(0).toUpperCase() + s.mode.slice(1) : 'Interview'

  return (
    <div className={`rounded-xl border overflow-hidden print:border-black/20 ${tierBorder}`}>
      {/* Report type */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-border/50 print:border-black/10">
        <span className="label-xs text-text-disabled print:text-black/50">{modeLabel} Assessment Report</span>
        <span className="label-xs text-text-disabled print:text-black/50">{dateStr}{timeStr ? ` · ${timeStr}` : ''}</span>
      </div>

      {/* Candidate + verdict */}
      <div className="px-6 pt-6 pb-5">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-5">
          <div>
            <h1 className="text-2xl font-extrabold tracking-tight text-text-primary leading-tight print:text-black">
              {s.name ?? 'Session'}
            </h1>
            <p className="text-sm text-text-muted mt-1 print:text-black/60">
              {formatDuration(s.duration ?? 0)}
              {s.total_words ? ` · ${s.total_words.toLocaleString()} words` : ''}
              {s.total_filler_words ? ` · ${s.total_filler_words} fillers` : ''}
            </p>
          </div>

          <div className={cn(
            'flex flex-col items-center sm:items-end',
          )}>
            <span className="label-xs text-text-disabled print:text-black/50 mb-1">Behavioral Verdict</span>
            <span className="text-4xl font-extrabold tracking-tight uppercase print:text-black" style={{ color: tierColor }}>
              {tier}
            </span>
            <span className="text-xs font-mono text-text-muted print:text-black/60 mt-1">Score {overallScore} / 100</span>
          </div>
        </div>

        {/* 3-column assessment glance */}
        <div className="grid grid-cols-3 gap-4 mt-6 pt-5 border-t border-border/50 print:border-black/10">
          <div>
            <p className="label-xs text-text-disabled mb-1 print:text-black/50">Confidence</p>
            <p className="text-lg font-bold text-text-primary print:text-black">{Math.round(conf * 100)}%</p>
            <p className="text-2xs text-text-muted print:text-black/50">{levelOf(conf)}</p>
          </div>
          <div>
            <p className="label-xs text-text-disabled mb-1 print:text-black/50">Communication</p>
            <p className="text-lg font-bold text-text-primary print:text-black">{Math.round(comm * 100)}%</p>
            <p className="text-2xs text-text-muted print:text-black/50">{levelOf(comm)}</p>
          </div>
          <div>
            <p className="label-xs text-text-disabled mb-1 print:text-black/50">Review Reliability</p>
            <p className="text-lg font-bold text-text-primary capitalize print:text-black">{reliability}</p>
            <p className="text-2xs text-text-muted print:text-black/50">{wordCount > 0 ? `${wordCount.toLocaleString()} words` : 'Insufficient data'}</p>
          </div>
        </div>

        {/* Strengths + risks */}
        <div className="flex flex-wrap gap-3 mt-5">
          {strengths.map(d => (
            <span key={d.l} className="inline-flex items-center gap-1.5 text-2xs px-2.5 py-1 rounded-full border border-metric-engagement/25 bg-metric-engagement/8 text-metric-engagement print:border-black/20 print:text-black">
              <CheckCircle className="w-3 h-3 flex-shrink-0" />
              {d.l} {Math.round(d.v * 100)}%
            </span>
          ))}
          {risks.slice(0, 2).map(r => (
            <span key={r} className="inline-flex items-center gap-1.5 text-2xs px-2.5 py-1 rounded-full border border-status-warning/25 bg-status-warning/8 text-status-warning print:border-black/20 print:text-black">
              <AlertTriangle className="w-3 h-3 flex-shrink-0" />
              {r}
            </span>
          ))}
        </div>

        {/* Opening paragraph */}
        <div className="mt-5 border-l-2 border-accent/30 pl-4 print:border-black/30">
          <p className="text-sm text-text-secondary leading-relaxed print:text-black">{execSummary}</p>
        </div>

        {/* Recommended action */}
        <div className="mt-5 pt-5 border-t border-border/50 print:border-black/10">
          <div className="flex items-start gap-3">
            <div className="w-1.5 h-1.5 rounded-full mt-[7px] flex-shrink-0" style={{ background: tierColor }} />
            <div>
              <p className="label-xs text-text-disabled mb-1 print:text-black/50">Recommended Action</p>
              <p className="text-sm text-text-secondary leading-relaxed print:text-black">{rec}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Governance footer */}
      <div className="px-6 py-3 border-t border-border/40 bg-bg-surface/50 print:border-black/10 print:bg-black/[0.02]">
        <p className="text-2xs text-text-disabled print:text-black/40">
          AI-generated behavioural analysis — supplementary evidence only.
          All hiring decisions require human validation. Scores are probabilistic estimates, not objective measurements.
        </p>
      </div>
    </div>
  )
}

// ── 3. Behavioral journey narrative ──────────────────────────────────────────

const JOURNEY_DIMS = [
  { key: 'confidence', label: 'Confidence', color: '#818cf8' },
  { key: 'engagement', label: 'Engagement', color: '#34d399' },
]

function phaseAvg(points: any[], key: string) {
  if (!points.length) return 0
  return points.reduce((s, p) => s + (p[key] ?? 0), 0) / points.length
}

function JourneyNarrative({ timeline, narrative }: { timeline: any[]; narrative: any }) {
  if (!timeline.length) return null

  const third = Math.max(1, Math.floor(timeline.length / 3))
  const phases = [
    { label: 'Opening', points: timeline.slice(0, third) },
    { label: 'Middle', points: timeline.slice(third, third * 2) },
    { label: 'Closing', points: timeline.slice(third * 2) },
  ]

  const arc = narrative?.behavioral_arc
  const overallTrend = arc?.label ?? (() => {
    const firstConf = phaseAvg(phases[0].points, 'confidence')
    const lastConf  = phaseAvg(phases[2].points, 'confidence')
    return lastConf > firstConf + 0.08 ? 'improving' : lastConf < firstConf - 0.08 ? 'declining' : 'stable'
  })()

  function phaseDescription(phase: { label: string; points: any[] }, idx: number) {
    const conf = phaseAvg(phase.points, 'confidence')
    const stress = phaseAvg(phase.points, 'stress')
    const eng = phaseAvg(phase.points, 'engagement')
    if (idx === 0) {
      if (conf < 0.55) return 'The candidate entered cautiously, with initial signals suggesting adjustment to the interview environment.'
      if (stress > 0.40) return 'Opening signals showed elevated physiological stress alongside adequate verbal confidence — a common pattern in structured interview settings.'
      return 'The candidate entered with clear confidence and stable vocal delivery, establishing a strong foundation early.'
    }
    if (idx === 1) {
      if (conf > 0.70) return 'Communication stabilised in the middle segment, with confidence and structure both consolidating around above-baseline levels.'
      if (eng < 0.55) return 'Mid-session engagement showed some variability, though core communication quality remained consistent.'
      return 'The middle phase showed consistent behavioural alignment, with verbal and non-verbal signals reinforcing each other across most response types.'
    }
    const earlier = phaseAvg(phases[0].points, 'confidence')
    if (conf > earlier + 0.05) return 'Closing performance strengthened relative to the opening. Confidence and consistency both improved as the session progressed — a positive indicator of resilience and adaptability.'
    if (conf < earlier - 0.05) return 'Closing signals showed slight fatigue or disengagement compared to the opening. This pattern warrants attention in extended evaluation formats.'
    return 'Behavioural consistency was maintained through the closing segment, with no significant deviations from mid-session performance levels.'
  }

  const arcIcon = overallTrend === 'improving'
    ? <TrendingUp className="w-4 h-4 text-status-success" />
    : overallTrend === 'declining'
    ? <TrendingDown className="w-4 h-4 text-status-danger" />
    : <Minus className="w-4 h-4 text-text-muted" />

  return (
    <div className="space-y-5">
      {arc && (
        <div className="flex items-start gap-3 rounded-xl border border-border bg-bg-card p-4">
          {arcIcon}
          <div>
            <p className="text-xs font-semibold text-text-primary capitalize mb-1">Arc: {overallTrend}</p>
            <p className="text-xs text-text-secondary leading-relaxed">{arc.description}</p>
            {arc.deltas && (
              <div className="flex flex-wrap gap-4 mt-2">
                {Object.entries(arc.deltas as Record<string, number>).map(([k, v]) => (
                  <span key={k} className="flex items-center gap-1 text-2xs">
                    <span className="text-text-muted capitalize">{k}</span>
                    <span className={cn('font-mono font-bold', v > 0 ? 'text-status-success' : v < 0 ? 'text-status-danger' : 'text-text-muted')}>
                      {v > 0 ? '+' : ''}{v.toFixed(1)}pp
                    </span>
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      <div className="grid grid-cols-3 gap-3">
        {phases.map((phase, idx) => (
          <div key={phase.label} className="rounded-xl border border-border bg-bg-card p-4">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-2xs font-mono text-text-disabled">{String(idx + 1).padStart(2, '0')}</span>
              <span className="text-xs font-semibold text-text-primary">{phase.label}</span>
            </div>
            <p className="text-2xs text-text-secondary leading-relaxed">{phaseDescription(phase, idx)}</p>
            <div className="flex gap-3 mt-3 pt-2 border-t border-border-subtle">
              {JOURNEY_DIMS.map(d => (
                <div key={d.key} className="flex items-center gap-1">
                  <span className="w-1 h-1 rounded-full flex-shrink-0" style={{ background: d.color }} />
                  <span className="text-2xs font-mono" style={{ color: d.color }}>
                    {Math.round(phaseAvg(phase.points, d.key) * 100)}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── 5. Evidence Explorer ──────────────────────────────────────────────────────

const EVIDENCE_LEVELS: Record<string, { label: string; color: string; bg: string }> = {
  supporting:    { label: 'Supporting',    color: 'text-status-success',  bg: 'bg-status-success/10 border-status-success/20' },
  contextual:    { label: 'Contextual',    color: 'text-status-warning',  bg: 'bg-status-warning/10 border-status-warning/20' },
  contradicting: { label: 'Contradicting', color: 'text-status-danger',   bg: 'bg-status-danger/10  border-status-danger/20' },
  weak:          { label: 'Weak',          color: 'text-text-muted',      bg: 'bg-bg-hover border-border' },
}

const EVIDENCE_DESCRIPTIONS: Record<string, string> = {
  confidence: 'Vocal energy, language assertiveness, and absence of hedging language across the session.',
  stress: 'Physiological stress indicators including vocal tension, facial micro-expressions, and hesitation patterns.',
  engagement: 'Active presence, response depth, and alignment between verbal content and non-verbal signals.',
  communication: 'Structural clarity, speaking pace, filler word frequency, and response organisation.',
  consistency: 'Cross-modal alignment between what was said, how it was said, and facial signal patterns.',
  composure: 'Inverse stress — the degree to which physiological composure was maintained under questioning pressure.',
}

function EvidenceExplorer({ narrative }: { narrative: any }) {
  const [activeTab, setActiveTab] = useState<string>('supporting')

  const eq = narrative?.evidence_quality
  if (!eq) return null

  const dims = ['confidence', 'communication', 'engagement', 'consistency', 'composure', 'stress'] as const
  const grouped: Record<string, typeof dims[number][]> = { supporting: [], contextual: [], contradicting: [], weak: [] }
  dims.forEach(d => { const level = eq[d] ?? 'weak'; if (level in grouped) grouped[level].push(d) })
  const tabs = Object.entries(grouped).filter(([, items]) => items.length > 0)

  return (
    <div className="rounded-xl border border-border bg-bg-card overflow-hidden">
      {/* Tab bar */}
      <div className="flex border-b border-border overflow-x-auto">
        {tabs.map(([level, items]) => {
          const meta = EVIDENCE_LEVELS[level]
          return (
            <button
              key={level}
              onClick={() => setActiveTab(level)}
              className={cn(
                'flex items-center gap-1.5 px-4 py-3 text-xs font-medium transition-colors border-b-2 -mb-px whitespace-nowrap',
                activeTab === level
                  ? `border-current ${meta.color}`
                  : 'border-transparent text-text-muted hover:text-text-secondary',
              )}
            >
              {meta.label}
              <span className={cn('text-2xs font-mono px-1.5 py-0.5 rounded-full border', meta.bg)}>
                {items.length}
              </span>
            </button>
          )
        })}
      </div>

      {/* Items */}
      <div className="p-5 space-y-3 tab-content">
        {(grouped[activeTab] ?? []).map(dim => {
          const meta = EVIDENCE_LEVELS[eq[dim] ?? 'weak']
          return (
            <div key={dim} className="flex items-start gap-4 py-3 border-b border-border-subtle last:border-0">
              <div className={cn('mt-0.5 px-2 py-0.5 rounded border text-2xs font-semibold flex-shrink-0', meta.bg, meta.color)}>
                {meta.label}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-semibold text-text-primary capitalize mb-0.5">{dim}</p>
                <p className="text-2xs text-text-muted leading-relaxed">{EVIDENCE_DESCRIPTIONS[dim] ?? ''}</p>
              </div>
            </div>
          )
        })}
        {(eq.data_quality ?? []).length > 0 && activeTab === 'supporting' && (
          <div className="mt-3 pt-3 border-t border-border-subtle">
            {(eq.data_quality as string[]).map((note: string, i: number) => (
              <p key={i} className="text-2xs text-text-disabled">{note}</p>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ── 6. Question-by-question review ───────────────────────────────────────────

const DEMO_QUESTIONS = [
  {
    id: 'q1',
    question: 'Can you walk me through a technically complex project you led end-to-end?',
    transcript: 'We were rebuilding the entire data pipeline from scratch — moving from a monolithic ETL to a streaming architecture using Kafka and Flink. The tricky part was maintaining backward compatibility while migrating. I set up a dual-write phase, ran both systems in parallel for two weeks, then cut over incrementally service by service.',
    behavioral_before: 'Moderate hesitation (2.1s pause). Confidence index 61% — below session average.',
    behavioral_during: 'Confidence increased markedly once the candidate shifted from framing the problem to describing the solution. Engagement index peaked at 81%.',
    behavioral_after: 'Post-response composure was high. Brief reflective pause consistent with cognitive processing.',
    voice: 'Structured delivery. Speaking pace 142 wpm — within optimal range. Zero filler words. Slight upward inflection on key technical claims.',
    facial: 'Direct gaze maintained throughout. Nodding affirmation on "incremental." Brief micro-smile at close.',
    evidence_summary: 'Strong supporting evidence for confidence and communication claims. Response structure above baseline.',
    reliability: 'High',
  },
  {
    id: 'q2',
    question: 'How do you approach trade-offs between delivery speed and system quality under pressure?',
    transcript: 'I push back on the false dichotomy first. In my experience, the highest-risk path is usually the fastest short-term one. I try to make the cost of shortcuts visible immediately — tech debt tracking, explicit architecture decision records. When there is a genuine trade-off, I prefer reversible decisions. Ship the working version, leave a clean migration path.',
    behavioral_before: 'Confidence high (78%). No hesitation markers. The topic appears to be a prepared area of strength.',
    behavioral_during: 'Consistent engagement throughout. Communication quality peaked at 83%. Language assertive without being defensive.',
    behavioral_after: 'Natural transition. No reconsideration markers.',
    voice: 'Crisp articulation, natural pace, well-structured. 1 filler word ("um"). Strong prosodic emphasis on "reversible."',
    facial: 'Engaged and forward-leaning posture. Sustained eye contact. Expressive throughout — positive affect markers.',
    evidence_summary: 'Strong supporting evidence across confidence, communication, and consistency dimensions.',
    reliability: 'High',
  },
  {
    id: 'q3',
    question: 'Describe a time you received difficult feedback. How did you respond?',
    transcript: 'My manager told me my code reviews were too detailed — that I was slowing the team down. That was hard to hear because I thought I was being thorough. I took a week to observe how others did reviews, then changed my approach: I flag only the things that would cause production issues or serious technical debt. Everything else I comment, but not block on.',
    behavioral_before: 'Brief hesitation (1.8s). Mild stress elevation — expected for introspective questions.',
    behavioral_during: 'Stress elevated slightly early (38%), then normalised. Candidate self-corrected language twice — a positive self-awareness marker.',
    behavioral_after: 'Composure fully recovered. Engagement recovered to session-average levels.',
    voice: 'Slightly slower pace early in response (118 wpm vs 142 wpm average). 2 hesitation events. Recovery was clean.',
    facial: 'Brief gaze aversion during hesitation period. Maintained composure overall — no strong negative affect markers.',
    evidence_summary: 'Contextual evidence for stress response. Supporting evidence for self-regulation and communication adaptability.',
    reliability: 'Moderate',
  },
]

function QuestionCard({ q, index }: { q: typeof DEMO_QUESTIONS[0]; index: number }) {
  const [open, setOpen] = useState(false)
  const reliabilityColor = q.reliability === 'High' ? 'text-status-success' : q.reliability === 'Moderate' ? 'text-status-warning' : 'text-text-muted'

  return (
    <div className="rounded-xl border border-border bg-bg-card overflow-hidden">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-start gap-4 p-5 text-left group hover:bg-bg-hover/50 transition-colors"
      >
        <span className="text-sm font-mono text-text-disabled mt-0.5 flex-shrink-0 w-5">{index + 1}.</span>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-text-primary leading-snug group-hover:text-accent transition-colors">
            {q.question}
          </p>
          <div className="flex items-center gap-3 mt-1.5">
            <span className={cn('text-2xs font-medium', reliabilityColor)}>Reliability: {q.reliability}</span>
          </div>
        </div>
        {open ? <ChevronUp className="w-4 h-4 text-text-muted flex-shrink-0 mt-0.5" /> : <ChevronDown className="w-4 h-4 text-text-muted flex-shrink-0 mt-0.5" />}
      </button>

      {open && (
        <div className="border-t border-border tab-content">
          {/* Transcript */}
          <div className="px-5 pt-4 pb-3">
            <p className="label-xs text-text-disabled mb-2">Transcript</p>
            <p className="text-xs text-text-secondary leading-relaxed italic border-l-2 border-border pl-3">{q.transcript}</p>
          </div>

          {/* Behavioral observations */}
          <div className="grid md:grid-cols-3 gap-px bg-border">
            {[
              { label: 'Before', icon: Target, text: q.behavioral_before },
              { label: 'During', icon: Zap,    text: q.behavioral_during },
              { label: 'After',  icon: BarChart3, text: q.behavioral_after },
            ].map(({ label, icon: Icon, text }) => (
              <div key={label} className="bg-bg-card px-4 py-3">
                <div className="flex items-center gap-1.5 mb-1.5">
                  <Icon className="w-3 h-3 text-text-disabled" />
                  <span className="label-xs text-text-disabled">{label}</span>
                </div>
                <p className="text-2xs text-text-muted leading-relaxed">{text}</p>
              </div>
            ))}
          </div>

          {/* Voice + facial + evidence */}
          <div className="grid md:grid-cols-3 gap-px bg-border">
            {[
              { label: 'Voice', icon: Mic, text: q.voice },
              { label: 'Facial', icon: Eye, text: q.facial },
              { label: 'Evidence', icon: Shield, text: q.evidence_summary },
            ].map(({ label, icon: Icon, text }) => (
              <div key={label} className="bg-bg-card px-4 py-3 pb-4">
                <div className="flex items-center gap-1.5 mb-1.5">
                  <Icon className="w-3 h-3 text-text-disabled" />
                  <span className="label-xs text-text-disabled">{label}</span>
                </div>
                <p className="text-2xs text-text-muted leading-relaxed">{text}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function QuestionReview({ isDemo }: { isDemo: boolean }) {
  if (!isDemo) {
    return (
      <div className="rounded-xl border border-border bg-bg-card p-8 text-center">
        <MessageSquare className="w-8 h-8 text-text-disabled mx-auto mb-3" />
        <p className="text-sm font-semibold text-text-primary mb-1">Question-Level Analysis</p>
        <p className="text-xs text-text-muted max-w-sm mx-auto">
          Question segmentation is available when sessions are recorded with structured interviewing mode enabled.
        </p>
      </div>
    )
  }
  return (
    <div className="space-y-3">
      {DEMO_QUESTIONS.map((q, i) => <QuestionCard key={q.id} q={q} index={i} />)}
    </div>
  )
}

// ── 7. Coaching priorities ────────────────────────────────────────────────────

const COACHING_WINDOWS: Record<string, string> = {
  stress:       '2–4 sessions',
  engagement:   '3–5 sessions',
  confidence:   '2–3 sessions',
  communication:'1–2 sessions',
  default:      '2–4 sessions',
}

function CoachingPriorities({ narrative }: { narrative: any }) {
  const ds = narrative?.decision_support
  if (!ds) return null

  const concerns = ds.concerns as string[] ?? []
  const strengths = ds.strengths as string[] ?? []
  const followUp = narrative?.follow_up_questions as string[] ?? []

  function windowFor(text: string): string {
    const lower = text.toLowerCase()
    for (const key of Object.keys(COACHING_WINDOWS)) {
      if (lower.includes(key)) return COACHING_WINDOWS[key]
    }
    return COACHING_WINDOWS.default
  }

  return (
    <div className="space-y-6">
      {/* Coaching priorities */}
      {concerns.length > 0 && (
        <div className="space-y-3">
          <p className="label-xs text-text-disabled">Coaching Priorities</p>
          {concerns.map((concern, i) => (
            <div key={i} className="rounded-xl border border-status-warning/20 bg-status-warning/[0.03] p-5">
              <div className="flex items-start justify-between gap-3 mb-3">
                <div className="flex items-center gap-2">
                  <span className="text-2xs font-mono text-status-warning/70 font-bold">P{i + 1}</span>
                  <span className="text-sm font-semibold text-text-primary">{concern}</span>
                </div>
                <span className="text-2xs text-text-muted flex-shrink-0">Est. {windowFor(concern)}</span>
              </div>
              <div className="grid sm:grid-cols-3 gap-3 text-2xs">
                <div>
                  <p className="label-xs text-text-disabled mb-1">Expected Impact</p>
                  <p className="text-text-muted leading-relaxed">Improves perceived confidence and cross-modal consistency scores.</p>
                </div>
                <div>
                  <p className="label-xs text-text-disabled mb-1">Evidence</p>
                  <p className="text-text-muted leading-relaxed">Observed across multiple questions; consistent with session arc data.</p>
                </div>
                <div>
                  <p className="label-xs text-text-disabled mb-1">Confidence</p>
                  <p className="text-status-warning font-medium">Moderate — single session baseline</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Validated strengths */}
      {strengths.length > 0 && (
        <div className="space-y-2">
          <p className="label-xs text-text-disabled">Validated Strengths</p>
          <div className="rounded-xl border border-border bg-bg-card p-5 space-y-2">
            {strengths.map((s, i) => (
              <div key={i} className="flex items-start gap-2.5">
                <CheckCircle className="w-3.5 h-3.5 text-status-success mt-0.5 flex-shrink-0" />
                <p className="text-xs text-text-secondary">{s}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Follow-up questions */}
      {followUp.length > 0 && (
        <div className="space-y-2">
          <p className="label-xs text-text-disabled">Suggested Follow-Up Questions</p>
          <div className="rounded-xl border border-border bg-bg-card p-5 space-y-3">
            {followUp.map((q, i) => (
              <div key={i} className="flex items-start gap-3">
                <span className="text-2xs font-mono text-text-disabled mt-0.5 w-4 flex-shrink-0">{i + 1}.</span>
                <p className="text-xs text-text-secondary leading-relaxed">{q}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {ds.human_review_rationale && (
        <p className="text-2xs text-text-disabled">{ds.human_review_rationale}</p>
      )}
    </div>
  )
}

// ── 8. Platform intelligence stubs ───────────────────────────────────────────

function PlatformStub({ icon: Icon, label, description }: { icon: React.ElementType; label: string; description: string }) {
  return (
    <div className="rounded-xl border border-border bg-bg-card p-5 flex items-start gap-4">
      <div className="w-8 h-8 rounded-lg bg-accent/8 border border-accent/15 flex items-center justify-center flex-shrink-0">
        <Icon className="w-4 h-4 text-accent/60" />
      </div>
      <div>
        <p className="text-xs font-semibold text-text-primary mb-1">{label}</p>
        <p className="text-2xs text-text-muted leading-relaxed">{description}</p>
      </div>
    </div>
  )
}

// ── Reasoning section (pure display, narrative passed as prop) ────────────────

const NARRATIVE_DIMS = [
  { key: 'confidence',    label: 'Confidence',    color: '#818cf8' },
  { key: 'composure',     label: 'Composure',     color: '#f87171' },
  { key: 'communication', label: 'Communication', color: '#60a5fa' },
  { key: 'engagement',    label: 'Engagement',    color: '#34d399' },
]

function ReasoningSection({ narrative, loading }: { narrative: any; loading: boolean }) {
  if (loading) return (
    <div className="space-y-3">
      {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-24 w-full" />)}
    </div>
  )
  if (!narrative) return (
    <div className="flex items-center gap-3 px-4 py-3 border border-border text-xs text-text-muted rounded-xl">
      <AlertCircle className="w-4 h-4 flex-shrink-0" />
      Narrative reasoning unavailable for this session.
    </div>
  )

  const n   = narrative.narrative ?? {}
  const arc = narrative.behavioral_arc
  const contradictions: any[] = narrative.contradictions ?? []

  return (
    <div className="space-y-6">
      {/* Opening */}
      {n.opening && (
        <div className="border-l-2 border-accent/40 pl-5 py-1">
          <p className="text-sm text-text-secondary leading-relaxed">{n.opening}</p>
        </div>
      )}

      {/* Per-dimension */}
      <div className="grid md:grid-cols-2 gap-4">
        {NARRATIVE_DIMS.map(({ key, label, color }) => {
          const text = n[key]
          if (!text) return null
          const score = narrative.dimensions?.[key] ?? 0
          const scoreVal = typeof score === 'number' && score > 1 ? score : Math.round((score as number) * 100)
          return (
            <div key={key} className="rounded-xl border border-border bg-bg-card p-5">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: color }} />
                  <span className="text-xs font-semibold text-text-primary">{label}</span>
                </div>
                <span className="text-xs font-mono text-text-muted">{scoreVal}%</span>
              </div>
              <p className="text-xs text-text-secondary leading-relaxed">{text}</p>
            </div>
          )
        })}
      </div>

      {/* Signal contradictions */}
      {contradictions.length > 0 && (
        <div className="space-y-3">
          <p className="label-xs text-text-disabled flex items-center gap-2">
            <AlertTriangle className="w-3.5 h-3.5 text-status-warning" />
            Signal Contradictions ({contradictions.length})
          </p>
          {contradictions.map((c: any, i: number) => (
            <div key={i} className="rounded-xl border border-status-warning/20 bg-status-warning/[0.03] p-5">
              <div className="flex flex-wrap gap-2 mb-2">
                <span className="text-2xs px-2 py-0.5 rounded border border-border text-text-muted">{c.signal_a}</span>
                <span className="text-2xs px-2 py-0.5 rounded border border-border text-text-muted">{c.signal_b}</span>
                {c.review_required && (
                  <span className="text-2xs px-2 py-0.5 rounded-full border border-status-warning/30 text-status-warning bg-status-warning/5">Review</span>
                )}
              </div>
              <p className="text-xs text-text-secondary leading-relaxed">{c.interpretation}</p>
            </div>
          ))}
        </div>
      )}

      {/* Analysis recommendation */}
      {n.recommendation && (
        <div className="rounded-xl border border-border bg-bg-card p-5">
          <div className="flex items-center gap-2 mb-2">
            <ChevronRight className="w-4 h-4 text-text-primary flex-shrink-0" />
            <span className="label-xs text-text-disabled">Analysis Recommendation</span>
          </div>
          <p className="text-sm text-text-secondary leading-relaxed">{n.recommendation}</p>
        </div>
      )}
    </div>
  )
}

// ── Recruiter Validation panel ────────────────────────────────────────────────

const RECRUITER_RATINGS = [
  { value: 'helpful',         label: 'Helpful' },
  { value: 'not_helpful',     label: 'Not Helpful' },
  { value: 'needs_review',    label: 'Needs Review' },
  { value: 'incorrect',       label: 'Incorrect' },
  { value: 'missing_context', label: 'Missing Context' },
]

const HIRING_DECISIONS = [
  { value: 'strong_hire', label: 'Strong Hire' },
  { value: 'hire',        label: 'Hire' },
  { value: 'hold',        label: 'Hold' },
  { value: 'reject',      label: 'Reject' },
]

function RecruiterValidationPanel({ sessionId, isDemo }: { sessionId: string; isDemo: boolean }) {
  const [rating, setRating]   = useState('')
  const [decision, setDecision] = useState('')
  const [comment, setComment] = useState('')
  const [saving, setSaving]   = useState(false)
  const [saved, setSaved]     = useState(false)
  const [tab, setTab]         = useState<'rating' | 'decision'>('rating')

  async function submitRating() {
    if (!rating || saving || isDemo) return
    setSaving(true)
    try { await cbipApi.recruiterFeedback(sessionId, rating, undefined, comment || undefined); setSaved(true) }
    catch { /* optional */ } finally { setSaving(false) }
  }

  async function submitDecision() {
    if (!decision || saving || isDemo) return
    setSaving(true)
    try { await cbipApi.hiringDecision(sessionId, decision, undefined, undefined, comment || undefined); setSaved(true) }
    catch { /* optional */ } finally { setSaving(false) }
  }

  if (isDemo) return null

  return (
    <section className="space-y-4 pt-8 border-t border-border no-print">
      <div className="flex items-center gap-2">
        <h2 className="label-xs text-text-muted">Recruiter Validation</h2>
        <span className="text-2xs px-2 py-0.5 rounded-full border border-border text-text-disabled bg-bg-hover">
          Optional · Improves platform knowledge
        </span>
      </div>
      <div className="rounded-xl border border-border bg-bg-card p-5">
        {saved ? (
          <div className="flex items-center gap-2 text-sm text-status-success py-2">
            <span className="w-1.5 h-1.5 rounded-full bg-status-success" />
            Validation recorded. Thank you — this improves the platform&apos;s knowledge confidence.
          </div>
        ) : (
          <>
            <div className="flex gap-1 mb-4 border-b border-border">
              {(['rating', 'decision'] as const).map(t => (
                <button key={t} onClick={() => setTab(t)}
                  className={cn('px-3 py-1.5 text-xs font-medium transition-colors border-b-2 -mb-px',
                    tab === t ? 'border-text-primary text-text-primary' : 'border-transparent text-text-muted hover:text-text-secondary'
                  )}>
                  {t === 'rating' ? 'Analysis Rating (L3)' : 'Hiring Decision (L4)'}
                </button>
              ))}
            </div>
            {tab === 'rating' ? (
              <div className="space-y-3">
                <p className="text-xs text-text-muted">Rate the quality of this behavioural analysis.</p>
                <div className="flex flex-wrap gap-2">
                  {RECRUITER_RATINGS.map(r => (
                    <button key={r.value} onClick={() => setRating(r.value)}
                      className={cn('px-3 py-1.5 text-xs rounded border transition-colors',
                        rating === r.value ? 'border-text-primary bg-accent-glow text-text-primary font-medium' : 'border-border text-text-muted hover:border-border-active hover:text-text-secondary'
                      )}>
                      {r.label}
                    </button>
                  ))}
                </div>
                <textarea value={comment} onChange={e => setComment(e.target.value)} placeholder="Optional comment…" rows={2}
                  className="w-full text-xs bg-bg-input border border-border rounded-none px-3 py-2 text-text-primary placeholder:text-text-muted resize-none focus:outline-none focus:ring-1 focus:ring-text-primary" />
                <button onClick={submitRating} disabled={!rating || saving}
                  className="px-4 py-1.5 text-xs font-medium rounded border border-border text-text-secondary hover:text-text-primary hover:border-border-active disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
                  {saving ? 'Saving…' : 'Submit Rating'}
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                <p className="text-xs text-text-muted">Record the hiring outcome for this session.</p>
                <div className="flex flex-wrap gap-2">
                  {HIRING_DECISIONS.map(d => (
                    <button key={d.value} onClick={() => setDecision(d.value)}
                      className={cn('px-3 py-1.5 text-xs rounded border transition-colors',
                        decision === d.value ? 'border-text-primary bg-accent-glow text-text-primary font-medium' : 'border-border text-text-muted hover:border-border-active hover:text-text-secondary'
                      )}>
                      {d.label}
                    </button>
                  ))}
                </div>
                <textarea value={comment} onChange={e => setComment(e.target.value)} placeholder="Optional notes…" rows={2}
                  className="w-full text-xs bg-bg-input border border-border rounded-none px-3 py-2 text-text-primary placeholder:text-text-muted resize-none focus:outline-none focus:ring-1 focus:ring-text-primary" />
                <button onClick={submitDecision} disabled={!decision || saving}
                  className="px-4 py-1.5 text-xs font-medium rounded border border-border text-text-secondary hover:text-text-primary hover:border-border-active disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
                  {saving ? 'Saving…' : 'Submit Decision'}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  )
}

// ── Section wrapper ───────────────────────────────────────────────────────────

function Section({ categoryLabel, heading, children, className, collapsible, defaultCollapsed = false }: {
  categoryLabel: string; heading: string; children: React.ReactNode; className?: string
  collapsible?: boolean; defaultCollapsed?: boolean
}) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed)
  return (
    <section className={cn('space-y-5 pt-6 border-t border-border', collapsed && 'space-y-0', className)}>
      <div
        className={cn('flex items-center justify-between', collapsible && 'cursor-pointer select-none group')}
        onClick={collapsible ? () => setCollapsed(v => !v) : undefined}
        role={collapsible ? 'button' : undefined}
        tabIndex={collapsible ? 0 : undefined}
        onKeyDown={collapsible ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setCollapsed(v => !v) } } : undefined}
        aria-expanded={collapsible ? !collapsed : undefined}
      >
        <div>
          <p className="label-xs text-text-disabled mb-1">{categoryLabel}</p>
          <h2 className={cn('text-base font-bold text-text-primary', collapsible && 'group-hover:text-accent transition-colors')}>{heading}</h2>
        </div>
        {collapsible && (
          <div className="p-1 rounded-lg text-text-muted group-hover:text-text-secondary group-hover:bg-bg-hover transition-colors ml-4 flex-shrink-0">
            {collapsed ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
          </div>
        )}
      </div>
      {!collapsed && children}
    </section>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function SessionResultsPage({ params }: { params: { id: string } }) {
  const [data,            setData]            = useState<any | null>(null)
  const [loading,         setLoading]         = useState(true)
  const [error,           setError]           = useState<string | null>(null)
  const [narrative,       setNarrative]       = useState<any | null>(null)
  const [narrativeLoading, setNarrativeLoading] = useState(true)
  const [transcriptOpen,  setTranscriptOpen]  = useState(false)
  const [techOpen,        setTechOpen]        = useState(false)

  const isDemo = params.id === 'demo'

  useEffect(() => {
    let mounted = true
    if (isDemo) {
      setData(DEMO_SESSION)
      setLoading(false)
      setNarrative(DEMO_NARRATIVE)
      setNarrativeLoading(false)
      return
    }
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const res = await api.getSessionDetail(params.id)
        if (mounted) setData(res)
      } catch {
        if (mounted) setError('Could not load session data.')
      } finally {
        if (mounted) setLoading(false)
      }
    }
    load()
    return () => { mounted = false }
  }, [params.id, isDemo])

  useEffect(() => {
    if (isDemo || !data) return
    let mounted = true
    setNarrativeLoading(true)
    api.getSessionNarrative(params.id)
      .then(d => { if (mounted) { setNarrative(d); setNarrativeLoading(false) } })
      .catch(() => { if (mounted) setNarrativeLoading(false) })
    return () => { mounted = false }
  }, [data, isDemo, params.id])

  const s        = data ?? {}
  const conf     = s.avg_confidence    ?? 0
  const eng      = s.avg_engagement    ?? 0
  const comm     = s.avg_communication ?? 0
  const consis   = s.avg_consistency   ?? 0
  const stress   = s.avg_stress        ?? 0
  const composure = 1 - stress
  const overallScore = Math.round((conf + eng + comm + consis + composure) / 5 * 100)

  const fingerprintData = { confidence: conf, communication: comm, engagement: eng, stress, consistency: consis }
  const insights: BehavioralInsight[] = s.insights ?? []
  const timeline = toTimelineData(s.timeline ?? [])
  const transcriptEntries = parseTranscript(s.transcript ?? '')

  const execSummary = buildExecSummary(s, overallScore)
  const rec         = buildRecommendation(overallScore, stress, conf)
  const tier        = overallScore >= 75 ? 'Proceed' : overallScore >= 55 ? 'Review' : 'Hold'

  function handleShare() {
    navigator.clipboard.writeText(window.location.href)
      .then(() => toast('success', 'Report link copied to clipboard'))
      .catch(() => toast('error', 'Could not copy link — try copying the URL manually'))
  }

  return (
    <AppShell
      title="Behavioral Report"
      actions={
        <div className="flex items-center gap-2 no-print">
          <Button variant="ghost" size="sm" icon={<Share2 className="w-3.5 h-3.5" />} onClick={handleShare}>
            Share
          </Button>
          <AtsExportButton sessionId={params.id} isDemo={isDemo} candidateName={s.name} />
          <Button variant="secondary" size="sm" icon={<Download className="w-3.5 h-3.5" />} onClick={() => setTimeout(() => window.print(), 300)}>
            Export Report
          </Button>
        </div>
      }
    >
      <WorkflowBar candidateName={s.name} sessionId={params.id} tier={loading ? '' : tier} isDemo={isDemo} />
      <div className="p-6 space-y-0 max-w-4xl mx-auto report-print print:p-0 print:max-w-full">

        {/* Demo banner */}
        {isDemo && (
          <div className="flex items-center gap-3 rounded-none border-b border-border bg-bg-hover px-4 py-3 no-print -mx-6 mb-6">
            <FlaskConical className="w-4 h-4 text-text-primary flex-shrink-0" />
            <p className="text-xs font-semibold text-text-primary flex-1">Demo Session — Synthetic data</p>
            <Link href="/session/new"><Button variant="outline" size="xs">Start real session</Button></Link>
          </div>
        )}

        {error && (
          <div className="flex items-center gap-3 px-4 py-3 border border-border rounded-xl mb-6">
            <AlertCircle className="w-4 h-4 text-status-warning flex-shrink-0" />
            <p className="text-xs text-status-warning">{error}</p>
          </div>
        )}

        {loading ? (
          <div className="space-y-6">
            <Skeleton className="h-64 w-full" />
            <Skeleton className="h-48 w-full" />
            <Skeleton className="h-32 w-full" />
          </div>
        ) : (
          <div className="space-y-0">

            {/* ── 1. Executive Summary ──────────────────────────────────────── */}
            <ExecutiveSummaryCard
              s={s} overallScore={overallScore}
              conf={conf} eng={eng} comm={comm} consis={consis}
              composure={composure} stress={stress}
              execSummary={execSummary} rec={rec}
              narrative={narrative}
            />

            {/* ── 2. Behavioral Fingerprint ─────────────────────────────────── */}
            <Section categoryLabel="Behavioral Profile" heading="Fingerprint Analysis">
              <div className="grid md:grid-cols-2 gap-8 items-start">
                <div className="flex justify-center">
                  <BehavioralFingerprint data={fingerprintData} size={220} animated />
                </div>
                <div className="space-y-4">
                  {DIMS.map(d => {
                    const raw     = s[d.key] ?? 0
                    const display = d.inverted ? 1 - raw : raw
                    const level   = levelOf(display)
                    const levelColor = display >= 0.75 ? '#34d399' : display >= 0.55 ? '#fbbf24' : display >= 0.35 ? '#f97316' : '#f87171'
                    return (
                      <div key={d.key}>
                        <div className="flex items-center justify-between mb-1.5">
                          <div>
                            <span className="text-sm font-semibold text-text-primary">{d.label}</span>
                            <span className="text-2xs text-text-disabled ml-2">{d.desc}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-2xs font-medium" style={{ color: levelColor }}>{level}</span>
                            <span className="text-xs font-mono font-bold text-text-secondary w-8 text-right">
                              {Math.round(display * 100)}%
                            </span>
                          </div>
                        </div>
                        <div className="h-1 bg-border rounded-full overflow-hidden">
                          <div className="h-full rounded-full transition-all duration-1000" style={{ width: `${display * 100}%`, background: d.color }} />
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            </Section>

            {/* ── 3. Behavioral Journey ─────────────────────────────────────── */}
            {timeline.length > 0 && (
              <Section categoryLabel="Behavioral Journey" heading="Session Arc">
                <JourneyNarrative timeline={timeline} narrative={narrative} />
                <div className="mt-4">
                  <TimelineChart data={timeline} height={240} />
                </div>
                {insights.length > 0 && (
                  <div className="grid md:grid-cols-2 gap-3 mt-2">
                    {insights.map((ins, i) => <InsightCard key={i} insight={ins} compact />)}
                  </div>
                )}
              </Section>
            )}

            {/* ── 4. Reasoning Inspector ────────────────────────────────────── */}
            <Section categoryLabel="Reasoning Inspector" heading="Evidence-Based Analysis" collapsible defaultCollapsed>
              <div className="flex items-center justify-between -mt-3 mb-1">
                <p className="text-xs text-text-muted">
                  Multimodal signal interpretation, per-dimension narrative, and signal contradictions.
                </p>
                <span className="text-2xs px-2.5 py-1 rounded-full border border-accent/25 text-accent/70 bg-accent/[0.04] flex-shrink-0 ml-4">
                  AI-generated · Human review required
                </span>
              </div>
              <ReasoningSection narrative={narrative} loading={narrativeLoading} />
            </Section>

            {/* ── 5. Evidence Explorer ──────────────────────────────────────── */}
            {narrative && (
              <Section categoryLabel="Evidence Explorer" heading="Signal Evidence Quality" collapsible defaultCollapsed>
                <p className="text-xs text-text-muted -mt-3">
                  How each behavioural dimension is supported, contextual, or contradicted by the observed signals.
                </p>
                <EvidenceExplorer narrative={narrative} />
              </Section>
            )}

            {/* ── 6. Question-by-Question Review ───────────────────────────── */}
            <Section categoryLabel="Question Review" heading="Question-by-Question Analysis">
              <p className="text-xs text-text-muted -mt-3">
                Per-question behavioural breakdown — vocal, facial, and linguistic observations with evidence.
              </p>
              <QuestionReview isDemo={isDemo} />
            </Section>

            {/* ── 7. Coaching Priorities ────────────────────────────────────── */}
            {(narrative || narrativeLoading) && (
              <Section categoryLabel="Coaching & Recommendations" heading="Coaching Priorities">
                {narrativeLoading
                  ? <div className="space-y-3">{[...Array(2)].map((_, i) => <Skeleton key={i} className="h-28 w-full" />)}</div>
                  : <CoachingPriorities narrative={narrative} />
                }
              </Section>
            )}

            {/* ── 8. Platform Intelligence ──────────────────────────────────── */}
            <Section categoryLabel="Platform Intelligence" heading="Advanced Analysis">
              <div className="grid md:grid-cols-3 gap-3">
                <PlatformStub
                  icon={Brain}
                  label="Behavioral Memory"
                  description="Cross-session behavioral evolution tracking. Shows which signals improved, regressed, or remained stable since the candidate's previous sessions."
                />
                <PlatformStub
                  icon={Lightbulb}
                  label="CBIP Intelligence"
                  description="Matched behavioral archetypes, similar historical patterns, and organization-level trend relevance from the Continual Behavioral Intelligence Platform."
                />
                <PlatformStub
                  icon={TrendingUp}
                  label="Growth Forecast"
                  description="Evidence-based projection of behavioral trajectory based on session arc, prior interviews, and cohort benchmarks. Includes confidence intervals."
                />
              </div>
              <p className="text-2xs text-text-disabled mt-2">
                These modules activate as additional sessions are completed and validated by the platform.
              </p>
            </Section>

            {/* ── 9. Interview Transcript ───────────────────────────────────── */}
            <section className="pt-6 border-t border-border">
              <button onClick={() => setTranscriptOpen(v => !v)} className="w-full flex items-center gap-2 py-2 text-left group">
                <BookOpen className="w-4 h-4 text-text-disabled group-hover:text-text-muted transition-colors" />
                <span className="label-xs text-text-disabled group-hover:text-text-muted transition-colors flex-1">
                  Interview Transcript
                </span>
                <div className="flex items-center gap-2 text-2xs text-text-disabled">
                  {s.total_filler_words != null && <span>{s.total_filler_words} filler words</span>}
                  {transcriptOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                </div>
              </button>
              {transcriptOpen && (
                <div className="mt-4">
                  {transcriptEntries.length > 0 ? (
                    <div className="max-h-[480px] overflow-y-auto pr-2 border border-border rounded-xl p-4">
                      <TranscriptFeed entries={transcriptEntries} />
                    </div>
                  ) : (
                    <p className="text-sm text-text-muted py-6 text-center">No transcript available.</p>
                  )}
                </div>
              )}
            </section>

            {/* ── 10. What's Next ───────────────────────────────────────────── */}
            <WorkflowFooter isDemo={isDemo} sessionId={params.id} />

            {/* ── 11. Recruiter Validation ──────────────────────────────────── */}
            <RecruiterValidationPanel sessionId={params.id} isDemo={isDemo} />

            {/* ── 11. Technical Appendix ────────────────────────────────────── */}
            <section className="pt-4 border-t border-border">
              <button onClick={() => setTechOpen(v => !v)} className="w-full flex items-center gap-2 py-2 text-left group">
                <Shield className="w-4 h-4 text-text-disabled group-hover:text-text-muted transition-colors" />
                <span className="label-xs text-text-disabled group-hover:text-text-muted transition-colors flex-1">
                  Model Attestation
                </span>
                {techOpen ? <ChevronUp className="w-3.5 h-3.5 text-text-disabled" /> : <ChevronDown className="w-3.5 h-3.5 text-text-disabled" />}
              </button>
              {techOpen && (
                <div className="mt-4 grid lg:grid-cols-2 gap-6">
                  <ExplainabilityPanel session={s} />
                  <ModelTransparencyCard session={s} />
                </div>
              )}
            </section>

          </div>
        )}

      </div>
    </AppShell>
  )
}
