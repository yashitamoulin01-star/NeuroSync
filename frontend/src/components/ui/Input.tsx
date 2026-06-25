import { forwardRef } from 'react'
import { cn } from '@/lib/utils'

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  hint?: string
  icon?: React.ReactNode
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, hint, icon, className, id, ...props }, ref) => {
    const inputId = id ?? label?.toLowerCase().replace(/\s+/g, '-')
    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label htmlFor={inputId} className="text-xs font-medium text-text-secondary">
            {label}
          </label>
        )}
        <div className="relative">
          {icon && (
            <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none">
              {icon}
            </span>
          )}
          <input
            ref={ref}
            id={inputId}
            className={cn(
              'h-8 w-full rounded-lg border border-border bg-bg-card px-3 text-xs text-text-primary',
              'placeholder:text-text-disabled',
              'transition-colors duration-150',
              'focus:outline-none focus:ring-2 focus:ring-accent focus:border-accent',
              'disabled:opacity-50 disabled:cursor-not-allowed',
              icon && 'pl-8',
              error && 'border-status-danger/50 focus:ring-status-danger',
              className,
            )}
            aria-describedby={error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined}
            aria-invalid={error ? 'true' : undefined}
            {...props}
          />
        </div>
        {hint && !error && (
          <p id={`${inputId}-hint`} className="text-2xs text-text-muted">{hint}</p>
        )}
        {error && (
          <p id={`${inputId}-error`} className="text-2xs text-status-danger" role="alert">{error}</p>
        )}
      </div>
    )
  }
)
Input.displayName = 'Input'
