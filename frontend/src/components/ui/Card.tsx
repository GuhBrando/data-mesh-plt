import { ReactNode, HTMLAttributes } from 'react'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
  padding?: boolean
}

export default function Card({
  children,
  padding = true,
  className = '',
  ...props
}: CardProps) {
  return (
    <div
      className={`card ${padding ? 'p-6' : ''} ${className}`}
      {...props}
    >
      {children}
    </div>
  )
}

export function CardHeader({
  children,
  className = '',
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div className={`flex items-center justify-between mb-4 ${className}`}>
      {children}
    </div>
  )
}

export function CardTitle({
  children,
  className = '',
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <h3 className={`text-[13px] font-semibold text-tx ${className}`}>
      {children}
    </h3>
  )
}
