'use client'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import {
  BrainCircuit, Menu, X, LogOut, User, ChevronDown, Settings,
} from 'lucide-react'
import { useState, useRef, useEffect } from 'react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/Button'
import { useAuth } from '@/lib/auth'
import { setEnterpriseToken } from '@/lib/api'
import { CORE_NAV, ENTERPRISE_NAV } from '@/lib/nav'

interface TopBarProps {
  title?: string
  actions?: React.ReactNode
}

function UserMenu() {
  const { user, logout, isAuthenticated } = useAuth()
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const ref  = useRef<HTMLDivElement>(null)

  // Keep the API client token in sync
  useEffect(() => {
    const stored = localStorage.getItem('nuanceai_auth')
    if (stored) {
      try { setEnterpriseToken(JSON.parse(stored).token) } catch {}
    }
  }, [isAuthenticated])

  // Close on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  if (!isAuthenticated || !user) {
    return (
      <Link href="/login">
        <Button variant="ghost" size="sm" icon={<User className="w-3.5 h-3.5" />}>
          Sign in
        </Button>
      </Link>
    )
  }

  function initials(name: string) {
    return name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()
  }

  function handleLogout() {
    setOpen(false)
    setEnterpriseToken(null)
    logout()
    router.push('/login')
  }

  const primary_role = user.roles?.[0] ?? 'viewer'

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-bg-hover transition-colors group"
      >
        {/* Avatar */}
        <div className="w-7 h-7 rounded-full bg-accent/20 border border-accent/30 flex items-center justify-center flex-shrink-0">
          <span className="text-2xs font-bold text-accent">{initials(user.display_name || user.email)}</span>
        </div>
        <div className="hidden sm:block text-left">
          <p className="text-xs font-medium text-text-primary leading-none">
            {user.display_name || user.email.split('@')[0]}
          </p>
          <p className="text-2xs text-text-muted leading-none mt-0.5 capitalize">{primary_role.replace('_', ' ')}</p>
        </div>
        <ChevronDown className={cn('w-3 h-3 text-text-muted transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-52 rounded-xl border border-border bg-bg-card shadow-card z-50 overflow-hidden">
          {/* Profile header */}
          <div className="px-4 py-3 border-b border-border">
            <p className="text-xs font-semibold text-text-primary truncate">
              {user.display_name || user.email}
            </p>
            <p className="text-2xs text-text-muted truncate mt-0.5">{user.email}</p>
            <p className="text-2xs text-accent mt-1 capitalize">{primary_role.replace(/_/g, ' ')}</p>
          </div>

          {/* Menu items */}
          <div className="p-1">
            <Link href="/settings" onClick={() => setOpen(false)}
              className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs text-text-secondary hover:text-text-primary hover:bg-bg-hover transition-colors">
              <Settings className="w-3.5 h-3.5 text-text-muted" />
              Settings
            </Link>

            <button
              onClick={handleLogout}
              className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs text-status-danger hover:bg-status-danger/8 transition-colors"
            >
              <LogOut className="w-3.5 h-3.5" />
              Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export function TopBar({ title, actions }: TopBarProps) {
  const path    = usePathname()
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <>
      {/* Top bar */}
      <header className="h-14 border-b border-border bg-bg-surface/80 backdrop-blur-sm sticky top-0 z-30 flex items-center px-4 gap-4">
        {/* Mobile logo */}
        <Link href="/dashboard" className="flex items-center gap-2 md:hidden">
          <div className="w-7 h-7 rounded-lg bg-accent-bright flex items-center justify-center shadow-glow-sm">
            <BrainCircuit className="w-4 h-4 text-white" />
          </div>
          <span className="text-sm font-bold text-text-primary">NuanceAI</span>
        </Link>

        {/* Page title */}
        {title && (
          <h1 className="hidden md:block text-base font-bold tracking-tight text-text-primary">{title}</h1>
        )}

        <div className="flex-1" />
        {actions && <div className="flex items-center gap-2">{actions}</div>}

        {/* User menu */}
        <UserMenu />

        {/* Mobile menu toggle */}
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          className="md:hidden p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-hover transition-colors"
        >
          {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </header>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 md:hidden" onClick={() => setMobileOpen(false)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm animate-fade-in" />
          <nav
            className="absolute top-14 left-0 right-0 max-h-[calc(100vh-3.5rem)] overflow-y-auto bg-bg-surface border-b border-border p-3 space-y-1"
            onClick={e => e.stopPropagation()}
            aria-label="Mobile navigation"
          >
            <p className="px-4 py-1 text-2xs font-semibold text-text-disabled uppercase tracking-widest">Platform</p>
            {CORE_NAV.map(({ href, label, icon: Icon }) => {
              const active = href === '/dashboard' ? path === '/dashboard' : path.startsWith(href)
              return (
                <Link
                  key={href}
                  href={href}
                  onClick={() => setMobileOpen(false)}
                  className={cn(
                    'flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm transition-colors',
                    active ? 'bg-accent-glow text-accent font-medium' : 'text-text-secondary hover:text-text-primary hover:bg-bg-hover',
                  )}
                >
                  <Icon className={cn('w-4 h-4', active ? 'text-accent' : 'text-text-disabled')} />
                  {label}
                </Link>
              )
            })}

            <div className="border-t border-border/40 my-2 pt-2">
              <p className="px-4 py-1 text-2xs font-semibold text-text-disabled uppercase tracking-widest">Enterprise</p>
              {ENTERPRISE_NAV.map(({ href, label, icon: Icon }) => {
                const active = path.startsWith(href)
                return (
                  <Link
                    key={href}
                    href={href}
                    onClick={() => setMobileOpen(false)}
                    className={cn(
                      'flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm transition-colors',
                      active ? 'bg-accent-glow text-accent font-medium' : 'text-text-secondary hover:text-text-primary hover:bg-bg-hover',
                    )}
                  >
                    <Icon className={cn('w-4 h-4', active ? 'text-accent' : 'text-text-disabled')} />
                    {label}
                  </Link>
                )
              })}
            </div>
          </nav>
        </div>
      )}
    </>
  )
}
