import { useNavigate } from 'react-router-dom'
import { useCreateDataContract } from '../../hooks/useDataContracts'
import PageHeader from '../../components/PageHeader'
import Card from '../../components/ui/Card'
import DataContractForm from './DataContractForm'
import type { DataContractInput } from '../../types'

export default function NewDataContract() {
  const navigate = useNavigate()
  const createMutation = useCreateDataContract()

  const handleSubmit = async (input: DataContractInput) => {
    const created = await createMutation.mutateAsync(input)
    navigate(`/data-contracts/${created.id}`)
  }

  return (
    <div className="mx-auto max-w-[880px]">
      <div className="animate-enter">
        <PageHeader
          title="New Data Contract"
          subtitle="Define a new ODCS-compliant contract for your data product. Start by classifying its tier."
          backTo="/data-contracts"
        />
      </div>
      <Card className="animate-enter [animation-delay:0.06s]">
        <DataContractForm
          onSubmit={handleSubmit}
          onCancel={() => navigate('/data-contracts')}
          isSubmitting={createMutation.isPending}
          showWizard
        />
        {createMutation.isError && (
          <p className="mt-3 text-[13px] text-bad">{createMutation.error.message}</p>
        )}
      </Card>
    </div>
  )
}
