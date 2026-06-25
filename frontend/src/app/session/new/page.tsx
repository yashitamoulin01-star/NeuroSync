'use client'
import { useState, useEffect, useRef } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { AppShell } from '@/components/layout/AppShell'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import {
  Users, Mic2, Presentation, ChevronRight, ArrowLeft,
  Zap, Info, CheckCircle2, AlertCircle, RefreshCw, UploadCloud,
} from 'lucide-react'

const MODES = [
  {
    id: 'interview',
    icon: Users,
    label: 'Interview',
    desc: 'Candidate assessment with behavioral scoring. Tracks confidence, stress, and communication under structured questioning.',
    color: '#818cf8',
  },
  {
    id: 'coaching',
    icon: Mic2,
    label: 'Coaching',
    desc: 'Ongoing performance coaching with trend tracking. Measures improvement across sessions over time.',
    color: '#34d399',
  },
  {
    id: 'presentation',
    icon: Presentation,
    label: 'Presentation',
    desc: 'Public speaking analysis with delivery scoring. Focuses on pace, vocal energy, and audience engagement signals.',
    color: '#60a5fa',
  },
]

type BackendStatus = 'checking' | 'online' | 'warming' | 'offline'

export default function NewSessionPage() {
  const router = useRouter()
  const [mode,    setMode]    = useState<string>('interview')
  const [name,    setName]    = useState('')
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState<string | null>(null)

  const [backendStatus,  setBackendStatus]  = useState<BackendStatus>('checking')
  const [debertaReady,   setDebertaReady]   = useState(false)
  const retryCountRef = useRef(0)

  useEffect(() => {
    let mounted = true
    let timer: ReturnType<typeof setTimeout>

    async function checkBackend() {
      if (!mounted) return
      setBackendStatus('checking')
      try {
        const h = await api.healthDetailed()
        if (!mounted) return
        retryCountRef.current = 0
        setDebertaReady(h.components.deberta.checkpoint_saved)
        setBackendStatus('online')
      } catch {
        if (!mounted) return
        setBackendStatus('offline')
        const delay = Math.min(5000 * Math.pow(1.5, retryCountRef.current), 30_000)
        retryCountRef.current++
        timer = setTimeout(() => { if (mounted) checkBackend() }, delay)
      }
    }

    checkBackend()
    return () => { mounted = false; clearTimeout(timer) }
  }, [])

  async function handleStart() {
    if (!name.trim()) { setError('Session name is required.'); return }
    if (backendStatus !== 'online') { setError('Backend is not available. Please wait.'); return }
    setLoading(true)
    setError(null)
    try {
      const res = await api.createSession({
        session_name: name.trim(),
        mode: mode as 'interview' | 'coaching' | 'presentation',
      })
      router.push(`/session/${res.session_id}`)
    } catch {
      setError('Session creation failed. The backend may be starting up.')
      setLoading(false)
    }
  }

  const selectedMode = MODES.find(m => m.id === mode)!

  const statusConfig: Record<BackendStatus, {
    label: string; variant: 'success' | 'warning' | 'muted' | 'danger'; pulse: boolean
  }> = {
    checking: { label: 'Checking...', variant: 'muted', pulse: false },
    online:   { label: 'Backend ready', variant: 'success', pulse: true },
    warming:  { label: 'Warming up...', variant: 'warning', pulse: true },
    offline:  { label: 'Reconnecting...', variant: 'danger', pulse: false },
  }

  const sc = statusConfig[backendStatus]

  return (
    <AppShell title="New Session">
      <div className="p-6 max-w-2xl">
        <div className="mb-6">
          <h2 className="text-xl font-bold text-text-primary">Configure session</h2>
          <p className="text-sm text-text-muted mt-1">Choose a session type and give it a name to begin analysis.</p>
        </div>

        <div className="space-y-6">
          {/* Mode selection */}
          <div>
            <label className="label-xs text-text-muted mb-3 block">Session type</label>
            <div className="grid gap-3">
              {MODES.map(m => (
                <button
                  key={m.id}
                  onClick={() => setMode(m.id)}
                  className={cn(
                    'w-full text-left rounded-xl border p-4 transition-all duration-150',
                    mode === m.id
                      ? 'border-accent/50 bg-accent-glow shadow-glow-accent'
                      : 'border-border bg-bg-card hover:border-border-strong hover:bg-bg-hover',
                  )}
                >
                  <div className="flex items-start gap-3">
                    <div className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5"
                      style={{ background: `${m.color}15` }}>
                      <m.icon className="w-[18px] h-[18px]" style={{ color: m.color }} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-text-primary">{m.label}</span>
                        {mode === m.id && (
                          <span className="text-2xs text-accent font-medium px-1.5 py-0.5 rounded-full bg-accent/10">
                            Selected
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-text-muted mt-0.5 leading-relaxed">{m.desc}</p>
                    </div>
                    <ChevronRight className={cn(
                      'w-4 h-4 flex-shrink-0 mt-2.5 transition-colors',
                      mode === m.id ? 'text-accent' : 'text-text-disabled',
                    )} />
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Session name */}
          <div>
            <label className="label-xs text-text-muted mb-2 block" htmlFor="session-name">
              Session name
            </label>
            <input
              id="session-name"
              type="text"
              placeholder={`e.g. "Senior Engineer, Final Round"`}
              value={name}
              onChange={e => { setName(e.target.value); setError(null) }}
              onKeyDown={e => e.key === 'Enter' && handleStart()}
              className={cn(
                'w-full h-10 rounded-lg border bg-bg-card px-3 text-sm text-text-primary placeholder:text-text-disabled transition-colors',
                'focus:outline-none focus:ring-2 focus:ring-accent-bright focus:ring-offset-1 focus:ring-offset-bg-base',
                error ? 'border-status-danger' : 'border-border hover:border-border-strong',
              )}
            />
            {error && (
              <div className="flex items-center gap-1.5 mt-2 text-xs text-status-danger">
                <AlertCircle className="w-3.5 h-3.5" />
                {error}
              </div>
            )}
          </div>

          {/* Backend status */}
          <div className={cn(
            'rounded-lg border p-3.5 flex gap-3',
            backendStatus === 'offline'
              ? 'border-status-danger/30 bg-status-danger/5'
              : backendStatus === 'warming'
              ? 'border-status-warning/30 bg-status-warning/5'
              : 'border-border-subtle bg-bg-hover',
          )}>
            {backendStatus === 'offline' ? (
              <AlertCircle className="w-4 h-4 text-status-danger flex-shrink-0 mt-0.5" />
            ) : backendStatus === 'online' ? (
              <CheckCircle2 className="w-4 h-4 text-status-success flex-shrink-0 mt-0.5" />
            ) : (
              <RefreshCw className="w-4 h-4 text-text-muted flex-shrink-0 mt-0.5 animate-spin" />
            )}
            <div className="flex-1 text-xs text-text-muted leading-relaxed">
              <div className="flex items-center gap-2 mb-0.5">
                <span className={cn(
                  'font-medium',
                  backendStatus === 'offline' ? 'text-status-danger' :
                  backendStatus === 'warming' ? 'text-status-warning' :
                  backendStatus === 'online'  ? 'text-status-success' : 'text-text-secondary',
                )}>
                  {sc.label}
                </span>
                {debertaReady && backendStatus === 'online' && (
                  <Badge variant="accent" dot>DeBERTa v3 ready</Badge>
                )}
              </div>
              {backendStatus === 'offline'
                ? 'Analysis engine unavailable. Retrying automatically…'
                : backendStatus === 'online'
                ? 'Webcam and microphone required for full behavioral analysis.'
                : 'Connecting to the NeuroSync analysis engine…'}
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3">
            <Button variant="ghost" size="md" icon={<ArrowLeft className="w-4 h-4" />}
              onClick={() => router.back()}>
              Back
            </Button>
            <Button
              variant="primary" size="md"
              className="flex-1"
              icon={<Zap className="w-4 h-4" />}
              loading={loading}
              onClick={handleStart}
              disabled={backendStatus !== 'online'}
            >
              Start {selectedMode.label.toLowerCase()} session
            </Button>
          </div>

          {/* Alternative entry: analyze an existing recording */}
          <div className="flex items-center justify-center gap-2 pt-1 text-xs text-text-muted">
            <span>Already have a recording?</span>
            <Link href="/upload" className="text-accent hover:text-accent-bright font-medium inline-flex items-center gap-1">
              <UploadCloud className="w-3.5 h-3.5" /> Upload &amp; analyze
            </Link>
          </div>
        </div>
      </div>
    </AppShell>
  )
}
