'use client'

import { useState } from 'react'
import { WifiOff, RotateCw } from 'lucide-react'
import { Button } from './Button'

interface BackendOfflineProps {
  onRetry?: () => Promise<void>
}

export function BackendOffline({ onRetry }: BackendOfflineProps) {
  const [retrying, setRetrying] = useState(false)

  const handleRetry = async () => {
    if (!onRetry) return
    setRetrying(true)
    try {
      await onRetry()
    } catch (e) {
      console.error(e)
    } finally {
      setRetrying(false)
    }
  }

  return (
    <div className="flex flex-col items-center justify-center text-center p-8 border border-status-danger/20 rounded-xl bg-status-danger/[0.02] shadow-glow-sm min-h-[350px] page-enter">
      <div className="w-14 h-14 rounded-full bg-destructive/10 border border-destructive/20 flex items-center justify-center mb-5 text-destructive animate-bounce">
        <WifiOff className="w-6 h-6" />
      </div>
      <h3 className="text-lg font-bold text-text-primary mb-2">Behavioral Engine Offline</h3>
      <p className="text-sm text-text-secondary max-w-md mb-6 leading-relaxed">
        The NeuroSync backend analysis services are currently unreachable. 
        Please check if the local server process is running, or verify network settings.
      </p>
      {onRetry && (
        <Button 
          variant="outline" 
          size="md" 
          onClick={handleRetry} 
          disabled={retrying}
          icon={
            <RotateCw className={`w-4 h-4 ${retrying ? 'animate-spin' : ''}`} />
          }
        >
          {retrying ? 'Reconnecting...' : 'Retry Connection'}
        </Button>
      )}
    </div>
  )
}
