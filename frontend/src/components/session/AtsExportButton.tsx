'use client'
import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { Button } from '@/components/ui/Button'
import { useAuth } from '@/lib/auth'
import { atsApi, setEnterpriseToken, type ATSConnection } from '@/lib/api'
import { Briefcase, Check, X, AlertCircle, ExternalLink } from 'lucide-react'

const PROVIDER_LABEL: Record<string, string> = {
  greenhouse: 'Greenhouse', lever: 'Lever', workday: 'Workday', ashby: 'Ashby',
}

/**
 * Export a completed behavioral report into a connected ATS. Always requires an
 * explicit recruiter confirmation step; NeuroSync never changes hiring decisions
 * in the ATS automatically. Hidden for demo sessions.
 */
export function AtsExportButton({ sessionId, isDemo, candidateName }: {
  sessionId: string; isDemo: boolean; candidateName?: string
}) {
  const { token } = useAuth()
  const [connections, setConnections] = useState<ATSConnection[]>([])
  const [open,    setOpen]    = useState(false)
  const [picked,  setPicked]  = useState<string | null>(null)
  const [busy,    setBusy]    = useState(false)
  const [result,  setResult]  = useState<{ ok: boolean; message: string; ref: string | null } | null>(null)

  const load = useCallback(async () => {
    if (!token) return
    setEnterpriseToken(token)
    try {
      const res = await atsApi.list()
      setConnections(res.connections.filter(c => c.status === 'connected'))
    } catch { /* no ATS configured — button still opens to guide the user */ }
  }, [token])

  useEffect(() => { if (open) load() }, [open, load])

  async function confirmExport() {
    if (!picked) return
    setBusy(true)
    setResult(null)
    try {
      const r = await atsApi.exportReport(picked, sessionId)
      setResult({ ok: r.ok, message: r.message, ref: r.external_ref })
    } catch (e: any) {
      setResult({ ok: false, message: e.message ?? 'Export failed', ref: null })
    } finally {
      setBusy(false)
    }
  }

  if (isDemo || !token) return null

  return (
    <>
      <Button variant="ghost" size="sm" icon={<Briefcase className="w-3.5 h-3.5" />} onClick={() => { setOpen(true); setResult(null); setPicked(null) }}>
        Export to ATS
      </Button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 no-print" onClick={() => setOpen(false)}>
          <div className="w-[420px] max-w-[92vw] rounded-xl border border-border bg-bg-card shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-border">
              <h3 className="text-sm font-bold text-text-primary">Export report to ATS</h3>
              <button onClick={() => setOpen(false)} className="text-text-muted hover:text-text-primary"><X className="w-4 h-4" /></button>
            </div>

            <div className="p-5 space-y-4">
              {result ? (
                <div className={result.ok ? 'space-y-2' : 'space-y-2'}>
                  <div className="flex items-center gap-2">
                    {result.ok
                      ? <Check className="w-4 h-4 text-status-success" />
                      : <AlertCircle className="w-4 h-4 text-status-danger" />}
                    <p className={`text-sm font-medium ${result.ok ? 'text-status-success' : 'text-status-danger'}`}>
                      {result.ok ? 'Exported' : 'Export failed'}
                    </p>
                  </div>
                  <p className="text-xs text-text-muted">{result.message}</p>
                  {result.ref && <p className="text-2xs font-mono text-text-disabled">Ref: {result.ref}</p>}
                </div>
              ) : connections.length === 0 ? (
                <div className="text-center py-4">
                  <Briefcase className="w-7 h-7 text-text-disabled mx-auto mb-2" />
                  <p className="text-sm text-text-primary mb-1">No ATS connected</p>
                  <p className="text-xs text-text-muted mb-3">Connect an ATS to export reports.</p>
                  <Link href="/settings?tab=ats"><Button variant="outline" size="sm" iconRight={<ExternalLink className="w-3.5 h-3.5" />}>Open ATS settings</Button></Link>
                </div>
              ) : (
                <>
                  <p className="text-xs text-text-muted">
                    Write the behavioral report for <span className="font-semibold text-text-secondary">{candidateName || 'this candidate'}</span> into your ATS.
                    NeuroSync never changes hiring decisions — this attaches decision-support evidence only.
                  </p>
                  <div className="space-y-1.5">
                    {connections.map(c => (
                      <button key={c.connection_id} onClick={() => setPicked(c.connection_id)}
                        className={`w-full flex items-center gap-2.5 rounded-lg border px-3 py-2.5 text-left transition-colors ${
                          picked === c.connection_id ? 'border-accent bg-accent/5' : 'border-border hover:border-border-strong'}`}>
                        <Briefcase className="w-4 h-4 text-text-secondary" />
                        <span className="text-sm text-text-primary flex-1">{PROVIDER_LABEL[c.provider] ?? c.name}</span>
                        {picked === c.connection_id && <Check className="w-4 h-4 text-accent" />}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>

            <div className="flex items-center justify-end gap-2 px-5 py-3.5 border-t border-border">
              <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>{result ? 'Close' : 'Cancel'}</Button>
              {!result && connections.length > 0 && (
                <Button variant="primary" size="sm" loading={busy} disabled={!picked} onClick={confirmExport}>
                  Confirm export
                </Button>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  )
}
