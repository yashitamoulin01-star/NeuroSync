import { AppShell } from '@/components/layout/AppShell'
import { Skeleton } from '@/components/ui/Skeleton'

export default function WorkspaceLoading() {
  return (
    <AppShell title="Workspace">
      <div className="p-6 space-y-4">
        <div className="flex gap-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-9 w-24" />
          ))}
        </div>
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-32 w-full" />
          ))}
        </div>
      </div>
    </AppShell>
  )
}
