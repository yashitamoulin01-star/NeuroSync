import { cn } from '@/lib/utils'
import { Sparkline } from '@/components/charts/Sparkline'
import { memo } from 'react'

interface KPICardProps {
  label:     string
  value:     string | number
  subValue?: string
  delta?:    number   // positive = good, negative = bad
  color?:    string
  history?:  number[] // for sparkline
  inverted?: boolean  // for stress (lower is better)
  className?: string
  icon?: React.ReactNode
}

export const KPICard = memo(function KPICard({
  label, value, subValue, delta, color = '#ffffff', history, inverted, className, icon,
}: KPICardProps) {
  const isPositive = delta != null ? (inverted ? delta <= 0 : delta >= 0) : null

  return (
    <div className={cn('flex flex-col gap-2 border-l border-border pl-4', className)}>
      <div className="flex items-center gap-1.5 text-text-muted">
        {icon && <span style={{ color: 'var(--text-secondary)' }}>{icon}</span>}
        <span className="text-xs font-semibold uppercase tracking-widest">{label}</span>
      </div>
      
      <div className="flex items-baseline gap-2">
        <span className="text-3xl font-bold tracking-tight text-text-primary metric-value">{value}</span>
        {delta != null && (
          <span className={cn(
            'text-xs font-mono font-medium',
            isPositive ? 'text-text-primary' : 'text-text-secondary',
          )}>
            {delta > 0 ? '+' : ''}{(delta * 100).toFixed(1)}%
          </span>
        )}
      </div>

      {subValue && (
        <span className="text-xs text-text-muted">{subValue}</span>
      )}

      {history && history.length > 3 && (
        <div className="mt-1 h-8 opacity-60">
          <Sparkline data={history} color={color} height={32} inverted={inverted} />
        </div>
      )}
    </div>
  )
})
