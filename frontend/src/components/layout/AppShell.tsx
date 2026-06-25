import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'
import { Toaster } from '@/components/ui/Toaster'

interface AppShellProps {
  children: React.ReactNode
  title?: string
  actions?: React.ReactNode
}

export function AppShell({ children, title, actions }: AppShellProps) {
  return (
    <div className="flex h-screen overflow-hidden bg-bg-base">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-hidden">
        <TopBar title={title} actions={actions} />
        <main id="main-content" aria-label="main content" className="flex-1 overflow-y-auto page-enter">{children}</main>
      </div>
      <Toaster />
    </div>
  )
}
