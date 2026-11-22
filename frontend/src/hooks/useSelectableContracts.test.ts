import { renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useSelectableContracts } from './useSelectableContracts'
import { useAuth } from '../contexts/AuthContext'
import { useDataContracts } from './useDataContracts'
import { useAllDomains } from './useDomains'
import { makeContract, makeDomain, makeUser } from '../test/fixtures'

vi.mock('../contexts/AuthContext', () => ({ useAuth: vi.fn() }))
vi.mock('./useDataContracts', () => ({ useDataContracts: vi.fn() }))
vi.mock('./useDomains', () => ({ useAllDomains: vi.fn() }))

const contracts = [
  makeContract({ id: 'mine', domain_id: 'd1' }),
  makeContract({ id: 'theirs', domain_id: 'd2' }),
]
const domains = [makeDomain({ id: 'd1', owner_id: 'u1' }), makeDomain({ id: 'd2', owner_id: 'u9', members: [] })]

function query(over: Record<string, unknown> = {}) {
  return { data: undefined, isLoading: false, error: null, ...over } as never
}

beforeEach(() => {
  vi.mocked(useAuth).mockReturnValue({ user: makeUser({ id: 'u1', role: 'DATA_OWNER' }) } as never)
  vi.mocked(useDataContracts).mockReturnValue(query({ data: contracts }))
  vi.mocked(useAllDomains).mockReturnValue(query({ data: domains }))
})

describe('useSelectableContracts', () => {
  it('returns the contracts of the signed-in user domains', () => {
    const { result } = renderHook(() => useSelectableContracts())
    expect(result.current.contracts.map((c) => c.id)).toEqual(['mine'])
    expect(result.current).toMatchObject({ isLoading: false, error: null })
  })

  it('keeps the given contract even outside those domains', () => {
    const { result } = renderHook(() => useSelectableContracts('theirs'))
    expect(result.current.contracts.map((c) => c.id)).toEqual(['theirs', 'mine'])
  })

  it('is loading while either source loads', () => {
    vi.mocked(useAllDomains).mockReturnValue(query({ isLoading: true }))
    const { result } = renderHook(() => useSelectableContracts())
    expect(result.current.isLoading).toBe(true)
    expect(result.current.contracts).toEqual([])
  })

  it('reports the first load error', () => {
    const boom = new Error('boom')
    vi.mocked(useDataContracts).mockReturnValue(query({ error: boom }))
    const { result } = renderHook(() => useSelectableContracts())
    expect(result.current.error).toBe(boom)
  })
})
