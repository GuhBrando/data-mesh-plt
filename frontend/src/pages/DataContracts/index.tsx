import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, FileText, Trash2 } from 'lucide-react'
import {
  useDataContracts,
  useDeleteDataContract,
} from '../../hooks/useDataContracts'
import PageHeader from '../../components/PageHeader'
import Table from '../../components/ui/Table'
import Button from '../../components/ui/Button'
import Badge from '../../components/ui/Badge'
import Modal from '../../components/ui/Modal'
import Spinner from '../../components/ui/Spinner'
import type { DataContract } from '../../types'
import { STATUS_COLORS } from './contractStatus'

const TIER_COLORS: Record<number, 'red' | 'yellow' | 'blue' | 'gray'> = {
  1: 'red',
  2: 'yellow',
  3: 'blue',
  4: 'gray',
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

export default function DataContractsList() {
  const navigate = useNavigate()
  const [deleteTarget, setDeleteTarget] = useState<DataContract | null>(null)

  const { data: contracts = [], isLoading, error } = useDataContracts()
  const deleteMutation = useDeleteDataContract()

  const handleDelete = async () => {
    if (!deleteTarget) return
    await deleteMutation.mutateAsync(deleteTarget.id)
    setDeleteTarget(null)
  }

  const columns = [
    {
      key: 'title',
      header: 'Title',
      render: (row: DataContract) => (
        <span className="font-medium text-gray-800 dark:text-slate-200">{row.title}</span>
      ),
    },
    {
      key: 'tier',
      header: 'Tier',
      render: (row: DataContract) => (
        <Badge variant={TIER_COLORS[row.tier]}>Tier {row.tier}</Badge>
      ),
      className: 'w-24',
    },
    {
      key: 'status',
      header: 'Status',
      render: (row: DataContract) => (
        <Badge variant={STATUS_COLORS[row.status] ?? 'gray'}>
          {row.status.replace('_', ' ')}
        </Badge>
      ),
      className: 'w-28',
    },
    {
      key: 'domain',
      header: 'Domain',
      render: (row: DataContract) => (
        <span className="text-sm text-gray-600 dark:text-slate-300">{row.domain}</span>
      ),
    },
    {
      key: 'created_at',
      header: 'Created',
      render: (row: DataContract) => (
        <span className="text-sm text-gray-500 dark:text-slate-400">{formatDate(row.created_at)}</span>
      ),
    },
    {
      key: 'actions',
      header: '',
      render: (row: DataContract) => (
        <button
          onClick={(e) => { e.stopPropagation(); setDeleteTarget(row) }}
          className="btn-danger"
          title="Delete"
        >
          <Trash2 size={13} />
          Delete
        </button>
      ),
      className: 'w-24',
    },
  ]

  return (
    <div>
      <PageHeader
        title="Data Contracts"
        subtitle={`${contracts.length} contract${contracts.length !== 1 ? 's' : ''}`}
        actions={
          <Button onClick={() => navigate('/data-contracts/new')}>
            <Plus size={16} />
            New Contract
          </Button>
        }
      />

      {isLoading ? (
        <div className="flex justify-center py-20"><Spinner size="lg" /></div>
      ) : error ? (
        <div className="text-center py-16">
          <p className="text-red-500">{error.message}</p>
        </div>
      ) : contracts.length === 0 ? (
        <div className="text-center py-20">
          <FileText size={48} className="text-gray-200 dark:text-slate-700 mx-auto mb-4" />
          <p className="text-gray-500 dark:text-slate-400 font-medium mb-1">No data contracts yet</p>
          <p className="text-sm text-gray-400 dark:text-slate-500 mb-4">
            Create your first contract to get started.
          </p>
          <Button onClick={() => navigate('/data-contracts/new')}>
            <Plus size={16} />
            New Contract
          </Button>
        </div>
      ) : (
        <Table
          columns={columns}
          data={contracts}
          keyExtractor={(c) => c.id}
          onRowClick={(c) => navigate(`/data-contracts/${c.id}`)}
          emptyMessage="No contracts found."
          mobileCardConfig={{ titleKey: 'title', badgeKey: 'status' }}
        />
      )}

      <Modal
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title="Delete Data Contract"
        size="sm"
      >
        <p className="text-sm text-gray-600 dark:text-slate-300 mb-2">
          Are you sure you want to delete{' '}
          <span className="font-medium">{deleteTarget?.title}</span>?
        </p>
        <p className="text-xs text-gray-400 dark:text-slate-500 mb-6">This action cannot be undone.</p>
        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={() => setDeleteTarget(null)}>Cancel</Button>
          <Button variant="danger" loading={deleteMutation.isPending} onClick={handleDelete}>
            Delete
          </Button>
        </div>
        {deleteMutation.isError && (
          <p className="mt-3 text-sm text-red-500">{deleteMutation.error.message}</p>
        )}
      </Modal>
    </div>
  )
}
