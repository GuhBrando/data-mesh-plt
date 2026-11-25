import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  useDataProducts,
  useCreateDataProduct,
  useDeleteDataProduct,
} from '../../hooks/useDataProducts'
import PageHeader from '../../components/PageHeader'
import Table from '../../components/ui/Table'
import Button from '../../components/ui/Button'
import Modal from '../../components/ui/Modal'
import Spinner from '../../components/ui/Spinner'
import { DomainChip, StatusGlyph } from '../../components/ui/Glyphs'
import {
  ArrowUpRightIcon,
  FilterIcon,
  GridIcon,
  ListIcon,
  PendingIcon,
  PlusIcon,
  ProductIcon,
  RepoIcon,
  TrashIcon,
} from '../../components/icons'
import { STATUS_LABELS, domainColor } from '../../lib/contracts'
import { relativeTime } from '../../lib/format'
import { PRODUCT_STATUSES } from '../../lib/products'
import DataProductForm from './DataProductForm'
import SaveWarnings from './SaveWarnings'
import type { DataProduct, DataProductInput, ProductStatus } from '../../types'

type View = 'grid' | 'list'
const ALL = 'all'

function portsSummary(p: DataProduct): string {
  const outputs = p.output_ports.length
  const inputs = p.input_ports.length
  return `${outputs} output${outputs === 1 ? '' : 's'} · ${inputs} input${inputs === 1 ? '' : 's'}`
}

function matches(p: DataProduct, domain: string, status: string, needle: string): boolean {
  if (domain !== ALL && p.domain !== domain) return false
  if (status !== ALL && p.status !== status) return false
  if (!needle) return true
  const ports = [...p.input_ports, ...p.output_ports]
  return [p.name, p.description, p.domain, ...ports.map((port) => port.name), ...ports.map((port) => port.contract?.title)].some(
    (v) => typeof v === 'string' && v.toLowerCase().includes(needle),
  )
}

function countDomains(products: DataProduct[]): [string, number][] {
  const counts = new Map<string, number>()
  for (const p of products) counts.set(p.domain, (counts.get(p.domain) ?? 0) + 1)
  return [...counts.entries()].sort((a, b) => a[0].localeCompare(b[0]))
}

function countStatuses(products: DataProduct[]): [ProductStatus, number][] {
  return PRODUCT_STATUSES.map((s) => [s, products.filter((p) => p.status === s).length] as [ProductStatus, number]).filter(
    ([, n]) => n > 0,
  )
}

function RepoState({ url }: { url?: string | null }) {
  if (url) {
    return (
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        onClick={(e) => e.stopPropagation()}
        className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-md text-xs text-tx2 transition-colors hover:text-tx"
        title="Open GitHub repo"
        aria-label="Open GitHub repo"
      >
        <RepoIcon size={14} className="text-tx3" />
        Repository
      </a>
    )
  }
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-xs text-warn" title="The repository is still being provisioned">
      <PendingIcon size={14} className="animate-spin [animation-duration:1.4s]" />
      Provisioning
    </span>
  )
}

function DeleteButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation()
        onClick()
      }}
      className="grid h-7 w-7 place-items-center rounded-md text-tx3 transition-colors hover:bg-bad/10 hover:text-bad focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-bad/40"
      title="Delete"
      aria-label="Delete data product"
    >
      <TrashIcon size={14} />
    </button>
  )
}

function ProductCard({
  product: p,
  index,
  onOpen,
  onDelete,
}: {
  product: DataProduct
  index: number
  onOpen: (p: DataProduct) => void
  onDelete: (p: DataProduct) => void
}) {
  return (
    <article
      onClick={() => onOpen(p)}
      className="group relative flex animate-enter cursor-pointer flex-col gap-3 rounded-xl border border-line bg-panel p-4 transition-[border-color,background-color,transform,box-shadow] duration-150 hover:-translate-y-0.5 hover:border-line2 hover:bg-raised hover:shadow-[var(--shadow)]"
      style={{ animationDelay: `${Math.min(index, 8) * 0.04}s` }}
    >
      <div className="flex items-center justify-between gap-2">
        <DomainChip name={p.domain} />
        <div className="flex items-center gap-1">
          <StatusGlyph status={p.status} className="!text-xs" />
          <span className="transition-opacity duration-150 md:opacity-0 md:focus-within:opacity-100 md:group-hover:opacity-100">
            <DeleteButton onClick={() => onDelete(p)} />
          </span>
        </div>
      </div>
      <div>
        <h3 className="m-0">
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation()
              onOpen(p)
            }}
            className="flex items-center gap-1.5 rounded text-left text-[15px] font-semibold leading-snug tracking-[-0.01em] text-tx focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-fg/50"
          >
            {p.name}
            <ArrowUpRightIcon
              size={14}
              className="-translate-x-0.5 translate-y-0.5 text-tx3 opacity-0 transition-[opacity,transform] duration-150 group-hover:translate-x-0 group-hover:translate-y-0 group-hover:opacity-100"
            />
          </button>
        </h3>
      </div>
      <p className="m-0 line-clamp-2 min-h-[37px] text-[12.5px] leading-normal text-tx2">{p.description}</p>
      <div className="mt-auto flex items-center justify-between gap-2.5 border-t border-line pt-3 text-xs">
        <span className="font-mono text-[11.5px] text-tx2">{portsSummary(p)}</span>
        <RepoState url={p.repo_url} />
      </div>
    </article>
  )
}

function ChipFilter<T extends string>({
  label,
  allLabel,
  options,
  total,
  value,
  onChange,
  swatch,
  labelOf = (v) => v,
}: {
  label: string
  allLabel: string
  options: [T, number][]
  total: number
  value: string
  onChange: (v: string) => void
  swatch?: (v: T) => string
  labelOf?: (v: T) => string
}) {
  if (options.length === 0) return null
  const chips: [string, string, number][] = [[ALL, allLabel, total], ...options.map(([v, n]): [string, string, number] => [v, labelOf(v), n])]
  return (
    <div role="group" className="flex flex-wrap gap-1.5" aria-label={label}>
      {chips.map(([v, text, n]) => (
        <button
          key={v}
          type="button"
          onClick={() => onChange(v)}
          aria-pressed={value === v}
          className={`inline-flex h-[30px] items-center gap-[7px] rounded-full border px-[11px] text-[12.5px] font-medium transition-colors duration-150 ${
            value === v ? 'border-tx3 bg-raised text-tx' : 'border-line text-tx2 hover:border-line2 hover:text-tx'
          }`}
        >
          {swatch && v !== ALL && <span className="h-2 w-2 rounded-sm" style={{ background: swatch(v as T) }} />}
          {text}
          <span className="font-mono text-[11px] text-tx3">{n}</span>
        </button>
      ))}
    </div>
  )
}

function ViewSwitch({ value, onChange }: { value: View; onChange: (v: View) => void }) {
  const options = [
    ['grid', 'Grid view', GridIcon],
    ['list', 'List view', ListIcon],
  ] as const
  return (
    <div className="ml-auto flex gap-0.5 rounded-lg border border-line bg-raised p-0.5" aria-label="Layout">
      {options.map(([v, label, Icon]) => (
        <button
          key={v}
          type="button"
          onClick={() => onChange(v)}
          aria-label={label}
          aria-pressed={value === v}
          className={`grid h-6 w-7 place-items-center rounded-md transition-colors duration-150 ${
            value === v ? 'bg-panel text-tx shadow-[0_0_0_1px_rgb(var(--line))]' : 'text-tx3 hover:text-tx'
          }`}
        >
          <Icon size={15} />
        </button>
      ))}
    </div>
  )
}

function EmptyState({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="flex animate-enter flex-col items-center rounded-[10px] border border-dashed border-line2 px-6 py-16 text-center">
      <span className="mb-4 grid h-11 w-11 place-items-center rounded-xl border border-line bg-raised text-tx3">
        <ProductIcon size={20} />
      </span>
      <p className="mb-1 font-medium text-tx">No data products yet</p>
      <p className="mb-5 text-[13px] text-tx3">Create your first data product to get started.</p>
      <Button onClick={onCreate}>
        <PlusIcon size={15} />
        New Data Product
      </Button>
    </div>
  )
}

function Catalog({
  products,
  query,
  onQuery,
  onOpen,
  onDelete,
}: {
  products: DataProduct[]
  query: string
  onQuery: (q: string) => void
  onOpen: (p: DataProduct) => void
  onDelete: (p: DataProduct) => void
}) {
  const [view, setView] = useState<View>('grid')
  const [domain, setDomain] = useState(ALL)
  const [status, setStatus] = useState(ALL)
  const domains = useMemo(() => countDomains(products), [products])
  const statuses = useMemo(() => countStatuses(products), [products])
  const needle = query.trim().toLowerCase()
  const shown = products.filter((p) => matches(p, domain, status, needle))

  const columns = [
    {
      key: 'name',
      header: 'Data product',
      render: (p: DataProduct) => (
        <span className="flex items-center gap-2.5">
          <ProductIcon className="text-tx3" />
          <span className="font-medium text-tx">{p.name}</span>
        </span>
      ),
    },
    { key: 'domain', header: 'Domain', render: (p: DataProduct) => <DomainChip name={p.domain} /> },
    { key: 'status', header: 'Status', render: (p: DataProduct) => <StatusGlyph status={p.status} /> },
    {
      key: 'ports',
      header: 'Ports',
      render: (p: DataProduct) => <span className="font-mono text-[11.5px] text-tx2">{portsSummary(p)}</span>,
    },
    { key: 'repo', header: 'Repository', render: (p: DataProduct) => <RepoState url={p.repo_url} /> },
    {
      key: 'updated',
      header: 'Updated',
      render: (p: DataProduct) => <span className="text-tx3">{relativeTime(p.updated_at)}</span>,
    },
    {
      key: 'actions',
      header: '',
      render: (p: DataProduct) => <DeleteButton onClick={() => onDelete(p)} />,
      className: 'w-12',
    },
  ]

  return (
    <div className="flex flex-col gap-4">
      <div className="flex animate-enter flex-wrap items-center gap-2 [animation-delay:0.06s]">
        <label className="flex h-8 w-full items-center gap-2 rounded-lg border border-line bg-panel px-2.5 text-tx3 transition-shadow focus-within:border-accent-fg focus-within:ring-[3px] focus-within:ring-accent/20 sm:w-[300px]">
          <FilterIcon size={15} />
          <input
            type="text"
            value={query}
            onChange={(e) => onQuery(e.target.value)}
            placeholder="Filter by name, port or contract"
            aria-label="Filter data products"
            className="min-w-0 flex-1 border-0 bg-transparent text-[13px] text-tx outline-none placeholder:text-tx3"
          />
        </label>
        <ChipFilter
          label="Filter by domain"
          allLabel="All domains"
          options={domains}
          total={products.length}
          value={domain}
          onChange={setDomain}
          swatch={domainColor}
        />
        <ViewSwitch value={view} onChange={setView} />
      </div>
      <ChipFilter
        label="Filter by status"
        allLabel="All statuses"
        options={statuses}
        total={products.length}
        value={status}
        onChange={setStatus}
        labelOf={(s) => STATUS_LABELS[s]}
      />

      <p className="text-[12.5px] text-tx3">
        <b className="font-medium tabular-nums text-tx">{shown.length}</b> of {products.length} data product
        {products.length !== 1 ? 's' : ''}
      </p>

      {shown.length === 0 && (
        <p className="rounded-[10px] border border-dashed border-line2 py-12 text-center text-[13px] text-tx3">
          No data products match this filter.
        </p>
      )}
      {shown.length > 0 && view === 'grid' && (
        <div key={`${domain}-${status}-${needle}`} className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-3.5">
          {shown.map((p, i) => (
            <ProductCard key={p.id} product={p} index={i} onOpen={onOpen} onDelete={onDelete} />
          ))}
        </div>
      )}
      {shown.length > 0 && view === 'list' && (
        <Table
          columns={columns}
          data={shown}
          keyExtractor={(p) => p.id}
          onRowClick={onOpen}
          emptyMessage="No products found."
          mobileCardConfig={{ titleKey: 'name' }}
        />
      )}
    </div>
  )
}

function subtitle(products: number, domains: number): string {
  const base = `${products} data product${products !== 1 ? 's' : ''}`
  const from = domains ? ` from ${domains} domain${domains !== 1 ? 's' : ''}` : ''
  return `${base}${from}.`
}

export default function DataProductsList() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [createOpen, setCreateOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<DataProduct | null>(null)
  const [warnings, setWarnings] = useState<string[]>([])

  const { data: products = [], isLoading, error } = useDataProducts()
  const createMutation = useCreateDataProduct()
  const deleteMutation = useDeleteDataProduct()

  // "New → Data product" in the sidebar lands here with ?new=1.
  useEffect(() => {
    if (searchParams.get('new') !== '1') return
    setCreateOpen(true)
    const next = new URLSearchParams(searchParams)
    next.delete('new')
    setSearchParams(next, { replace: true })
  }, [searchParams, setSearchParams])

  function setQuery(value: string) {
    const next = new URLSearchParams(searchParams)
    if (value) next.set('q', value)
    else next.delete('q')
    setSearchParams(next, { replace: true })
  }

  const sorted = useMemo(
    () => [...products].sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()),
    [products],
  )

  const handleCreate = async (values: DataProductInput) => {
    const created = await createMutation.mutateAsync(values)
    setWarnings(created.warnings ?? [])
    setCreateOpen(false)
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    await deleteMutation.mutateAsync(deleteTarget.id)
    setDeleteTarget(null)
  }

  let body
  if (isLoading) {
    body = (
      <div className="flex justify-center py-20">
        <Spinner size="lg" />
      </div>
    )
  } else if (error) {
    body = <p className="py-16 text-center text-bad">{error.message}</p>
  } else if (products.length === 0) {
    body = <EmptyState onCreate={() => setCreateOpen(true)} />
  } else {
    body = (
      <Catalog
        products={sorted}
        query={searchParams.get('q') ?? ''}
        onQuery={setQuery}
        onOpen={(p) => navigate(`/data-products/${p.id}`)}
        onDelete={setDeleteTarget}
      />
    )
  }

  return (
    <div>
      <div className="animate-enter">
        <PageHeader
          title="Marketplace"
          subtitle={subtitle(products.length, countDomains(products).length)}
          actions={
            <Button onClick={() => setCreateOpen(true)}>
              <PlusIcon size={15} />
              New Data Product
            </Button>
          }
        />
      </div>

      <div className="mb-4">
        <SaveWarnings warnings={warnings} onDismiss={() => setWarnings([])} />
      </div>

      {body}

      {/* Create Modal */}
      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="New Data Product" size="lg">
        <DataProductForm
          onSubmit={handleCreate}
          onCancel={() => setCreateOpen(false)}
          isSubmitting={createMutation.isPending}
        />
        {createMutation.isError && <p className="mt-3 text-[13px] text-bad">{createMutation.error.message}</p>}
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal open={!!deleteTarget} onClose={() => setDeleteTarget(null)} title="Delete Data Product" size="sm">
        <p className="mb-2 text-[13px] text-tx2">
          Are you sure you want to delete <span className="font-medium text-tx">{deleteTarget?.name}</span>?
        </p>
        <p className="mb-6 text-xs text-tx3">This action cannot be undone.</p>
        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={() => setDeleteTarget(null)}>
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
