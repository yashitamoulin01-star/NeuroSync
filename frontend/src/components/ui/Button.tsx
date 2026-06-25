'use client'
import { forwardRef } from 'react'
import { cn } from '@/lib/utils'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'outline'
type Size    = 'xs' | 'sm' | 'md' | 'lg'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  loading?: boolean
  icon?: React.ReactNode
  iconRight?: React.ReactNode
}

const variants: Record<Variant, string> = {
  primary:   'bg-accent-bright text-white hover:bg-indigo-500 active:bg-indigo-700 shadow-glow-sm',
  secondary: 'bg-bg-hover text-text-primary hover:bg-bg-selected border border-border',
  ghost:     'text-text-secondary hover:text-text-primary hover:bg-bg-hover',
  danger:    'bg-status-danger/10 text-status-danger hover:bg-status-danger/20 border border-status-danger/20',
  outline:   'border border-border text-text-secondary hover:border-border-strong hover:text-text-primary',
}

const sizes: Record<Size, string> = {
  xs: 'h-6  px-2   text-xs  gap-1   rounded-md',
  sm: 'h-8  px-3   text-xs  gap-1.5 rounded-md',
  md: 'h-9  px-4   text-sm  gap-2   rounded-lg',
  lg: 'h-11 px-5   text-sm  gap-2   rounded-lg',
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'secondary', size = 'md', loading, icon, iconRight, children, className, disabled, ...props }, ref) => (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cn(
        'inline-flex items-center justify-center font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-bright focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base disabled:opacity-40 disabled:pointer-events-none select-none',
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    >
      {loading ? <Spinner size={size} /> : icon}
      {children}
      {!loading && iconRight}
    </button>
  )
)
Button.displayName = 'Button'

function Spinner({ size }: { size: Size }) {
  const s = size === 'xs' || size === 'sm' ? 'w-3 h-3' : 'w-4 h-4'
  return (
    <svg className={cn(s, 'animate-spin')} viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeOpacity="0.3" />
      <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  )
}
