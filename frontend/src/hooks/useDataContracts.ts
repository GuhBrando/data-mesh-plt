import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { get, post, put, del, getText } from '../lib/api'
import type { DataContract, DataContractInput } from '../types'

const KEYS = {
  all: ['data-contracts'] as const,
  one: (id: string) => ['data-contracts', id] as const,
  yaml: (id: string) => ['data-contracts', id, 'yaml'] as const,
}

export function useDataContracts() {
  return useQuery<DataContract[]>({
    queryKey: KEYS.all,
    queryFn: () => get<DataContract[]>('/data-contracts'),
  })
}

export function useDataContract(id: string) {
  return useQuery<DataContract>({
    queryKey: KEYS.one(id),
    queryFn: () => get<DataContract>(`/data-contracts/${id}`),
    enabled: !!id,
  })
}

export function useDataContractYaml(id: string, enabled: boolean) {
  return useQuery<string>({
    queryKey: KEYS.yaml(id),
    queryFn: () => getText(`/data-contracts/${id}/yaml`),
    enabled: !!id && enabled,
  })
}

export function useCreateDataContract() {
  const qc = useQueryClient()
  return useMutation<DataContract, Error, DataContractInput>({
    mutationFn: (input) => post<DataContract>('/data-contracts', input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.all })
      qc.invalidateQueries({ queryKey: ['domains'] })
    },
  })
}

export function useUpdateDataContract() {
  const qc = useQueryClient()
  return useMutation<DataContract, Error, { id: string } & Partial<DataContractInput>>({
    mutationFn: ({ id, ...body }) =>
      put<DataContract>(`/data-contracts/${id}`, body),
    onSuccess: (updated) => {
      qc.invalidateQueries({ queryKey: KEYS.all })
      qc.invalidateQueries({ queryKey: KEYS.one(updated.id) })
      qc.invalidateQueries({ queryKey: KEYS.yaml(updated.id) })
    },
  })
}

export function useDeleteDataContract() {
  const qc = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: (id) => del(`/data-contracts/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.all })
      qc.invalidateQueries({ queryKey: ['domains'] })
    },
  })
}
