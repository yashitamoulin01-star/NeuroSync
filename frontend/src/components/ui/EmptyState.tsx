import { LucideIcon } from 'lucide-react'
import { Button } from './Button'

interface EmptyStateProps {
  icon: LucideIcon
  title: string
  description: string
  actionLabel?: string
  onAction?: () => void
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  actionLabel,
  onAction,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center text-center p-8 border border-dashed border-border/80 rounded-xl bg-bg-surface/20 min-h-[300px] page-enter">
      <div className="w-12 h-12 rounded-xl bg-accent/5 border border-accent/20 flex items-center justify-center mb-4 text-accent">
        <Icon className="w-6 h-6" />
      </div>
      <h3 className="text-base font-bold text-text-primary mb-1.5">{title}</h3>
      <p className="text-sm text-text-muted max-w-sm mb-6 leading-relaxed">{description}</p>
      {actionLabel && onAction && (
        <Button variant="primary" size="sm" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  )
}
