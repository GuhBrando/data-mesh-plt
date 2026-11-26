import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { get, getText, post, put, del } from '../lib/api'
import type { DataProduct, DataProductInput } from '../types'

const KEYS = {
  all: ['data-products'] as const,
  one: (id: string) => ['data-products', id] as const,
  // Under KEYS.one(id), so an update's invalidation refreshes the export too.
  odps: (id: string) => ['data-products', id, 'odps'] as const,
}

// A product write changes who produces and consumes each contract it names.
const CONTRACTS = ['data-contracts'] as const

// ---- Queries ----

export function useDataProducts() {
  return useQuery<DataProduct[]>({
    queryKey: KEYS.all,
    queryFn: () => get<DataProduct[]>('/data-products'),
  })
}

export function useDataProduct(id: string) {
  return useQuery<DataProduct>({
    queryKey: KEYS.one(id),
    queryFn: () => get<DataProduct>(`/data-products/${id}`),
    enabled: !!id,
  })
}

/** The product as an ODPS v1.1.0 YAML document, fetched only when `enabled`. */
export function useDataProductOdps(id: string, enabled: boolean) {
  return useQuery<string>({
    queryKey: KEYS.odps(id),
    queryFn: () => getText(`/data-products/${id}/odps`),
    enabled: !!id && enabled,
  })
}

// ---- Mutations ----

export function useCreateDataProduct() {
  const qc = useQueryClient()
  return useMutation<DataProduct, Error, DataProductInput>({
    mutationFn: (data) => post<DataProduct>('/data-products', data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.all })
      qc.invalidateQueries({ queryKey: CONTRACTS })
    },
  })
}

export function useUpdateDataProduct() {
  const qc = useQueryClient()
  return useMutation<
    DataProduct,
    Error,
    { id: string } & DataProductInput
  >({
    mutationFn: ({ id, ...data }) =>
      put<DataProduct>(`/data-products/${id}`, data),
    onSuccess: (updated) => {
      qc.invalidateQueries({ queryKey: KEYS.all })
      qc.invalidateQueries({ queryKey: KEYS.one(updated.id) })
      qc.invalidateQueries({ queryKey: CONTRACTS })
    },
  })
}

export function useDeleteDataProduct() {
  const qc = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: (id) => del(`/data-products/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.all })
      qc.invalidateQueries({ queryKey: CONTRACTS })
    },
  })
}
