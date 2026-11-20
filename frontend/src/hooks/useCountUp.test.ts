import { renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useCountUp } from './useCountUp'

function preferReducedMotion(reduce: boolean) {
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: reduce && query.includes('reduce'),
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  }))
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('useCountUp', () => {
  it('jumps straight to the value when motion is reduced', () => {
    preferReducedMotion(true)
    const { result } = renderHook(() => useCountUp(42))
    expect(result.current).toBe(42)
  })

  it('counts up to the value', async () => {
    preferReducedMotion(false)
    const { result } = renderHook(() => useCountUp(12, 30))
    await waitFor(() => expect(result.current).toBe(12))
  })
})
