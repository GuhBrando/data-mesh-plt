import { useEffect, useRef, useState } from 'react'

/**
 * Counts from the previous value up to `target` with an ease-out curve.
 * Skips straight to the value when the user prefers reduced motion.
 */
export function useCountUp(target: number, duration = 850): number {
  const [value, setValue] = useState(0)
  const from = useRef(0)

  useEffect(() => {
    const reduce =
      typeof window !== 'undefined' &&
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduce || typeof requestAnimationFrame !== 'function') {
      from.current = target
      setValue(target)
      return
    }
    const start = from.current
    let raf = 0
    let t0: number | null = null
    const tick = (t: number) => {
      if (t0 === null) t0 = t
      const p = Math.min(1, (t - t0) / duration)
      const eased = 1 - Math.pow(1 - p, 3)
      const next = Math.round(start + (target - start) * eased)
      setValue(next)
      from.current = next
      if (p < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target, duration])

  return value
}
