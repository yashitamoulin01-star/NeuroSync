import Link from 'next/link'
import { Button } from '@/components/ui/Button'
import { ArrowLeft } from 'lucide-react'

export default function NotFound() {
  return (
    <div className="bg-bg-base text-text-primary min-h-screen flex items-center justify-center">
      <div className="text-center max-w-md px-6">
        <p className="label-xs text-accent mb-3">404</p>
        <h1 className="page-heading mb-2">Page not found</h1>
        <p className="text-sm text-text-muted mb-6">
          The page you are looking for does not exist or has been moved.
        </p>
        <Link href="/">
          <Button icon={<ArrowLeft className="w-3.5 h-3.5" />}>
            Back to home
          </Button>
        </Link>
      </div>
    </div>
  )
}
