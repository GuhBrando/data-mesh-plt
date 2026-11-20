import { ButtonHTMLAttributes, ReactNode } from 'react'
import Spinner from './Spinner'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost'
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
  children: ReactNode
}

const variantClasses: Record<string, string> = {
  primary: 'btn-primary',
  secondary: 'btn-secondary',
  danger:
    'inline-flex items-center gap-2 h-8 px-3 bg-bad text-white dark:text-slate-900 text-[13px] font-medium rounded-lg whitespace-nowrap transition-[filter] hover:brightness-110 focus:outline-none focus-visible:ring-[3px] focus-visible:ring-bad/40 disabled:opacity-50 disabled:cursor-not-allowed',
  ghost:
    'inline-flex items-center gap-2 h-8 px-3 text-tx2 text-[13px] font-medium rounded-lg hover:bg-hover hover:text-tx focus:outline-none focus-visible:ring-2 focus-visible:ring-line2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed',
}

const sizeClasses: Record<string, string> = {
  sm: '!h-7 text-xs !px-2.5',
  md: '',
  lg: '!h-10 text-sm !px-4',
}

export default function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  children,
  className = '',
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      type="button"
      className={`${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <Spinner size="sm" />}
      {children}
    </button>
  )
}
