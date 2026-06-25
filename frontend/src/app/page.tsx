'use client'

import { useEffect, useRef, useCallback } from 'react'
import Link from 'next/link'
import dynamic from 'next/dynamic'
import {
  BrainCircuit, ArrowRight, Eye, Mic, MessageSquare,
  Shield, CheckCircle, Github, AlertTriangle, Users, FileX, Brain,
  Database, Lock, LineChart, Building2, GitBranch, Layers, Activity,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import ShinyText from '@/components/animations/ShinyText'
import TrueFocus from '@/components/animations/TrueFocus/TrueFocus'

const DotGrid = dynamic(() => import('@/components/animations/DotGrid'), { ssr: false })

// ── Data ──────────────────────────────────────────────────────────────────────

const NAV_LINKS = [
  { label: 'Product',    href: '#product' },
  { label: 'Research',   href: '#research' },
  { label: 'Enterprise', href: '#enterprise' },
]

const PROOF_POINTS = [
  { value: '82.4%', label: 'Model F1',         sub: 'Macro across 5 dimensions' },
  { value: '74K',   label: 'Training samples',  sub: 'Verified behavioral data' },
  { value: '< 1s',  label: 'Inference latency', sub: 'Per analysis window' },
  { value: '100%',  label: 'Local inference',   sub: 'No data leaves your server' },
]

const SIGNALS = [
  { icon: Eye,           label: 'Face',     detail: 'Eye contact · Blink rate · Head stability · Micro-tension',    color: '#818cf8' },
  { icon: Mic,           label: 'Voice',    detail: 'Pitch variance · Vocal energy · Pause ratio · Speech pace',    color: '#34d399' },
  { icon: MessageSquare, label: 'Language', detail: 'Confidence markers · Hesitation · Filler frequency · Clarity', color: '#60a5fa' },
]

const INTERVIEW_PROBLEMS = [
  {
    icon: Brain,
    color: '#f87171',
    title: 'Memory decay',
    desc: 'An interviewer assessing their eighth candidate of the day retains roughly 40% of what was said. Early impressions dominate final recall.',
  },
  {
    icon: Users,
    color: '#fbbf24',
    title: 'Evaluator inconsistency',
    desc: 'Two qualified interviewers evaluating the same candidate with the same rubric agree less than 60% of the time on final rating.',
  },
  {
    icon: FileX,
    color: '#f97316',
    title: 'No evidence trail',
    desc: 'When a hiring decision is questioned — legally or internally — there is rarely a structured record available to defend it.',
  },
  {
    icon: AlertTriangle,
    color: '#818cf8',
    title: 'Anchoring effects',
    desc: 'The first 90 seconds of an interview account for over 50% of the final rating. Everything that follows is largely confirmatory.',
  },
]

const ENTERPRISE_CARDS = [
  {
    icon: Database,
    color: '#818cf8',
    title: 'Structured candidate records',
    desc: 'Every interview generates a timestamped behavioral report with evidence, scores, and reasoning — searchable and comparable across candidates.',
  },
  {
    icon: Lock,
    color: '#34d399',
    title: 'Self-hosted, air-gapped capable',
    desc: 'All inference runs locally. Candidate data never leaves your infrastructure. GDPR and SOC 2 deployment patterns included.',
  },
  {
    icon: LineChart,
    color: '#60a5fa',
    title: 'Shortlist with confidence',
    desc: 'Compare candidates on five consistent behavioral dimensions rather than five interviewers\' subjective memories.',
  },
  {
    icon: Shield,
    color: '#fbbf24',
    title: 'Audit-ready governance',
    desc: 'Full audit trail, immutable reports, and AI decision logs meet enterprise compliance requirements out of the box.',
  },
  {
    icon: GitBranch,
    color: '#f87171',
    title: 'Multi-team, multi-role support',
    desc: 'Role-based access for recruiters, hiring managers, candidates, and admins. Isolation between organizations.',
  },
  {
    icon: Building2,
    color: '#a78bfa',
    title: 'Enterprise integrations',
    desc: 'REST and WebSocket APIs. Role definitions, permission scopes, and webhook delivery for pipeline integration.',
  },
  {
    icon: Layers,
    color: '#22d3ee',
    title: 'Calibrated, not black-box',
    desc: 'ECE calibration, drift detection, and a golden test suite catch model degradation before it reaches production.',
  },
]

const TRUST_QA = [
  {
    q: 'Does NeuroSync make hiring decisions?',
    a: 'No. NeuroSync provides structured behavioral evidence. All consequential decisions remain with the recruiter. The platform is designed as a decision-support tool, not a decision-making system.',
  },
  {
    q: 'Where is candidate data processed?',
    a: 'Entirely on your infrastructure. Audio, video, and transcripts are never transmitted to external services. The model runs locally at inference time.',
  },
  {
    q: 'How are scores explained?',
    a: 'Every score links to the specific timestamp and signal that produced it. Reasoning chains, evidence weights, and contradiction flags are inspectable by engineers and reviewers.',
  },
  {
    q: 'What happens when the model is uncertain?',
    a: 'Reliability tiers (insufficient · low · medium · high) are attached to each output based on session length and signal coverage. Uncertain outputs are flagged, not silently presented as conclusions.',
  },
  {
    q: 'How is model quality maintained over time?',
    a: 'A regression gate of 10 golden test scenarios runs before every deployment. ECE calibration scores and PSI/KL drift metrics are continuously monitored in the AI Platform dashboard.',
  },
]

// ── Animated fingerprint ──────────────────────────────────────────────────────

function AnimatedFingerprint() {
  const cx = 130, cy = 130, maxR = 90
  const dims = [
    { angle: -90,       value: 0.82, color: '#818cf8' },
    { angle: -90 + 72,  value: 0.73, color: '#34d399' },
    { angle: -90 + 144, value: 0.78, color: '#60a5fa' },
    { angle: -90 + 216, value: 0.66, color: '#fbbf24' },
    { angle: -90 + 288, value: 0.72, color: '#f87171' },
  ]
  function pt(angle: number, r: number) {
    const rad = (angle * Math.PI) / 180
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) }
  }
  const polygon = dims.map(d => pt(d.angle, d.value * maxR))
  const points  = polygon.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')

  return (
    <svg viewBox="0 0 260 260" width="240" height="240" className="select-none" aria-hidden="true">
      {[0.25, 0.5, 0.75, 1].map(r => (
        <circle key={r} cx={cx} cy={cy} r={maxR * r} fill="none" stroke="rgba(255,255,255,0.04)" strokeWidth="1" />
      ))}
      {dims.map((d, i) => {
        const end = pt(d.angle, maxR)
        return <line key={i} x1={cx} y1={cy} x2={end.x} y2={end.y} stroke="rgba(255,255,255,0.05)" strokeWidth="1" />
      })}
      <polygon
        points={points}
        fill="rgba(99,102,241,0.08)"
        stroke="rgba(129,140,248,0.4)"
        strokeWidth="1.5"
        strokeLinejoin="round"
        style={{ animation: 'breathe 4s ease-in-out infinite', transformOrigin: `${cx}px ${cy}px` }}
      />
      {dims.map((d, i) => {
        const dot = pt(d.angle, d.value * maxR)
        return (
          <g key={i}>
            <circle cx={dot.x} cy={dot.y} r="5.5" fill="none" stroke={d.color} strokeWidth="1" strokeOpacity="0.3" />
            <circle cx={dot.x} cy={dot.y} r="3" fill={d.color} />
          </g>
        )
      })}
      <text x={cx} y={cy - 6} textAnchor="middle" fill="#f4f4f5" fontSize="21"
        fontWeight="700" fontFamily="'JetBrains Mono', monospace">78</text>
      <text x={cx} y={cy + 9} textAnchor="middle" fill="rgba(161,161,170,0.5)" fontSize="7.5"
        fontFamily="Inter, sans-serif" fontWeight="600" letterSpacing="0.12em">BEHAVIORAL SCORE</text>
    </svg>
  )
}

// ── MagicRings ────────────────────────────────────────────────────────────────

function MagicRings() {
  const radii = [120, 180, 240, 300, 360, 420]
  return (
    <svg
      viewBox="0 0 900 900"
      className="absolute inset-0 w-full h-full pointer-events-none"
      aria-hidden="true"
      preserveAspectRatio="xMidYMid slice"
    >
      {radii.map((r, i) => (
        <circle
          key={r}
          cx="450"
          cy="450"
          r={r}
          fill="none"
          stroke="rgba(129,140,248,0.06)"
          strokeWidth="1"
          style={{
            animation: `breathe ${4 + i * 0.6}s ease-in-out infinite`,
            animationDelay: `${i * 0.4}s`,
            transformOrigin: '450px 450px',
          }}
        />
      ))}
    </svg>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function LandingPage() {
  const cursorLightRef = useRef<HTMLDivElement>(null)

  const handleMouseMove = useCallback((e: MouseEvent) => {
    const el = cursorLightRef.current
    if (!el) return
    el.style.background = `radial-gradient(600px at ${e.clientX}px ${e.clientY}px, rgba(99,102,241,0.04) 0%, transparent 70%)`
  }, [])

  useEffect(() => {
    window.addEventListener('mousemove', handleMouseMove, { passive: true })
    return () => window.removeEventListener('mousemove', handleMouseMove)
  }, [handleMouseMove])

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) entry.target.classList.add('visible')
        })
      },
      { threshold: 0.08 }
    )
    document.querySelectorAll('.reveal').forEach((el) => observer.observe(el))
    return () => observer.disconnect()
  }, [])

  return (
    <div className="min-h-screen bg-bg-base text-text-primary overflow-x-hidden">

      {/* Cursor radial light — direct DOM mutation, no re-renders */}
      <div
        ref={cursorLightRef}
        className="pointer-events-none fixed inset-0 z-30 transition-none"
        aria-hidden="true"
      />

      {/* ── Nav ─────────────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-50 border-b border-border/50 bg-bg-base/80 backdrop-blur-xl">
        <div className="max-w-6xl mx-auto px-6 h-[60px] flex items-center gap-8">
          <Link href="/" className="flex items-center gap-2.5 flex-shrink-0" aria-label="NuanceAI home">
            <div className="w-7 h-7 rounded-lg bg-accent-bright flex items-center justify-center shadow-glow-sm">
              <BrainCircuit className="w-[15px] h-[15px] text-white" />
            </div>
            <div className="flex flex-col leading-none">
              <span className="text-[13px] font-bold text-text-primary tracking-tight">NuanceAI</span>
              <span className="text-[9px] text-text-disabled tracking-widest uppercase font-medium mt-0.5">NeuroSync Platform</span>
            </div>
          </Link>

          <nav className="hidden lg:flex items-center gap-1 ml-2" aria-label="Site navigation">
            {NAV_LINKS.map(l => (
              <a key={l.label} href={l.href}
                className="px-3 py-1.5 text-sm text-text-muted hover:text-text-primary transition-colors rounded-md hover:bg-bg-hover">
                {l.label}
              </a>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-3">
            <Link href="/dashboard" className="hidden sm:block">
              <span className="text-sm text-text-muted hover:text-text-primary transition-colors cursor-pointer">
                Dashboard
              </span>
            </Link>
            <Link href="/session/new">
              <Button variant="primary" size="sm" iconRight={<ArrowRight className="w-3.5 h-3.5" />}>
                Start interview
              </Button>
            </Link>
          </div>
        </div>
      </header>

      {/* ── Hero ────────────────────────────────────────────────────────────── */}
      <section className="relative pt-[130px] pb-[100px] overflow-hidden">
        <div className="absolute inset-0 pointer-events-none"
          style={{
            maskImage: 'linear-gradient(to bottom, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.85) 55%, transparent 90%), linear-gradient(to right, transparent 0%, black 5%, black 95%, transparent 100%)',
            WebkitMaskImage: 'linear-gradient(to bottom, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.85) 55%, transparent 90%), linear-gradient(to right, transparent 0%, black 5%, black 95%, transparent 100%)',
          }}>
          <DotGrid dotSize={3} gap={20} baseColor="#181830" activeColor="#4855cc"
            proximity={80} shockRadius={110} shockStrength={1.0} resistance={1400}
            returnDuration={2.5} className="w-full h-full" style={{}} />
        </div>

        <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-accent/25 to-transparent pointer-events-none" />
        <div className="absolute top-[-200px] left-1/2 -translate-x-1/2 w-[900px] h-[600px]
          bg-[radial-gradient(ellipse_at_50%_30%,rgba(99,102,241,0.05)_0%,transparent_65%)] pointer-events-none" />

        <div className="relative max-w-6xl mx-auto px-6">
          <div className="max-w-[800px]">

            {/* Badge */}
            <div className="inline-flex items-center gap-2 rounded-full border border-accent/20 bg-accent/5
              px-3 py-[5px] mb-10 text-xs font-medium text-accent">
              <span className="w-1.5 h-1.5 rounded-full bg-accent-bright animate-pulse flex-shrink-0" />
              <ShinyText text="Behavioral Intelligence Platform · v1.2.0-rc1" speed={7} delay={4}
                color="rgba(129,140,248,0.8)" shineColor="#FFFFFF" spread={80} direction="left" />
            </div>

            {/* Headline — trust-first, not technology-first */}
            <h1 className="text-[clamp(2.8rem,5vw,4.2rem)] font-[800] tracking-[-0.045em] leading-[1.04]
              text-text-primary mb-6">
              Decisions that matter<br />
              deserve structured evidence.
            </h1>

            <p className="text-[1.05rem] text-text-secondary leading-[1.7] max-w-[560px] mb-10 font-[400]">
              Interviewers make consequential decisions with limited, inconsistent data. NeuroSync
              analyzes voice, face, and language simultaneously — producing auditable behavioral
              evidence your team can review, compare, and defend.
            </p>

            {/* 3-tier CTAs */}
            <div className="flex flex-wrap items-center gap-3 mb-16">
              <Link href="/session/new">
                <Button variant="primary" size="lg" iconRight={<ArrowRight className="w-4 h-4" />}>
                  Start interview
                </Button>
              </Link>
              <Link href="/session/demo/results">
                <Button variant="outline" size="lg">
                  View demo report
                </Button>
              </Link>
              <Link href="/dashboard" className="hidden sm:block">
                <Button variant="ghost" size="lg">
                  Open dashboard
                </Button>
              </Link>
            </div>

            {/* Unified metrics panel */}
            <div className="inline-flex flex-wrap gap-8 rounded-xl border border-border/60 bg-bg-card/60 px-6 py-4 backdrop-blur-sm">
              {PROOF_POINTS.map(p => (
                <div key={p.label}>
                  <p className="text-xl font-bold font-mono text-text-primary tracking-tight">{p.value}</p>
                  <p className="text-xs font-semibold text-text-secondary mt-0.5">{p.label}</p>
                  <p className="text-2xs text-text-muted">{p.sub}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── Why traditional interviews fail ──────────────────────────────────── */}
      <section className="py-24 border-t border-border reveal">
        <div className="max-w-6xl mx-auto px-6">
          <div className="mb-12 max-w-xl">
            <p className="label-xs text-accent mb-3">The problem</p>
            <h2 className="text-[clamp(1.6rem,2.8vw,2.2rem)] font-[700] tracking-[-0.03em] text-text-primary leading-[1.12] mb-4">
              Why traditional interviews fail<br />high-stakes decisions.
            </h2>
            <p className="text-sm text-text-secondary leading-relaxed">
              These are not fixable with better training. They are structural limitations of unstructured evaluation.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-4">
            {INTERVIEW_PROBLEMS.map(p => (
              <div key={p.title}
                className="rounded-xl border border-border bg-bg-card p-6 hover:border-border-strong transition-colors">
                <div className="w-9 h-9 rounded-lg flex items-center justify-center mb-4"
                  style={{ background: `${p.color}12` }}>
                  <p.icon className="w-[18px] h-[18px]" style={{ color: p.color }} />
                </div>
                <p className="text-sm font-semibold text-text-primary mb-2">{p.title}</p>
                <p className="text-xs text-text-muted leading-relaxed">{p.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Behavioral Fingerprint ───────────────────────────────────────────── */}
      <section id="product" className="py-32 border-t border-border bg-bg-surface/30 reveal">
        <div className="max-w-6xl mx-auto px-6">
          <div className="grid lg:grid-cols-2 gap-20 items-center">

            {/* Visualization */}
            <div className="flex justify-center lg:order-2">
              <div className="relative">
                <div className="relative w-[280px] h-[280px] rounded-full p-[1.5px] bg-gradient-to-br from-indigo-500/30 via-border/50 to-blue-500/30 shadow-glow-accent/5">
                  <div className="relative w-full h-full rounded-full bg-bg-card flex items-center justify-center">
                    {[
                      { label: 'Confidence',    angle: -90,       color: '#818cf8' },
                      { label: 'Engagement',    angle: -90 + 72,  color: '#34d399' },
                      { label: 'Communication', angle: -90 + 144, color: '#60a5fa' },
                      { label: 'Consistency',   angle: -90 + 216, color: '#fbbf24' },
                      { label: 'Composure',     angle: -90 + 288, color: '#f87171' },
                    ].map((d) => {
                      const rad = (d.angle * Math.PI) / 180
                      const r = 152
                      return (
                        <div key={d.label} className="absolute text-center pointer-events-none"
                          style={{ left: 139 + r * Math.cos(rad), top: 139 + r * Math.sin(rad), transform: 'translate(-50%,-50%)', width: 64 }}>
                          <div className="w-1.5 h-1.5 rounded-full mx-auto mb-0.5" style={{ background: d.color }} />
                          <p className="text-[9px] text-text-muted leading-tight font-medium">{d.label}</p>
                        </div>
                      )
                    })}
                    <AnimatedFingerprint />
                  </div>
                </div>

                <div className="absolute top-4 -right-28 hidden lg:block">
                  <div className="rounded-xl border border-border bg-bg-card p-3 w-28 shadow-card">
                    <p className="text-2xs text-text-muted mb-1">Confidence</p>
                    <p className="text-base font-bold font-mono text-metric-confidence">82%</p>
                    <div className="h-0.5 bg-bg-hover rounded-full mt-2">
                      <div className="h-full rounded-full bg-metric-confidence bar-fill" style={{ width: '82%' }} />
                    </div>
                  </div>
                </div>
                <div className="absolute bottom-6 -left-28 hidden lg:block">
                  <div className="rounded-xl border border-border bg-bg-card p-3 w-28 shadow-card">
                    <p className="text-2xs text-text-muted mb-1">Composure</p>
                    <p className="text-base font-bold font-mono text-metric-engagement">76%</p>
                    <div className="h-0.5 bg-bg-hover rounded-full mt-2">
                      <div className="h-full rounded-full bg-metric-engagement bar-fill" style={{ width: '76%' }} />
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Copy */}
            <div className="lg:order-1">
              <p className="label-xs text-accent mb-4">Behavioral Fingerprint</p>
              <h2 className="text-[clamp(1.6rem,2.8vw,2.2rem)] font-[700] tracking-[-0.03em] leading-[1.1]
                text-text-primary mb-5">
                Five dimensions.<br />One coherent view.
              </h2>

              <div className="mb-7">
                <TrueFocus
                  sentence="Confidence Communication Engagement Consistency Composure"
                  separator=" "
                  manualMode={false}
                  blurAmount={2}
                  borderColor="rgba(99,102,241,0.6)"
                  glowColor="rgba(99,102,241,0.10)"
                  animationDuration={1.8}
                  pauseBetweenAnimations={3}
                />
              </div>

              <p className="text-sm text-text-secondary leading-relaxed mb-8 max-w-md">
                Each dimension draws from three independent signal sources simultaneously.
                The final score reflects a converging behavioral state — not any single isolated metric.
              </p>

              <div className="space-y-4">
                {[
                  { color: '#818cf8', label: 'Confidence',    desc: 'Language assertiveness · vocal projection · sustained eye contact' },
                  { color: '#34d399', label: 'Engagement',    desc: 'Active presence · response energy · behavioral consistency' },
                  { color: '#60a5fa', label: 'Communication', desc: 'Structural clarity · pace · filler word frequency' },
                  { color: '#fbbf24', label: 'Consistency',   desc: 'Signal coherence — whether voice, face, and language tell the same story' },
                  { color: '#f87171', label: 'Composure',     desc: 'Inverse stress — vocal stability and facial calm under pressure' },
                ].map(d => (
                  <div key={d.label} className="flex items-start gap-3">
                    <div className="w-2 h-2 rounded-full mt-[5px] flex-shrink-0" style={{ background: d.color }} />
                    <div>
                      <span className="text-sm font-semibold text-text-primary">{d.label}</span>
                      <p className="text-xs text-text-muted mt-0.5">{d.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Signal Pipeline ──────────────────────────────────────────────────── */}
      <section className="py-32 border-t border-border reveal">
        <div className="max-w-6xl mx-auto px-6">
          <div className="mb-14 max-w-xl">
            <p className="label-xs text-accent mb-3">Signal Pipeline</p>
            <h2 className="text-[clamp(1.6rem,2.8vw,2.2rem)] font-[700] tracking-[-0.03em] text-text-primary leading-[1.12] mb-4">
              Three sources.<br />One synchronized view.
            </h2>
            <p className="text-sm text-text-secondary leading-relaxed">
              NeuroSync processes three independent signal streams in parallel. A time-windowed
              fusion layer synchronizes them into a single behavioral state, updated every 500ms.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-5 mb-14">
            {SIGNALS.map(s => (
              <div key={s.label}
                className="rounded-xl border border-border bg-bg-card p-6 hover:border-border-strong transition-colors">
                <div className="w-10 h-10 rounded-lg flex items-center justify-center mb-5"
                  style={{ background: `${s.color}12` }}>
                  <s.icon className="w-5 h-5" style={{ color: s.color }} />
                </div>
                <p className="text-sm font-semibold text-text-primary mb-2">{s.label} Analysis</p>
                <p className="text-xs text-text-muted leading-relaxed">{s.detail}</p>
              </div>
            ))}
          </div>

          <div className="grid md:grid-cols-4 gap-4">
            {[
              { step: '01', color: '#818cf8', title: 'Capture',  desc: 'Video frames and audio chunks stream to the backend via WebSocket at 500ms windows.' },
              { step: '02', color: '#34d399', title: 'Analyse',  desc: 'Face mesh, audio features, Whisper transcription, and DeBERTa inference run concurrently.' },
              { step: '03', color: '#60a5fa', title: 'Fuse',     desc: 'A sliding 3-second window synchronizes signals and computes composite behavioral scores.' },
              { step: '04', color: '#fbbf24', title: 'Explain',  desc: 'Every score links to the specific moment and signal that produced it. Evidence and reasoning are fully inspectable.' },
            ].map(s => (
              <div key={s.step} className="flex gap-3">
                <div className="w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0 text-xs font-bold font-mono mt-0.5"
                  style={{ background: `${s.color}12`, color: s.color }}>
                  {s.step}
                </div>
                <div>
                  <p className="text-sm font-semibold text-text-primary mb-1">{s.title}</p>
                  <p className="text-xs text-text-muted leading-relaxed">{s.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Research / Model card ─────────────────────────────────────────────── */}
      <section id="research" className="py-32 border-t border-border bg-bg-surface/30 reveal">
        <div className="max-w-6xl mx-auto px-6">
          <div className="grid lg:grid-cols-2 gap-16 items-start">

            {/* Model card */}
            <div className="rounded-xl border border-accent/20 bg-accent/[0.03] p-6">
              <div className="flex items-center gap-3 mb-6">
                <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
                  <BrainCircuit className="w-4 h-4 text-accent" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-text-primary">DeBERTa v3-base</p>
                  <p className="text-xs text-text-muted">LoRA fine-tuned · Production checkpoint</p>
                </div>
                <span className="ml-auto px-2.5 py-1 rounded-full bg-status-success/10 text-status-success
                  text-2xs font-semibold border border-status-success/20">
                  Active
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3 mb-6">
                {[
                  { label: 'Training samples', value: '74,288' },
                  { label: 'Trainable params',  value: '442K / 184M' },
                  { label: 'LoRA rank',          value: 'r=16, α=32' },
                  { label: 'Best checkpoint',    value: 'Step 18,000' },
                ].map(m => (
                  <div key={m.label} className="rounded-lg bg-bg-card border border-border p-3">
                    <p className="text-2xs text-text-muted">{m.label}</p>
                    <p className="text-sm font-bold font-mono text-text-primary mt-0.5">{m.value}</p>
                  </div>
                ))}
              </div>

              <p className="text-2xs text-text-disabled font-semibold uppercase tracking-widest mb-3">
                Test macro-F1 per task
              </p>
              <div className="space-y-2.5">
                {[
                  { label: 'Confidence',    f1: 0.862, color: '#818cf8' },
                  { label: 'Stress',        f1: 0.848, color: '#f87171' },
                  { label: 'Hesitation',    f1: 0.817, color: '#fbbf24' },
                  { label: 'Communication', f1: 0.769, color: '#60a5fa' },
                ].map(m => (
                  <div key={m.label} className="flex items-center gap-3">
                    <span className="text-xs text-text-muted w-24 flex-shrink-0">{m.label}</span>
                    <div className="flex-1 h-0.5 bg-bg-hover rounded-full overflow-hidden">
                      <div className="h-full rounded-full" style={{ width: `${m.f1 * 100}%`, background: m.color }} />
                    </div>
                    <span className="text-xs font-mono text-text-secondary w-10 text-right">
                      {(m.f1 * 100).toFixed(1)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Architecture copy */}
            <div>
              <p className="label-xs text-accent mb-4">Intelligence Architecture</p>
              <h2 className="text-[clamp(1.5rem,2.5vw,2rem)] font-[700] tracking-[-0.03em] text-text-primary
                leading-[1.15] mb-5">
                Reasoning,<br />not just scoring.
              </h2>
              <p className="text-sm text-text-secondary leading-relaxed mb-8">
                Every behavioral conclusion is the product of evidence extraction, contradiction
                detection, cross-modal consistency checks, and confidence calibration — not a
                single classifier output.
              </p>

              <div className="space-y-5">
                {[
                  { color: '#818cf8', title: 'Evidence Graph',           desc: 'Signals are extracted per modality and weighted by source quality before reasoning begins.' },
                  { color: '#34d399', title: 'Contradiction Detection',  desc: 'When face, voice, and language signals conflict, the system flags the contradiction rather than averaging it away.' },
                  { color: '#60a5fa', title: 'Behavioral State Machine', desc: 'State transitions over time capture arc and recovery — not just point-in-time scores.' },
                  { color: '#fbbf24', title: 'Calibrated Confidence',    desc: 'Every score includes a reliability tier: insufficient · low · medium · high — based on session length and signal coverage.' },
                ].map(s => (
                  <div key={s.title} className="flex gap-4">
                    <div className="w-1.5 rounded-full flex-shrink-0 mt-1 self-stretch" style={{ background: s.color, minHeight: 16 }} />
                    <div>
                      <p className="text-sm font-semibold text-text-primary mb-0.5">{s.title}</p>
                      <p className="text-xs text-text-muted leading-relaxed">{s.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Enterprise Platform ───────────────────────────────────────────────── */}
      <section id="enterprise" className="py-32 border-t border-border reveal">
        <div className="max-w-6xl mx-auto px-6">
          <div className="mb-14 max-w-xl">
            <p className="label-xs text-accent mb-3">Enterprise Platform</p>
            <h2 className="text-[clamp(1.6rem,2.8vw,2.2rem)] font-[700] tracking-[-0.03em] text-text-primary leading-[1.12] mb-4">
              Built for organizations<br />that need to be accountable.
            </h2>
            <p className="text-sm text-text-secondary leading-relaxed">
              NeuroSync is not a point tool. It is a governed behavioral intelligence platform —
              with multi-tenancy, compliance infrastructure, and enterprise access control built in from the start.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {ENTERPRISE_CARDS.map(c => (
              <div key={c.title}
                className="rounded-xl border border-border bg-bg-card p-5 hover:border-border-strong transition-colors">
                <div className="w-9 h-9 rounded-lg flex items-center justify-center mb-4"
                  style={{ background: `${c.color}12` }}>
                  <c.icon className="w-[18px] h-[18px]" style={{ color: c.color }} />
                </div>
                <p className="text-sm font-semibold text-text-primary mb-1.5">{c.title}</p>
                <p className="text-xs text-text-muted leading-relaxed">{c.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── AI Trust Center ───────────────────────────────────────────────────── */}
      <section className="py-24 border-t border-border bg-bg-surface/30 reveal">
        <div className="max-w-6xl mx-auto px-6">
          <div className="mb-12 max-w-lg">
            <p className="label-xs text-accent mb-3">AI Trust Center</p>
            <h2 className="text-[clamp(1.6rem,2.8vw,2.2rem)] font-[700] tracking-[-0.03em] text-text-primary leading-[1.12]">
              Questions you should<br />ask every AI vendor.
            </h2>
            <p className="text-sm text-text-secondary mt-4 leading-relaxed">
              These are ours — and we publish the answers, not the marketing copy.
            </p>
          </div>

          <div className="space-y-3 max-w-3xl">
            {TRUST_QA.map(item => (
              <div key={item.q} className="flex gap-4 rounded-xl border border-border bg-bg-card p-5">
                <CheckCircle className="w-4 h-4 text-status-success flex-shrink-0 mt-0.5" aria-hidden="true" />
                <div>
                  <p className="text-sm font-semibold text-text-primary mb-1.5">{item.q}</p>
                  <p className="text-xs text-text-muted leading-relaxed">{item.a}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ──────────────────────────────────────────────────────────────── */}
      <section className="py-32 border-t border-border relative overflow-hidden reveal">
        <MagicRings />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_50%_50%,rgba(99,102,241,0.05)_0%,transparent_60%)] pointer-events-none" />
        <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-accent/20 to-transparent" />

        <div className="relative max-w-6xl mx-auto px-6 text-center">
          <p className="label-xs text-accent mb-6">Get started</p>
          <h2 className="text-[clamp(2rem,4vw,3rem)] font-[800] tracking-[-0.04em] text-text-primary
            leading-[1.05] mb-5 max-w-2xl mx-auto">
            Structured evidence for<br />every interview decision.
          </h2>
          <p className="text-sm text-text-secondary max-w-md mx-auto mb-10 leading-relaxed">
            Self-hosted. No external configuration required. Connect a camera and microphone
            — the platform handles analysis, reporting, and audit trails.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-12">
            <Link href="/session/new">
              <Button variant="primary" size="lg" iconRight={<ArrowRight className="w-4 h-4" />}>
                Start interview
              </Button>
            </Link>
            <Link href="/session/demo/results">
              <Button variant="outline" size="lg">
                View demo report
              </Button>
            </Link>
            <Link href="/dashboard" className="hidden sm:block">
              <Button variant="ghost" size="lg">
                Open dashboard
              </Button>
            </Link>
          </div>

          <div className="flex flex-wrap justify-center gap-6 text-xs text-text-disabled">
            {[
              'Data never leaves your server',
              'Real-time behavioral analysis',
              'Human oversight by design',
              'Full audit trail',
            ].map(t => (
              <span key={t} className="flex items-center gap-2">
                <Activity className="w-3 h-3 text-text-disabled" aria-hidden="true" />
                {t}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* ── Footer ───────────────────────────────────────────────────────────── */}
      <footer className="border-t border-border py-16 bg-bg-surface/10">
        <div className="max-w-6xl mx-auto px-6">

          {/* 4-column grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-10 pb-12 border-b border-border/50">
            <div>
              <div className="flex items-center gap-2.5 mb-5">
                <div className="w-7 h-7 rounded-lg bg-accent-bright flex items-center justify-center shadow-glow-sm">
                  <BrainCircuit className="w-[14px] h-[14px] text-white" />
                </div>
                <div className="flex flex-col leading-none">
                  <span className="text-[12px] font-bold text-text-primary tracking-tight">NuanceAI</span>
                  <span className="text-[8px] text-text-disabled tracking-widest uppercase font-medium mt-0.5">NeuroSync Platform</span>
                </div>
              </div>
              <p className="text-xs text-text-muted leading-relaxed">
                Behavioral intelligence infrastructure for structured, auditable hiring.
              </p>
            </div>

            <div>
              <p className="text-2xs font-semibold uppercase tracking-widest text-text-disabled mb-4">Platform</p>
              <div className="space-y-2.5">
                {[
                  { label: 'Dashboard',     href: '/dashboard' },
                  { label: 'New interview', href: '/session/new' },
                  { label: 'History',       href: '/history' },
                  { label: 'Growth',        href: '/growth' },
                  { label: 'Demo report',   href: '/session/demo/results' },
                ].map(l => (
                  <Link key={l.label} href={l.href}
                    className="block text-sm text-text-muted hover:text-text-primary transition-colors">
                    {l.label}
                  </Link>
                ))}
              </div>
            </div>

            <div>
              <p className="text-2xs font-semibold uppercase tracking-widest text-text-disabled mb-4">Research</p>
              <div className="space-y-2.5">
                {[
                  { label: 'AI Platform',  href: '/ai-platform' },
                  { label: 'Model card',   href: '#research' },
                  { label: 'Benchmarks',   href: '/benchmarks' },
                  { label: 'Knowledge',    href: '/knowledge' },
                  { label: 'Architecture', href: '/architecture' },
                ].map(l => (
                  <Link key={l.label} href={l.href}
                    className="block text-sm text-text-muted hover:text-text-primary transition-colors">
                    {l.label}
                  </Link>
                ))}
              </div>
            </div>

            <div>
              <p className="text-2xs font-semibold uppercase tracking-widest text-text-disabled mb-4">Enterprise</p>
              <div className="space-y-2.5">
                {[
                  { label: 'Governance',    href: '/governance' },
                  { label: 'Operations',    href: '/operations' },
                  { label: 'Workspace',     href: '/workspace' },
                  { label: 'Settings',      href: '/settings' },
                  { label: 'Technical FAQ', href: '/faq' },
                ].map(l => (
                  <Link key={l.label} href={l.href}
                    className="block text-sm text-text-muted hover:text-text-primary transition-colors">
                    {l.label}
                  </Link>
                ))}
              </div>
            </div>
          </div>

          {/* Bottom bar */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-8 text-2xs text-text-disabled">
            <div className="flex items-center gap-3">
              <Shield className="w-3 h-3 text-status-success" aria-hidden="true" />
              <span>NeuroSync Behavioral Intelligence Platform · v1.2.0-rc1</span>
            </div>
            <div className="flex items-center gap-4">
              <span>DeBERTa v3-base · Whisper Fine-Tuned · MediaPipe Fusion · Local Inference</span>
              <a href="https://github.com" target="_blank" rel="noopener noreferrer"
                className="text-text-muted hover:text-text-primary transition-colors" aria-label="GitHub Repository">
                <Github className="w-4 h-4" />
              </a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}
