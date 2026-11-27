import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { get, post, del } from '../lib/api'
import type { Stakeholder } from '../types'

// Under the contract's key, so refreshing the contract refreshes who reviews it.
const key = (id: string) => ['data-contracts', id, 'stakeholders'] as const

export function useContractStakeholders(id: string, enabled: boolean) {
  return useQuery<Stakeholder[]>({
    queryKey: key(id),
    queryFn: () => get<Stakeholder[]>(`/data-contracts/${id}/stakeholders`),
    enabled: !!id && enabled,
  })
}

export function useInviteStakeholders(id: string) {
  const qc = useQueryClient()
  return useMutation<void, Error, string[]>({
    // One request per person; re-inviting someone is not an error.
    mutationFn: async (userIds) => {
      await Promise.all(userIds.map((user_id) => post(`/data-contracts/${id}/stakeholders`, { user_id })))
    },
    onSettled: () => qc.invalidateQueries({ queryKey: key(id) }),
  })
}

export function useRemoveStakeholder(id: string) {
  const qc = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: (userId) => del(`/data-contracts/${id}/stakeholders/${userId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: key(id) }),
  })
}
