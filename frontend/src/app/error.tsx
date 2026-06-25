'use client'
import { useEffect } from 'react'
import { Button } from '@/components/ui/Button'
import { RefreshCw } from 'lucide-react'

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error(error)
  }, [error])

  return (
    <html lang="en">
      <body className="bg-bg-base text-text-primary antialiased min-h-screen flex items-center justify-center">
        <div className="text-center max-w-md px-6">
          <p className="label-xs text-accent mb-3">Error</p>
          <h1 className="page-heading mb-2">Something went wrong</h1>
          <p className="text-sm text-text-muted mb-6">
            An unexpected error occurred. If the problem persists, contact support.
          </p>
          {error.digest && (
            <p className="text-2xs text-text-disabled font-mono mb-6">Error ID: {error.digest}</p>
          )}
          <Button onClick={reset} icon={<RefreshCw className="w-3.5 h-3.5" />}>
            Try again
          </Button>
        </div>
      </body>
    </html>
  )
}
