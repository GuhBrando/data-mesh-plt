import { useState } from 'react'
import {
  Shield,
  ShieldAlert,
  Building2,
  User as UserIcon,
  Lock,
  ChevronRight,
  Eye,
  EyeOff,
  CheckCircle2,
  XCircle,
  Trash2,
  Pencil,
  Plus,
} from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import { useUserDomains, useChangePassword } from '../hooks/useProfile'
import Button from '../components/ui/Button'
import { Input, Textarea } from '../components/ui/Input'
import Modal from '../components/ui/Modal'
import Table, { Column } from '../components/ui/Table'
import { useAllDomains, useCreateDomain, useUpdateDomain, useDeleteDomain } from '../hooks/useDomains'
import { useUsers } from '../hooks/useUsers'
import type { DomainWithMembers, DomainInput, User } from '../types'
import { Avatar } from '../components/ui/Glyphs'

const ROLE_META: Record<
  string,
  { label: string; color: string; description: string; permissions: string[] }
> = {
  PLATFORM_ADMIN: {
    label: 'Platform Admin',
    color: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300',
    description: 'Full control over all platform resources.',
    permissions: [
      'Create and delete users',
      'Assign any role to any user',
      'Create domains and manage all domain memberships',
      'Create, edit, and delete any data contract',
      'Assign stakeholders to any contract',
    ],
  },
  DATA_OWNER: {
    label: 'Data Owner',
    color: 'bg-accent/15 text-accent-fg dark:bg-accent/10 dark:text-accent-fg',
    description: 'Governs your domain and its data contracts.',
    permissions: [
      'Add and remove members within your domain',
      'Approve, reject, and delete contracts in your domain',
      'View all data contracts',
    ],
  },
  DATA_STEWARD: {
    label: 'Data Steward',
    color: 'bg-accent/15 text-accent-fg dark:bg-accent/10 dark:text-accent-fg',
    description: 'Creates and manages data contracts in your domain.',
    permissions: [
      'Create and edit data contracts within your domain',
      'Assign stakeholders to contracts in your domain',
      'View all data contracts',
    ],
  },
  DATA_CONSUMER: {
    label: 'Data Consumer',
    color: 'bg-slate-100 text-slate-700 dark:bg-slate-700/50 dark:text-slate-300',
    description: 'Read-only access to contracts where you are a stakeholder.',
    permissions: [
      'View data contracts where assigned as stakeholder',
      'View your own profile and domain memberships',
    ],
  },
}

type Section = 'role' | 'password' | 'admin-domains' | 'admin-users'

const ACCOUNT_NAV: { id: Section; label: string; icon: React.ReactNode }[] = [
  { id: 'role', label: 'My Role', icon: <Shield size={16} /> },
  { id: 'password', label: 'Change Password', icon: <Lock size={16} /> },
]

const ADMIN_NAV: { id: Section; label: string; icon: React.ReactNode }[] = [
  { id: 'admin-domains', label: 'Domains', icon: <Building2 size={16} /> },
  { id: 'admin-users', label: 'Users', icon: <ShieldAlert size={16} /> },
]

function validatePassword(v: string): string | null {
  if (v.length < 8) return 'At least 8 characters'
  if (!/[A-Z]/.test(v)) return 'At least one uppercase letter'
  if (!/[a-z]/.test(v)) return 'At least one lowercase letter'
  if (!/\d/.test(v)) return 'At least one number'
  if (!/[!@#$%^&*]/.test(v)) return 'At least one special character (!@#$%^&*)'
  return null
}

// ── Sections ────────────────────────────────────────────────────────────────

function RoleSection({ userId }: { userId: string | undefined }) {
  const { user } = useAuth()
  const { data: domains, isLoading } = useUserDomains(userId)

  if (!user) return null
  const role = ROLE_META[user.role] ?? {
    label: user.role,
    color: 'bg-slate-100 text-slate-700 dark:bg-slate-700/50 dark:text-slate-300',
    description: '',
    permissions: [],
  }

  return (
    <div className="space-y-6">
      <div className="card p-6 space-y-4">
        <div className="flex items-center gap-2">
          <Shield size={16} className="text-slate-500 dark:text-slate-400" />
          <h2 className="font-semibold text-slate-900 dark:text-white">Permissions</h2>
        </div>
        {role.description && (
          <p className="text-sm text-slate-600 dark:text-slate-400">{role.description}</p>
        )}
        <ul className="space-y-2">
          {role.permissions.map((p) => (
            <li key={p} className="flex items-start gap-2 text-sm text-slate-700 dark:text-slate-300">
              <ChevronRight size={14} className="mt-0.5 shrink-0 text-accent-fg dark:text-accent-fg" />
              {p}
            </li>
          ))}
        </ul>
      </div>

      <div className="card p-6 space-y-4">
        <div className="flex items-center gap-2">
          <Building2 size={16} className="text-slate-500 dark:text-slate-400" />
          <h2 className="font-semibold text-slate-900 dark:text-white">Domain Memberships</h2>
        </div>
        {isLoading ? (
          <p className="text-sm text-slate-500 dark:text-slate-400">Loading…</p>
        ) : domains && domains.length > 0 ? (
          <ul className="divide-y divide-slate-100 dark:divide-slate-700">
            {domains.map((d) => (
              <li key={d.id} className="flex items-center gap-3 py-2.5 first:pt-0 last:pb-0">
                <div className="w-7 h-7 rounded-md bg-accent/15 dark:bg-accent/10 flex items-center justify-center shrink-0">
                  <UserIcon size={13} className="text-accent-fg dark:text-accent-fg" />
                </div>
                <span className="text-sm text-slate-800 dark:text-slate-200 font-medium">{d.name}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-500 dark:text-slate-400">
            You are not a member of any domain yet.
          </p>
        )}
      </div>
    </div>
  )
}

function ShowablePasswordInput({
  label,
  value,
  onChange,
  error,
  autoComplete,
}: {
  label: string
  value: string
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void
  error?: string
  autoComplete?: string
}) {
  const [show, setShow] = useState(false)
  return (
    <div className="relative">
      <Input
        label={label}
        type={show ? 'text' : 'password'}
        value={value}
        onChange={onChange}
        error={error}
        autoComplete={autoComplete}
      />
      <button
        type="button"
        onClick={() => setShow((v) => !v)}
        className="absolute right-3 top-8 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
        tabIndex={-1}
      >
        {show ? <EyeOff size={15} /> : <Eye size={15} />}
      </button>
    </div>
  )
}

function PasswordSection({ userId }: { userId: string }) {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [success, setSuccess] = useState(false)

  const mutation = useChangePassword(userId)

  const policyError = next ? validatePassword(next) : null
  const confirmError = confirm && next !== confirm ? 'Passwords do not match' : null
  const canSubmit = current && next && confirm && !policyError && !confirmError

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSuccess(false)
    try {
      await mutation.mutateAsync({ current_password: current, new_password: next })
      setSuccess(true)
      setCurrent('')
      setNext('')
      setConfirm('')
    } catch {
      // error shown via mutation.error
    }
  }

  return (
    <div className="card p-6 space-y-5">
      <div className="flex items-center gap-2">
        <Lock size={16} className="text-slate-500 dark:text-slate-400" />
        <h2 className="font-semibold text-slate-900 dark:text-white">Change Password</h2>
      </div>

      {success && (
        <div className="flex items-center gap-2 text-sm text-green-700 dark:text-green-400 bg-green-50 dark:bg-green-900/20 rounded-lg px-3 py-2">
          <CheckCircle2 size={15} />
          Password updated successfully.
        </div>
      )}

      {mutation.error && (
        <div className="flex items-center gap-2 text-sm text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded-lg px-3 py-2">
          <XCircle size={15} />
          {(mutation.error as Error).message}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <ShowablePasswordInput
          label="Current password"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          autoComplete="current-password"
        />

        <ShowablePasswordInput
          label="New password"
          value={next}
          onChange={(e) => setNext(e.target.value)}
          error={policyError ?? undefined}
          autoComplete="new-password"
        />

        <Input
          label="Confirm new password"
          type="password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          error={confirmError ?? undefined}
          autoComplete="new-password"
        />

        <p className="text-xs text-slate-500 dark:text-slate-400">
          Min 8 chars · uppercase · lowercase · number · special char (!@#$%^&*)
        </p>

        <Button type="submit" loading={mutation.isPending} disabled={!canSubmit}>
          Update password
        </Button>
      </form>
    </div>
  )
}

// ── Admin sections ───────────────────────────────────────────────────────────

function OwnerSearch({
  value,
  selectedId,
  users,
  onChange,
  onSelect,
}: {
  value: string
  selectedId: string
  users: User[]
  onChange: (v: string) => void
  onSelect: (id: string, username: string) => void
}) {
  const filtered = users.filter((u) =>
    u.username.toLowerCase().includes(value.toLowerCase()),
  )
  const showList = value && !selectedId && filtered.length > 0
  const showEmpty = value && !selectedId && filtered.length === 0

  return (
    <div>
      <Input
        label="Owner"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Search by username…"
      />
      {showList && (
        <div className="mt-1 border border-slate-200 dark:border-slate-700 rounded-lg overflow-hidden max-h-32 overflow-y-auto">
          {filtered.map((u) => (
            <button
              key={u.id}
              type="button"
              onClick={() => onSelect(u.id, u.username)}
              className="w-full text-left px-3 py-2 text-sm hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300"
            >
              {u.username}
            </button>
          ))}
        </div>
      )}
      {showEmpty && (
        <p className="text-xs text-slate-400 mt-1">No users found.</p>
      )}
    </div>
  )
}

function useDomainForm(domain: DomainWithMembers | null, onClose: () => void) {
  const { data: users = [] } = useUsers()
  const createDomain = useCreateDomain()
  const updateDomain = useUpdateDomain()

  const [name, setName] = useState(domain?.name ?? '')
  const [description, setDescription] = useState(domain?.description ?? '')
  const [ownerId, setOwnerId] = useState(domain?.owner_id ?? '')
  const [ownerSearch, setOwnerSearch] = useState(domain?.owner_username ?? '')

  const isEdit = domain !== null
  const mutation = isEdit ? updateDomain : createDomain

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const data: DomainInput = { name, description, owner_id: ownerId }
    try {
      if (isEdit) {
        await updateDomain.mutateAsync({ id: domain.id, ...data })
      } else {
        await createDomain.mutateAsync(data)
      }
      onClose()
    } catch {
      // error surfaced via mutation.error
    }
  }

  return { users, name, setName, description, setDescription, ownerId, setOwnerId, ownerSearch, setOwnerSearch, mutation, isEdit, handleSubmit }
}

function DomainFormModal({
  domain,
  open,
  onClose,
}: {
  domain: DomainWithMembers | null
  open: boolean
  onClose: () => void
}) {
  const {
    users, name, setName, description, setDescription,
    ownerId, setOwnerId, ownerSearch, setOwnerSearch,
    mutation, isEdit, handleSubmit,
  } = useDomainForm(domain, onClose)

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={isEdit ? 'Edit Domain' : 'New Domain'}
      size="sm"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <Textarea
          label="Description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={3}
          required
        />
        <OwnerSearch
          value={ownerSearch}
          selectedId={ownerId}
          users={users}
          onChange={(v) => { setOwnerSearch(v); setOwnerId('') }}
          onSelect={(id, username) => { setOwnerId(id); setOwnerSearch(username) }}
        />

        {mutation.error && (
          <p className="text-xs text-red-600 dark:text-red-400">
            {mutation.error.message}
          </p>
        )}

        <div className="flex gap-2 pt-1">
          <Button variant="secondary" onClick={onClose} className="flex-1">
            Cancel
          </Button>
          <Button
            type="submit"
            loading={mutation.isPending}
            disabled={!name || !description || !ownerId}
            className="flex-1"
          >
            {isEdit ? 'Save' : 'Create'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}

function DeleteDomainModal({
  domain,
  open,
  onClose,
}: {
  domain: DomainWithMembers | null
  open: boolean
  onClose: () => void
}) {
  const deleteDomain = useDeleteDomain()

  function handleClose() {
    deleteDomain.reset()
    onClose()
  }

  async function handleDelete() {
    if (!domain) return
    try {
      await deleteDomain.mutateAsync(domain.id)
      handleClose()
    } catch {
      // error surfaced via deleteDomain.error
    }
  }

  return (
    <Modal open={open} onClose={handleClose} title="Delete Domain" size="sm">
      <div className="space-y-4">
        <p className="text-sm text-slate-700 dark:text-slate-300">
          Delete <strong>{domain?.name}</strong>? This will not delete associated data contracts.
          All members will lose domain access.
        </p>
        {deleteDomain.error && (
          <p className="text-xs text-red-600 dark:text-red-400">
            {deleteDomain.error.message}
          </p>
        )}
        <div className="flex gap-2">
          <Button variant="secondary" onClick={handleClose} className="flex-1">
            Cancel
          </Button>
          <Button
            variant="danger"
            loading={deleteDomain.isPending}
            onClick={handleDelete}
            className="flex-1"
          >
            Delete
          </Button>
        </div>
      </div>
    </Modal>
  )
}

function AdminDomainsSection() {
  const { data: domains = [], isLoading } = useAllDomains()
  const [formOpen, setFormOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<DomainWithMembers | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<DomainWithMembers | null>(null)

  const columns: Column<DomainWithMembers>[] = [
    {
      key: 'name',
      header: 'Name',
      render: (d: DomainWithMembers) => (
        <span className="font-medium text-slate-900 dark:text-white">{d.name}</span>
      ),
    },
    {
      key: 'owner',
      header: 'Owner',
      render: (d: DomainWithMembers) => (
        <span className="text-slate-500 dark:text-slate-400">{d.owner_username}</span>
      ),
    },
    {
      key: 'members',
      header: 'Members',
      render: (d: DomainWithMembers) => (
        <span className="text-slate-500 dark:text-slate-400">{d.members.length}</span>
      ),
    },
    {
      key: 'contracts',
      header: 'Contracts',
      render: (d: DomainWithMembers) => (
        <span className="text-slate-500 dark:text-slate-400">{d.contract_count}</span>
      ),
    },
    {
      key: 'actions',
      header: '',
      render: (d: DomainWithMembers) => (
        <div className="flex gap-2 justify-end">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => { setEditTarget(d); setFormOpen(true) }}
            className="flex items-center gap-1"
          >
            <Pencil size={12} /> Edit
          </Button>
          <Button
            variant="danger"
            size="sm"
            onClick={() => setDeleteTarget(d)}
            className="flex items-center gap-1"
          >
            <Trash2 size={12} /> Delete
          </Button>
        </div>
      ),
    },
  ]

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-semibold text-slate-900 dark:text-white">Manage Domains</h2>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Create, edit, and delete platform domains
          </p>
        </div>
        <Button
          size="sm"
          onClick={() => { setEditTarget(null); setFormOpen(true) }}
          className="flex items-center gap-1.5"
        >
          <Plus size={13} /> New Domain
        </Button>
      </div>

      {isLoading ? (
        <p className="text-sm text-slate-500 dark:text-slate-400">Loading…</p>
      ) : (
        <Table
          columns={columns}
          data={domains}
          keyExtractor={(d) => d.id}
          emptyMessage="No domains yet."
        />
      )}

      <DomainFormModal
        key={editTarget?.id ?? 'new'}
        domain={editTarget}
        open={formOpen}
        onClose={() => { setFormOpen(false); setEditTarget(null) }}
      />
      <DeleteDomainModal
        domain={deleteTarget}
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
      />
    </div>
  )
}

function AdminUsersSection() {
  return (
    <div className="card p-6 text-center">
      <ShieldAlert size={32} className="mx-auto text-slate-300 dark:text-slate-600 mb-3" />
      <p className="text-sm font-medium text-slate-700 dark:text-slate-300">
        User management coming soon.
      </p>
      <p className="text-xs text-slate-400 mt-1">
        Additional admin functions will be added here.
      </p>
    </div>
  )
}

// ── Page ────────────────────────────────────────────────────────────────────

export default function Profile() {
  const { user } = useAuth()
  const [section, setSection] = useState<Section>('role')
  const isAdmin = user?.role === 'PLATFORM_ADMIN'

  if (!user) return null

  const role = ROLE_META[user.role] ?? {
    label: user.role,
    color: 'bg-slate-100 text-slate-700 dark:bg-slate-700/50 dark:text-slate-300',
    description: '',
    permissions: [],
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h1 className="text-xl font-semibold text-slate-900 dark:text-white">My Profile</h1>

      {/* Identity card — always visible */}
      <div className="card p-6 flex items-center gap-5">
        <Avatar name={user.username} size={56} />
        <div className="min-w-0">
          <p className="text-lg font-semibold text-slate-900 dark:text-white truncate">
            {user.username}
          </p>
          <p className="text-sm text-slate-500 dark:text-slate-400 truncate">{user.email}</p>
          <span className={`mt-1.5 inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold ${role.color}`}>
            {role.label}
          </span>
        </div>
      </div>

      {/* Two-column: sidebar nav + content */}
      <div className="flex flex-col md:flex-row gap-4">

        {/* Sidebar nav */}
        <nav className="md:w-48 shrink-0">
          {/* Mobile: horizontal scrollable tab row */}
          <div className="flex md:hidden gap-1 card p-1 overflow-x-auto">
            {ACCOUNT_NAV.map((item) => (
              <button
                key={item.id}
                onClick={() => setSection(item.id)}
                className={`shrink-0 flex flex-col items-center gap-1 py-2 px-2 rounded-md text-xs font-medium transition-colors ${
                  section === item.id
                    ? 'bg-accent text-accent-ink'
                    : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700'
                }`}
              >
                {item.icon}
                <span className="leading-none">{item.label.split(' ')[0]}</span>
              </button>
            ))}
            {isAdmin &&
              ADMIN_NAV.map((item) => (
                <button
                  key={item.id}
                  onClick={() => setSection(item.id)}
                  className={`shrink-0 flex flex-col items-center gap-1 py-2 px-2 rounded-md text-xs font-medium transition-colors ${
                    section === item.id
                      ? 'bg-red-600 text-white'
                      : 'text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20'
                  }`}
                >
                  {item.icon}
                  <span className="leading-none">🛡 {item.label}</span>
                </button>
              ))}
          </div>

          {/* Desktop: vertical list with sections */}
          <div className="hidden md:flex flex-col card p-2 gap-0.5">
            <p className="px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
              Account
            </p>
            {ACCOUNT_NAV.map((item) => (
              <button
                key={item.id}
                onClick={() => setSection(item.id)}
                className={`flex items-center gap-2.5 px-3 py-2.5 rounded-md text-sm font-medium transition-colors w-full text-left ${
                  section === item.id
                    ? 'bg-accent text-accent-ink'
                    : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700'
                }`}
              >
                {item.icon}
                {item.label}
              </button>
            ))}
            {isAdmin && (
              <>
                <p className="px-3 py-1 mt-2 text-[10px] font-semibold uppercase tracking-wider text-red-500">
                  🛡 Admin
                </p>
                {ADMIN_NAV.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => setSection(item.id)}
                    className={`flex items-center gap-2.5 px-3 py-2.5 rounded-md text-sm font-medium transition-colors w-full text-left ${
                      section === item.id
                        ? 'bg-red-600 text-white'
                        : 'text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20'
                    }`}
                  >
                    {item.icon}
                    {item.label}
                  </button>
                ))}
              </>
            )}
          </div>
        </nav>

        {/* Content panel */}
        <div className="flex-1 min-w-0">
          {section === 'role' && <RoleSection userId={user.id} />}
          {section === 'password' && <PasswordSection userId={user.id} />}
          {section === 'admin-domains' && isAdmin && <AdminDomainsSection />}
          {section === 'admin-users' && isAdmin && <AdminUsersSection />}
        </div>
      </div>
    </div>
  )
}
