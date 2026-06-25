'use client'
import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/Button'
import { useAuth } from '@/lib/auth'
import { api, connectorApi, setEnterpriseToken, type UpcomingMeeting } from '@/lib/api'
import { CalendarClock, Video, ArrowRight, Users } from 'lucide-react'

const PLATFORM_LABEL: Record<string, string> = {
  google_meet:     'Google Meet',
  microsoft_teams: 'Microsoft Teams',
  zoom:            'Zoom',
  webex:           'Webex',
  slack:           'Slack',
}

const SOURCE_LABEL: Record<string, string> = {
  google_calendar:    'Google Calendar',
  microsoft_calendar: 'Outlook Calendar',
}

function fmtTime(ts: number): string {
  const d = new Date(ts * 1000)
  return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
}

function relLabel(ts: number): string {
  const mins = Math.round((ts * 1000 - Date.now()) / 60000)
  if (mins < 0) return 'now'
  if (mins < 60) return `in ${mins}m`
  return `in ${Math.round(mins / 60)}h`
}

/**
 * "Upcoming Interviews" — the signature workflow. Lists scheduled meetings from
 * connected providers; one click launches a live analysis session. Renders
 * nothing when the user isn't authenticated or has no connected providers, so it
 * never adds noise to the dashboard before connectors are set up.
 */
export function UpcomingInterviews() {
  const { token } = useAuth()
  const router = useRouter()
  const [meetings, setMeetings] = useState<UpcomingMeeting[]>([])
  const [loading,  setLoading]  = useState(true)
  const [busy,     setBusy]     = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!token) { setLoading(false); return }
    setEnterpriseToken(token)
    try {
      const res = await connectorApi.upcomingMeetings()
      setMeetings(res.meetings)
    } catch {
      /* silent — surface nothing if connectors aren't reachable */
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { load() }, [load])

  // Auto-refresh the schedule without a manual reload.
  useEffect(() => {
    if (!token) return
    const t = setInterval(load, 60_000)
    return () => clearInterval(t)
  }, [token, load])

  async function joinAnalysis(m: UpcomingMeeting) {
    setBusy(m.external_id)
    try {
      const res = await api.createSession({ session_name: m.title, mode: 'interview' })
      router.push(`/session/${res.session_id}`)
    } catch {
      setBusy(null)
    }
  }

  if (loading || !token || meetings.length === 0) return null

  return (
    <div className="rounded-xl border border-border bg-bg-card overflow-hidden">
      <div className="flex items-center gap-2.5 px-5 py-3 border-b border-border">
        <CalendarClock className="w-3.5 h-3.5 text-accent" />
        <span className="text-sm font-bold text-text-primary">Upcoming Interviews</span>
        <span className="text-2xs text-text-disabled ml-auto">{meetings.length} scheduled</span>
      </div>
      <div className="divide-y divide-border">
        {meetings.slice(0, 5).map(m => (
          <div key={m.connector_id + m.external_id} className="flex items-center gap-3 px-5 py-3">
            <div className="w-9 h-9 rounded-lg bg-bg-hover flex items-center justify-center flex-shrink-0">
              <Video className="w-4 h-4 text-text-secondary" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-text-primary truncate">{m.title}</p>
              <p className="text-2xs text-text-disabled flex items-center gap-2">
                <span className="text-text-secondary font-medium">{m.platform ? (PLATFORM_LABEL[m.platform] ?? m.platform) : 'Meeting'}</span>
                <span>·</span>
                <span className="font-mono">{fmtTime(m.start_time)} · {relLabel(m.start_time)}</span>
                {m.participants > 0 && (
                  <>
                    <span>·</span>
                    <span className="inline-flex items-center gap-1"><Users className="w-3 h-3" />{m.participants}</span>
                  </>
                )}
                <span>·</span>
                <span>via {SOURCE_LABEL[m.provider] ?? m.provider}</span>
              </p>
            </div>
            <Button variant="primary" size="sm" loading={busy === m.external_id}
              iconRight={<ArrowRight className="w-3.5 h-3.5" />}
              onClick={() => joinAnalysis(m)}>
              Join Analysis
            </Button>
          </div>
        ))}
      </div>
    </div>
  )
}
