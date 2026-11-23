import { useMemo } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { useDataContracts } from './useDataContracts'
import { useAllDomains } from './useDomains'
import { selectableContracts } from '../lib/domains'

/** The contracts the signed-in user can pick for a data product. */
export function useSelectableContracts(keepId?: string) {
  const { user } = useAuth()
  const contracts = useDataContracts()
  const domains = useAllDomains()
  const data = useMemo(
    () => selectableContracts(contracts.data ?? [], domains.data ?? [], user, keepId),
    [contracts.data, domains.data, user, keepId],
  )
  return {
    contracts: data,
    isLoading: contracts.isLoading || domains.isLoading,
    error: contracts.error ?? domains.error ?? null,
  }
}
