import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  useDataContracts,
  useDeleteDataContract,
} from '../../hooks/useDataContracts'
import PageHeader from '../../components/PageHeader'
import Table from '../../components/ui/Table'
import Button from '../../components/ui/Button'
import Modal from '../../components/ui/Modal'
import Spinner from '../../components/ui/Spinner'
import { Avatar, DomainChip, StatusGlyph, TierGlyph } from '../../components/ui/Glyphs'
import { ContractIcon, NewContractIcon, TrashIcon } from '../../components/icons'
import { relativeTime } from '../../lib/format'
import type { DataContract } from '../../types'

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

  const sorted = [...contracts].sort(
    (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
  )

  const columns = [
    {
      key: 'title',
      header: 'Contract',
      render: (row: DataContract) => (
        <span className="flex min-w-0 items-center gap-2.5">
          <ContractIcon className="text-tx3" />
          <span className="truncate font-medium text-tx">{row.title}</span>
          <span className="font-mono text-[11.5px] text-tx3">v{row.version}</span>
        </span>
      ),
    },
    {
      key: 'domain',
      header: 'Domain',
      render: (row: DataContract) => <DomainChip name={row.domain} />,
    },
    {
      key: 'status',
      header: 'Status',
      render: (row: DataContract) => <StatusGlyph status={row.status} />,
      className: 'w-32',
    },
    {
      key: 'tier',
      header: 'Tier',
      render: (row: DataContract) => <TierGlyph tier={row.tier} />,
      className: 'w-20',
    },
    {
      key: 'owner',
      header: 'Owner',
      mobileHidden: true,
      render: (row: DataContract) =>
        row.owner ? (
          <span className="inline-flex items-center gap-2 text-[12.5px]">
            <Avatar name={row.owner} size={20} />
            {row.owner}
          </span>
        ) : (
          <span className="text-tx3">—</span>
        ),
    },
    {
      key: 'updated_at',
      header: 'Updated',
      render: (row: DataContract) => <span className="text-tx3">{relativeTime(row.updated_at)}</span>,
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
          <TrashIcon size={13} />
          Delete
        </button>
      ),
      className: 'w-24',
    },
  ]

  return (
    <div>
      <div className="animate-enter">
      <PageHeader
        title="Data Contracts"
        subtitle={`${contracts.length} contract${contracts.length !== 1 ? 's' : ''}`}
        actions={
          <Button onClick={() => navigate('/data-contracts/new')}>
            <NewContractIcon size={15} />
            New Contract
          </Button>
        }
      />
      </div>

      {isLoading ? (
        <div className="flex justify-center py-20"><Spinner size="lg" /></div>
      ) : error ? (
        <div className="text-center py-16">
          <p className="text-bad">{error.message}</p>
        </div>
      ) : contracts.length === 0 ? (
        <div className="flex animate-enter flex-col items-center rounded-[10px] border border-dashed border-line2 px-6 py-16 text-center">
          <span className="mb-4 grid h-11 w-11 place-items-center rounded-xl border border-line bg-raised text-tx3">
            <ContractIcon size={20} />
          </span>
          <p className="mb-1 font-medium text-tx">No data contracts yet</p>
          <p className="mb-5 text-[13px] text-tx3">Create your first contract to get started.</p>
          <Button onClick={() => navigate('/data-contracts/new')}>
            <NewContractIcon size={15} />
            New Contract
          </Button>
        </div>
      ) : (
        <div className="animate-enter [animation-delay:0.06s]">
        <Table
          columns={columns}
          data={sorted}
          keyExtractor={(c) => c.id}
          onRowClick={(c) => navigate(`/data-contracts/${c.id}`)}
          emptyMessage="No contracts found."
          mobileCardConfig={{ titleKey: 'title', badgeKey: 'status' }}
        />
        </div>
      )}

      <Modal
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title="Delete Data Contract"
        size="sm"
      >
        <p className="text-[13px] text-tx2 mb-2">
          Are you sure you want to delete{' '}
          <span className="font-medium text-tx">{deleteTarget?.title}</span>?
        </p>
        <p className="text-xs text-tx3 mb-6">This action cannot be undone.</p>
        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={() => setDeleteTarget(null)}>Cancel</Button>
          <Button variant="danger" loading={deleteMutation.isPending} onClick={handleDelete}>
            Delete
          </Button>
        </div>
        {deleteMutation.isError && (
          <p className="mt-3 text-[13px] text-bad">{deleteMutation.error.message}</p>
        )}
      </Modal>
    </div>
  )
}
