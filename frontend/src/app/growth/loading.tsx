import { AppShell } from '@/components/layout/AppShell'
import { Skeleton } from '@/components/ui/Skeleton'

export default function GrowthLoading() {
  return (
    <AppShell title="Growth">
      <div className="p-6 space-y-6">
        <div className="grid grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
        <Skeleton className="h-56 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    </AppShell>
  )
}
