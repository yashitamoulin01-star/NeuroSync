'use client'
import { useState, useEffect } from 'react'
import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-react'
import { subscribeToasts } from '@/lib/toast'
import type { ToastEntry } from '@/lib/toast'
import { cn } from '@/lib/utils'

const META: Record<string, { Icon: React.ElementType; classes: string }> = {
  success: { Icon: CheckCircle,   classes: 'border-status-success/25 bg-status-success/8 text-status-success' },
  error:   { Icon: XCircle,       classes: 'border-status-danger/25  bg-status-danger/8  text-status-danger'  },
  warning: { Icon: AlertTriangle, classes: 'border-status-warning/25 bg-status-warning/8 text-status-warning' },
  info:    { Icon: Info,          classes: 'border-border             bg-bg-card          text-text-secondary' },
}

export function Toaster() {
  const [toasts, setToasts] = useState<ToastEntry[]>([])

  useEffect(() => {
    return subscribeToasts(t => {
      setToasts(prev => [...prev, t].slice(-4))
      setTimeout(() => setToasts(prev => prev.filter(p => p.id !== t.id)), 3800)
    })
  }, [])

  if (!toasts.length) return null

  return (
    <div className="fixed bottom-4 right-4 z-[200] flex flex-col gap-2 no-print" role="region" aria-label="Notifications" aria-live="polite">
      {toasts.map(t => {
        const m = META[t.type] ?? META.info
        return (
          <div key={t.id} className={cn('flex items-center gap-3 rounded-xl border px-4 py-3 shadow-card text-xs font-medium toast-enter', m.classes)}>
            <m.Icon className="w-3.5 h-3.5 flex-shrink-0" aria-hidden />
            <span className="flex-1">{t.message}</span>
            <button
              onClick={() => setToasts(prev => prev.filter(p => p.id !== t.id))}
              className="opacity-50 hover:opacity-100 transition-opacity ml-1"
              aria-label="Dismiss"
            >
              <X className="w-3 h-3" />
            </button>
          </div>
        )
      })}
    </div>
  )
}
