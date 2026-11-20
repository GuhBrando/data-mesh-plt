import { useState } from 'react'
import {
  useUsers,
  useCreateUser,
  useUpdateUser,
  useDeleteUser,
} from '../../hooks/useUsers'
import PageHeader from '../../components/PageHeader'
import Table from '../../components/ui/Table'
import Button from '../../components/ui/Button'
import Modal from '../../components/ui/Modal'
import Badge from '../../components/ui/Badge'
import Spinner from '../../components/ui/Spinner'
import UserForm from './UserForm'
import type { User, UserFormData } from '../../types'
import { Avatar } from '../../components/ui/Glyphs'
import { EditIcon, PlusIcon, TrashIcon, UsersIcon } from '../../components/icons'

export default function UsersList() {
  const [createOpen, setCreateOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<User | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<User | null>(null)

  const { data: users = [], isLoading, error } = useUsers()
  const createMutation = useCreateUser()
  const updateMutation = useUpdateUser()
  const deleteMutation = useDeleteUser()

  const handleCreate = async (values: UserFormData) => {
    await createMutation.mutateAsync(values)
    setCreateOpen(false)
  }

  const handleUpdate = async (values: UserFormData) => {
    if (!editTarget) return
    await updateMutation.mutateAsync({ id: editTarget.id, ...values })
    setEditTarget(null)
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    await deleteMutation.mutateAsync(deleteTarget.id)
    setDeleteTarget(null)
  }

  const columns = [
    {
      key: 'name',
      header: 'Name',
      render: (row: User) => (
        <div className="flex items-center gap-3">
          <Avatar name={row.username} size={28} />
          <span className="font-medium text-tx">{row.username}</span>
        </div>
      ),
    },
    {
      key: 'role',
      header: 'Role',
      render: (row: User) => (
        <Badge variant={row.role === 'admin' ? 'blue' : 'gray'} className="capitalize">
          {row.role}
        </Badge>
      ),
      className: 'w-28',
    },
    {
      key: 'email',
      header: 'Email',
      render: (row: User) => (
        <a
          href={`mailto:${row.email}`}
          className="text-[13px] text-tx2 hover:text-accent-fg hover:underline"
          onClick={(e) => e.stopPropagation()}
        >
          {row.email}
        </a>
      ),
    },
    {
      key: 'id',
      header: 'ID',
      render: (row: User) => (
        <span className="font-mono text-[11.5px] text-tx3" title={row.id}>{row.id.slice(0, 8)}…</span>
      ),
    },
    {
      key: 'actions',
      header: '',
      render: (row: User) => (
        <div className="flex items-center gap-2">
          <button
            onClick={(e) => {
              e.stopPropagation()
              setEditTarget(row)
            }}
            className="grid h-7 w-7 place-items-center rounded-md text-tx3 transition-colors hover:bg-hover hover:text-tx"
            title="Edit"
          >
            <EditIcon size={14} />
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation()
              setDeleteTarget(row)
            }}
            className="btn-danger"
            title="Delete"
          >
            <TrashIcon size={13} />
            Delete
          </button>
        </div>
      ),
      className: 'w-32',
    },
  ]

  return (
    <div>
      <div className="animate-enter">
      <PageHeader
        title="Users"
        subtitle={`${users.length} user${users.length !== 1 ? 's' : ''}`}
        actions={
          <Button onClick={() => setCreateOpen(true)}>
            <PlusIcon size={15} />
            New User
          </Button>
        }
      />
      </div>

      {isLoading ? (
        <div className="flex justify-center py-20">
          <Spinner size="lg" />
        </div>
      ) : error ? (
        <div className="text-center py-16">
          <p className="text-bad">{error.message}</p>
        </div>
      ) : users.length === 0 ? (
        <div className="flex animate-enter flex-col items-center rounded-[10px] border border-dashed border-line2 px-6 py-16 text-center">
          <span className="mb-4 grid h-11 w-11 place-items-center rounded-xl border border-line bg-raised text-tx3">
            <UsersIcon size={20} />
          </span>
          <p className="mb-1 font-medium text-tx">No users yet</p>
          <p className="mb-5 text-[13px] text-tx3">Add your first user to get started.</p>
          <Button onClick={() => setCreateOpen(true)}>
            <PlusIcon size={15} />
            New User
          </Button>
        </div>
      ) : (
        <div className="animate-enter [animation-delay:0.06s]">
        <Table
          columns={columns}
          data={users}
          keyExtractor={(u) => u.id}
          emptyMessage="No users found."
          mobileCardConfig={{ titleKey: 'name', badgeKey: 'role' }}
        />
        </div>
      )}

      {/* Create Modal */}
      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="New User"
        size="sm"
      >
        <UserForm
          onSubmit={handleCreate}
          onCancel={() => setCreateOpen(false)}
          isSubmitting={createMutation.isPending}
          apiError={createMutation.isError ? createMutation.error.message : undefined}
        />
      </Modal>

      {/* Edit Modal */}
      <Modal
        open={!!editTarget}
        onClose={() => setEditTarget(null)}
        title="Edit User"
        size="sm"
      >
        <UserForm
          defaultValues={editTarget ?? undefined}
          onSubmit={handleUpdate}
          onCancel={() => setEditTarget(null)}
          isSubmitting={updateMutation.isPending}
          apiError={updateMutation.isError ? updateMutation.error.message : undefined}
        />
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title="Delete User"
        size="sm"
      >
        <p className="text-sm text-gray-600 dark:text-slate-300 mb-2">
          Are you sure you want to delete{' '}
          <span className="font-medium">{deleteTarget?.username}</span>?
        </p>
        <p className="text-xs text-gray-400 dark:text-slate-500 mb-6">This action cannot be undone.</p>
        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={() => setDeleteTarget(null)}>
            Cancel
          </Button>
          <Button
            variant="danger"
            loading={deleteMutation.isPending}
            onClick={handleDelete}
          >
            Delete
          </Button>
        </div>
        {deleteMutation.isError && (
          <p className="mt-3 text-sm text-red-500">
            {deleteMutation.error.message}
          </p>
        )}
      </Modal>
    </div>
  )
}
