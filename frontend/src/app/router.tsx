import type { ReactNode } from 'react'
import { Link, Navigate, Route, Routes } from 'react-router'
import { Alert, FeedbackPage, Loading } from '../components/ui/Feedback'
import { useAuth } from '../features/auth/AuthProvider'
import { LoginPage } from '../features/auth/LoginPage'
import type { Role } from '../features/auth/schemas/auth'
import { DashboardPage } from '../pages/DashboardPage'

function SessionGate({ children }: { children: ReactNode }) {
  const { view, store } = useAuth()
  if (view.status === 'checking') return <Loading />
  if (view.status === 'unavailable') {
    return (
      <FeedbackPage title="Workspace access could not be verified" actions={
        <>
          <button className="button button-primary" onClick={store.retryProfile}>Try again</button>
          <button className="button button-secondary" onClick={() => void store.signOut()}>Sign out</button>
        </>
      }>
        <Alert>{view.message}</Alert>
      </FeedbackPage>
    )
  }
  return children
}

function Landing({ login }: { login?: boolean }) {
  const { view } = useAuth()
  if (view.status === 'ready') return <Navigate replace to={`/${view.profile.role}`} />
  if (view.status === 'denied') return <Navigate replace to="/unauthorized" />
  return login ? <LoginPage /> : <Navigate replace to="/login" />
}

function Protected({ role }: { role: Role }) {
  const { view } = useAuth()
  if (view.status === 'anonymous') return <Navigate replace to="/login" />
  if (view.status !== 'ready' || view.profile.role !== role) return <Navigate replace to="/unauthorized" />
  return <DashboardPage key={view.profile.id} profile={view.profile} />
}

function Unauthorized() {
  const { view, store } = useAuth()
  if (view.status === 'anonymous') return <Navigate replace to="/login" />
  return (
    <FeedbackPage title="Access denied" actions={
      view.status === 'ready'
        ? <Link className="button button-primary" to={`/${view.profile.role}`}>Go to my dashboard</Link>
        : <button className="button button-secondary" onClick={() => void store.signOut()}>Sign out</button>
    }>
      <p>Your account does not have access to this workspace.</p>
    </FeedbackPage>
  )
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<SessionGate><Landing /></SessionGate>} />
      <Route path="/login" element={<SessionGate><Landing login /></SessionGate>} />
      <Route path="/student" element={<SessionGate><Protected role="student" /></SessionGate>} />
      <Route path="/admin" element={<SessionGate><Protected role="admin" /></SessionGate>} />
      <Route path="/unauthorized" element={<SessionGate><Unauthorized /></SessionGate>} />
      <Route path="*" element={
        <FeedbackPage title="Page not found"
          actions={<Link className="button button-primary" to="/">Go to workspace</Link>}>
          <p>Check the address or return to your workspace.</p>
        </FeedbackPage>
      } />
    </Routes>
  )
}
