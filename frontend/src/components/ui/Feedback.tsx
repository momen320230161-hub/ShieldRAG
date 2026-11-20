import { AlertCircle, LoaderCircle } from 'lucide-react'
import type { ReactNode } from 'react'
import { Brand } from './Brand'

export function Alert({ children }: { children: ReactNode }) {
  return (
    <div className="alert" role="alert">
      <AlertCircle size={18} aria-hidden="true" />
      <span>{children}</span>
    </div>
  )
}

export function Loading() {
  return (
    <main className="feedback-page">
      <Brand />
      <p role="status" className="flex items-center gap-3">
        <LoaderCircle size={20} className="motion-safe:animate-spin" aria-hidden="true" />
        Checking workspace access…
      </p>
    </main>
  )
}

export function FeedbackPage({ title, children, actions }: {
  title: string
  children: ReactNode
  actions?: ReactNode
}) {
  return (
    <main className="feedback-page">
      <Brand />
      <section>
        <h1>{title}</h1>
        <div className="feedback-copy">{children}</div>
        {actions && <div className="feedback-actions">{actions}</div>}
      </section>
    </main>
  )
}
