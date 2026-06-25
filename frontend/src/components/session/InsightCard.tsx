import { cn, getSeverityLabel, formatDuration } from '@/lib/utils'
import type { BehavioralInsight } from '@/lib/types'
import { AlertTriangle, CheckCircle, Info, TrendingUp, Eye, Mic, MessageSquare } from 'lucide-react'

const INSIGHT_META: Record<string, { icon: React.ElementType; color: string; label: string }> = {
  stress_spike:       { icon: AlertTriangle, color: '#f87171', label: 'Stress Spike' },
  gaze_aversion:      { icon: Eye,           color: '#fbbf24', label: 'Gaze Aversion' },
  hesitation_burst:   { icon: MessageSquare, color: '#fb923c', label: 'Hesitation' },
  strong_delivery:    { icon: TrendingUp,    color: '#34d399', label: 'Strong Delivery' },
  low_engagement:     { icon: Info,          color: '#60a5fa', label: 'Low Engagement' },
  confidence_drop:    { icon: AlertTriangle, color: '#f87171', label: 'Confidence Drop' },
  vocal_tension:      { icon: Mic,           color: '#fbbf24', label: 'Vocal Tension' },
  positive_signal:    { icon: CheckCircle,   color: '#34d399', label: 'Positive Signal' },
}

interface Props {
  insight: BehavioralInsight
  compact?: boolean
}

import { memo } from 'react'

export const InsightCard = memo(function InsightCard({ insight, compact }: Props) {
  const meta = INSIGHT_META[insight.type] ?? { icon: Info, color: '#60a5fa', label: insight.type }
  const Icon = meta.icon
  const sev  = getSeverityLabel(insight.severity)

  if (compact) {
    return (
      <div className="flex items-start gap-3 py-2.5 border-b border-border-subtle last:border-0">
        <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5"
          style={{ background: `${meta.color}12` }}>
          <Icon className="w-3.5 h-3.5" style={{ color: meta.color }} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <span className="text-xs font-semibold text-text-primary">{meta.label}</span>
            <span className="text-2xs text-text-muted ml-auto">{formatDuration(insight.timestamp)}</span>
          </div>
          <p className="text-xs text-text-muted leading-relaxed line-clamp-2">{insight.description}</p>
        </div>
      </div>
    )
  }

  return (
    <div
      className={cn(
        'rounded-xl border p-4 card-hover',
        insight.severity >= 0.5
          ? 'border-status-danger/20 bg-status-danger/5 hover:bg-status-danger/8'
          : insight.severity >= 0.25
          ? 'border-status-warning/20 bg-status-warning/5 hover:bg-status-warning/8'
          : 'border-border bg-bg-card hover:bg-bg-hover hover:border-border-strong',
      )}
    >
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
          style={{ background: `${meta.color}15` }}>
          <Icon className="w-4 h-4" style={{ color: meta.color }} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm font-semibold text-text-primary">{meta.label}</span>
            <span className={cn('text-2xs font-medium px-1.5 py-0.5 rounded-full',
              insight.severity >= 0.5 ? 'text-status-danger bg-status-danger/15'
              : insight.severity >= 0.25 ? 'text-status-warning bg-status-warning/15'
              : 'text-status-success bg-status-success/15',
            )}>
              {sev}
            </span>
            <span className="text-2xs text-text-muted ml-auto font-mono">{formatDuration(insight.timestamp)}</span>
          </div>
          <p className="text-xs text-text-secondary leading-relaxed">{insight.description}</p>
          {insight.modalities_involved.length > 0 && (
            <div className="flex gap-1.5 mt-2">
              {insight.modalities_involved.map(m => (
                <span key={m} className="text-2xs px-1.5 py-0.5 rounded-full bg-bg-hover text-text-muted border border-border-subtle">
                  {m}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
})
