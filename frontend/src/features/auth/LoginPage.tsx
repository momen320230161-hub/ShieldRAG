import { useRef, useState } from 'react'
import { Eye, EyeOff, LoaderCircle, LockKeyhole } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Brand } from '../../components/ui/Brand'
import { Alert } from '../../components/ui/Feedback'
import { useAuth } from './AuthProvider'
import { loginSchema } from './schemas/auth'
import type { LoginInput } from './schemas/auth'

export function LoginPage() {
  const { view, store } = useAuth()
  const [visible, setVisible] = useState(false)
  const [feedback, setFeedback] = useState<string>()
  const submitting = useRef(false)
  const { register, handleSubmit, resetField, formState: { errors, isSubmitting } } = useForm<LoginInput>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: '', password: '' },
  })

  async function submit(input: LoginInput) {
    if (submitting.current) return
    submitting.current = true
    setFeedback(undefined)
    try {
      setFeedback(await store.signIn(input))
    } finally {
      submitting.current = false
      resetField('password')
    }
  }

  const PasswordIcon = visible ? EyeOff : Eye

  return (
    <main className="login-layout">
      <section className="login-brand">
        <Brand />
        <div className="login-art" aria-hidden="true">
          <span className="art-orbit orbit-outer" />
          <span className="art-orbit orbit-inner" />
          <span className="art-node node-one" />
          <span className="art-node node-two" />
          <span className="art-lock"><LockKeyhole size={44} strokeWidth={1.5} /></span>
        </div>
        <div className="login-brand-copy">
          <p>Academic knowledge<br />workspace</p>
          <span>Your account determines which workspace opens.</span>
        </div>
      </section>

      <section className="login-panel" aria-labelledby="login-title">
        <div className="login-form">
          <div className="login-heading">
            <h1 id="login-title">Sign in to ShieldRAG</h1>
            <p>Use your assigned account to open your workspace.</p>
          </div>

          <form onSubmit={handleSubmit(submit)} noValidate>
            {(feedback || (view.status === 'anonymous' && view.notice)) && (
              <Alert>{feedback || (view.status === 'anonymous' && view.notice)}</Alert>
            )}
            <div className="field">
              <label htmlFor="email">Email address</label>
              <input id="email" type="email" autoComplete="username" inputMode="email"
                required aria-invalid={Boolean(errors.email)}
                aria-describedby={errors.email ? 'email-error' : undefined}
                placeholder="you@example.edu" {...register('email')} />
              {errors.email && <span className="field-error" id="email-error">{errors.email.message}</span>}
            </div>
            <div className="field">
              <label htmlFor="password">Password</label>
              <div className="password-field">
                <input id="password" type={visible ? 'text' : 'password'} autoComplete="current-password"
                  required aria-invalid={Boolean(errors.password)}
                  aria-describedby={errors.password ? 'password-error' : undefined}
                  {...register('password')} />
                <button className="icon-button" type="button" aria-controls="password"
                  aria-label={visible ? 'Hide password' : 'Show password'}
                  onClick={() => setVisible(!visible)}>
                  <PasswordIcon size={19} aria-hidden="true" />
                </button>
              </div>
              {errors.password && <span className="field-error" id="password-error">{errors.password.message}</span>}
            </div>
            <button className="button button-primary login-submit" type="submit" disabled={isSubmitting}>
              {isSubmitting && <LoaderCircle size={18} className="motion-safe:animate-spin" aria-hidden="true" />}
              {isSubmitting ? 'Signing in…' : 'Sign in'}
            </button>
          </form>

          <p className="login-help">Need an account? Contact your ShieldRAG administrator.</p>
        </div>
      </section>
    </main>
  )
}
