import { useState, type ReactNode } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  useDataProduct,
  useUpdateDataProduct,
  useDeleteDataProduct,
} from '../../hooks/useDataProducts'
import Button from '../../components/ui/Button'
import Modal from '../../components/ui/Modal'
import Spinner from '../../components/ui/Spinner'
import { DomainChip, StatusGlyph } from '../../components/ui/Glyphs'
import {
  ArrowUpRightIcon,
  ClockIcon,
  EditIcon,
  PendingIcon,
  ProductIcon,
  RepoIcon,
  SchemaIcon,
  TrashIcon,
} from '../../components/icons'
import { relativeTime } from '../../lib/format'
import DataProductForm from './DataProductForm'
import ProductLineage from './ProductLineage'
import { productFacts } from './ProductFacts'
import SaveWarnings from './SaveWarnings'
import type { DataProduct, DataProductInput } from '../../types'

function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

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
  onEdit,
  onDelete,
}: {
  product: DataProduct
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
          <DomainChip name={product.domain} />
          <StatusGlyph status={product.status} />
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

function About({ product }: { product: DataProduct }) {
  const { purpose, usage, limitations } = product.description
  const extra: [string, string][] = [
    ['Usage', usage],
    ['Limitations', limitations],
  ]
  return (
    <Panel title="About">
      <div className="space-y-3 px-4 py-3.5 text-[13px] leading-relaxed text-tx2">
        <p className="whitespace-pre-wrap">{purpose}</p>
        {extra
          .filter(([, text]) => text)
          .map(([label, text]) => (
            <div key={label}>
              <h3 className="text-[11.5px] font-medium text-tx3">{label}</h3>
              <p className="whitespace-pre-wrap">{text}</p>
            </div>
          ))}
      </div>
    </Panel>
  )
}

function Rail({ product }: { product: DataProduct }) {
  const facts = productFacts(product)
  return (
    <aside aria-label="Product details" className="flex min-w-0 flex-[1_1_300px] animate-enter flex-col gap-3.5 [animation-delay:0.14s]">
      {facts.length > 0 && (
        <Panel title="ODPS" icon={<SchemaIcon size={15} />}>
          <ul className="px-4 py-1 text-[12.5px]">{facts}</ul>
        </Panel>
      )}
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
  const [warnings, setWarnings] = useState<string[]>([])
  const [lineageError, setLineageError] = useState<string | null>(null)

  const { data: product, isLoading, error } = useDataProduct(id ?? '')
  const updateMutation = useUpdateDataProduct()
  const deleteMutation = useDeleteDataProduct()

  const save = async (values: DataProductInput) => {
    if (!id) return
    const saved = await updateMutation.mutateAsync({ id, ...values })
    setWarnings(saved.warnings ?? [])
  }

  const handleUpdate = async (values: DataProductInput) => {
    await save(values)
    setEditOpen(false)
  }

  // A version move from the lineage: one save of the whole product.
  const handleMove = async (values: DataProductInput) => {
    setLineageError(null)
    try {
      await save(values)
    } catch (e) {
      setLineageError((e as Error).message)
    }
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
      <Header product={product} onEdit={() => setEditOpen(true)} onDelete={() => setDeleteConfirm(true)} />

      <SaveWarnings warnings={warnings} onDismiss={() => setWarnings([])} />

      <div className="flex flex-wrap items-start gap-5">
        <div className="flex min-w-0 flex-[999_1_620px] animate-enter flex-col gap-3.5 [animation-delay:0.08s]">
          <About product={product} />
          <Panel title="Lineage" icon={<SchemaIcon size={15} />}>
            <ProductLineage product={product} onChange={handleMove} saving={updateMutation.isPending} />
            {lineageError && <p className="border-t border-line px-4 py-2.5 text-[13px] text-bad">{lineageError}</p>}
          </Panel>
        </div>
        <Rail product={product} />
      </div>

      {/* Edit Modal */}
      <Modal open={editOpen} onClose={() => setEditOpen(false)} title="Edit Data Product" size="lg">
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
