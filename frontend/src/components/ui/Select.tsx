import { forwardRef } from 'react'
import { cn } from '@/lib/utils'

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string
  error?: string
  hint?: string
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, error, hint, className, id, children, ...props }, ref) => {
    const selectId = id ?? label?.toLowerCase().replace(/\s+/g, '-')
    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label htmlFor={selectId} className="text-xs font-medium text-text-secondary">
            {label}
          </label>
        )}
        <select
          ref={ref}
          id={selectId}
          className={cn(
            'h-8 w-full rounded-lg border border-border bg-bg-card px-3 text-xs text-text-primary',
            'transition-colors duration-150',
            'focus:outline-none focus:ring-2 focus:ring-accent focus:border-accent',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            error && 'border-status-danger/50 focus:ring-status-danger',
            className,
          )}
          aria-describedby={error ? `${selectId}-error` : hint ? `${selectId}-hint` : undefined}
          aria-invalid={error ? 'true' : undefined}
          {...props}
        >
          {children}
        </select>
        {hint && !error && (
          <p id={`${selectId}-hint`} className="text-2xs text-text-muted">{hint}</p>
        )}
        {error && (
          <p id={`${selectId}-error`} className="text-2xs text-status-danger" role="alert">{error}</p>
        )}
      </div>
    )
  }
)
Select.displayName = 'Select'
