import { Activity, ClipboardCheck, Database, FileText, MessageSquareText, ShieldCheck } from 'lucide-react'
import { Workspace } from '../components/layout/Workspace'
import type { Profile } from '../features/auth/schemas/auth'

const dashboards = {
  student: {
    title: 'Student dashboard',
    description: 'Your workspace for approved learning material and source-grounded research.',
    features: [
      { icon: FileText, name: 'Documents', description: 'Find approved learning materials you can access.' },
      { icon: MessageSquareText, name: 'Ask questions', description: 'Ask about approved materials and follow supporting citations.' },
      { icon: ShieldCheck, name: 'Secure RAG', description: 'Ask questions with additional security screening.' },
    ],
  },
  admin: {
    title: 'Admin dashboard',
    description: 'Your workspace for document oversight and retrieval security.',
    features: [
      { icon: ClipboardCheck, name: 'Document review', description: 'Review documents before making them available.' },
      { icon: Database, name: 'Document indexing', description: 'Prepare approved documents for retrieval.' },
      { icon: Activity, name: 'Security and evaluation', description: 'Review security activity and evaluate answer quality.' },
    ],
  },
}

export function DashboardPage({ profile }: { profile: Profile }) {
  const { title, description, features } = dashboards[profile.role]

  return (
    <Workspace profile={profile}>
      <div className="dashboard-heading">
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <section className="upcoming-panel" aria-labelledby="upcoming-title">
        <h2 id="upcoming-title">Coming to this workspace</h2>
        <ul>
          {features.map(({ icon: Icon, name, description }) => (
            <li key={name}>
              <span className="feature-icon"><Icon size={21} aria-hidden="true" /></span>
              <div><h3>{name}</h3><p>{description}</p></div>
            </li>
          ))}
        </ul>
      </section>
    </Workspace>
  )
}
