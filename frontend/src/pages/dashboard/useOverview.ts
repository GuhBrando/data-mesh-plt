import { useMemo } from 'react'
import { useDataContracts } from '../../hooks/useDataContracts'
import { useDataProducts } from '../../hooks/useDataProducts'
import { useAllDomains } from '../../hooks/useDomains'
import { useUsers } from '../../hooks/useUsers'
import type { DataContract, DataProduct, DomainWithMembers, User } from '../../types'

function isReady(q: { isLoading: boolean; isError: boolean }): boolean {
  return !q.isLoading && !q.isError
}

export interface Overview {
  products: DataProduct[]
  contracts: DataContract[]
  users: User[]
  domains: DomainWithMembers[]
  ready: { products: boolean; contracts: boolean; domains: boolean; users: boolean }
  contractsLoading: boolean
  syncedAt: number
}

/** Everything the Overview page reads, from the cached catalog queries. */
export function useOverview(): Overview {
  const productsQuery = useDataProducts()
  const contractsQuery = useDataContracts()
  const usersQuery = useUsers()
  const domainsQuery = useAllDomains()

  const empty = useMemo(() => [], [])
  return {
    products: productsQuery.data ?? empty,
    contracts: contractsQuery.data ?? empty,
    users: usersQuery.data ?? empty,
    domains: domainsQuery.data ?? empty,
    ready: {
      products: isReady(productsQuery),
      contracts: isReady(contractsQuery),
      domains: isReady(domainsQuery),
      users: isReady(usersQuery),
    },
    contractsLoading: contractsQuery.isLoading,
    syncedAt: contractsQuery.dataUpdatedAt,
  }
}
