import { Link } from 'react-router-dom'
import Spinner from '../../components/ui/Spinner'
import { useContractPorts } from '../../hooks/useDataContracts'
import type { DataContract, PortUsage } from '../../types'

function UsageList({ label, rows, empty, current }: { label: string; rows: PortUsage[]; empty: string; current: string }) {
  return (
    <div>
      <h3 className="mb-1 text-[11.5px] font-medium text-tx3">{label}</h3>
      {rows.length === 0 ? (
        <p className="text-[12.5px] text-tx3">{empty}</p>
      ) : (
        <ul aria-label={label} className="space-y-1.5">
          {rows.map((u) => (
            <li key={`${u.product_id}-${u.port_name}-${u.version}`} className="flex flex-wrap items-center gap-x-2 text-[12.5px]">
              <Link to={`/data-products/${u.product_id}`} className="font-medium text-tx hover:text-accent-fg hover:underline">
                {u.product_name}
              </Link>
              <span className="font-mono text-[11.5px] text-tx2">
                {u.port_name} · v{u.version}
              </span>
              {u.version !== current && (
                <span className="inline-flex items-center gap-1 text-xs text-warn">
                  <span aria-hidden="true">⚠</span>
                  <span>pinned to an older version</span>
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/** Who produces and who consumes a contract, from the products' ports. */
export default function ContractUsage({ contract }: { contract: DataContract }) {
  const { data = [], isLoading, isError } = useContractPorts(contract.id)
  if (isLoading) {
    return (
      <div className="flex justify-center py-6">
        <Spinner size="sm" />
      </div>
    )
  }
  if (isError) return <p className="px-4 py-6 text-center text-[13px] text-bad">Could not load the usage.</p>
  if (data.length === 0) {
    return <p className="px-4 py-6 text-center text-[13px] text-tx3">No data product uses this contract yet.</p>
  }
  return (
    <div className="space-y-3 px-4 py-3.5">
      <UsageList label="Produced by" rows={data.filter((u) => u.role === 'output')} empty="No producer yet" current={contract.version} />
      <UsageList label="Consumed by" rows={data.filter((u) => u.role === 'input')} empty="No consumers yet" current={contract.version} />
    </div>
  )
}
