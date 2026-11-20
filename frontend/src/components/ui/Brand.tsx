import { ShieldCheck } from 'lucide-react'

export function Brand() {
  return (
    <div className="brand">
      <span className="brand-mark"><ShieldCheck size={21} aria-hidden="true" /></span>
      <span>ShieldRAG</span>
    </div>
  )
}
