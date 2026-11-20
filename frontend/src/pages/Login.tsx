import React, { useState, useRef, useLayoutEffect } from 'react'
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Loader2 } from 'lucide-react'
import { post, get } from '../lib/api'
import { setTokens, isSafeRedirect, decodeJwtPayload } from '../lib/auth'
import { useAuth } from '../contexts/AuthContext'
import Mark from '../components/brand/Mark'
import { ArrowRightIcon } from '../components/icons'
import type { User } from '../types'

// ─── Schemas ─────────────────────────────────────────────────────────────────

const signInSchema = z.object({
  email: z.string().email('Enter a valid email'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
})

const registerSchema = z
  .object({
    username: z.string().min(2, 'Username must be at least 2 characters'),
    email: z.string().email('Enter a valid email'),
    password: z.string().min(8, 'Password must be at least 8 characters'),
    confirmPassword: z.string(),
  })
  .refine((d) => d.password === d.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  })

type SignInValues = z.infer<typeof signInSchema>
type RegisterValues = z.infer<typeof registerSchema>

// ─── Helpers ─────────────────────────────────────────────────────────────────

interface LoginApiResponse {
  access_token: string
  refresh_token: string
}

async function performLogin(email: string, password: string): Promise<User> {
  const { access_token, refresh_token } = await post<LoginApiResponse>(
    '/auth/login',
    { email, password },
  )
  setTokens(access_token, refresh_token)
  const { sub } = decodeJwtPayload(access_token)
  return get<User>(`/users/${sub}`)
}

// ─── Sub-components ───────────────────────────────────────────────────────────

const AuthInput = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement> & { hasError?: boolean }
>(({ hasError, className, ...props }, ref) => (
  <input
    ref={ref}
    {...props}
    className={`form-input h-10 text-[13.5px] ${hasError ? 'error' : ''} ${className ?? ''}`}
  />
))
AuthInput.displayName = 'AuthInput'

function AuthField({
  label,
  htmlFor,
  error,
  children,
}: {
  label: string
  htmlFor: string
  error?: string
  children: React.ReactNode
}) {
  return (
    <div className="mb-3.5">
      <label htmlFor={htmlFor} className="form-label">
        {label}
      </label>
      {children}
      {error && <p className="form-error">{error}</p>}
    </div>
  )
}

function SubmitButton({
  children,
  loading,
}: {
  children: React.ReactNode
  loading: boolean
}) {
  return (
    <button
      type="submit"
      disabled={loading}
      className="btn-primary group mt-2 h-[42px] w-full justify-center text-[14px]"
    >
      {loading && <Loader2 size={15} className="animate-spin" />}
      {children}
      {!loading && (
        <ArrowRightIcon className="transition-transform duration-200 group-hover:translate-x-[3px]" />
      )}
    </button>
  )
}

// Domains as a graph, data products on the edges, data flowing along contracts.
const EDGES = [
  'M172 70C240 70 310 110 310 182',
  'M438 60C370 60 310 110 310 182',
  'M310 218C310 290 240 330 182 330',
  'M310 218C310 290 380 330 438 330',
  'M500 78C560 140 560 270 500 312',
  'M110 88C50 150 60 260 120 312',
]
const FLOWS = [0, 1, 3, 4]
const PRODUCTS: [number, number][] = [
  [266.5, 99], [348.5, 94], [267.75, 301], [352.25, 301], [545, 202.5], [70, 203.75],
]
const DOMAINS: { label: string; x: number; y: number; color: string }[] = [
  { label: 'Risk', x: 48, y: 52, color: '#F08A6C' },
  { label: 'Credit', x: 438, y: 42, color: '#6FA8F2' },
  { label: 'Payments', x: 248, y: 182, color: '#E2B556' },
  { label: 'Customers', x: 58, y: 312, color: '#4FC4BD' },
  { label: 'Collections', x: 438, y: 312, color: '#B591F2' },
]

function MeshIllustration() {
  return (
    <svg
      viewBox="0 0 620 400"
      className="h-auto w-full max-w-[620px] self-center overflow-visible"
      aria-hidden="true"
    >
      {EDGES.map((d, i) => (
        <path key={d} d={d} pathLength={100} className="mesh-edge" style={{ animationDelay: `${0.26 + i * 0.1}s` }} />
      ))}
      {FLOWS.map((i) => (
        <path key={`flow-${i}`} d={EDGES[i]} className="mesh-flow" />
      ))}
      {PRODUCTS.map(([cx, cy], i) => (
        <circle
          key={`${cx}-${cy}`}
          cx={cx}
          cy={cy}
          r={4.5}
          className="mesh-node fill-bg stroke-tx2"
          strokeWidth={1.5}
          style={{ animationDelay: `${0.85 + Math.floor(i / 2) * 0.1}s` }}
        />
      ))}
      {DOMAINS.map((d, i) => (
        <g key={d.label} className="mesh-node" style={{ animationDelay: `${0.05 + i * 0.07}s` }}>
          <rect x={d.x} y={d.y} width={124} height={36} rx={8} className="fill-panel stroke-line2" />
          <rect x={d.x + 14} y={d.y + 14} width={8} height={8} rx={2} fill={d.color} />
          <text x={d.x + 30} y={d.y + 22.5} className="fill-tx text-[12px] font-medium">
            {d.label}
          </text>
        </g>
      ))}
    </svg>
  )
}

type Mode = 'signin' | 'register'

const HEADINGS: Record<Mode, [string, string]> = {
  signin: ['Sign in to DataMesh', 'Find, trust and govern data products across every domain.'],
  register: ['Create your account', 'You join as a member. A domain owner can grant you more access later.'],
}

function AuthHeading({ mode }: { mode: Mode }) {
  const [title, lead] = HEADINGS[mode]
  return (
    <div key={mode} className="animate-swap">
      <h1 className="text-[24px] font-semibold tracking-[-0.02em] text-tx">{title}</h1>
      <p className="mt-2 text-[13.5px] text-tx2">{lead}</p>
    </div>
  )
}

// Mode tabs — the underline slides between them.
function ModeTabs({ mode, onSwitch }: { mode: Mode; onSwitch: (m: Mode) => void }) {
  return (
    <div className="relative mb-6 mt-7 flex border-b border-line">
      {(['signin', 'register'] as const).map((m) => (
        <button
          key={m}
          type="button"
          onClick={() => onSwitch(m)}
          aria-pressed={mode === m}
          className={`h-[38px] flex-1 text-[13px] font-medium transition-colors duration-150 ${
            mode === m ? 'text-tx' : 'text-tx3 hover:text-tx2'
          }`}
        >
          {m === 'signin' ? 'Sign In' : 'Register'}
        </button>
      ))}
      <span
        aria-hidden="true"
        className="absolute -bottom-px left-0 h-0.5 w-1/2 rounded-full bg-accent-fg transition-transform duration-300 ease-[cubic-bezier(0.3,0.7,0.2,1)]"
        style={{ transform: mode === 'register' ? 'translateX(100%)' : 'translateX(0)' }}
      />
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function Login() {
  const [mode, setMode] = useState<Mode>('signin')
  const [error, setError] = useState<string | null>(null)
  const { user, isLoading, setUser } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const signInForm = useForm<SignInValues>({ resolver: zodResolver(signInSchema) })
  const registerForm = useForm<RegisterValues>({ resolver: zodResolver(registerSchema) })

  // Ref to the dynamic content area — used to animate height when mode changes
  const formContainerRef = useRef<HTMLDivElement>(null)

  // After mode changes, animate the container from its locked height to the new content height
  useLayoutEffect(() => {
    const el = formContainerRef.current
    if (!el || !el.style.height) return

    const lockedHeight = el.style.height

    requestAnimationFrame(() => {
      const target = formContainerRef.current
      if (!target) return

      // Measure true content height without the container constraint
      target.style.height = 'auto'
      const targetHeight = `${target.scrollHeight}px`

      // Restore locked height and flush layout — this becomes the transition's start value
      target.style.height = lockedHeight
      target.getBoundingClientRect()

      // Setting to target now triggers the CSS transition
      target.style.height = targetHeight

      // After the transition, restore auto so errors/validation text can expand the container freely
      const onEnd = () => {
        target.style.height = 'auto'
        target.removeEventListener('transitionend', onEnd)
      }
      target.addEventListener('transitionend', onEnd)
    })
  }, [mode])

  // Already authenticated — skip the login page
  if (!isLoading && user) return <Navigate to="/dashboard" replace />

  const rawRedirect = searchParams.get('redirect') ?? ''
  const redirectTo = isSafeRedirect(rawRedirect) ? rawRedirect : '/dashboard'

  function switchMode(next: Mode) {
    // Lock current height before content changes so the transition has a start value
    const el = formContainerRef.current
    if (el) el.style.height = `${el.scrollHeight}px`
    setMode(next)
    setError(null)
    signInForm.reset()
    registerForm.reset()
  }

  async function handleSignIn(values: SignInValues) {
    setError(null)
    try {
      const fetched = await performLogin(values.email, values.password)
      setUser(fetched)
      navigate(redirectTo, { replace: true })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong. Please try again.')
    }
  }

  async function handleRegister(values: RegisterValues) {
    setError(null)
    registerForm.clearErrors('email')
    try {
      await post('/users', {
        username: values.username,
        email: values.email,
        password: values.password,
      })
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Registration failed. Please try again.'
      if (/email already in use/i.test(msg)) {
        registerForm.setError('email', { message: 'This email is already in use' })
      } else {
        setError(msg)
      }
      return
    }
    try {
      const fetched = await performLogin(values.email, values.password)
      setUser(fetched)
      navigate(redirectTo, { replace: true })
    } catch {
      switchMode('signin')
      setError('Account created. Please sign in to continue.')
    }
  }

  return (
    <div className="flex min-h-screen flex-wrap items-stretch bg-bg">
      {/* Form side */}
      <section className="flex min-w-0 flex-[1_1_440px] flex-col justify-between gap-12 px-6 py-7 sm:px-12">
        <div className="flex animate-enter items-center gap-2.5">
          <Mark size={26} />
          <span className="text-[15px] font-semibold tracking-[-0.01em] text-tx">DataMesh</span>
        </div>

        <div className="w-full max-w-[360px] animate-enter self-center [animation-delay:0.12s]">
          <AuthHeading mode={mode} />
          <ModeTabs mode={mode} onSwitch={switchMode} />

          {/* Dynamic area — height animates smoothly when switching modes */}
          <div ref={formContainerRef} style={{ overflow: 'hidden', transition: 'height 0.3s ease' }}>
            {error && (
              <div
                role="alert"
                className="mb-4 rounded-lg border border-bad/30 bg-bad/10 px-3.5 py-3 text-[13px] text-bad"
              >
                {error}
              </div>
            )}

            {mode === 'signin' && (
              <form onSubmit={signInForm.handleSubmit(handleSignIn)} noValidate className="animate-swap">
                <AuthField
                  label="Email"
                  htmlFor="signin-email"
                  error={signInForm.formState.errors.email?.message}
                >
                  <AuthInput
                    {...signInForm.register('email')}
                    id="signin-email"
                    type="email"
                    placeholder="you@company.com"
                    autoComplete="email"
                    hasError={!!signInForm.formState.errors.email}
                  />
                </AuthField>
                <AuthField
                  label="Password"
                  htmlFor="signin-password"
                  error={signInForm.formState.errors.password?.message}
                >
                  <AuthInput
                    {...signInForm.register('password')}
                    id="signin-password"
                    type="password"
                    placeholder="At least 8 characters"
                    autoComplete="current-password"
                    hasError={!!signInForm.formState.errors.password}
                  />
                </AuthField>
                <SubmitButton loading={signInForm.formState.isSubmitting}>Sign In</SubmitButton>
              </form>
            )}

            {mode === 'register' && (
              <form onSubmit={registerForm.handleSubmit(handleRegister)} noValidate className="animate-swap">
                <AuthField
                  label="Username"
                  htmlFor="reg-username"
                  error={registerForm.formState.errors.username?.message}
                >
                  <AuthInput
                    {...registerForm.register('username')}
                    id="reg-username"
                    type="text"
                    placeholder="johndoe"
                    autoComplete="username"
                    hasError={!!registerForm.formState.errors.username}
                  />
                </AuthField>
                <AuthField
                  label="Email"
                  htmlFor="reg-email"
                  error={registerForm.formState.errors.email?.message}
                >
                  <AuthInput
                    {...registerForm.register('email')}
                    id="reg-email"
                    type="email"
                    placeholder="you@company.com"
                    autoComplete="email"
                    hasError={!!registerForm.formState.errors.email}
                  />
                </AuthField>
                <div className="grid grid-cols-1 gap-x-3 sm:grid-cols-2">
                  <AuthField
                    label="Password"
                    htmlFor="reg-password"
                    error={registerForm.formState.errors.password?.message}
                  >
                    <AuthInput
                      {...registerForm.register('password')}
                      id="reg-password"
                      type="password"
                      placeholder="8+ characters"
                      autoComplete="new-password"
                      hasError={!!registerForm.formState.errors.password}
                    />
                  </AuthField>
                  <AuthField
                    label="Confirm Password"
                    htmlFor="reg-confirm"
                    error={registerForm.formState.errors.confirmPassword?.message}
                  >
                    <AuthInput
                      {...registerForm.register('confirmPassword')}
                      id="reg-confirm"
                      type="password"
                      placeholder="Repeat it"
                      autoComplete="new-password"
                      hasError={!!registerForm.formState.errors.confirmPassword}
                    />
                  </AuthField>
                </div>
                <SubmitButton loading={registerForm.formState.isSubmitting}>Create Account</SubmitButton>
              </form>
            )}
          </div>
        </div>

        <footer className="flex animate-enter items-center justify-between gap-4 text-xs text-tx3 [animation-delay:0.2s]">
          <span>Access is managed by your workspace admin.</span>
        </footer>
      </section>

      {/* Illustration side */}
      <section
        aria-hidden="true"
        className="mesh-dots hidden min-w-0 flex-[1_1_560px] flex-col justify-center gap-8 border-l border-line bg-side px-14 py-12 lg:flex"
      >
        <MeshIllustration />
        <div className="w-full max-w-[620px] animate-enter self-center [animation-delay:1.25s]">
          <p className="max-w-[340px] text-[17px] font-semibold leading-snug tracking-[-0.01em] text-tx">
            Domains publish data products. Contracts make them dependable.
          </p>
          <div className="mt-3.5 flex flex-wrap gap-4 text-xs text-tx3">
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-sm bg-tx3" />
              Domain
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full border-[1.5px] border-tx2" />
              Data product
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="relative h-px w-5 bg-line2">
                <span className="absolute left-1/2 top-1/2 h-[3px] w-[3px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-accent-fg" />
              </span>
              Contracted flow
            </span>
          </div>
        </div>
      </section>
    </div>
  )
}
