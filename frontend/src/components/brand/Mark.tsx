interface MarkProps {
  size?: number
  className?: string
  title?: string
}

/**
 * DataMesh mark: our own penguin on the accent tile. White face and belly,
 * dot eyes, a small red beak, amber feet. Blinks every few seconds and
 * waddles on hover; prefers-reduced-motion keeps it still.
 */
export default function Mark({ size = 24, className = '', title }: MarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      className={`mark shrink-0 ${className}`}
      role={title ? 'img' : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
    >
      <rect width="24" height="24" rx="6" className="fill-accent" />
      <g className="mark-body">
        <ellipse cx="9.9" cy="20.6" rx="1.8" ry="0.95" fill="#F4A93B" />
        <ellipse cx="14.1" cy="20.6" rx="1.8" ry="0.95" fill="#F4A93B" />
        <path
          className="fill-accent-ink"
          d="M7.3 11.6C5.7 12.6 5 14.6 5.1 16.5c1-.5 1.8-1.4 2.3-2.4zM16.7 11.6c1.6 1 2.3 3 2.2 4.9-1-.5-1.8-1.4-2.3-2.4z"
        />
        <path
          className="fill-accent-ink"
          d="M12 3.5C8.9 3.5 7.6 5.9 7.6 8.8c0 1.4-.5 2.6-.8 4-.4 2.1.1 5.4 1.8 6.7 1 .7 2.2.9 3.4.9s2.4-.2 3.4-.9c1.7-1.3 2.2-4.6 1.8-6.7-.3-1.4-.8-2.6-.8-4 0-2.9-1.3-5.3-4.4-5.3z"
        />
        <path
          fill="#FAFAF6"
          d="M12 7.6c-.8-1-2.6-1-2.9.6-.3 1.4.2 2.4.1 3.6-.2 2.2-.6 4.6.4 6.2.7 1 1.5 1.3 2.4 1.3s1.7-.3 2.4-1.3c1-1.6.6-4 .4-6.2-.1-1.2.4-2.2.1-3.6-.3-1.6-2.1-1.6-2.9-.6z"
        />
        <g className="mark-eyes">
          <circle className="fill-accent-ink" cx="10.45" cy="8.75" r="0.85" />
          <circle className="fill-accent-ink" cx="13.55" cy="8.75" r="0.85" />
        </g>
        <path fill="#E5484D" d="M11 9.75h2l-1 1.3z" />
      </g>
    </svg>
  )
}
