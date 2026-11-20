import { useState } from 'react'
import type { ReactNode } from 'react'
import { ChevronDown, LayoutDashboard, LogOut, Menu, ShieldCheck, X } from 'lucide-react'
import { NavLink } from 'react-router'
import { Brand } from '../ui/Brand'
import { useAuth } from '../../features/auth/AuthProvider'
import type { Profile, Role } from '../../features/auth/schemas/auth'

export const roleLabels: Record<Role, string> = { student: 'Student', admin: 'Admin' }

export function Workspace({ profile, children }: { profile: Profile; children: ReactNode }) {
  const { store } = useAuth()
  const [open, setOpen] = useState(false)
  const identity = profile.display_name?.trim() || profile.email || roleLabels[profile.role]

  return (
    <div className="workspace">
      <a href="#workspace-main" className="skip-link">Skip to content</a>
      <aside className="sidebar" data-open={open}>
        <div className="sidebar-top">
          <Brand />
          <button type="button" className="icon-button menu-toggle" aria-controls="workspace-navigation"
            aria-expanded={open} aria-label={open ? 'Close navigation' : 'Open navigation'}
            onClick={() => setOpen(!open)}>
            {open ? <X size={22} aria-hidden="true" /> : <Menu size={22} aria-hidden="true" />}
          </button>
        </div>
        <nav id="workspace-navigation" aria-label="Workspace">
          <p className="sidebar-context">{roleLabels[profile.role]} workspace</p>
          <NavLink to={`/${profile.role}`} end onClick={() => setOpen(false)}>
            <LayoutDashboard size={18} aria-hidden="true" />
            Overview
          </NavLink>
        </nav>
      </aside>
      <div className="workspace-body">
        <header className="workspace-header">
          <span className="header-path">Workspace <span aria-hidden="true">/</span> Overview</span>
          <details className="profile-menu">
            <summary aria-label="Account menu">
              <span className="avatar" aria-hidden="true">{identity.slice(0, 1).toUpperCase()}</span>
              <span className="profile-text">
                <strong>{identity}</strong>
                <span>{roleLabels[profile.role]}</span>
              </span>
              <ChevronDown size={16} aria-hidden="true" />
            </summary>
            <div className="profile-options">
              <button type="button" className="button button-secondary" onClick={() => void store.signOut()}>
                <LogOut size={16} aria-hidden="true" /> Sign out
              </button>
            </div>
          </details>
        </header>
        <main id="workspace-main" tabIndex={-1} className="workspace-main">
          <span className="status-chip">
            <ShieldCheck size={16} aria-hidden="true" /> Verified {roleLabels[profile.role]} access
          </span>
          {children}
        </main>
      </div>
    </div>
  )
}
