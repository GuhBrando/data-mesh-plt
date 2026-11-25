import { useEffect, useMemo } from 'react'
import { Controller, useForm, useWatch, type Resolver } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Input } from '../../components/ui/Input'
import Button from '../../components/ui/Button'
import { useAuth } from '../../contexts/AuthContext'
import { useAllDomains } from '../../hooks/useDomains'
import { useDataContracts } from '../../hooks/useDataContracts'
import { useDataProducts } from '../../hooks/useDataProducts'
import { useSelectableContracts } from '../../hooks/useSelectableContracts'
import { STATUS_LABELS } from '../../lib/contracts'
import { selectableDomains } from '../../lib/domains'
import { PRODUCT_STATUSES, producersByContract } from '../../lib/products'
import { InputPortsEditor, OutputPortsEditor, emptyOutput, type ContractSource } from './PortEditors'
import type { DataProduct, DataProductInput, InputPort, OutputPort } from '../../types'

// Mirrors only the rules a user breaks while typing; the API owns the rest.
// ODPS objects are loose: fields the form does not show go back unchanged.
const anyObject = z.looseObject({})
const portName = z.string().trim().min(1, 'Every port needs a name')
const inputPort = z.object({
  name: portName,
  contract_id: z.string().nullable(),
  version: z.string().nullable(),
  deprecated: z.boolean(),
  authoritative_definitions: z.array(anyObject),
  tags: z.array(z.string()),
  custom_properties: z.array(anyObject),
})
// Explicit fields: the id the API assigns is dropped on submit.
const managementPort = z.object({
  name: z.string().trim().min(1, 'Every management port needs a name'),
  content: z.string().trim().min(1, 'Every management port needs a content'),
  type: z.string(),
  url: z.string().nullish(),
  channel: z.string().nullish(),
  description: z.string().nullish(),
  deprecated: z.boolean(),
  tags: z.array(z.string()).optional(),
  custom_properties: z.array(anyObject).optional(),
  authoritative_definitions: z.array(anyObject).optional(),
})
const outputPort = inputPort.extend({
  type: z.string().nullable(),
  description: z.string().nullable(),
  input_contracts: z.array(z.object({ contract_id: z.string(), version: z.string() })),
  synonyms: z.array(anyObject),
  context: anyObject,
  sbom: z.array(anyObject),
})

function duplicate(ports: { name: string; version: string | null }[], kind: string): string | null {
  const seen = new Set<string>()
  for (const { name, version } of ports) {
    const key = JSON.stringify([name.trim(), version])
    if (seen.has(key)) return `Two ${kind} share the name ${name.trim()} and version ${version ?? '(none)'}`
    seen.add(key)
  }
  return null
}

const schema = z
  .object({
    name: z.string().min(3, 'Name must be at least 3 characters'),
    description: z.looseObject({
      purpose: z.string().min(10, 'Description must be at least 10 characters'),
      usage: z.string(),
      limitations: z.string(),
    }),
    domain_id: z.string().min(1, 'Choose a domain'),
    status: z.enum(['proposed', 'draft', 'active', 'deprecated', 'retired']),
    version: z.string().nullable(),
    type: z.string().nullable(),
    tenant: z.string().nullable(),
    tags: z.array(z.string()),
    synonyms: z.array(anyObject),
    context: anyObject,
    team: anyObject,
    support: z.array(anyObject),
    custom_properties: z.array(anyObject),
    authoritative_definitions: z.array(anyObject),
    input_ports: z.array(inputPort),
    output_ports: z.array(outputPort).min(1, 'A data product needs at least one output'),
    management_ports: z.array(managementPort),
  })
  .superRefine((values, ctx) => {
    for (const [key, kind] of [
      ['input_ports', 'inputs'],
      ['output_ports', 'outputs'],
    ] as const) {
      const message = duplicate(values[key], kind)
      if (message) ctx.addIssue({ code: 'custom', path: [key], message })
    }
  })

/** Rows of one name together, the newest version first. */
function grouped<T extends InputPort | OutputPort>(ports: T[]): T[] {
  return [...ports].sort(
    (a, b) => a.name.localeCompare(b.name) || (b.version ?? '').localeCompare(a.version ?? '', undefined, { numeric: true }),
  )
}

const EMPTY: DataProductInput = {
  name: '',
  description: { purpose: '', usage: '', limitations: '' },
  domain_id: '',
  status: 'draft',
  version: null,
  type: null,
  tenant: null,
  tags: [],
  synonyms: [],
  context: {},
  team: {},
  support: [],
  custom_properties: [],
  authoritative_definitions: [],
  input_ports: [],
  output_ports: [],
  management_ports: [],
}

/** The form's values. Ports keep their contract summary for display; the
 *  schema drops it, with every other computed field, on submit. */
function valuesOf(p?: DataProduct): DataProductInput {
  if (!p) return { ...EMPTY, output_ports: [emptyOutput()] }
  const editable = Object.fromEntries(Object.keys(EMPTY).map((key) => [key, p[key as keyof DataProduct]]))
  return {
    ...(editable as unknown as DataProductInput),
    input_ports: grouped(p.input_ports),
    output_ports: grouped(p.output_ports),
  }
}

/** The message for a port list: the list's own rule, or its first broken row. */
function listError(error: unknown): string | undefined {
  if (!error || typeof error !== 'object') return undefined
  const { message, root } = error as { message?: string; root?: { message?: string } }
  if (message) return message
  if (root?.message) return root.message
  for (const row of Object.values(error)) {
    const name = (row as { name?: { message?: string } } | undefined)?.name
    if (name?.message) return name.message
  }
  return undefined
}

function sourceOf(contracts: ContractSource['contracts'] | undefined, loading: boolean, error: Error | null): ContractSource {
  return { contracts: contracts ?? [], loading, error: error?.message ?? null }
}

interface DataProductFormProps {
  defaultValues?: DataProduct
  onSubmit: (values: DataProductInput) => void
  onCancel: () => void
  isSubmitting: boolean
}

export default function DataProductForm({ defaultValues, onSubmit, onCancel, isSubmitting }: DataProductFormProps) {
  const { user } = useAuth()
  const domains = useAllDomains()
  const allContracts = useDataContracts()
  const products = useDataProducts()
  const own = useSelectableContracts()

  const domainChoices = useMemo(
    () => selectableDomains(domains.data ?? [], user, defaultValues?.domain_id),
    [domains.data, user, defaultValues?.domain_id],
  )
  const producers = useMemo(
    () => producersByContract((products.data ?? []).filter((p) => p.id !== defaultValues?.id)),
    [products.data, defaultValues?.id],
  )
  // Outputs: the user's own domains. Inputs: every contract, since reading
  // across domains is the point.
  const outputSource = sourceOf(own.contracts, own.isLoading, own.error)
  const inputSource = sourceOf(allContracts.data, allContracts.isLoading, allContracts.error)

  const {
    register,
    control,
    handleSubmit,
    reset,
    getValues,
    setValue,
    formState: { errors },
  } = useForm<DataProductInput>({
    resolver: zodResolver(schema) as unknown as Resolver<DataProductInput>,
    defaultValues: valuesOf(defaultValues),
  })
  const inputs = useWatch({ control, name: 'input_ports' })

  useEffect(() => {
    if (defaultValues) reset(valuesOf(defaultValues))
  }, [defaultValues, reset])

  // The platform fills what it knows: a user in one domain creates in it.
  useEffect(() => {
    if (!defaultValues && domainChoices.length === 1 && !getValues('domain_id')) {
      setValue('domain_id', domainChoices[0].id)
    }
  }, [defaultValues, domainChoices, getValues, setValue])

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
      <Input label="Name" placeholder="My Data Product" error={errors.name?.message} {...register('name')} />

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="product-domain" className="form-label">
            Domain
          </label>
          {/* Controlled: the domain list may arrive after the form opens. */}
          <Controller
            name="domain_id"
            control={control}
            render={({ field }) => (
              <select id="product-domain" className={`form-input ${errors.domain_id ? 'error' : ''}`} {...field}>
                <option value="">Select…</option>
                {domainChoices.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            )}
          />
          {errors.domain_id && <p className="form-error">{errors.domain_id.message}</p>}
        </div>
        <div>
          <label htmlFor="product-status" className="form-label">
            Status
          </label>
          <select id="product-status" className="form-input" {...register('status')}>
            {PRODUCT_STATUSES.map((s) => (
              <option key={s} value={s}>
                {STATUS_LABELS[s]}
              </option>
            ))}
          </select>
        </div>
      </div>

      <Input
        label="Description"
        placeholder="What this product is for and who uses it..."
        id="description"
        error={errors.description?.purpose?.message}
        {...register('description.purpose')}
      />

      <Controller
        name="output_ports"
        control={control}
        render={({ field }) => (
          <OutputPortsEditor
            rows={field.value}
            onChange={field.onChange}
            inputs={inputs}
            source={outputSource}
            error={listError(errors.output_ports)}
          />
        )}
      />

      <Controller
        name="input_ports"
        control={control}
        render={({ field }) => (
          <InputPortsEditor
            rows={field.value}
            onChange={field.onChange}
            source={inputSource}
            producers={producers}
            error={listError(errors.input_ports)}
          />
        )}
      />

      <div className="flex justify-end gap-3 pt-2">
        <Button type="button" variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" loading={isSubmitting}>
          {defaultValues ? 'Save Changes' : 'Create Product'}
        </Button>
      </div>
    </form>
  )
}
