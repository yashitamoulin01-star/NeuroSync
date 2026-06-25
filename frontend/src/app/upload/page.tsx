'use client'
import { useState, useEffect, useCallback, useRef } from 'react'
import Link from 'next/link'
import { AppShell } from '@/components/layout/AppShell'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Skeleton } from '@/components/ui/Skeleton'
import { EmptyState } from '@/components/ui/EmptyState'
import { cn } from '@/lib/utils'
import { useAuth } from '@/lib/auth'
import { uploadApi, setEnterpriseToken, type UploadJob } from '@/lib/api'
import {
  UploadCloud, FileVideo, FileAudio, AlertCircle, CheckCircle2,
  RotateCw, Trash2, ArrowRight, FileUp, Film,
} from 'lucide-react'

const MODES = ['interview', 'coaching', 'presentation'] as const
const ACCEPT = '.mp4,.mov,.avi,.mkv,.webm,.wav,.mp3,.m4a,.flac'

const STATUS_BADGE: Record<UploadJob['status'], { label: string; variant: 'default' | 'success' | 'warning' | 'danger' }> = {
  queued:     { label: 'Queued',     variant: 'default' },
  processing: { label: 'Processing', variant: 'warning' },
  completed:  { label: 'Completed',  variant: 'success' },
  failed:     { label: 'Failed',     variant: 'danger'  },
  canceled:   { label: 'Canceled',   variant: 'default' },
}

function fmtSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`
}

export default function UploadPage() {
  const { token } = useAuth()
  const [jobs,    setJobs]    = useState<UploadJob[]>([])
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState<string | null>(null)
  const [mode,    setMode]    = useState<string>('interview')
  const [name,    setName]    = useState('')
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [busy,    setBusy]    = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const load = useCallback(async () => {
    if (!token) { setLoading(false); return }
    setEnterpriseToken(token)
    try {
      const res = await uploadApi.list()
      setJobs(res.jobs)
      setError(null)
    } catch (e: any) {
      setError(e.message ?? 'Failed to load uploads')
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { load() }, [load])

  // Poll while any job is active.
  const hasActive = jobs.some(j => j.status === 'queued' || j.status === 'processing')
  useEffect(() => {
    if (!hasActive) return
    const t = setInterval(load, 3000)
    return () => clearInterval(t)
  }, [hasActive, load])

  async function handleFiles(files: FileList | null) {
    if (!files || !files.length || !token) return
    setEnterpriseToken(token)
    setUploading(true)
    setError(null)
    try {
      for (const file of Array.from(files)) {
        await uploadApi.create(file, mode, name.trim())
      }
      setName('')
      await load()
    } catch (e: any) {
      setError(e.message ?? 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  async function handleAction(id: string, action: 'retry' | 'remove') {
    setBusy(id)
    try {
      if (action === 'retry') await uploadApi.retry(id)
      else await uploadApi.remove(id)
      await load()
    } catch (e: any) {
      setError(e.message ?? `${action} failed`)
    } finally {
      setBusy(null)
    }
  }

  if (!token) {
    return (
      <AppShell title="Upload Recording">
        <div className="p-6 max-w-2xl mx-auto mt-12">
          <EmptyState icon={FileUp} title="Sign in required"
            description="Authentication is required to upload and analyze recordings." />
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell title="Upload Recording">
      <div className="p-6 space-y-8 max-w-5xl page-enter">

        <div>
          <p className="label-xs text-text-disabled mb-1">Recorded Interviews</p>
          <h2 className="text-base font-bold text-text-primary">Analyze a recording</h2>
          <p className="text-xs text-text-muted mt-1 max-w-2xl">
            Upload an interview recording to run the same behavioral analysis as a live session.
            Processing happens in the background, so you can close this page and return later. Video
            is analyzed for facial signals; WAV audio adds voice and transcript analysis.
          </p>
        </div>

        {error && (
          <div className="flex items-center gap-2 rounded-lg border border-status-danger/25 bg-status-danger/5 px-3 py-2.5">
            <AlertCircle className="w-3.5 h-3.5 text-status-danger flex-shrink-0" />
            <p className="text-xs text-status-danger">{error}</p>
          </div>
        )}

        {/* ── Upload form ──────────────────────────────────────────────────── */}
        <div className="grid sm:grid-cols-[1fr_auto] gap-3 items-end">
          <div className="space-y-3">
            <div className="flex flex-wrap gap-3">
              <div className="flex rounded-lg border border-border overflow-hidden">
                {MODES.map(m => (
                  <button key={m} onClick={() => setMode(m)}
                    className={cn('px-3 py-1.5 text-xs font-medium capitalize transition-colors border-r border-border last:border-0',
                      mode === m ? 'bg-bg-hover text-text-primary' : 'text-text-muted hover:text-text-secondary')}>
                    {m}
                  </button>
                ))}
              </div>
              <input
                value={name} onChange={e => setName(e.target.value)}
                placeholder="Candidate / session name (optional)"
                className="flex-1 min-w-[200px] rounded-lg border border-border bg-bg-card px-3 py-1.5 text-xs text-text-primary placeholder:text-text-disabled focus:outline-none focus:border-border-strong"
              />
            </div>
          </div>
        </div>

        {/* Drop zone */}
        <div
          onDragOver={e => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={e => { e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer.files) }}
          onClick={() => fileRef.current?.click()}
          className={cn(
            'rounded-xl border-2 border-dashed cursor-pointer transition-colors py-12 flex flex-col items-center justify-center text-center',
            dragging ? 'border-accent bg-accent/5' : 'border-border hover:border-border-strong bg-bg-card',
          )}
        >
          <input ref={fileRef} type="file" accept={ACCEPT} multiple className="hidden"
            onChange={e => handleFiles(e.target.files)} />
          <UploadCloud className={cn('w-8 h-8 mb-3', dragging ? 'text-accent' : 'text-text-muted')} />
          <p className="text-sm font-medium text-text-primary">
            {uploading ? 'Uploading…' : 'Drop a recording here, or click to browse'}
          </p>
          <p className="text-2xs text-text-disabled mt-1">
            MP4 · MOV · AVI · MKV · WebM · WAV · MP3 · M4A · FLAC
          </p>
        </div>

        {/* ── Processing queue ─────────────────────────────────────────────── */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <div>
              <p className="label-xs text-text-disabled mb-1">Processing Queue</p>
              <h3 className="text-base font-bold text-text-primary">Uploads</h3>
            </div>
            {hasActive && (
              <span className="flex items-center gap-1.5 text-2xs text-text-muted">
                <span className="w-1.5 h-1.5 rounded-full bg-status-warning animate-pulse" />
                Live
              </span>
            )}
          </div>

          {loading ? (
            <div className="space-y-3">
              {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-16 w-full" />)}
            </div>
          ) : jobs.length === 0 ? (
            <EmptyState icon={Film} title="No uploads yet"
              description="Upload a recording above to see it analyzed here." />
          ) : (
            <div className="space-y-2">
              {jobs.map(job => {
                const badge = STATUS_BADGE[job.status]
                const Icon = job.media_kind === 'video' ? FileVideo : FileAudio
                return (
                  <div key={job.job_id} className="rounded-xl border border-border bg-bg-card p-3.5 flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-bg-hover flex items-center justify-center flex-shrink-0">
                      <Icon className="w-4 h-4 text-text-secondary" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-medium text-text-primary truncate">{job.candidate_name || job.filename}</p>
                        <Badge variant={badge.variant} dot>{badge.label}</Badge>
                      </div>
                      <p className="text-2xs text-text-disabled truncate">
                        {job.filename} · {fmtSize(job.size_bytes)} · {job.mode}
                      </p>
                      {job.status === 'processing' && (
                        <div className="mt-1.5 h-1 bg-bg-hover rounded-full overflow-hidden">
                          <div className="h-full rounded-full bg-accent transition-all duration-500"
                            style={{ width: `${Math.round(job.progress * 100)}%` }} />
                        </div>
                      )}
                      {job.status === 'failed' && job.error && (
                        <p className="text-2xs text-status-danger mt-1 truncate">{job.error}</p>
                      )}
                    </div>

                    <div className="flex items-center gap-1.5 flex-shrink-0">
                      {job.status === 'completed' && job.session_id && (
                        <Link href={`/session/${job.session_id}/results`}>
                          <Button variant="primary" size="xs" iconRight={<ArrowRight className="w-3 h-3" />}>
                            View report
                          </Button>
                        </Link>
                      )}
                      {job.status === 'completed' && (
                        <CheckCircle2 className="w-4 h-4 text-status-success" />
                      )}
                      {(job.status === 'failed' || job.status === 'canceled') && (
                        <Button variant="ghost" size="xs" icon={<RotateCw className="w-3 h-3" />}
                          loading={busy === job.job_id}
                          onClick={() => handleAction(job.job_id, 'retry')}>
                          Retry
                        </Button>
                      )}
                      {job.status !== 'processing' && (
                        <button onClick={() => handleAction(job.job_id, 'remove')}
                          className="p-1.5 rounded-md text-text-disabled hover:text-status-danger hover:bg-status-danger/10 transition-colors"
                          aria-label="Delete upload">
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </AppShell>
  )
}
