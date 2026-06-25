'use client'
import { useEffect, useRef, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { AppShell } from '@/components/layout/AppShell'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { BehavioralFingerprint } from '@/components/charts/BehavioralFingerprint'
import { MetricGauge } from '@/components/session/MetricGauge'
import { TranscriptFeed } from '@/components/session/TranscriptFeed'
import { InsightCard } from '@/components/session/InsightCard'
import { useWebSocket } from '@/lib/hooks/useWebSocket'
import { formatDuration } from '@/lib/utils'
import { api } from '@/lib/api'
import {
  Square, Wifi, WifiOff, RefreshCw, Activity,
  Camera, CameraOff, Mic, MicOff, AlertCircle, ChevronDown, ChevronUp, Brain,
} from 'lucide-react'
import type { BehavioralInsight } from '@/lib/types'
import { cn } from '@/lib/utils'

interface TranscriptEntry { timestamp: number; text: string; fillerWords: string[] }

// ── Media capture hook ────────────────────────────────────────────────────────

function useMediaCapture(
  onFrame: (b64: string) => void,
  onAudio: (b64: string, rate: number) => void,
) {
  const streamRef        = useRef<MediaStream | null>(null)
  const videoRef         = useRef<HTMLVideoElement | null>(null)
  const canvasRef        = useRef<HTMLCanvasElement | null>(null)
  const audioCtxRef      = useRef<AudioContext | null>(null)
  const frameTimerRef    = useRef<ReturnType<typeof setInterval>>()
  const audioBufferRef   = useRef<Float32Array[]>([])
  const audioTimerRef    = useRef<ReturnType<typeof setInterval>>()

  const [camActive,  setCamActive]  = useState(false)
  const [micActive,  setMicActive]  = useState(false)
  const [permError,  setPermError]  = useState<string | null>(null)

  const start = useCallback(async (video: HTMLVideoElement) => {
    videoRef.current  = video
    canvasRef.current = document.createElement('canvas')
    canvasRef.current.width  = 320
    canvasRef.current.height = 240

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 320, height: 240, frameRate: { ideal: 10 } },
        audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true },
      })
      streamRef.current = stream
      video.srcObject   = stream
      await video.play().catch(() => {})

      // ── Video: capture a frame every 200ms (5fps) ──────────────────────
      setCamActive(true)
      frameTimerRef.current = setInterval(() => {
        const canvas = canvasRef.current
        const vid    = videoRef.current
        if (!canvas || !vid || vid.readyState < 2) return
        const ctx = canvas.getContext('2d')
        if (!ctx) return
        ctx.drawImage(vid, 0, 0, canvas.width, canvas.height)
        const b64 = canvas.toDataURL('image/jpeg', 0.7).split(',')[1]
        if (b64) onFrame(b64)
      }, 200)

      // ── Audio: ScriptProcessor → float32 → Int16 → base64 ─────────────
      const audioTrack = stream.getAudioTracks()[0]
      if (audioTrack) {
        setMicActive(true)
        const ctx = new AudioContext({ sampleRate: 16000 })
        audioCtxRef.current = ctx
        const src  = ctx.createMediaStreamSource(stream)
        const proc = ctx.createScriptProcessor(4096, 1, 1)
        proc.onaudioprocess = (e) => {
          const f32 = e.inputBuffer.getChannelData(0)
          audioBufferRef.current.push(new Float32Array(f32))
        }
        src.connect(proc)
        proc.connect(ctx.destination)

        // Flush audio buffer every 500ms
        audioTimerRef.current = setInterval(() => {
          const chunks = audioBufferRef.current.splice(0)
          if (!chunks.length) return
          const total  = chunks.reduce((n, c) => n + c.length, 0)
          const merged = new Float32Array(total)
          let offset   = 0
          for (const c of chunks) { merged.set(c, offset); offset += c.length }
          // Convert float32 → int16
          const i16    = new Int16Array(merged.length)
          for (let i = 0; i < merged.length; i++) {
            i16[i] = Math.max(-32768, Math.min(32767, Math.round(merged[i] * 32768)))
          }
          const b64 = btoa(String.fromCharCode(...new Uint8Array(i16.buffer)))
          onAudio(b64, 16000)
        }, 500)
      }

    } catch (err: any) {
      const msg = err?.name === 'NotAllowedError'
        ? 'Camera and microphone access denied. Allow permissions to enable analysis.'
        : 'Media device unavailable. Check your camera and microphone.'
      setPermError(msg)
    }
  }, [onFrame, onAudio])

  const stop = useCallback(() => {
    clearInterval(frameTimerRef.current)
    clearInterval(audioTimerRef.current)
    audioCtxRef.current?.close().catch(() => {})
    streamRef.current?.getTracks().forEach(t => t.stop())
    streamRef.current  = null
    setCamActive(false)
    setMicActive(false)
  }, [])

  useEffect(() => () => { stop() }, [stop])

  return { start, stop, camActive, micActive, permError, videoRef }
}

// ── Live session page ─────────────────────────────────────────────────────────

export default function LiveSessionPage({ params }: { params: { id: string } }) {
  const router   = useRouter()

  // Demo sessions bypass the live capture flow entirely
  useEffect(() => {
    if (params.id === 'demo') {
      router.replace('/session/demo/results')
    }
  }, [params.id, router])

  const { analytics, status, send, sendEnd } = useWebSocket(params.id)

  const [elapsed,   setElapsed]   = useState(0)
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([])
  const [insights,  setInsights]  = useState<BehavioralInsight[]>([])
  const [ending,    setEnding]    = useState(false)
  const [inspectorOpen, setInspectorOpen] = useState(false)
  const startRef  = useRef(Date.now())
  const domVideoRef = useRef<HTMLVideoElement>(null)

  // Media capture
  const onFrame = useCallback((b64: string) => {
    send({ type: 'frame', session_id: params.id, payload: { image_b64: b64 } })
  }, [send, params.id])

  const onAudio = useCallback((b64: string, rate: number) => {
    send({ type: 'audio', session_id: params.id, payload: { pcm_b64: b64, sample_rate: rate } })
  }, [send, params.id])

  const { start: startMedia, stop: stopMedia, camActive, micActive, permError } =
    useMediaCapture(onFrame, onAudio)

  // Start media when WS connects
  useEffect(() => {
    if (status === 'connected' && domVideoRef.current && !camActive) {
      startMedia(domVideoRef.current)
    }
  }, [status, camActive, startMedia])

  // Timer
  useEffect(() => {
    const t = setInterval(() => setElapsed(Math.floor((Date.now() - startRef.current) / 1000)), 500)
    return () => clearInterval(t)
  }, [])

  // Accumulate transcript + insights
  useEffect(() => {
    if (!analytics) return
    if (analytics.nlp?.transcript_chunk) {
      setTranscript(prev => [
        ...prev,
        {
          timestamp: analytics.session_duration,
          text: analytics.nlp!.transcript_chunk,
          fillerWords: analytics.nlp!.filler_words_detected.map(f => f.word),
        },
      ])
    }
    if (analytics.insights?.length) {
      setInsights(prev => {
        const newer = analytics.insights.filter(
          ni => !prev.some(p => p.timestamp === ni.timestamp && p.type === ni.type)
        )
        return [...prev, ...newer].slice(-20)
      })
    }
  }, [analytics])

  async function handleEnd() {
    if (ending) return
    setEnding(true)
    stopMedia()
    sendEnd()
    try {
      await api.endSession(params.id)
    } catch {
      // session may have already been ended via WS "end" message
    }
    router.push(`/session/${params.id}/results`)
  }

  // Display data — live when connected, neutral defaults otherwise
  const liveData = analytics ?? {
    overall_confidence:     0, communication_quality: 0,
    engagement_score:       0, stress_level:          0,
    behavioral_consistency: 0,
    face:  null, audio: null, nlp: null,
    session_duration:   elapsed,
    total_words_spoken: 0,
    total_filler_words: 0,
    avg_speaking_pace:  0,
    session_id:  params.id,
    timestamp:   Date.now() / 1000,
    insights:    [],
  }

  const fp = {
    confidence:    liveData.overall_confidence,
    communication: liveData.communication_quality,
    engagement:    liveData.engagement_score,
    stress:        liveData.stress_level,
    consistency:   liveData.behavioral_consistency,
  }

  const wsConnected   = status === 'connected'
  const wsReconnecting = status === 'reconnecting' || status === 'connecting'

  const statusLabel = wsConnected ? 'Live' :
    wsReconnecting ? 'Reconnecting…' : 'Offline'

  const statusColor = wsConnected ? 'text-status-success' :
    wsReconnecting ? 'text-status-warning' : 'text-status-danger'

  return (
    <AppShell
      title="Live Session"
      actions={
        <div className="flex items-center gap-3">
          {/* Connection badge */}
          <div className={cn('flex items-center gap-1.5 text-xs font-medium', statusColor)}>
            {wsConnected   ? <Wifi       className="w-3.5 h-3.5" /> :
             wsReconnecting ? <RefreshCw  className="w-3.5 h-3.5 animate-spin" /> :
                              <WifiOff    className="w-3.5 h-3.5" />}
            {statusLabel}
          </div>
          {/* Cam / Mic badges */}
          {(camActive || micActive) && (
            <div className="flex items-center gap-1.5">
              {camActive  ? <Camera  className="w-3.5 h-3.5 text-status-success" /> :
                            <CameraOff className="w-3.5 h-3.5 text-text-disabled" />}
              {micActive  ? <Mic    className="w-3.5 h-3.5 text-status-success" /> :
                            <MicOff  className="w-3.5 h-3.5 text-text-disabled" />}
            </div>
          )}
          <Button
            variant="danger" size="sm"
            icon={<Square className="w-3.5 h-3.5" />}
            loading={ending}
            onClick={handleEnd}
          >
            End Session
          </Button>
        </div>
      }
    >
      <div className="p-6 max-w-7xl">

        {/* Live indicator bar */}
        <div className="flex items-center gap-3 mb-6">
          <div className="flex items-center gap-2">
            <span className="relative flex w-2.5 h-2.5">
              {wsConnected && (
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-status-danger opacity-75" />
              )}
              <span className={cn(
                'relative inline-flex rounded-full h-2.5 w-2.5',
                wsConnected ? 'bg-status-danger' : 'bg-text-disabled',
              )} />
            </span>
            <span className="text-sm font-medium text-text-primary">
              {wsConnected ? 'Recording' : wsReconnecting ? 'Reconnecting' : 'Disconnected'}
            </span>
          </div>
          <span className="text-sm font-mono text-text-muted">{formatDuration(elapsed)}</span>
          <Badge variant="muted">{Math.round(liveData.total_words_spoken)} words</Badge>
          <Badge variant="warning">{liveData.total_filler_words} fillers</Badge>
        </div>

        {/* Permission / device error */}
        {permError && (
          <div className="flex items-center gap-3 rounded-xl border border-status-warning/30 bg-status-warning/5 px-4 py-3 mb-6">
            <AlertCircle className="w-4 h-4 text-status-warning flex-shrink-0" />
            <p className="text-xs text-status-warning">{permError}</p>
          </div>
        )}

        <div className="grid lg:grid-cols-3 gap-6">

          {/* Left: fingerprint + gauges + modalities */}
          <div className="space-y-4">
            <div className="rounded-xl border border-border bg-bg-card p-5">
              <h3 className="text-xs font-semibold text-text-muted uppercase tracking-widest mb-4">Behavioral State</h3>

              {/* Hidden video element for webcam capture */}
              <video
                ref={domVideoRef}
                autoPlay
                muted
                playsInline
                className={cn(
                  'w-full rounded-lg mb-4 object-cover bg-bg-hover',
                  camActive ? 'h-32' : 'h-0 overflow-hidden',
                )}
              />

              <div className="flex justify-center mb-4">
                <BehavioralFingerprint data={fp} size={170} animated={wsConnected} />
              </div>
              <div className="space-y-3">
                {[
                  { label: 'Confidence',    value: fp.confidence,    color: '#818cf8' },
                  { label: 'Engagement',    value: fp.engagement,    color: '#34d399' },
                  { label: 'Communication', value: fp.communication, color: '#60a5fa' },
                  { label: 'Consistency',   value: fp.consistency,   color: '#fbbf24' },
                  { label: 'Composure',     value: 1 - fp.stress,    color: '#f87171' },
                ].map(d => <MetricGauge key={d.label} {...d} />)}
              </div>
            </div>

            {/* Modality status */}
            <div className="rounded-xl border border-border bg-bg-card p-4 space-y-3">
              <h3 className="text-xs font-semibold text-text-muted uppercase tracking-widest">Modalities</h3>
              {[
                {
                  label: 'Face',
                  active: camActive && (liveData.face?.face_detected ?? false),
                  detail: camActive
                    ? (liveData.face?.face_detected ? liveData.face.expression_label : 'Detecting…')
                    : 'Awaiting camera',
                },
                {
                  label: 'Voice',
                  active: micActive && (liveData.audio?.is_speaking ?? false),
                  detail: micActive
                    ? (liveData.audio ? `${Math.round(liveData.avg_speaking_pace)} WPM` : 'Listening…')
                    : 'Awaiting microphone',
                },
                {
                  label: 'Language',
                  active: wsConnected,
                  detail: wsConnected ? 'DeBERTa v3 active' : 'Awaiting connection',
                },
              ].map(({ label, active, detail }) => (
                <div key={label} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={cn(
                      'w-2 h-2 rounded-full flex-shrink-0',
                      active ? 'bg-status-success' : 'bg-text-disabled',
                    )} />
                    <span className="text-xs text-text-secondary">{label}</span>
                  </div>
                  <span className="text-2xs text-text-muted font-mono">{detail}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Center: transcript feed */}
          <div className="rounded-xl border border-border bg-bg-card p-5 flex flex-col min-h-[520px]">
            <h3 className="text-xs font-semibold text-text-muted uppercase tracking-widest mb-4">Live Transcript</h3>
            <div className="flex-1 overflow-y-auto">
              <TranscriptFeed entries={transcript} live />
            </div>
          </div>

          {/* Right: live insights */}
          <div className="rounded-xl border border-border bg-bg-card p-5 flex flex-col min-h-[520px]">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-xs font-semibold text-text-muted uppercase tracking-widest">Live Insights</h3>
              {insights.length > 0 && <Badge variant="accent" dot>{insights.length}</Badge>}
            </div>

            {insights.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center text-center">
                <Activity className="w-8 h-8 text-text-disabled mb-3" />
                <p className="text-xs text-text-muted leading-relaxed">
                  {wsConnected
                    ? 'Insights appear as behavioral\npatterns are detected'
                    : status === 'reconnecting' || status === 'connecting'
                    ? 'Connecting to analysis engine…'
                    : 'Backend disconnected.\nCheck that the server is running.'}
                </p>
              </div>
            ) : (
              <div className="flex-1 space-y-0 overflow-y-auto">
                {insights.slice().reverse().map((ins, i) => (
                  <InsightCard key={i} insight={ins} compact />
                ))}
              </div>
            )}

            {/* Reconnect prompt when offline */}
            {!wsConnected && !wsReconnecting && (
              <div className="mt-4 pt-4 border-t border-border-subtle">
                <p className="text-2xs text-text-muted text-center mb-2">
                  Connection lost · Retrying automatically
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Reasoning Inspector */}
        <div className="mt-6">
          <button
            onClick={() => setInspectorOpen(o => !o)}
            className="flex items-center gap-2 text-xs font-semibold text-text-muted hover:text-text-primary transition-colors w-full"
          >
            <Brain className="w-3.5 h-3.5" />
            Reasoning Inspector
            {inspectorOpen
              ? <ChevronUp className="w-3.5 h-3.5 ml-auto" />
              : <ChevronDown className="w-3.5 h-3.5 ml-auto" />}
          </button>

          {inspectorOpen && (
            <div className="mt-3 rounded-xl border border-border bg-bg-card p-5 space-y-5">

              {/* Row 1: State + Trends + Calibration */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
                {/* Behavioral State */}
                <div>
                  <p className="text-2xs font-semibold uppercase tracking-widest text-text-muted mb-2">State</p>
                  <p className="text-sm font-mono text-text-primary capitalize">
                    {analytics?.behavioral_state?.replace(/_/g, ' ') ?? '—'}
                  </p>
                  {analytics?.behavioral_pattern && (
                    <p className="text-2xs text-text-muted mt-1 capitalize">
                      {analytics.behavioral_pattern.replace(/_/g, ' ')}
                    </p>
                  )}
                  {analytics?.segment && (
                    <p className="text-2xs text-text-muted capitalize">{analytics.segment.replace(/_/g, ' ')}</p>
                  )}
                  {(analytics?.conflict_count ?? 0) > 0 && (
                    <p className="text-2xs text-status-warning mt-1">{analytics!.conflict_count} conflict{analytics!.conflict_count !== 1 ? 's' : ''}</p>
                  )}
                </div>

                {/* Dimension Trends */}
                <div>
                  <p className="text-2xs font-semibold uppercase tracking-widest text-text-muted mb-2">Trends</p>
                  {analytics?.trends
                    ? Object.entries(analytics.trends).map(([dim, trend]) => (
                      <div key={dim} className="flex items-center justify-between text-2xs mb-1">
                        <span className="text-text-muted capitalize">{dim}</span>
                        <span className={cn(
                          'font-mono',
                          trend === 'rising'  ? 'text-metric-engagement' :
                          trend === 'falling' ? 'text-metric-stress' :
                          'text-text-disabled',
                        )}>
                          {trend === 'rising' ? '↑' : trend === 'falling' ? '↓' : '→'}
                        </span>
                      </div>
                    ))
                    : <p className="text-2xs text-text-disabled">—</p>
                  }
                </div>

                {/* Calibration */}
                <div className="col-span-2">
                  <p className="text-2xs font-semibold uppercase tracking-widest text-text-muted mb-2">Calibration</p>
                  {analytics?.calibration
                    ? (
                      <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                        {Object.entries(analytics.calibration as Record<string, unknown>)
                          .filter(([, v]) => typeof v === 'number')
                          .map(([k, v]) => (
                            <div key={k} className="space-y-0.5">
                              <div className="flex items-center justify-between">
                                <span className="text-2xs text-text-muted capitalize">{k.replace(/_/g, ' ')}</span>
                                <span className="text-2xs font-mono text-text-secondary">{Math.round((v as number) * 100)}%</span>
                              </div>
                              <div className="h-0.5 bg-border rounded-none overflow-hidden">
                                <div className="h-full bg-text-muted" style={{ width: `${(v as number) * 100}%` }} />
                              </div>
                            </div>
                          ))
                        }
                      </div>
                    )
                    : <p className="text-2xs text-text-disabled">Calibration data appears after first analysis window.</p>
                  }
                </div>
              </div>

              {/* Row 2: Per-modality raw signals */}
              <div className="border-t border-border-subtle pt-4 grid grid-cols-3 gap-6">

                {/* Face signals */}
                <div>
                  <p className="text-2xs font-semibold uppercase tracking-widest text-text-muted mb-2">Face</p>
                  {analytics?.face ? (
                    <div className="space-y-1">
                      {[
                        { label: 'Eye contact', value: analytics.face.eye_contact_score, pct: true },
                        { label: 'Head stability', value: analytics.face.head_stability, pct: true },
                        { label: 'Facial tension', value: analytics.face.facial_tension, pct: true },
                        { label: 'Blink rate', value: analytics.face.blink_rate, unit: '/min', pct: false },
                        { label: 'Gaze', value: null, raw: analytics.face.gaze_direction },
                        { label: 'Expression', value: null, raw: analytics.face.expression_label },
                      ].map(({ label, value, pct, unit, raw }) => (
                        <div key={label} className="flex items-center justify-between text-2xs">
                          <span className="text-text-disabled">{label}</span>
                          <span className="font-mono text-text-secondary">
                            {raw ?? (value != null ? `${Math.round((pct ? value * 100 : value))}${pct ? '%' : (unit ?? '')}` : '—')}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-2xs text-text-disabled">Awaiting face data…</p>
                  )}
                </div>

                {/* Audio signals */}
                <div>
                  <p className="text-2xs font-semibold uppercase tracking-widest text-text-muted mb-2">Audio</p>
                  {analytics?.audio ? (
                    <div className="space-y-1">
                      {[
                        { label: 'Pitch mean', value: analytics.audio.pitch_mean, unit: 'Hz' },
                        { label: 'Pitch variance', value: analytics.audio.pitch_variance, unit: '' },
                        { label: 'Energy', value: analytics.audio.energy_level, pct: true },
                        { label: 'Vocal stability', value: analytics.audio.vocal_stability, pct: true },
                        { label: 'Voice stress', value: analytics.audio.voice_stress_score, pct: true },
                        { label: 'Pause ratio', value: analytics.audio.pause_ratio, pct: true },
                      ].map(({ label, value, pct, unit }) => (
                        <div key={label} className="flex items-center justify-between text-2xs">
                          <span className="text-text-disabled">{label}</span>
                          <span className="font-mono text-text-secondary">
                            {value != null
                              ? pct
                                ? `${Math.round(value * 100)}%`
                                : `${value.toFixed(1)}${unit ?? ''}`
                              : '—'}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-2xs text-text-disabled">Awaiting audio data…</p>
                  )}
                </div>

                {/* NLP signals */}
                <div>
                  <p className="text-2xs font-semibold uppercase tracking-widest text-text-muted mb-2">Language</p>
                  {analytics?.nlp ? (
                    <div className="space-y-1">
                      {[
                        { label: 'Confidence language', value: analytics.nlp.confidence_language_score, pct: true },
                        { label: 'Hesitation', value: analytics.nlp.hesitation_score, pct: true },
                        { label: 'Clarity', value: analytics.nlp.clarity_score, pct: true },
                        { label: 'Sentiment', value: analytics.nlp.sentiment_polarity, pct: false, unit: '' },
                        { label: 'Words / chunk', value: analytics.nlp.words_per_chunk, pct: false, unit: '' },
                        { label: 'Filler words', value: analytics.nlp.filler_word_count, pct: false, unit: '' },
                      ].map(({ label, value, pct, unit }) => (
                        <div key={label} className="flex items-center justify-between text-2xs">
                          <span className="text-text-disabled">{label}</span>
                          <span className="font-mono text-text-secondary">
                            {value != null
                              ? pct
                                ? `${Math.round(value * 100)}%`
                                : `${typeof value === 'number' ? value.toFixed(2) : value}${unit ?? ''}`
                              : '—'}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-2xs text-text-disabled">Awaiting language data…</p>
                  )}
                </div>

              </div>

            </div>
          )}
        </div>

      </div>
    </AppShell>
  )
}
