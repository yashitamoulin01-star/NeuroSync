import { cn } from '@/lib/utils'

type Variant = 'default' | 'success' | 'warning' | 'danger' | 'accent' | 'muted'

interface BadgeProps {
  children: React.ReactNode
  variant?: Variant
  dot?: boolean
  className?: string
}

const variants: Record<Variant, string> = {
  default: 'bg-bg-hover text-text-secondary border border-border',
  success: 'bg-status-success/10 text-status-success border border-status-success/20',
  warning: 'bg-status-warning/10 text-status-warning border border-status-warning/20',
  danger:  'bg-status-danger/10  text-status-danger  border border-status-danger/20',
  accent:  'bg-accent/10         text-accent         border border-accent/20',
  muted:   'bg-bg-surface        text-text-muted     border border-border-subtle',
}

const dots: Record<Variant, string> = {
  default: 'bg-text-muted',
  success: 'bg-status-success',
  warning: 'bg-status-warning',
  danger:  'bg-status-danger',
  accent:  'bg-accent-bright',
  muted:   'bg-text-muted',
}

export function Badge({ children, variant = 'default', dot, className }: BadgeProps) {
  return (
    <span className={cn(
      'inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium',
      variants[variant],
      className,
    )}>
      {dot && <span className={cn('w-1.5 h-1.5 rounded-full flex-shrink-0', dots[variant])} />}
      {children}
    </span>
  )
}
