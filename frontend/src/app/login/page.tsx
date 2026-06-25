'use client'
import { useState, FormEvent } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { BrainCircuit, Eye, EyeOff, AlertCircle, Lock } from 'lucide-react'
import { useAuth } from '@/lib/auth'
import { Button } from '@/components/ui/Button'

export default function LoginPage() {
  const router   = useRouter()
  const { login } = useAuth()

  const [tenantId, setTenantId] = useState('default')
  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [showPw,   setShowPw]   = useState(false)
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await login(tenantId, email, password)
      router.push('/dashboard')
    } catch (err: any) {
      setError(err.message ?? 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-bg-base flex items-center justify-center p-4">

      {/* Background glow */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px]
          bg-[radial-gradient(ellipse_at_center,rgba(99,102,241,0.06)_0%,transparent_65%)]" />
      </div>

      <div className="relative w-full max-w-sm">

        {/* Logo */}
        <Link href="/" className="flex items-center gap-2.5 mb-8 justify-center group">
          <div className="w-9 h-9 rounded-xl bg-accent-bright flex items-center justify-center shadow-glow-sm
            group-hover:shadow-[0_0_0_3px_rgba(99,102,241,0.15)] transition-shadow">
            <BrainCircuit className="w-5 h-5 text-white" />
          </div>
          <div>
            <p className="text-base font-bold text-text-primary tracking-tight">NuanceAI</p>
            <p className="text-2xs text-text-muted leading-none">NeuroSync Platform</p>
          </div>
        </Link>

        {/* Card */}
        <div className="rounded-2xl border border-border bg-bg-card p-7 shadow-card">

          <div className="flex items-center gap-2 mb-1">
            <Lock className="w-4 h-4 text-accent" />
            <h1 className="text-lg font-bold text-text-primary">Sign in</h1>
          </div>
          <p className="text-xs text-text-muted mb-6 pl-6">Access your behavioral analytics workspace</p>

          {error && (
            <div className="flex items-start gap-2 rounded-lg border border-metric-stress/25 bg-metric-stress/8 px-3 py-2.5 mb-5">
              <AlertCircle className="w-3.5 h-3.5 text-metric-stress mt-0.5 flex-shrink-0" />
              <p className="text-xs text-metric-stress">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">

            {/* Tenant ID */}
            <div>
              <label htmlFor="login-tenant" className="block text-xs font-medium text-text-secondary mb-1.5">
                Tenant ID
              </label>
              <input
                id="login-tenant"
                value={tenantId}
                onChange={e => setTenantId(e.target.value)}
                placeholder="default"
                required
                className="w-full h-9 rounded-lg border border-border bg-bg-base px-3 text-sm text-text-primary
                  placeholder:text-text-disabled focus:outline-none focus:ring-2 focus:ring-accent
                  focus:border-transparent transition-colors hover:border-border-strong"
              />
              <p className="text-2xs text-text-disabled mt-1">Your organization&apos;s tenant workspace ID</p>
            </div>

            {/* Email */}
            <div>
              <label htmlFor="login-email" className="block text-xs font-medium text-text-secondary mb-1.5">Email</label>
              <input
                id="login-email"
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@company.com"
                required
                autoComplete="email"
                className="w-full h-9 rounded-lg border border-border bg-bg-base px-3 text-sm text-text-primary
                  placeholder:text-text-disabled focus:outline-none focus:ring-2 focus:ring-accent
                  focus:border-transparent transition-colors hover:border-border-strong"
              />
            </div>

            {/* Password */}
            <div>
              <label htmlFor="login-password" className="block text-xs font-medium text-text-secondary mb-1.5">Password</label>
              <div className="relative">
                <input
                  id="login-password"
                  type={showPw ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="Minimum 8 characters"
                  required
                  autoComplete="current-password"
                  className="w-full h-9 rounded-lg border border-border bg-bg-base px-3 pr-10 text-sm text-text-primary
                    placeholder:text-text-disabled focus:outline-none focus:ring-2 focus:ring-accent
                    focus:border-transparent transition-colors hover:border-border-strong"
                />
                <button
                  type="button"
                  tabIndex={-1}
                  onClick={() => setShowPw(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-secondary transition-colors"
                >
                  {showPw ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                </button>
              </div>
            </div>

            <Button
              variant="primary"
              className="w-full mt-2"
              disabled={loading}
            >
              {loading ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>

          <div className="mt-5 pt-5 border-t border-border flex items-center justify-between text-xs text-text-muted">
            <span>Accounts are provisioned by your organization admin.</span>
            <Link href="/dashboard" className="hover:text-text-secondary transition-colors">
              Continue as guest
            </Link>
          </div>
        </div>

        <p className="text-center text-2xs text-text-disabled mt-4">
          By signing in, you accept the NeuroSync Responsible AI Policy
        </p>
      </div>
    </div>
  )
}
