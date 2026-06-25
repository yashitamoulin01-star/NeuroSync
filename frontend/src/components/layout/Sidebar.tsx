'use client'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import {
  BrainCircuit, PlayCircle, LogIn, LogOut, Cpu, ChevronDown, ChevronUp,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { api, setEnterpriseToken } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { CORE_NAV, ENTERPRISE_NAV } from '@/lib/nav'

// ── NavLink ───────────────────────────────────────────────────────────────────

function NavLink({
  href, label, icon: Icon, isActive, indent = false,
}: {
  href: string; label: string; icon: React.ElementType; isActive: boolean; indent?: boolean
}) {
  return (
    <Link
      href={href}
      aria-current={isActive ? 'page' : undefined}
      className={cn(
        'flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-all duration-150 group',
        indent && 'pl-4',
        isActive
          ? 'bg-accent-glow text-accent font-medium'
          : 'text-text-muted hover:text-text-primary hover:bg-bg-hover',
      )}
    >
      <Icon className={cn(
        'w-4 h-4 flex-shrink-0 transition-colors',
        isActive ? 'text-accent' : 'text-text-disabled group-hover:text-text-muted',
      )} />
      <span className="flex-1 truncate">{label}</span>
    </Link>
  )
}

// ── NavSection ────────────────────────────────────────────────────────────────

function NavSection({
  label, items, path, collapsible = false,
}: {
  label: string
  items: ReadonlyArray<{ href: string; label: string; icon: React.ElementType }>
  path: string
  collapsible?: boolean
}) {
  const hasActive   = items.some(i => path.startsWith(i.href))
  const [open, setOpen] = useState(!collapsible || hasActive)

  return (
    <div className="pt-1">
      <button
        onClick={() => collapsible && setOpen(v => !v)}
        className={cn(
          'w-full flex items-center gap-1.5 px-3 py-1 mb-0.5',
          collapsible ? 'cursor-pointer hover:text-text-muted transition-colors' : 'cursor-default',
        )}
        aria-expanded={collapsible ? open : undefined}
      >
        <span className="text-2xs font-semibold text-text-disabled uppercase tracking-widest flex-1 text-left">
          {label}
        </span>
        {collapsible && (
          open
            ? <ChevronUp className="w-3 h-3 text-text-disabled" />
            : <ChevronDown className="w-3 h-3 text-text-disabled" />
        )}
      </button>

      {open && items.map(({ href, label: lbl, icon: Icon }) => {
        const isActive = href === '/dashboard'
          ? path === '/dashboard'
          : path.startsWith(href)
        return (
          <NavLink key={href} href={href} label={lbl} icon={Icon} isActive={isActive} />
        )
      })}
    </div>
  )
}

// ── Sidebar ───────────────────────────────────────────────────────────────────

export function Sidebar() {
  const path   = usePathname()
  const router = useRouter()
  const { user, token, isAuthenticated, logout } = useAuth()
  const [f1, setF1]         = useState<number | null>(null)
  const [online, setOnline] = useState(false)

  useEffect(() => { setEnterpriseToken(token) }, [token])

  useEffect(() => {
    let mounted = true
    async function check() {
      try {
        const h = await api.healthDetailed()
        if (!mounted) return
        setOnline(h.status === 'ok')
        if (h.components.deberta.best_f1 != null) setF1(h.components.deberta.best_f1)
      } catch {
        if (mounted) setOnline(false)
      }
    }
    check()
    const id = setInterval(check, 30_000)
    return () => { mounted = false; clearInterval(id) }
  }, [])

  return (
    <aside
      className="hidden md:flex flex-col w-[220px] border-r border-border bg-bg-surface h-screen sticky top-0 flex-shrink-0"
      aria-label="Main navigation"
    >
      {/* Logo */}
      <div className="px-4 pt-5 pb-4 border-b border-border">
        <Link href="/dashboard" className="flex items-center gap-2.5 group">
          <div className="w-7 h-7 rounded-lg bg-accent-bright flex items-center justify-center flex-shrink-0 shadow-glow-sm">
            <BrainCircuit className="w-4 h-4 text-white" />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-bold text-text-primary tracking-tight leading-tight">NuanceAI</p>
            <p className="text-[10px] text-text-disabled leading-none mt-0.5 tracking-wide uppercase">NeuroSync Platform</p>
          </div>
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
        {CORE_NAV.map(({ href, label, icon: Icon }) => {
          const isActive = href === '/dashboard' ? path === '/dashboard' : path.startsWith(href)
          return <NavLink key={href} href={href} label={label} icon={Icon} isActive={isActive} />
        })}

        <NavSection
          label="Enterprise"
          items={ENTERPRISE_NAV}
          path={path}
          collapsible={true}
        />
      </nav>

      {/* Demo quick-access */}
      <div className="px-2 pb-2">
        <Link
          href="/session/new"
          className={cn(
            'flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-all duration-150 group',
            path === '/session/new'
              ? 'bg-accent-glow text-accent font-medium'
              : 'text-text-muted hover:text-text-primary hover:bg-bg-hover',
          )}
        >
          <PlayCircle className={cn(
            'w-4 h-4 flex-shrink-0',
            path === '/session/new' ? 'text-accent' : 'text-text-disabled group-hover:text-text-muted',
          )} />
          New Session
        </Link>
      </div>

      {/* Auth section */}
      <div className="px-2 pb-2">
        {isAuthenticated && user ? (
          <div className="rounded-lg border border-border bg-bg-card p-3">
            <div className="flex items-center gap-2 min-w-0">
              <div className="w-7 h-7 rounded-full bg-accent/10 border border-accent/20 flex items-center justify-center flex-shrink-0">
                <span className="text-[10px] font-bold text-accent">
                  {(user.display_name || user.email).slice(0, 2).toUpperCase()}
                </span>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-text-primary truncate leading-tight">
                  {user.display_name || user.email.split('@')[0]}
                </p>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <span className="text-[9px] font-semibold text-accent bg-accent/15 border border-accent/25 px-1.5 py-0.5 rounded-full leading-none">
                    {user.roles && user.roles.length > 0
                      ? user.roles[0].charAt(0).toUpperCase() + user.roles[0].slice(1).toLowerCase()
                      : 'Recruiter'}
                  </span>
                </div>
              </div>
            </div>
            <button
              onClick={() => { setEnterpriseToken(null); logout(); router.push('/login') }}
              aria-label="Sign out"
              className="flex items-center gap-1.5 text-[11px] text-text-disabled hover:text-status-danger transition-colors mt-2.5"
            >
              <LogOut className="w-3 h-3" />
              Sign out
            </button>
          </div>
        ) : (
          <NavLink href="/login" label="Sign in" icon={LogIn} isActive={path === '/login'} />
        )}
      </div>

      {/* Engine status */}
      <div className="p-3 border-t border-border">
        <div className="rounded-lg bg-bg-card border border-border px-3 py-2.5">
          <div className="flex items-center gap-2 mb-1.5">
            <Cpu className={cn('w-3.5 h-3.5 flex-shrink-0', online ? 'text-status-success' : 'text-text-disabled')} />
            <span className="text-xs text-text-secondary font-medium truncate flex-1">
              {online ? 'MBA Engine' : 'Offline'}
            </span>
            <div className="relative w-1.5 h-1.5 flex-shrink-0" aria-hidden="true">
              {online && (
                <span className="absolute inset-0 rounded-full bg-status-success/60 ping-ring" />
              )}
              <span
                className={cn('absolute inset-0 rounded-full', online ? 'bg-status-success' : 'bg-text-disabled')}
              />
            </div>
          </div>
          <p className="text-[10px] text-text-disabled leading-relaxed">
            {online
              ? `DeBERTa v3 · F1 ${f1 != null ? `${Math.round(f1 * 100)}%` : '82.4%'}`
              : 'Start backend to enable AI analysis'}
          </p>
          <div
            className="mt-2 h-0.5 bg-bg-hover rounded-full overflow-hidden"
            role="progressbar"
            aria-valuenow={f1 != null ? Math.round(f1 * 100) : 82}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div
              className={cn('h-full rounded-full transition-all duration-1000', online ? 'bg-status-success' : 'bg-text-disabled')}
              style={{ width: online ? `${(f1 ?? 0.824) * 100}%` : '0%' }}
            />
          </div>
          <div className="flex items-center justify-between text-[9px] text-text-disabled mt-2.5 pt-2 border-t border-border/30">
            <span>Version</span>
            <span className="font-semibold px-1 py-0.5 rounded bg-bg-hover">v1.2.0-rc1</span>
          </div>
        </div>
      </div>
    </aside>
  )
}
