import { useState } from 'react'
import type { ReactNode } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  useContractVersionYaml,
  useContractVersions,
  useDataContract,
  useUpdateDataContract,
  useDeleteDataContract,
  useDataContractYaml,
  useChangeContractStatus,
} from '../../hooks/useDataContracts'
import Button from '../../components/ui/Button'
import Badge from '../../components/ui/Badge'
import Modal from '../../components/ui/Modal'
import YamlModal from '../../components/ui/YamlModal'
import Spinner from '../../components/ui/Spinner'
import { Avatar, DomainChip, TierGlyph } from '../../components/ui/Glyphs'
import {
  AlertIcon,
  ClockIcon,
  CodeFileIcon,
  ContractIcon,
  EditIcon,
  ProductIcon,
  SchemaIcon,
  ServerIcon,
  ShieldIcon,
  SupportIcon,
  TrashIcon,
  UsersIcon,
  XCircleIcon,
  type IconProps,
} from '../../components/icons'
import DataContractForm from './DataContractForm'
import ContractUsage from './ContractUsage'
import StatusBar from './StatusBar'
import { safeUrl, serverLocation } from './contractMetadata'
import { STATUS_COLORS } from './contractStatus'
import { describeCheck } from '../../lib/qualityRules'
import { formatServiceLevel } from '../../lib/serviceLevels'
import { relativeTime } from '../../lib/format'
import type {
  ContractServer,
  DataContractInput,
  DataContract as DataContractType,
  QualityRule,
  SchemaField,
  SupportChannel,
  TeamMember,
} from '../../types'

function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

const dash = (value?: string | null) => value || '—'

// ─── Building blocks ──────────────────────────────────────────────────────────

function Panel({ title, icon, aside, children }: { title: string; icon?: ReactNode; aside?: ReactNode; children: ReactNode }) {
  return (
    <section className="min-w-0 rounded-[10px] border border-line bg-panel">
      <header className="flex min-h-[44px] items-center gap-2 border-b border-line px-4 text-tx3">
        {icon}
        <h2 className="text-[13px] font-semibold text-tx">{title}</h2>
        {aside && <span className="ml-auto text-xs text-tx3">{aside}</span>}
      </header>
      {children}
    </section>
  )
}

function Empty({ children }: { children: ReactNode }) {
  return <p className="px-4 py-6 text-center text-[13px] text-tx3">{children}</p>
}

function SupportUrl({ url }: { url: string }) {
  if (!url) return <>—</>
  const href = safeUrl(url)
  // Anything but http(s) and mailto stays text: a synced file can carry javascript:.
  if (!href) return <span className="break-all">{url}</span>
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="break-all text-accent-fg hover:underline">
      {url}
    </a>
  )
}

// ─── Header ───────────────────────────────────────────────────────────────────

function DetailActions({
  contract,
  onYaml,
  onEdit,
  onDelete,
  onMove,
}: {
  contract: DataContractType
  onYaml: () => void
  onEdit: () => void
  onDelete: () => void
  onMove: (to: DataContractType['status']) => void
}) {
  const can = contract.permissions
  // An active contract has no status bar: its owner finds Deprecate and Retire here.
  const lifecycle = contract.status === 'active' ? (can?.transitions ?? []) : []
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button variant="secondary" onClick={onYaml}>
        <CodeFileIcon size={14} />
        View YAML
      </Button>
      {can?.edit && (
        <Button variant="secondary" onClick={onEdit}>
          <EditIcon size={14} />
          Edit
        </Button>
      )}
      {lifecycle.includes('deprecated') && (
        <Button variant="secondary" onClick={() => onMove('deprecated')}>
          <AlertIcon size={14} />
          Deprecate
        </Button>
      )}
      {lifecycle.includes('retired') && (
        <Button variant="secondary" onClick={() => onMove('retired')}>
          <XCircleIcon size={14} />
          Retire
        </Button>
      )}
      {can?.delete && (
        <button
          type="button"
          onClick={onDelete}
          className="inline-flex h-8 items-center gap-2 rounded-lg border border-bad/25 bg-bad/10 px-3 text-[13px] font-medium text-bad transition-colors hover:bg-bad/15 focus:outline-none focus-visible:ring-[3px] focus-visible:ring-bad/30"
        >
          <TrashIcon size={14} />
          Delete
        </button>
      )}
    </div>
  )
}

function DetailHeader({ contract, actions }: { contract: DataContractType; actions: ReactNode }) {
  return (
    <div className="flex animate-enter flex-wrap items-start gap-4">
      <span className="grid h-11 w-11 shrink-0 place-items-center rounded-[11px] border border-line bg-raised text-accent-fg">
        <ContractIcon size={22} />
      </span>
      <div className="min-w-0 flex-[1_1_420px]">
        <h1 className="truncate text-[22px] font-semibold leading-tight tracking-[-0.02em] text-tx">{contract.title}</h1>
        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-2">
          <span className="inline-flex h-[22px] items-center rounded-md border border-line2 px-2 font-mono text-[11.5px] text-tx">
            v{contract.version}
          </span>
          <Badge variant={STATUS_COLORS[contract.status] ?? 'gray'} className="!h-[22px] capitalize">
            {contract.status.replace('_', ' ')}
          </Badge>
          <TierGlyph tier={contract.tier} showName />
          <DomainChip name={contract.domain} />
          {contract.owner && (
            <span className="inline-flex items-center gap-2 text-[12.5px] text-tx2">
              <Avatar name={contract.owner} size={20} />
              {contract.owner}
            </span>
          )}
          <span className="text-xs text-tx3" title={`Created ${formatDateTime(contract.created_at)}`}>
            Updated {relativeTime(contract.updated_at).toLowerCase()}
          </span>
        </div>
      </div>
      {actions}
    </div>
  )
}

function DescriptionPanel({ description }: { description?: DataContractType['description'] }) {
  const entries = [
    ['Purpose', description?.purpose],
    ['Usage', description?.usage],
    ['Limitations', description?.limitations],
  ].filter(([, text]) => text)
  if (entries.length === 0) return null
  return (
    <section className="animate-enter rounded-[10px] border border-line bg-panel [animation-delay:0.08s]">
      <h2 className="sr-only">Description</h2>
      <dl className="grid divide-y divide-line md:grid-cols-3 md:divide-x md:divide-y-0">
        {entries.map(([label, text]) => (
          <div key={label} className="min-w-0 px-4 py-3.5">
            <dt className="mb-1.5 text-[11.5px] font-medium text-tx3">{label}</dt>
            <dd className="whitespace-pre-wrap text-[12.5px] leading-relaxed text-tx2">{text}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

// ─── Schema ───────────────────────────────────────────────────────────────────

const CLASSIFICATION_STYLE: Record<string, string> = {
  public: 'border-line2 text-tx3',
  internal: 'border-line bg-raised text-tx2',
  confidential: 'border-warn/30 bg-warn/10 text-warn',
  restricted: 'border-bad/30 bg-bad/10 text-bad',
}

function Tag({ children, title, tone = '' }: { children: ReactNode; title: string; tone?: string }) {
  return (
    <span title={title} className={`inline-flex h-[18px] items-center rounded border px-[5px] font-mono text-[10.5px] font-medium ${tone || 'border-line2 text-tx2'}`}>
      {children}
    </span>
  )
}

function FieldRow({ f }: { f: SchemaField }) {
  return (
    <tr className="transition-colors duration-150 hover:bg-hover">
      <td className="h-[42px] border-b border-line px-4">
        <span className="inline-flex items-center gap-2 font-mono text-[12.5px] font-medium text-tx">{f.name}</span>
      </td>
      <td className="border-b border-line px-4">
        <span className="font-mono text-xs text-tx2">{f.type}</span>
        {f.physical_type && <span className="ml-1.5 font-mono text-[11px] text-tx3">{f.physical_type}</span>}
      </td>
      <td className="border-b border-line px-4">
        <span className="inline-flex gap-1">
          {f.primary_key && <Tag title="Primary key" tone="border-accent-fg/40 text-accent-fg">PK</Tag>}
          {f.unique && <Tag title="Unique">UQ</Tag>}
          {f.nullable ? <Tag title="Nullable" tone="border-dashed border-line2 text-tx3">null</Tag> : <Tag title="Not null">NN</Tag>}
        </span>
      </td>
      <td className="border-b border-line px-4">
        {f.classification ? (
          <span className={`inline-flex h-5 items-center rounded-[5px] border px-[7px] text-[11.5px] font-medium capitalize ${CLASSIFICATION_STYLE[f.classification] ?? CLASSIFICATION_STYLE.internal}`}>
            {f.classification}
          </span>
        ) : (
          <span className="text-tx3">—</span>
        )}
      </td>
      <td className="max-w-[320px] truncate border-b border-line px-4 text-[12.5px] text-tx2">{dash(f.description)}</td>
    </tr>
  )
}

function SchemaTable({ fields }: { fields: SchemaField[] }) {
  if (fields.length === 0) return <Empty>No fields defined.</Empty>
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] border-collapse">
        <thead>
          <tr className="text-left text-[11.5px] text-tx3">
            {['Field', 'Type', 'Constraints', 'Classification', 'Description'].map((h) => (
              <th key={h} className="border-b border-line px-4 py-2.5 font-medium">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="[&>tr:last-child>td]:border-b-0">
          {fields.map((f) => (
            <FieldRow key={f.name} f={f} />
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ─── Quality ──────────────────────────────────────────────────────────────────

function QualityList({ rules }: { rules: QualityRule[] }) {
  if (rules.length === 0) return <Empty>No quality rules yet.</Empty>
  return (
    <ul className="divide-y divide-line">
      {rules.map((r, i) => (
        <li key={i} className="grid min-h-[46px] grid-cols-[130px_minmax(0,1fr)_auto] items-center gap-3.5 px-4 py-2 transition-colors duration-150 hover:bg-hover md:grid-cols-[130px_minmax(0,1fr)_180px_70px]">
          <span className="inline-flex items-center gap-[7px] text-[12.5px] capitalize text-tx">
            <ShieldIcon size={14} className="text-tx3" />
            {dash(r.dimension)}
          </span>
          <span className="min-w-0">
            {r.type === 'text' ? (
              <span className="text-[12.5px] text-tx2">{dash(r.description)}</span>
            ) : (
              <>
                <span className="block truncate font-mono text-xs text-tx">{describeCheck(r)}</span>
                {r.description && <span className="block truncate text-[11.5px] text-tx3">{r.description}</span>}
              </>
            )}
          </span>
          <span className="hidden truncate font-mono text-xs text-tx2 md:block">{dash(r.column)}</span>
          <span className="justify-self-end rounded border border-line2 px-[5px] font-mono text-[10.5px] font-medium leading-[17px] text-tx3">
            {r.type}
          </span>
        </li>
      ))}
    </ul>
  )
}

// ─── Versions ─────────────────────────────────────────────────────────────────

function VersionHistory({
  contractId,
  currentVersion,
  onView,
}: {
  contractId: string
  currentVersion: string
  onView: (version: string) => void
}) {
  const { data: versions = [], isLoading, isError } = useContractVersions(contractId)
  if (isLoading) return <div className="flex justify-center py-6"><Spinner /></div>
  if (isError) return <Empty><span className="text-bad">Could not load version history.</span></Empty>
  if (versions.length === 0) return <Empty>No history yet. It starts at the next version change.</Empty>
  return (
    <ul className="px-4 py-2">
      {versions.map((v, i) => {
        const current = v.version === currentVersion
        return (
          <li key={v.version} data-testid="version-row" className="relative flex items-center gap-3.5 py-3 pl-[22px]">
            <span
              aria-hidden="true"
              className={`absolute left-[4px] w-px bg-line2 ${i === 0 ? 'top-1/2' : 'top-0'} ${i === versions.length - 1 ? 'bottom-1/2' : 'bottom-0'}`}
            />
            <span
              aria-hidden="true"
              className={`absolute left-0 top-1/2 h-[9px] w-[9px] -translate-y-1/2 rounded-full border-[1.5px] ${
                current ? 'border-accent bg-accent shadow-[0_0_0_4px_rgb(var(--accent)/0.16)]' : 'border-tx3 bg-panel'
              }`}
            />
            <span className="min-w-[72px] font-mono text-[13px] font-medium text-tx">{v.version}</span>
            <span className="flex min-w-0 flex-1 items-center gap-2 text-[12.5px] text-tx3">
              {v.created_by && (
                <>
                  <Avatar name={v.created_by} size={18} />
                  {v.created_by} ·
                </>
              )}
              {formatDateTime(v.created_at)}
              {current && (
                <span className="rounded bg-accent px-1.5 text-[10.5px] font-medium leading-[17px] text-accent-ink">current</span>
              )}
            </span>
            <Button variant="secondary" size="sm" aria-label={`View YAML for version ${v.version}`} onClick={() => onView(v.version)}>
              <CodeFileIcon size={14} />
              YAML
            </Button>
          </li>
        )
      })}
    </ul>
  )
}

// ─── Tabs ─────────────────────────────────────────────────────────────────────

type Tab = 'schema' | 'quality' | 'versions'

function ContractTabs({ contract, onViewVersion }: { contract: DataContractType; onViewVersion: (v: string) => void }) {
  const [tab, setTab] = useState<Tab>('schema')
  const { data: versions } = useContractVersions(contract.id)
  const fields = contract.models.fields ?? []
  const rules = contract.models.quality ?? []
  const tabs: [Tab, string, number | undefined, (p: IconProps) => ReactNode][] = [
    ['schema', 'Schema', fields.length, SchemaIcon],
    ['quality', 'Quality', rules.length, ShieldIcon],
    ['versions', 'Versions', versions?.length, ClockIcon],
  ]
  return (
    <div className="min-w-0 flex-[999_1_620px] animate-enter [animation-delay:0.12s]">
      <div role="tablist" aria-label="Contract sections" className="mb-3.5 flex items-center gap-0.5 border-b border-line">
        {tabs.map(([key, label, count, Icon]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={tab === key}
            onClick={() => setTab(key)}
            className={`relative inline-flex h-10 items-center gap-[7px] px-3 text-[13px] font-medium transition-colors duration-150 after:absolute after:inset-x-2.5 after:-bottom-px after:h-0.5 after:rounded-full after:bg-accent-fg after:transition-transform after:duration-300 ${
              tab === key ? 'text-tx after:scale-x-100' : 'text-tx3 after:scale-x-0 hover:text-tx'
            }`}
          >
            <Icon size={15} />
            {label}
            {count !== undefined && <span className="font-mono text-[11px] text-tx3">{count}</span>}
          </button>
        ))}
      </div>
      <section key={tab} role="tabpanel" aria-label={tab} className="animate-swap rounded-[10px] border border-line bg-panel">
        {tab === 'schema' && <SchemaTable fields={fields} />}
        {tab === 'quality' && <QualityList rules={rules} />}
        {tab === 'versions' && (
          <VersionHistory contractId={contract.id} currentVersion={contract.version} onView={onViewVersion} />
        )}
      </section>
    </div>
  )
}

// ─── Rail ─────────────────────────────────────────────────────────────────────

function ServiceLevelsPanel({ sla }: { sla?: DataContractType['servicelevels'] }) {
  // An unmigrated row holds no properties key; it shows as empty instead of crashing.
  const properties = Array.isArray(sla?.properties) ? sla.properties : []
  return (
    <Panel title="Service Levels" icon={<ClockIcon size={15} />}>
      {properties.length === 0 ? (
        <Empty>No service levels</Empty>
      ) : (
        <ul className="px-4 py-1">
          {properties.map((p) => (
            <li key={p.property} className="flex h-9 items-center justify-between gap-2.5 border-b border-line text-[12.5px] last:border-0">
              <span className="capitalize text-tx2">{p.property}</span>
              <b className="font-mono text-[12.5px] font-medium text-tx">{formatServiceLevel(p)}</b>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}

function ServersPanel({ servers = [] }: { servers?: ContractServer[] }) {
  if (servers.length === 0) return null
  return (
    <Panel title="Servers" icon={<ServerIcon size={15} />} aside={servers.length}>
      <ul className="divide-y divide-line">
        {servers.map((s, i) => (
          <li key={`${s.server}-${i}`} className="flex gap-3 px-4 py-3">
            <span className="grid h-[30px] w-[30px] shrink-0 place-items-center rounded-lg border border-line bg-raised text-tx2">
              <ServerIcon size={15} />
            </span>
            <span className="min-w-0 flex-1">
              <span className="flex items-center gap-2">
                <b className="text-[12.5px] font-medium text-tx">{s.server}</b>
                <span className="text-xs text-tx3">{s.type}</span>
                {s.environment && (
                  <span className="rounded border border-line2 px-[5px] font-mono text-[10.5px] font-medium leading-[17px] text-tx3">
                    {s.environment}
                  </span>
                )}
              </span>
              <span className="block truncate font-mono text-[11.5px] text-tx3">{serverLocation(s)}</span>
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  )
}

function TeamPanel({ members = [] }: { members?: TeamMember[] }) {
  if (members.length === 0) return null
  return (
    <Panel title="Team Members" icon={<UsersIcon size={15} />} aside={members.length}>
      <ul className="px-4 py-1.5">
        {members.map((m) => (
          <li key={m.username} className="flex h-[38px] items-center gap-2.5 text-[12.5px]">
            <Avatar name={m.name || m.username} />
            <span className="min-w-0 truncate text-tx">{m.username}</span>
            {m.name && <span className="truncate text-tx3">{m.name}</span>}
            <span className="ml-auto shrink-0 text-xs text-tx3">{dash(m.role)}</span>
          </li>
        ))}
      </ul>
    </Panel>
  )
}

function SupportPanel({ channels = [] }: { channels?: SupportChannel[] }) {
  if (channels.length === 0) return null
  return (
    <Panel title="Support" icon={<SupportIcon size={15} />} aside={channels.length}>
      <ul className="divide-y divide-line">
        {channels.map((c, i) => (
          <li key={`${c.channel}-${i}`} className="px-4 py-2.5 text-[12.5px]">
            <span className="flex items-center gap-2">
              <b className="font-medium text-tx">{c.channel}</b>
              {c.tool && <span className="text-xs text-tx3">{c.tool}</span>}
              {c.scope && <span className="ml-auto text-xs text-tx3">{c.scope}</span>}
            </span>
            <span className="mt-0.5 block text-xs text-tx2">
              <SupportUrl url={c.url} />
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  )
}

function DatesPanel({ contract }: { contract: DataContractType }) {
  return (
    <Panel title="Details">
      <ul className="px-4 py-1 text-[12.5px]">
        <li className="flex h-9 items-center justify-between gap-2.5 border-b border-line">
          <span className="text-tx2">Created</span>
          <span className="text-tx">{formatDateTime(contract.created_at)}</span>
        </li>
        <li className="flex h-9 items-center justify-between gap-2.5">
          <span className="text-tx2">Updated</span>
          <span className="text-tx">{formatDateTime(contract.updated_at)}</span>
        </li>
      </ul>
    </Panel>
  )
}

// ─── Modals ───────────────────────────────────────────────────────────────────

function VersionYamlModal({
  contractId,
  version,
  onClose,
}: {
  contractId: string
  version: string | null
  onClose: () => void
}) {
  const { data, isFetching } = useContractVersionYaml(contractId, version)
  return (
    <YamlModal title={`Version ${version}`} open={version !== null} content={data} loading={isFetching} onClose={onClose} />
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function DataContractDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [editOpen, setEditOpen] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState(false)
  const [retireConfirm, setRetireConfirm] = useState(false)
  const [yamlOpen, setYamlOpen] = useState(false)
  const [openVersion, setOpenVersion] = useState<string | null>(null)

  const { data: contract, isLoading, error } = useDataContract(id ?? '')
  const updateMutation = useUpdateDataContract()
  const deleteMutation = useDeleteDataContract()
  const statusMutation = useChangeContractStatus()
  const { data: yamlContent, isFetching: yamlLoading } = useDataContractYaml(id ?? '', yamlOpen)

  const handleUpdate = async (input: DataContractInput) => {
    await updateMutation.mutateAsync({ id: id!, ...input })
    setEditOpen(false)
  }

  // Retiring is permanent, so it asks first; every other move goes at once.
  const move = (to: DataContractType['status']) => {
    if (to === 'retired') setRetireConfirm(true)
    else statusMutation.mutate({ id: id!, status: to })
  }

  const handleRetire = () => {
    statusMutation.mutate({ id: id!, status: 'retired' }, { onSuccess: () => setRetireConfirm(false) })
  }

  const handleDelete = async () => {
    await deleteMutation.mutateAsync(id!)
    navigate('/data-contracts')
  }

  if (isLoading) {
    return <div className="flex h-64 items-center justify-center"><Spinner size="lg" /></div>
  }

  if (error || !contract) {
    return (
      <div className="py-16 text-center">
        <p className="font-medium text-bad">{error?.message ?? 'Contract not found'}</p>
        <button onClick={() => navigate('/data-contracts')} className="mt-3 text-[13px] text-accent-fg hover:underline">
          Back to list
        </button>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-[18px]">
      <DetailHeader
        contract={contract}
        actions={
          <DetailActions
            contract={contract}
            onYaml={() => setYamlOpen(true)}
            onEdit={() => setEditOpen(true)}
            onDelete={() => setDeleteConfirm(true)}
            onMove={move}
          />
        }
      />

      <StatusBar
        contract={contract}
        pending={statusMutation.isPending}
        error={statusMutation.isError ? statusMutation.error.message : null}
        onMove={move}
      />

      <DescriptionPanel description={contract.description} />

      <div className="flex flex-wrap items-start gap-5">
        <ContractTabs contract={contract} onViewVersion={setOpenVersion} />
        <aside aria-label="Contract details" className="flex min-w-0 flex-[1_1_300px] animate-enter flex-col gap-3.5 [animation-delay:0.18s]">
          <Panel title="Usage" icon={<ProductIcon size={15} />}>
            <ContractUsage contract={contract} />
          </Panel>
          <ServiceLevelsPanel sla={contract.servicelevels} />
          <ServersPanel servers={contract.servers} />
          <TeamPanel members={contract.team_members} />
          <SupportPanel channels={contract.support} />
          <DatesPanel contract={contract} />
        </aside>
      </div>

      <VersionYamlModal contractId={contract.id} version={openVersion} onClose={() => setOpenVersion(null)} />

      <YamlModal title="ODCS YAML" open={yamlOpen} content={yamlContent} loading={yamlLoading} onClose={() => setYamlOpen(false)} />

      <Modal open={editOpen} onClose={() => setEditOpen(false)} title="Edit Data Contract" size="lg">
        <DataContractForm
          defaultValues={contract}
          onSubmit={handleUpdate}
          onCancel={() => setEditOpen(false)}
          isSubmitting={updateMutation.isPending}
        />
        {updateMutation.isError && <p className="mt-3 text-[13px] text-bad">{updateMutation.error.message}</p>}
      </Modal>

      <Modal open={retireConfirm} onClose={() => setRetireConfirm(false)} title="Retire contract" size="sm">
        <p className="mb-6 text-[13px] text-tx2">
          Retiring is permanent: the contract can no longer be edited or reactivated.
        </p>
        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={() => setRetireConfirm(false)}>Cancel</Button>
          <Button variant="danger" loading={statusMutation.isPending} onClick={handleRetire}>Retire</Button>
        </div>
        {statusMutation.isError && <p className="mt-3 text-[13px] text-bad">{statusMutation.error.message}</p>}
      </Modal>

      <Modal open={deleteConfirm} onClose={() => setDeleteConfirm(false)} title="Delete Data Contract" size="sm">
        <p className="mb-6 text-[13px] text-tx2">
          Are you sure you want to delete <span className="font-medium text-tx">{contract.title}</span>? This cannot be undone.
        </p>
        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={() => setDeleteConfirm(false)}>Cancel</Button>
          <Button variant="danger" loading={deleteMutation.isPending} onClick={handleDelete}>Delete</Button>
        </div>
        {deleteMutation.isError && <p className="mt-3 text-[13px] text-bad">{deleteMutation.error.message}</p>}
      </Modal>
    </div>
  )
}
