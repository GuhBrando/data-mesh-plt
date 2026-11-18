import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Edit2, Trash2, Calendar, Clock, FileCode } from 'lucide-react'
import {
  useContractVersionYaml,
  useContractVersions,
  useDataContract,
  useUpdateDataContract,
  useDeleteDataContract,
  useDataContractYaml,
} from '../../hooks/useDataContracts'
import PageHeader from '../../components/PageHeader'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import Badge from '../../components/ui/Badge'
import Modal from '../../components/ui/Modal'
import Spinner from '../../components/ui/Spinner'
import DataContractForm from './DataContractForm'
import { safeUrl, serverLocation } from './contractMetadata'
import { describeCheck } from '../../lib/qualityRules'
import { formatServiceLevel } from '../../lib/serviceLevels'
import type { DataContractInput, DataContract as DataContractType } from '../../types'

const TIER_COLORS: Record<number, 'red' | 'yellow' | 'blue' | 'gray'> = {
  1: 'red', 2: 'yellow', 3: 'blue', 4: 'gray',
}
const TIER_NAMES: Record<number, string> = {
  1: 'Critical / Regulated', 2: 'Business Important',
  3: 'Operational / Internal', 4: 'Experimental / Sandbox',
}
const STATUS_COLORS: Record<string, 'gray' | 'yellow' | 'green' | 'red'> = {
  draft: 'gray', in_review: 'yellow', active: 'green', deprecated: 'red',
}

function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

function SchemaFieldsCard({ fields }: { fields: DataContractType['models']['fields'] }) {
  return (
    <Card>
      <h2 className="text-sm font-semibold text-gray-700 dark:text-slate-200 mb-3">
        Schema Fields ({fields.length})
      </h2>
      {fields.length === 0 ? (
        <p className="text-sm text-gray-400 dark:text-slate-500 italic">No fields defined.</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-gray-400 dark:text-slate-500 border-b border-gray-200 dark:border-slate-700">
              <th className="pb-2 pr-4">Field</th>
              <th className="pb-2 pr-4">Type</th>
              <th className="pb-2 pr-4">Nullable</th>
              <th className="pb-2 pr-4">PK</th>
              <th className="pb-2 pr-4">Physical</th>
              <th className="pb-2 pr-4">Classification</th>
              <th className="pb-2 pr-4">Unique</th>
              <th className="pb-2">Description</th>
            </tr>
          </thead>
          <tbody>
            {fields.map((f, i) => (
              <tr key={i} className="border-b border-gray-100 dark:border-slate-800 last:border-0">
                <td className="py-2 pr-4 font-mono text-gray-800 dark:text-slate-200">{f.name}</td>
                <td className="py-2 pr-4 text-gray-600 dark:text-slate-300">{f.type}</td>
                <td className="py-2 pr-4 text-gray-500 dark:text-slate-400">{f.nullable ? 'yes' : 'no'}</td>
                <td className="py-2 pr-4 text-gray-500 dark:text-slate-400">{f.primary_key ? '✓' : '—'}</td>
                <td className="py-2 pr-4 font-mono text-gray-600 dark:text-slate-300">{f.physical_type || '—'}</td>
                <td className="py-2 pr-4 text-gray-500 dark:text-slate-400">{f.classification || '—'}</td>
                <td className="py-2 pr-4 text-gray-500 dark:text-slate-400">{f.unique ? '✓' : '—'}</td>
                <td className="py-2 text-gray-500 dark:text-slate-400">{f.description || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  )
}

function ServiceLevelsCard({ sla }: { sla?: DataContractType['servicelevels'] }) {
  // An unmigrated row holds no properties key; it shows as empty instead of crashing.
  const properties = Array.isArray(sla?.properties) ? sla.properties : []
  return (
    <Card>
      <h2 className="text-sm font-semibold text-gray-700 dark:text-slate-200 mb-3">Service Levels</h2>
      {properties.length === 0 ? (
        <p className="text-sm text-gray-400 dark:text-slate-500 italic">No service levels</p>
      ) : (
        <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
          {properties.map((p) => (
            <div key={p.property}>
              <dt className="text-gray-400 dark:text-slate-500">{p.property}</dt>
              <dd className="text-gray-800 dark:text-slate-200">{formatServiceLevel(p)}</dd>
            </div>
          ))}
        </dl>
      )}
    </Card>
  )
}

function QualityRulesCard({ rules }: { rules: NonNullable<DataContractType['models']['quality']> }) {
  if (rules.length === 0) return null
  return (
    <Card>
      <h2 className="text-sm font-semibold text-gray-700 dark:text-slate-200 mb-3">
        Quality Rules ({rules.length})
      </h2>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-gray-400 dark:text-slate-500 border-b border-gray-200 dark:border-slate-700">
            <th className="pb-2 pr-4">Type</th>
            <th className="pb-2 pr-4">Dimension</th>
            <th className="pb-2 pr-4">Column</th>
            <th className="pb-2 pr-4">Check</th>
            <th className="pb-2">Description</th>
          </tr>
        </thead>
        <tbody>
          {rules.map((r, i) => (
            <tr key={i} className="border-b border-gray-100 dark:border-slate-800 last:border-0">
              <td className="py-2 pr-4 text-gray-500 dark:text-slate-400">{r.type}</td>
              <td className="py-2 pr-4 text-gray-800 dark:text-slate-200">{r.dimension ?? '—'}</td>
              <td className="py-2 pr-4 font-mono text-gray-600 dark:text-slate-300">{r.column || '—'}</td>
              <td className="py-2 pr-4 font-mono text-gray-800 dark:text-slate-200">{describeCheck(r)}</td>
              <td className="py-2 text-gray-500 dark:text-slate-400">{r.description || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  )
}

function DescriptionCard({ description }: { description?: DataContractType['description'] }) {
  const entries = [
    ['Purpose', description?.purpose],
    ['Usage', description?.usage],
    ['Limitations', description?.limitations],
  ].filter(([, text]) => text)
  if (entries.length === 0) return null
  return (
    <Card>
      <h2 className="text-sm font-semibold text-gray-700 dark:text-slate-200 mb-3">Description</h2>
      <dl className="space-y-2 text-sm">
        {entries.map(([label, text]) => (
          <div key={label}>
            <dt className="text-gray-400 dark:text-slate-500">{label}</dt>
            <dd className="text-gray-800 dark:text-slate-200 whitespace-pre-wrap">{text}</dd>
          </div>
        ))}
      </dl>
    </Card>
  )
}

function TeamCard({ members = [] }: { members?: DataContractType['team_members'] }) {
  if (members.length === 0) return null
  return (
    <Card>
      <h2 className="text-sm font-semibold text-gray-700 dark:text-slate-200 mb-3">Team Members</h2>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-gray-400 dark:text-slate-500 border-b border-gray-200 dark:border-slate-700">
            <th className="pb-2 pr-4">Username</th>
            <th className="pb-2 pr-4">Name</th>
            <th className="pb-2">Role</th>
          </tr>
        </thead>
        <tbody>
          {members.map((m, i) => (
            <tr key={i} className="border-b border-gray-100 dark:border-slate-800 last:border-0">
              <td className="py-2 pr-4 text-gray-800 dark:text-slate-200">{m.username}</td>
              <td className="py-2 pr-4 text-gray-500 dark:text-slate-400">{m.name || '—'}</td>
              <td className="py-2 text-gray-500 dark:text-slate-400">{m.role || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  )
}

function SupportUrl({ url }: { url: string }) {
  if (!url) return <>—</>
  const href = safeUrl(url)
  // Anything but http(s) and mailto stays text: a synced file can carry javascript:.
  if (!href) return <>{url}</>
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-blue-600 dark:text-blue-400 hover:underline"
    >
      {url}
    </a>
  )
}

function SupportCard({ channels = [] }: { channels?: DataContractType['support'] }) {
  if (channels.length === 0) return null
  return (
    <Card>
      <h2 className="text-sm font-semibold text-gray-700 dark:text-slate-200 mb-3">Support</h2>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-gray-400 dark:text-slate-500 border-b border-gray-200 dark:border-slate-700">
            <th className="pb-2 pr-4">Channel</th>
            <th className="pb-2 pr-4">URL</th>
            <th className="pb-2 pr-4">Tool</th>
            <th className="pb-2">Scope</th>
          </tr>
        </thead>
        <tbody>
          {channels.map((c, i) => (
            <tr key={i} className="border-b border-gray-100 dark:border-slate-800 last:border-0">
              <td className="py-2 pr-4 text-gray-800 dark:text-slate-200">{c.channel}</td>
              <td className="py-2 pr-4 text-gray-500 dark:text-slate-400"><SupportUrl url={c.url} /></td>
              <td className="py-2 pr-4 text-gray-500 dark:text-slate-400">{c.tool || '—'}</td>
              <td className="py-2 text-gray-500 dark:text-slate-400">{c.scope || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  )
}

function ServersCard({ servers = [] }: { servers?: DataContractType['servers'] }) {
  if (servers.length === 0) return null
  return (
    <Card>
      <h2 className="text-sm font-semibold text-gray-700 dark:text-slate-200 mb-3">Servers</h2>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-gray-400 dark:text-slate-500 border-b border-gray-200 dark:border-slate-700">
            <th className="pb-2 pr-4">Server</th>
            <th className="pb-2 pr-4">Type</th>
            <th className="pb-2 pr-4">Environment</th>
            <th className="pb-2">Location</th>
          </tr>
        </thead>
        <tbody>
          {servers.map((s, i) => (
            <tr key={i} className="border-b border-gray-100 dark:border-slate-800 last:border-0">
              <td className="py-2 pr-4 text-gray-800 dark:text-slate-200">{s.server}</td>
              <td className="py-2 pr-4 text-gray-500 dark:text-slate-400">{s.type}</td>
              <td className="py-2 pr-4 text-gray-500 dark:text-slate-400">{s.environment || '—'}</td>
              <td className="py-2 font-mono text-gray-600 dark:text-slate-300">{serverLocation(s)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  )
}

function VersionHistoryCard({
  contractId,
  currentVersion,
  onView,
}: {
  contractId: string
  currentVersion: string
  onView: (version: string) => void
}) {
  const { data: versions = [], isLoading, isError } = useContractVersions(contractId)
  let body
  if (isLoading) {
    body = <div className="flex justify-center py-4"><Spinner /></div>
  } else if (isError) {
    body = <p className="text-sm text-red-500">Could not load version history.</p>
  } else if (versions.length === 0) {
    body = (
      <p className="text-sm text-gray-400 dark:text-slate-500 italic">
        No history yet. It starts at the next version change.
      </p>
    )
  } else {
    body = (
      <ul className="divide-y divide-gray-100 dark:divide-slate-800 text-sm">
        {versions.map((v) => (
          <li key={v.version} data-testid="version-row" className="flex items-center gap-3 py-2">
            <span className="font-mono text-gray-800 dark:text-slate-200">{v.version}</span>
            {v.version === currentVersion && <Badge variant="green">current</Badge>}
            <span className="flex-1 text-gray-500 dark:text-slate-400">{formatDateTime(v.created_at)}</span>
            <Button
              variant="secondary"
              size="sm"
              aria-label={`View YAML for version ${v.version}`}
              onClick={() => onView(v.version)}
            >
              <FileCode size={14} />
              YAML
            </Button>
          </li>
        ))}
      </ul>
    )
  }
  return (
    <Card>
      <h2 className="text-sm font-semibold text-gray-700 dark:text-slate-200 mb-3">Version History</h2>
      {body}
    </Card>
  )
}

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
    <Modal open={version !== null} onClose={onClose} title={`Version ${version}`} size="lg">
      {isFetching ? (
        <div className="flex justify-center py-8"><Spinner /></div>
      ) : (
        <pre className="bg-gray-50 dark:bg-slate-900 border border-gray-200 dark:border-slate-700 rounded-lg p-4 text-xs font-mono text-gray-700 dark:text-slate-300 overflow-x-auto whitespace-pre-wrap">
          {data}
        </pre>
      )}
    </Modal>
  )
}

function DetailActions({
  retired,
  onYaml,
  onEdit,
  onDelete,
}: {
  retired: boolean
  onYaml: () => void
  onEdit: () => void
  onDelete: () => void
}) {
  return (
    <>
      <Button variant="secondary" size="sm" onClick={onYaml}>
        <FileCode size={14} />
        View YAML
      </Button>
      {/* Retired is terminal: the API refuses every edit. */}
      {!retired && (
        <Button variant="secondary" size="sm" onClick={onEdit}>
          <Edit2 size={14} />
          Edit
        </Button>
      )}
      <Button variant="danger" size="sm" onClick={onDelete}>
        <Trash2 size={14} />
        Delete
      </Button>
    </>
  )
}

export default function DataContractDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [editOpen, setEditOpen] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState(false)
  const [yamlOpen, setYamlOpen] = useState(false)
  const [openVersion, setOpenVersion] = useState<string | null>(null)

  const { data: contract, isLoading, error } = useDataContract(id ?? '')
  const updateMutation = useUpdateDataContract()
  const deleteMutation = useDeleteDataContract()
  const { data: yamlContent, isFetching: yamlLoading } = useDataContractYaml(id ?? '', yamlOpen)

  const handleUpdate = async (input: DataContractInput) => {
    await updateMutation.mutateAsync({ id: id!, ...input })
    setEditOpen(false)
  }

  const handleDelete = async () => {
    await deleteMutation.mutateAsync(id!)
    navigate('/data-contracts')
  }

  const handleApprove = () => {
    updateMutation.mutate({ id: id!, status: 'active' })
  }

  const handleRequestChanges = () => {
    updateMutation.mutate({ id: id!, status: 'draft' })
  }

  if (isLoading) {
    return <div className="flex items-center justify-center h-64"><Spinner size="lg" /></div>
  }

  if (error || !contract) {
    return (
      <div className="text-center py-16">
        <p className="text-red-500 font-medium">{error?.message ?? 'Contract not found'}</p>
        <button onClick={() => navigate('/data-contracts')}
          className="mt-3 text-sm text-blue-600 dark:text-blue-400 hover:underline">
          Back to list
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={contract.title}
        subtitle={`v${contract.version} · ${contract.domain}`}
        backTo="/data-contracts"
        actions={
          <DetailActions
            retired={contract.status === 'retired'}
            onYaml={() => setYamlOpen(true)}
            onEdit={() => setEditOpen(true)}
            onDelete={() => setDeleteConfirm(true)}
          />
        }
      />

      {contract.status === 'in_review' && (
        <div className="flex items-center gap-3 p-3 rounded-lg border border-yellow-200 bg-yellow-50 dark:border-yellow-700 dark:bg-yellow-900/20">
          <p className="text-sm text-yellow-800 dark:text-yellow-300 flex-1">
            This contract is awaiting review.
          </p>
          <Button size="sm" onClick={handleApprove} loading={updateMutation.isPending}>
            Approve
          </Button>
          <Button size="sm" variant="secondary" onClick={handleRequestChanges}
            loading={updateMutation.isPending}>
            Request Changes
          </Button>
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <Badge variant={TIER_COLORS[contract.tier]}>
          Tier {contract.tier} — {TIER_NAMES[contract.tier]}
        </Badge>
        <Badge variant={STATUS_COLORS[contract.status] ?? 'gray'}>
          {contract.status.replace('_', ' ')}
        </Badge>
        <Badge variant="gray">
          <Calendar size={11} className="mr-1" />
          Created {formatDateTime(contract.created_at)}
        </Badge>
        <Badge variant="gray">
          <Clock size={11} className="mr-1" />
          Updated {formatDateTime(contract.updated_at)}
        </Badge>
      </div>

      <Card>
        <h2 className="text-sm font-semibold text-gray-700 dark:text-slate-200 mb-3">Info</h2>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
          <div><dt className="text-gray-400 dark:text-slate-500">Owner</dt><dd className="text-gray-800 dark:text-slate-200">{contract.owner}</dd></div>
          <div><dt className="text-gray-400 dark:text-slate-500">Domain</dt><dd className="text-gray-800 dark:text-slate-200">{contract.domain}</dd></div>
          <div><dt className="text-gray-400 dark:text-slate-500">Version</dt><dd className="text-gray-800 dark:text-slate-200">{contract.version}</dd></div>
          <div><dt className="text-gray-400 dark:text-slate-500">Status</dt><dd className="text-gray-800 dark:text-slate-200">{contract.status.replace('_', ' ')}</dd></div>
        </dl>
      </Card>

      <DescriptionCard description={contract.description} />

      <SchemaFieldsCard fields={contract.models.fields} />

      <QualityRulesCard rules={contract.models.quality ?? []} />

      <ServiceLevelsCard sla={contract.servicelevels} />

      <TeamCard members={contract.team_members} />

      <SupportCard channels={contract.support} />

      <ServersCard servers={contract.servers} />

      <VersionHistoryCard
        contractId={contract.id}
        currentVersion={contract.version}
        onView={setOpenVersion}
      />

      <VersionYamlModal
        contractId={contract.id}
        version={openVersion}
        onClose={() => setOpenVersion(null)}
      />

      <Modal open={yamlOpen} onClose={() => setYamlOpen(false)} title="ODCS YAML" size="lg">
        {yamlLoading ? (
          <div className="flex justify-center py-8"><Spinner /></div>
        ) : (
          <pre className="bg-gray-50 dark:bg-slate-900 border border-gray-200 dark:border-slate-700 rounded-lg p-4 text-xs font-mono text-gray-700 dark:text-slate-300 overflow-x-auto whitespace-pre-wrap">
            {yamlContent}
          </pre>
        )}
      </Modal>

      <Modal open={editOpen} onClose={() => setEditOpen(false)} title="Edit Data Contract" size="lg">
        <DataContractForm
          defaultValues={contract}
          onSubmit={handleUpdate}
          onCancel={() => setEditOpen(false)}
          isSubmitting={updateMutation.isPending}
        />
        {updateMutation.isError && (
          <p className="mt-3 text-sm text-red-500">{updateMutation.error.message}</p>
        )}
      </Modal>

      <Modal open={deleteConfirm} onClose={() => setDeleteConfirm(false)} title="Delete Data Contract" size="sm">
        <p className="text-sm text-gray-600 dark:text-slate-300 mb-6">
          Are you sure you want to delete <span className="font-medium">{contract.title}</span>? This cannot be undone.
        </p>
        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={() => setDeleteConfirm(false)}>Cancel</Button>
          <Button variant="danger" loading={deleteMutation.isPending} onClick={handleDelete}>Delete</Button>
        </div>
        {deleteMutation.isError && (
          <p className="mt-3 text-sm text-red-500">{deleteMutation.error.message}</p>
        )}
      </Modal>
    </div>
  )
}
