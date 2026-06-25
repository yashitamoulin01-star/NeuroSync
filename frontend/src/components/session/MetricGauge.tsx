import { cn, formatScore } from '@/lib/utils'

interface MetricGaugeProps {
  label:     string
  value:     number
  color:     string
  inverted?: boolean
  subLabel?: string
}

export function MetricGauge({ label, value, color, inverted, subLabel }: MetricGaugeProps) {
  const display = Math.round(value * 100)
  const quality = inverted ? 1 - value : value
  const qualityLabel =
    quality >= 0.75 ? 'Excellent' :
    quality >= 0.50 ? 'Good' :
    quality >= 0.25 ? 'Fair' :
                      'Low'

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="text-xs text-text-muted font-medium">{label}</span>
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-muted">{qualityLabel}</span>
          <span className="text-sm font-bold font-mono text-text-primary tabular-nums">
            {display}%
          </span>
        </div>
      </div>
      <div className="h-1.5 bg-bg-hover rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700 ease-out"
          style={{ width: `${display}%`, background: color }}
        />
      </div>
      {subLabel && <p className="text-2xs text-text-muted">{subLabel}</p>}
    </div>
  )
}
