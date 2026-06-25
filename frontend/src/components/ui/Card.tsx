import { cn } from '@/lib/utils'

interface CardProps {
  children: React.ReactNode
  className?: string
  hover?: boolean
  glow?: boolean
  padding?: 'none' | 'sm' | 'md' | 'lg'
}

const paddings = {
  none: '',
  sm:   'p-3',
  md:   'p-4',
  lg:   'p-6',
}

export function Card({ children, className, hover, glow, padding = 'md' }: CardProps) {
  return (
    <div className={cn(
      'rounded-xl border border-border bg-bg-card',
      paddings[padding],
      hover && 'transition-all duration-200 hover:border-border-strong hover:bg-bg-hover cursor-pointer',
      glow  && 'shadow-glow-accent',
      className,
    )}>
      {children}
    </div>
  )
}

export function CardHeader({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn('mb-4', className)}>{children}</div>
}

export function CardTitle({ children, className }: { children: React.ReactNode; className?: string }) {
  return <h3 className={cn('text-sm font-semibold text-text-primary', className)}>{children}</h3>
}

export function CardDescription({ children, className }: { children: React.ReactNode; className?: string }) {
  return <p className={cn('text-xs text-text-muted mt-0.5', className)}>{children}</p>
}

export function Divider({ className }: { className?: string }) {
  return <hr className={cn('border-border', className)} />
}
