import { useState, type ReactNode } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  useDataProduct,
  useUpdateDataProduct,
  useDeleteDataProduct,
} from '../../hooks/useDataProducts'
import { useDataContract } from '../../hooks/useDataContracts'
import Button from '../../components/ui/Button'
import Modal from '../../components/ui/Modal'
import Spinner from '../../components/ui/Spinner'
import { Avatar, DomainChip, StatusGlyph, TierGlyph } from '../../components/ui/Glyphs'
import {
  ArrowRightIcon,
  ArrowUpRightIcon,
  ClockIcon,
  ContractIcon,
  EditIcon,
  PendingIcon,
  ProductIcon,
  RepoIcon,
  SchemaIcon,
  TrashIcon,
} from '../../components/icons'
import { relativeTime } from '../../lib/format'
import DataProductForm from './DataProductForm'
import type { DataContract, DataProduct, DataProductFormData } from '../../types'

function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const SCHEMA_PREVIEW = 6

function Panel({ title, icon, children }: { title: string; icon?: ReactNode; children: ReactNode }) {
  return (
    <section className="min-w-0 rounded-[10px] border border-line bg-panel">
      <header className="flex min-h-[44px] items-center gap-2 border-b border-line px-4 text-tx3">
        {icon}
        <h2 className="text-[13px] font-semibold text-tx">{title}</h2>
      </header>
      {children}
    </section>
  )
}

function Header({
  product,
  contract,
  onEdit,
  onDelete,
}: {
  product: DataProduct
  contract?: DataContract
  onEdit: () => void
  onDelete: () => void
}) {
  return (
    <div className="flex animate-enter flex-wrap items-start gap-4">
      <span className="grid h-11 w-11 shrink-0 place-items-center rounded-[11px] border border-line bg-raised text-accent-fg">
        <ProductIcon size={22} />
      </span>
      <div className="min-w-0 flex-[1_1_420px]">
        <h1 className="truncate text-[22px] font-semibold leading-tight tracking-[-0.02em] text-tx">{product.name}</h1>
        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-2">
          {contract && <DomainChip name={contract.domain} />}
          {contract && <StatusGlyph status={contract.status} />}
          {contract && <TierGlyph tier={contract.tier} showName />}
          <span className="text-xs text-tx3" title={`Created ${formatDateTime(product.created_at)}`}>
            Updated {relativeTime(product.updated_at).toLowerCase()}
          </span>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {product.repo_url && (
          <a
            href={product.repo_url}
            target="_blank"
            rel="noopener noreferrer"
            aria-label="View GitHub repository"
            className="btn-secondary"
          >
            <RepoIcon size={14} />
            GitHub
          </a>
        )}
        <Button variant="secondary" onClick={onEdit}>
          <EditIcon size={14} />
          Edit
        </Button>
        <button
          type="button"
          onClick={onDelete}
          className="inline-flex h-8 items-center gap-2 rounded-lg border border-bad/25 bg-bad/10 px-3 text-[13px] font-medium text-bad transition-colors hover:bg-bad/15 focus:outline-none focus-visible:ring-[3px] focus-visible:ring-bad/30"
        >
          <TrashIcon size={14} />
          Delete
        </button>
      </div>
    </div>
  )
}

function ContractPanel({
  product,
  contract,
  onOpen,
}: {
  product: DataProduct
  contract?: DataContract
  onOpen: () => void
}) {
  const fields = contract?.models.fields ?? []
  return (
    <Panel title="Data contract" icon={<ContractIcon size={15} />}>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3.5">
        <button
          type="button"
          onClick={onOpen}
          className="min-w-0 break-all text-left font-mono text-[13px] font-medium text-tx hover:text-accent-fg hover:underline"
        >
          {contract?.title ?? product.data_contracts_id}
        </button>
        {contract && (
          <>
            <span className="rounded-md border border-line2 px-1.5 font-mono text-[11.5px] leading-5 text-tx">v{contract.version}</span>
            <StatusGlyph status={contract.status} />
            {contract.owner && (
              <span className="inline-flex items-center gap-2 text-[12.5px] text-tx2">
                <Avatar name={contract.owner} size={20} />
                {contract.owner}
              </span>
            )}
          </>
        )}
      </div>
      {fields.length > 0 && (
        <div className="border-t border-line">
          <p className="flex items-center gap-2 px-4 pb-1 pt-3 text-[11.5px] font-medium text-tx3">
            <SchemaIcon size={13} />
            Schema · {fields.length} field{fields.length === 1 ? '' : 's'}
          </p>
          <ul className="px-4 pb-2">
            {fields.slice(0, SCHEMA_PREVIEW).map((f) => (
              <li key={f.name} className="flex h-8 items-center gap-3 border-b border-line text-xs last:border-0">
                <span className="min-w-0 flex-1 truncate font-mono text-tx">{f.name}</span>
                {f.primary_key && (
                  <span className="rounded border border-accent-fg/40 px-[5px] font-mono text-[10.5px] font-medium leading-[17px] text-accent-fg">
                    PK
                  </span>
                )}
                <span className="font-mono text-tx2">{f.type}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="border-t border-line px-4 py-2.5">
        <button
          type="button"
          onClick={onOpen}
          className="group inline-flex items-center gap-1 text-xs text-tx2 transition-colors hover:text-tx"
          aria-label="Open the data contract"
        >
          {fields.length > SCHEMA_PREVIEW ? `See all ${fields.length} fields in the contract` : 'Open the contract'}
          <ArrowRightIcon size={12} className="transition-transform duration-150 group-hover:translate-x-0.5" />
        </button>
      </div>
    </Panel>
  )
}

function Rail({ product }: { product: DataProduct }) {
  return (
    <aside aria-label="Product details" className="flex min-w-0 flex-[1_1_300px] animate-enter flex-col gap-3.5 [animation-delay:0.14s]">
      <Panel title="Repository" icon={<RepoIcon size={15} />}>
        <div className="px-4 py-3.5 text-[12.5px]">
          {product.repo_url ? (
            <a
              href={product.repo_url}
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Open repository"
              className="group inline-flex max-w-full items-center gap-1.5 break-all font-mono text-[11.5px] text-tx2 hover:text-tx"
            >
              {product.repo_url.replace(/^https?:\/\//, '')}
              <ArrowUpRightIcon size={13} className="shrink-0 text-tx3 group-hover:text-tx" />
            </a>
          ) : (
            <span className="inline-flex items-center gap-2 text-warn">
              <PendingIcon size={14} className="animate-spin [animation-duration:1.4s]" />
              Provisioning in progress
            </span>
          )}
        </div>
      </Panel>
      <Panel title="Details" icon={<ClockIcon size={15} />}>
        <ul className="px-4 py-1 text-[12.5px]">
          <li className="flex flex-col gap-0.5 border-b border-line py-2.5">
            <span className="text-tx2">ID</span>
            <span className="break-all font-mono text-[11.5px] text-tx">{product.id}</span>
          </li>
          <li className="flex h-9 items-center justify-between gap-2.5 border-b border-line">
            <span className="text-tx2">Created</span>
            <span className="text-tx">{formatDateTime(product.created_at)}</span>
          </li>
          <li className="flex h-9 items-center justify-between gap-2.5">
            <span className="text-tx2">Updated</span>
            <span className="text-tx">{formatDateTime(product.updated_at)}</span>
          </li>
        </ul>
      </Panel>
    </aside>
  )
}

export default function DataProductDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [editOpen, setEditOpen] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState(false)

  const { data: product, isLoading, error } = useDataProduct(id ?? '')
  const { data: contract } = useDataContract(product?.data_contracts_id ?? '')
  const updateMutation = useUpdateDataProduct()
  const deleteMutation = useDeleteDataProduct()

  const handleUpdate = async (values: DataProductFormData) => {
    if (!id) return
    await updateMutation.mutateAsync({ id, ...values })
    setEditOpen(false)
  }

  const handleDelete = async () => {
    if (!id) return
    await deleteMutation.mutateAsync(id)
    navigate('/data-products')
  }

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Spinner size="lg" />
      </div>
    )
  }

  if (error || !product) {
    return (
      <div className="py-16 text-center">
        <p className="font-medium text-bad">{error?.message ?? 'Product not found'}</p>
        <button onClick={() => navigate('/data-products')} className="mt-3 text-[13px] text-accent-fg hover:underline">
          Back to list
        </button>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-[18px]">
      <Header product={product} contract={contract} onEdit={() => setEditOpen(true)} onDelete={() => setDeleteConfirm(true)} />

      <div className="flex flex-wrap items-start gap-5">
        <div className="flex min-w-0 flex-[999_1_620px] animate-enter flex-col gap-3.5 [animation-delay:0.08s]">
          <Panel title="About">
            <p className="whitespace-pre-wrap px-4 py-3.5 text-[13px] leading-relaxed text-tx2">{product.description}</p>
          </Panel>
          <ContractPanel
            product={product}
            contract={contract}
            onOpen={() => navigate(`/data-contracts/${product.data_contracts_id}`)}
          />
        </div>
        <Rail product={product} />
      </div>

      {/* Edit Modal */}
      <Modal open={editOpen} onClose={() => setEditOpen(false)} title="Edit Data Product">
        <DataProductForm
          defaultValues={product}
          onSubmit={handleUpdate}
          onCancel={() => setEditOpen(false)}
          isSubmitting={updateMutation.isPending}
        />
        {updateMutation.isError && <p className="mt-3 text-[13px] text-bad">{updateMutation.error.message}</p>}
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal open={deleteConfirm} onClose={() => setDeleteConfirm(false)} title="Delete Data Product" size="sm">
        <p className="mb-2 text-[13px] text-tx2">
          Are you sure you want to delete <span className="font-medium text-tx">{product.name}</span>?
        </p>
        <p className="mb-6 text-xs text-tx3">This action cannot be undone.</p>
        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={() => setDeleteConfirm(false)}>
            Cancel
          </Button>
          <Button variant="danger" loading={deleteMutation.isPending} onClick={handleDelete}>
            Delete
          </Button>
        </div>
        {deleteMutation.isError && <p className="mt-3 text-[13px] text-bad">{deleteMutation.error.message}</p>}
      </Modal>
    </div>
  )
}
