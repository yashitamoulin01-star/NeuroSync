import { cn } from '@/lib/utils'

interface Props {
  value: number          // 0–1
  label?: string
  showPct?: boolean
  size?: 'sm' | 'md'
  className?: string
}

export function ConfidenceBar({ value, label, showPct = true, size = 'md', className }: Props) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100)
  const color = pct >= 75 ? '#22c55e' : pct >= 55 ? '#f59e0b' : '#ef4444'
  const tier  = pct >= 75 ? 'High' : pct >= 55 ? 'Moderate' : 'Low'

  return (
    <div className={cn('flex items-center gap-2', className)}>
      {label && (
        <span className={cn('text-text-muted flex-shrink-0', size === 'sm' ? 'text-2xs' : 'text-xs')}>
          {label}
        </span>
      )}
      <div className={cn(
        'flex-1 rounded-full overflow-hidden bg-bg-base',
        size === 'sm' ? 'h-1' : 'h-1.5',
      )}>
        <div
          className="h-full rounded-full bar-fill transition-all duration-700"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      {showPct && (
        <span
          className={cn(
            'font-mono font-semibold flex-shrink-0 tabular-nums',
            size === 'sm' ? 'text-2xs w-7' : 'text-xs w-8',
          )}
          style={{ color }}
        >
          {pct}%
        </span>
      )}
    </div>
  )
}

// Inline chip variant — used in report headers, recommendation badges
export function ConfidenceChip({ value, className }: { value: number; className?: string }) {
  const pct   = Math.round(Math.max(0, Math.min(1, value)) * 100)
  const color = pct >= 75 ? { bg: 'bg-status-success/10', text: 'text-status-success', border: 'border-status-success/20' }
    : pct >= 55 ? { bg: 'bg-status-warning/10', text: 'text-status-warning', border: 'border-status-warning/20' }
    : { bg: 'bg-status-danger/10', text: 'text-status-danger', border: 'border-status-danger/20' }
  return (
    <span className={cn(
      'inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-2xs font-semibold font-mono',
      color.bg, color.text, color.border, className,
    )}>
      {pct}% confidence
    </span>
  )
}
