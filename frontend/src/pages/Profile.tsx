import { useState } from 'react'
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
import { CheckCircleIcon, ChevronRightIcon, DomainIcon, EditIcon, EyeIcon, EyeOffIcon, LockIcon, PlusIcon, ShieldAlertIcon, ShieldIcon, TrashIcon, UserIcon, XCircleIcon } from '../components/icons'

const ROLE_META: Record<
  string,
  { label: string; color: string; description: string; permissions: string[] }
> = {
  PLATFORM_ADMIN: {
    label: 'Platform Admin',
    color: 'bg-bad/15 text-bad',
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
      'Approve, deprecate, retire and delete contracts in your domain',
      "View published contracts and your domain's drafts",
    ],
  },
  DATA_STEWARD: {
    label: 'Data Steward',
    color: 'bg-accent/15 text-accent-fg dark:bg-accent/10 dark:text-accent-fg',
    description: 'Creates and manages data contracts in your domain.',
    permissions: [
      'Create and edit data contracts within your domain',
      'Submit drafts for review and invite reviewers',
      "View published contracts and your domain's drafts",
    ],
  },
  DATA_CONSUMER: {
    label: 'Data Consumer',
    color: 'bg-raised text-tx2',
    description: 'Reads every published contract; drafts when invited as a stakeholder.',
    permissions: [
      'View every published data contract',
      'View drafts you are invited to review',
      'View your own profile and domain memberships',
    ],
  },
}

type Section = 'role' | 'password' | 'admin-domains' | 'admin-users'

const ACCOUNT_NAV: { id: Section; label: string; icon: React.ReactNode }[] = [
  { id: 'role', label: 'My Role', icon: <ShieldIcon size={16} /> },
  { id: 'password', label: 'Change Password', icon: <LockIcon size={16} /> },
]

const ADMIN_NAV: { id: Section; label: string; icon: React.ReactNode }[] = [
  { id: 'admin-domains', label: 'Domains', icon: <DomainIcon size={16} /> },
  { id: 'admin-users', label: 'Users', icon: <ShieldAlertIcon size={16} /> },
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
    color: 'bg-raised text-tx2',
    description: '',
    permissions: [],
  }

  return (
    <div className="space-y-6">
      <div className="card p-6 space-y-4">
        <div className="flex items-center gap-2">
          <ShieldIcon size={16} className="text-tx3" />
          <h2 className="font-semibold text-tx">Permissions</h2>
        </div>
        {role.description && (
          <p className="text-sm text-tx2">{role.description}</p>
        )}
        <ul className="space-y-2">
          {role.permissions.map((p) => (
            <li key={p} className="flex items-start gap-2 text-sm text-tx2">
              <ChevronRightIcon size={14} className="mt-0.5 shrink-0 text-accent-fg dark:text-accent-fg" />
              {p}
            </li>
          ))}
        </ul>
      </div>

      <div className="card p-6 space-y-4">
        <div className="flex items-center gap-2">
          <DomainIcon size={16} className="text-tx3" />
          <h2 className="font-semibold text-tx">Domain Memberships</h2>
        </div>
        {isLoading ? (
          <p className="text-sm text-tx3">Loading…</p>
        ) : domains && domains.length > 0 ? (
          <ul className="divide-y divide-line">
            {domains.map((d) => (
              <li key={d.id} className="flex items-center gap-3 py-2.5 first:pt-0 last:pb-0">
                <div className="w-7 h-7 rounded-md bg-accent/15 dark:bg-accent/10 flex items-center justify-center shrink-0">
                  <UserIcon size={13} className="text-accent-fg dark:text-accent-fg" />
                </div>
                <span className="text-sm text-tx font-medium">{d.name}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-tx3">
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
        className="absolute right-3 top-8 text-tx3 hover:text-tx"
        tabIndex={-1}
      >
        {show ? <EyeOffIcon size={15} /> : <EyeIcon size={15} />}
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
        <LockIcon size={16} className="text-tx3" />
        <h2 className="font-semibold text-tx">Change Password</h2>
      </div>

      {success && (
        <div className="flex items-center gap-2 text-sm text-ok bg-ok/10 rounded-lg px-3 py-2">
          <CheckCircleIcon size={15} />
          Password updated successfully.
        </div>
      )}

      {mutation.error && (
        <div className="flex items-center gap-2 text-sm text-bad bg-bad/10 rounded-lg px-3 py-2">
          <XCircleIcon size={15} />
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

        <p className="text-xs text-tx3">
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
        <div className="mt-1 border border-line rounded-lg overflow-hidden max-h-32 overflow-y-auto">
          {filtered.map((u) => (
            <button
              key={u.id}
              type="button"
              onClick={() => onSelect(u.id, u.username)}
              className="w-full text-left px-3 py-2 text-sm hover:bg-hover text-tx2"
            >
              {u.username}
            </button>
          ))}
        </div>
      )}
      {showEmpty && (
        <p className="text-xs text-tx3 mt-1">No users found.</p>
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
          <p className="text-xs text-bad">
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
        <p className="text-sm text-tx2">
          Delete <strong>{domain?.name}</strong>? This will not delete associated data contracts.
          All members will lose domain access.
        </p>
        {deleteDomain.error && (
          <p className="text-xs text-bad">
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
        <span className="font-medium text-tx">{d.name}</span>
      ),
    },
    {
      key: 'owner',
      header: 'Owner',
      render: (d: DomainWithMembers) => (
        <span className="text-tx3">{d.owner_username}</span>
      ),
    },
    {
      key: 'members',
      header: 'Members',
      render: (d: DomainWithMembers) => (
        <span className="text-tx3">{d.members.length}</span>
      ),
    },
    {
      key: 'contracts',
      header: 'Contracts',
      render: (d: DomainWithMembers) => (
        <span className="text-tx3">{d.contract_count}</span>
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
            <EditIcon size={12} /> Edit
          </Button>
          <Button
            variant="danger"
            size="sm"
            onClick={() => setDeleteTarget(d)}
            className="flex items-center gap-1"
          >
            <TrashIcon size={12} /> Delete
          </Button>
        </div>
      ),
    },
  ]

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-semibold text-tx">Manage Domains</h2>
          <p className="text-xs text-tx3 mt-0.5">
            Create, edit, and delete platform domains
          </p>
        </div>
        <Button
          size="sm"
          onClick={() => { setEditTarget(null); setFormOpen(true) }}
          className="flex items-center gap-1.5"
        >
          <PlusIcon size={13} /> New Domain
        </Button>
      </div>

      {isLoading ? (
        <p className="text-sm text-tx3">Loading…</p>
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
      <ShieldAlertIcon size={32} className="mx-auto text-tx3 mb-3" />
      <p className="text-sm font-medium text-tx2">
        User management coming soon.
      </p>
      <p className="text-xs text-tx3 mt-1">
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
    color: 'bg-raised text-tx2',
    description: '',
    permissions: [],
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h1 className="text-[22px] font-semibold leading-tight tracking-[-0.02em] text-tx">My Profile</h1>

      {/* Identity card — always visible */}
      <div className="card p-6 flex items-center gap-5">
        <Avatar name={user.username} size={56} />
        <div className="min-w-0">
          <p className="text-lg font-semibold text-tx truncate">
            {user.username}
          </p>
          <p className="text-sm text-tx3 truncate">{user.email}</p>
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
                    ? 'bg-raised text-tx shadow-[inset_0_0_0_1px_rgb(var(--line))] [&>svg]:text-accent-fg'
                    : 'text-tx2 hover:bg-hover hover:text-tx [&>svg]:text-tx3'
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
                      ? 'bg-raised text-tx shadow-[inset_0_0_0_1px_rgb(var(--line))] [&>svg]:text-accent-fg'
                      : 'text-tx2 hover:bg-hover hover:text-tx [&>svg]:text-tx3'
                  }`}
                >
                  {item.icon}
                  <span className="leading-none">{item.label}</span>
                </button>
              ))}
          </div>

          {/* Desktop: vertical list with sections */}
          <div className="hidden md:flex flex-col card p-2 gap-0.5">
            <p className="px-2.5 pb-1.5 pt-1 text-[11px] font-medium text-tx3">Account</p>
            {ACCOUNT_NAV.map((item) => (
              <button
                key={item.id}
                onClick={() => setSection(item.id)}
                className={`flex h-[30px] w-full items-center gap-2.5 rounded-[7px] px-2.5 text-left text-[13px] transition-colors ${
                  section === item.id
                    ? 'bg-raised text-tx shadow-[inset_0_0_0_1px_rgb(var(--line))] [&>svg]:text-accent-fg'
                    : 'text-tx2 hover:bg-hover hover:text-tx [&>svg]:text-tx3'
                }`}
              >
                {item.icon}
                {item.label}
              </button>
            ))}
            {isAdmin && (
              <>
                <p className="px-2.5 pb-1.5 pt-4 text-[11px] font-medium text-tx3">Admin</p>
                {ADMIN_NAV.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => setSection(item.id)}
                    className={`flex h-[30px] w-full items-center gap-2.5 rounded-[7px] px-2.5 text-left text-[13px] transition-colors ${
                      section === item.id
                        ? 'bg-raised text-tx shadow-[inset_0_0_0_1px_rgb(var(--line))] [&>svg]:text-accent-fg'
                        : 'text-tx2 hover:bg-hover hover:text-tx [&>svg]:text-tx3'
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
