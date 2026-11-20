import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Edit2, Trash2, Calendar, Clock, FileText, Github } from 'lucide-react'
import {
  useDataProduct,
  useUpdateDataProduct,
  useDeleteDataProduct,
} from '../../hooks/useDataProducts'
import PageHeader from '../../components/PageHeader'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import Badge from '../../components/ui/Badge'
import Modal from '../../components/ui/Modal'
import Spinner from '../../components/ui/Spinner'
import DataProductForm from './DataProductForm'
import type { DataProductFormData } from '../../types'

function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export default function DataProductDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [editOpen, setEditOpen] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState(false)

  const { data: product, isLoading, error } = useDataProduct(id ?? '')
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
      <div className="flex items-center justify-center h-64">
        <Spinner size="lg" />
      </div>
    )
  }

  if (error || !product) {
    return (
      <div className="text-center py-16">
        <p className="text-red-500 font-medium">
          {error?.message ?? 'Product not found'}
        </p>
        <button
          onClick={() => navigate('/data-products')}
          className="mt-3 text-sm text-accent-fg dark:text-accent-fg hover:underline"
        >
          Back to list
        </button>
      </div>
    )
  }

  return (
    <div>
      <PageHeader
        title={product.name}
        subtitle={product.id}
        backTo="/data-products"
        actions={
          <>
            {product.repo_url && (
              <a
                href={product.repo_url}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="View GitHub repository"
                className="btn-secondary text-xs px-3 py-1.5"
              >
                <Github size={14} />
                GitHub
              </a>
            )}
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setEditOpen(true)}
            >
              <Edit2 size={14} />
              Edit
            </Button>
            <Button
              variant="danger"
              size="sm"
              onClick={() => setDeleteConfirm(true)}
            >
              <Trash2 size={14} />
              Delete
            </Button>
          </>
        }
      />

      {/* Metadata badges */}
      <div className="flex flex-wrap gap-3 mb-6">
        <Badge variant="gray">
          <Calendar size={11} className="mr-1" />
          Created {formatDateTime(product.created_at)}
        </Badge>
        <Badge variant="gray">
          <Clock size={11} className="mr-1" />
          Updated {formatDateTime(product.updated_at)}
        </Badge>
      </div>

      {/* Details card */}
      <Card className="mb-4">
        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-4">
          <div>
            <dt className="text-xs font-semibold text-gray-400 dark:text-slate-500 uppercase tracking-wider mb-1">
              Name
            </dt>
            <dd className="text-sm font-medium text-gray-900 dark:text-slate-100">{product.name}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold text-gray-400 dark:text-slate-500 uppercase tracking-wider mb-1">
              ID
            </dt>
            <dd className="text-xs font-mono text-gray-600 dark:text-slate-400 break-all">{product.id}</dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-xs font-semibold text-gray-400 dark:text-slate-500 uppercase tracking-wider mb-1">
              Description
            </dt>
            <dd className="text-sm text-gray-700 dark:text-slate-300">{product.description}</dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-xs font-semibold text-gray-400 dark:text-slate-500 uppercase tracking-wider mb-1">
              Data Contract ID
            </dt>
            <dd className="flex items-center gap-2">
              <FileText size={13} className="text-accent-fg shrink-0" />
              <button
                className="text-xs font-mono text-accent-fg dark:text-accent-fg hover:underline break-all"
                onClick={() =>
                  navigate(`/data-contracts/${product.data_contracts_id}`)
                }
              >
                {product.data_contracts_id}
              </button>
            </dd>
          </div>
        </dl>
      </Card>

      {/* Edit Modal */}
      <Modal
        open={editOpen}
        onClose={() => setEditOpen(false)}
        title="Edit Data Product"
      >
        <DataProductForm
          defaultValues={product}
          onSubmit={handleUpdate}
          onCancel={() => setEditOpen(false)}
          isSubmitting={updateMutation.isPending}
        />
        {updateMutation.isError && (
          <p className="mt-3 text-sm text-red-500">
            {updateMutation.error.message}
          </p>
        )}
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        open={deleteConfirm}
        onClose={() => setDeleteConfirm(false)}
        title="Delete Data Product"
        size="sm"
      >
        <p className="text-sm text-gray-600 dark:text-slate-300 mb-2">
          Are you sure you want to delete{' '}
          <span className="font-medium">{product.name}</span>?
        </p>
        <p className="text-xs text-gray-400 dark:text-slate-500 mb-6">This action cannot be undone.</p>
        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={() => setDeleteConfirm(false)}>
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
