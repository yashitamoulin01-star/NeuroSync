import { AppShell } from '@/components/layout/AppShell'
import { Skeleton } from '@/components/ui/Skeleton'

export default function DashboardLoading() {
  return (
    <AppShell title="Dashboard">
      <div className="p-6 space-y-6">
        <div className="flex gap-6">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-20 flex-1" />
          ))}
        </div>
        <div className="grid grid-cols-3 gap-6">
          <Skeleton className="col-span-2 h-64" />
          <Skeleton className="h-64" />
        </div>
        <Skeleton className="h-48 w-full" />
      </div>
    </AppShell>
  )
}
