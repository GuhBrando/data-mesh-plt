import { useState, useMemo } from 'react'

function useAccessibleDomains() {
  const { user } = useAuth()
  const { data: allDomains = [], isLoading } = useAllDomains()
  const domains = useMemo(
    () => allDomains.filter((d) => getDomainAccess(d, user?.id ?? '', user?.role) !== 'none'),
    [allDomains, user],
  )
  return { domains, isLoading }
}
import { useForm, Controller } from 'react-hook-form'
import type { UseFormRegister, FieldErrors } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import Button from '../../components/ui/Button'
import { Input, Textarea } from '../../components/ui/Input'
import TierWizard from './TierWizard'
import ContractFields, { withFieldDefaults } from './ContractFields'
import QualityRules from './QualityRules'
import TeamMembers from './TeamMembers'
import SupportChannels from './SupportChannels'
import ContractServers from './ContractServers'
import { metadataError } from './contractMetadata'
import { qualityProblem } from '../../lib/qualityRules'
import { SLA_KEYS, UNITS, readSlaInputs, slaInputProblem, toServiceLevels } from '../../lib/serviceLevels'
import type { SlaInput, SlaKey } from '../../lib/serviceLevels'
import { useAllDomains } from '../../hooks/useDomains'
import { useAuth } from '../../contexts/AuthContext'
import { getDomainAccess } from '../../lib/domains'
import type {
  ContractServer,
  DataContract,
  DataContractInput,
  QualityRule,
  SchemaField,
  SupportChannel,
  TeamMember,
} from '../../types'

const tierShowsSLAs = (t: number) => t <= 3
const tierShowsQuality = (t: number) => t <= 3
const tierRequiresQuality = (t: number) => t === 1
const tierRequiresFields = (t: number) => t <= 2

const SLA_LABELS: Record<SlaKey, string> = {
  freshness: 'Freshness',
  availability: 'Availability',
  retention: 'Retention',
  latency: 'Latency',
}
const SLA_PLACEHOLDERS: Record<SlaKey, string> = {
  freshness: 'e.g. 24',
  availability: 'e.g. 99.9',
  retention: 'e.g. 365',
  latency: 'e.g. 1',
}
const unitKey = (key: SlaKey) => `${key}Unit` as const

function requiredSlaKeys(tier: number): SlaKey[] {
  if (tier === 1) return [...SLA_KEYS]
  if (tier === 2) return ['freshness', 'availability']
  return []
}

const schema = z
  .object({
    title: z.string().min(1, 'Title is required'),
    version: z.string().min(1, 'Version is required'),
    owner: z.string().min(1, 'Owner is required'),
    domain_id: z.string().min(1, 'Domain is required'),
    tier: z.number().int().min(1).max(4),
    status: z.enum(['draft', 'in_review', 'active', 'deprecated', 'retired']),
    freshness: z.string(),
    freshnessUnit: z.string(),
    availability: z.string(),
    availabilityUnit: z.string(),
    retention: z.string(),
    retentionUnit: z.string(),
    latency: z.string(),
    latencyUnit: z.string(),
    purpose: z.string(),
    usage: z.string(),
    limitations: z.string(),
  })
  .superRefine((data, ctx) => {
    const required = requiredSlaKeys(data.tier)
    for (const key of SLA_KEYS) {
      const input = { value: data[key], unit: data[unitKey(key)] }
      const message = !input.value.trim() && required.includes(key)
        ? `Required for Tier ${data.tier}`
        : slaInputProblem(input)
      if (message) ctx.addIssue({ code: z.ZodIssueCode.custom, message, path: [key] })
    }
  })

type FormValues = z.infer<typeof schema>

interface DataContractFormProps {
  defaultValues?: DataContract
  onSubmit: (input: DataContractInput) => void
  onCancel: () => void
  isSubmitting: boolean
  showWizard?: boolean
}

function slaDefaults(v?: DataContract) {
  const sla = readSlaInputs(v?.servicelevels)
  return {
    freshness: sla.freshness.value, freshnessUnit: sla.freshness.unit,
    availability: sla.availability.value, availabilityUnit: sla.availability.unit,
    retention: sla.retention.value, retentionUnit: sla.retention.unit,
    latency: sla.latency.value, latencyUnit: sla.latency.unit,
  }
}

function slaInputsFrom(values: FormValues): Record<SlaKey, SlaInput> {
  const inputs = {} as Record<SlaKey, SlaInput>
  for (const key of SLA_KEYS) {
    // Tier 4 hides service levels: the four shown ones are cleared.
    inputs[key] = tierShowsSLAs(values.tier)
      ? { value: values[key], unit: values[unitKey(key)] }
      : { value: '', unit: '' }
  }
  return inputs
}

function normalizeDefaults(v?: DataContract): FormValues {
  if (!v) {
    return {
      title: '', version: '1.0.0', owner: '', domain_id: '',
      tier: 4, status: 'draft',
      ...slaDefaults(),
      purpose: '', usage: '', limitations: '',
    }
  }
  return {
    title: v.title, version: v.version, owner: v.owner, domain_id: v.domain_id,
    tier: v.tier, status: v.status,
    ...slaDefaults(v),
    purpose: v.description?.purpose ?? '',
    usage: v.description?.usage ?? '',
    limitations: v.description?.limitations ?? '',
  }
}

function getInitialFields(v?: DataContract): SchemaField[] {
  if (!v) return []
  return v.models.fields.map(withFieldDefaults)
}

function getInitialQuality(v?: DataContract): QualityRule[] {
  if (!v) return []
  return v.models.quality ?? []
}

function qualityErrorFor(tier: number, fields: SchemaField[], quality: QualityRule[]): string | null {
  if (tierRequiresQuality(tier) && quality.length === 0) {
    return 'At least one quality rule is required for Tier 1'
  }
  if (!tierShowsQuality(tier)) return null
  return qualityProblem(quality, fields.map((f) => f.name))
}

function validateFormArrays(
  tier: number,
  fields: SchemaField[],
  quality: QualityRule[],
  setFieldsError: (e: string | null) => void,
  setQualityError: (e: string | null) => void,
): boolean {
  let valid = true
  if (tierRequiresFields(tier) && fields.length === 0) {
    setFieldsError(`At least one schema field is required for Tier ${tier}`)
    valid = false
  } else {
    setFieldsError(null)
  }
  const qualityError = qualityErrorFor(tier, fields, quality)
  setQualityError(qualityError)
  return valid && qualityError === null
}

function SectionHeader({
  label,
  required,
  optional,
}: {
  label: string
  required?: boolean
  optional?: boolean
}) {
  return (
    <div className="flex items-center gap-2">
      <h3 className="text-sm font-semibold text-gray-700 dark:text-slate-200">{label}</h3>
      {required && (
        <span className="text-xs px-1.5 py-0.5 bg-red-50 text-red-600 border border-red-200 rounded dark:bg-red-900/20 dark:text-red-400 dark:border-red-800">
          Required
        </span>
      )}
      {optional && (
        <span className="text-xs px-1.5 py-0.5 bg-gray-100 text-gray-500 border border-gray-200 rounded dark:bg-slate-700 dark:text-slate-400 dark:border-slate-600">
          Optional
        </span>
      )}
    </div>
  )
}

function ServiceLevelsSection({
  tier,
  register,
  errors,
  currentUnits,
}: {
  tier: number
  register: UseFormRegister<FormValues>
  errors: FieldErrors<FormValues>
  currentUnits: Record<SlaKey, string>
}) {
  const required = requiredSlaKeys(tier)
  return (
    <div className="space-y-3">
      <SectionHeader
        label="Service Levels"
        required={required.length > 0}
        optional={required.length === 0}
      />
      <p className="text-xs text-gray-400 dark:text-slate-500">
        A number with a unit, or text with no unit.
      </p>
      <div className="grid grid-cols-2 gap-3">
        {SLA_KEYS.map((key) => (
          <SlaInputRow
            key={key}
            slaKey={key}
            required={required.includes(key)}
            register={register}
            error={errors[key]?.message}
            unit={currentUnits[key]}
          />
        ))}
      </div>
    </div>
  )
}

function SlaInputRow({
  slaKey,
  required,
  register,
  error,
  unit,
}: {
  slaKey: SlaKey
  required: boolean
  register: UseFormRegister<FormValues>
  error?: string
  unit: string
}) {
  // A stored unit outside the list (written by another tool) stays selectable.
  const units = unit && !UNITS[slaKey].includes(unit) ? [...UNITS[slaKey], unit] : UNITS[slaKey]
  return (
    <div className="flex items-start gap-2">
      <Input
        label={`${SLA_LABELS[slaKey]}${required ? ' *' : ''}`}
        placeholder={SLA_PLACEHOLDERS[slaKey]}
        error={error}
        {...register(slaKey)}
      />
      <select
        aria-label={`${SLA_LABELS[slaKey]} unit`}
        className="mt-6 text-sm border border-gray-300 dark:border-slate-600 rounded-lg px-2 py-2 bg-white dark:bg-slate-800 text-gray-800 dark:text-slate-200"
        {...register(unitKey(slaKey))}
      >
        <option value="">—</option>
        {units.map((u) => (
          <option key={u} value={u}>{u}</option>
        ))}
      </select>
    </div>
  )
}

function QualitySection({
  tier,
  quality,
  fieldNames,
  onChange,
  error,
}: {
  tier: number
  quality: QualityRule[]
  fieldNames: string[]
  onChange: (rules: QualityRule[]) => void
  error: string | null
}) {
  return (
    <div className="space-y-3">
      <SectionHeader
        label="Quality Rules"
        required={tierRequiresQuality(tier)}
        optional={!tierRequiresQuality(tier)}
      />
      <p className="text-xs text-gray-400 dark:text-slate-500">
        A library rule is a check datacontract-cli runs on the data. A text rule documents a
        check no tool runs.
      </p>
      <QualityRules rules={quality} fieldNames={fieldNames} onChange={onChange} />
      {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
    </div>
  )
}

function useMetadataRows(v?: DataContract) {
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>(v?.team_members ?? [])
  const [support, setSupport] = useState<SupportChannel[]>(v?.support ?? [])
  const [servers, setServers] = useState<ContractServer[]>(v?.servers ?? [])
  const [error, setError] = useState<string | null>(null)
  const validate = (): boolean => {
    const problem = metadataError(teamMembers, support, servers)
    setError(problem)
    return problem === null
  }
  return { teamMembers, setTeamMembers, support, setSupport, servers, setServers, error, validate }
}

function MetadataSections({
  register,
  metadata,
}: {
  register: UseFormRegister<FormValues>
  metadata: ReturnType<typeof useMetadataRows>
}) {
  return (
    <>
      <div className="space-y-3">
        <SectionHeader label="Description" optional />
        <Textarea label="Purpose" rows={2} {...register('purpose')} />
        <Textarea label="Usage" rows={2} {...register('usage')} />
        <Textarea label="Limitations" rows={2} {...register('limitations')} />
      </div>
      <div className="space-y-3">
        <SectionHeader label="Team Members" optional />
        <TeamMembers rows={metadata.teamMembers} onChange={metadata.setTeamMembers} />
      </div>
      <div className="space-y-3">
        <SectionHeader label="Support" optional />
        <SupportChannels rows={metadata.support} onChange={metadata.setSupport} />
      </div>
      <div className="space-y-3">
        <SectionHeader label="Servers" optional />
        <p className="text-xs text-gray-400 dark:text-slate-500">
          Where the data lives. Coordinates only: never a password, token or connection string.
        </p>
        <ContractServers rows={metadata.servers} onChange={metadata.setServers} />
      </div>
      {metadata.error && <p className="text-xs text-red-500 mt-1">{metadata.error}</p>}
    </>
  )
}

function StatusSelect({
  register,
  editing,
}: {
  register: UseFormRegister<FormValues>
  editing: boolean
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-1">
        Status
      </label>
      <select
        className="w-full text-sm border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 bg-white dark:bg-slate-800 text-gray-800 dark:text-slate-200"
        {...register('status')}
      >
        <option value="draft">Draft</option>
        <option value="in_review">In Review</option>
        <option value="active">Active</option>
        <option value="deprecated">Deprecated</option>
        {/* A contract is not born retired; retiring is an edit. */}
        {editing && <option value="retired">Retired</option>}
      </select>
    </div>
  )
}

function DomainSelect({
  domains,
  loading,
  register,
  error,
}: {
  domains: { id: string; name: string }[]
  loading: boolean
  register: ReturnType<typeof useForm<FormValues>>['register']
  error?: string
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-1">
        Domain
      </label>
      <select
        className="w-full text-sm border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 bg-white dark:bg-slate-800 text-gray-800 dark:text-slate-200 disabled:opacity-50"
        disabled={loading}
        {...register('domain_id')}
      >
        <option value="">{loading ? 'Loading domains…' : 'Select a domain'}</option>
        {domains.map((d) => (
          <option key={d.id} value={d.id}>{d.name}</option>
        ))}
      </select>
      {error && <p className="mt-1 text-xs text-red-500">{error}</p>}
    </div>
  )
}

export default function DataContractForm({
  defaultValues,
  onSubmit,
  onCancel,
  isSubmitting,
  showWizard = false,
}: DataContractFormProps) {
  const [tierDone, setTierDone] = useState(!showWizard)
  const [fields, setFields] = useState<SchemaField[]>(getInitialFields(defaultValues))
  const [quality, setQuality] = useState<QualityRule[]>(getInitialQuality(defaultValues))
  const [fieldsError, setFieldsError] = useState<string | null>(null)
  const [qualityError, setQualityError] = useState<string | null>(null)
  const metadata = useMetadataRows(defaultValues)

  const { domains: accessibleDomains, isLoading: domainsLoading } = useAccessibleDomains()

  const {
    register,
    handleSubmit,
    control,
    watch,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: normalizeDefaults(defaultValues),
  })

  const tier = watch('tier')
  const currentUnits = Object.fromEntries(
    SLA_KEYS.map((key) => [key, watch(unitKey(key))]),
  ) as Record<SlaKey, string>

  const handleFormSubmit = (values: FormValues) => {
    if (!validateFormArrays(values.tier, fields, quality, setFieldsError, setQualityError)) return
    if (!metadata.validate()) return

    onSubmit({
      title: values.title,
      version: values.version,
      owner: values.owner,
      domain_id: values.domain_id,
      tier: values.tier,
      status: values.status,
      models: {
        fields,
        quality: tierShowsQuality(values.tier) ? quality : [],
      },
      // Properties the form does not show, such as frequency, are kept.
      servicelevels: toServiceLevels(slaInputsFrom(values), defaultValues?.servicelevels),
      description: {
        purpose: values.purpose,
        usage: values.usage,
        limitations: values.limitations,
      },
      team_members: metadata.teamMembers,
      support: metadata.support,
      servers: metadata.servers,
    })
  }

  return (
    <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-6">
      {showWizard && (
        <Controller
          name="tier"
          control={control}
          render={({ field }) => (
            <TierWizard
              value={field.value}
              onChange={(t) => {
                field.onChange(t)
                setTierDone(true)
              }}
            />
          )}
        />
      )}

      {tierDone && (
        <>
          <div className="space-y-3">
            <SectionHeader label="Contract Info" />
            <div className="grid grid-cols-2 gap-3">
              <Input label="Title" error={errors.title?.message} {...register('title')} />
              <Input label="Version" error={errors.version?.message} {...register('version')} />
              <Input label="Owner" error={errors.owner?.message} {...register('owner')} />
              <DomainSelect
                domains={accessibleDomains}
                loading={domainsLoading}
                register={register}
                error={errors.domain_id?.message}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              {!showWizard && (
                <div>
                  <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-1">
                    Tier
                  </label>
                  <select
                    className="w-full text-sm border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 bg-white dark:bg-slate-800 text-gray-800 dark:text-slate-200"
                    {...register('tier', { valueAsNumber: true })}
                  >
                    <option value={1}>Tier 1 — Critical / Regulated</option>
                    <option value={2}>Tier 2 — Business Important</option>
                    <option value={3}>Tier 3 — Operational / Internal</option>
                    <option value={4}>Tier 4 — Experimental / Sandbox</option>
                  </select>
                </div>
              )}
              <StatusSelect register={register} editing={!!defaultValues} />
            </div>
          </div>

          <div className="space-y-3">
            <SectionHeader
              label="Schema Fields"
              required={tierRequiresFields(tier)}
              optional={!tierRequiresFields(tier)}
            />
            <ContractFields fields={fields} onChange={setFields} />
            {fieldsError && <p className="text-xs text-red-500 mt-1">{fieldsError}</p>}
          </div>

          {tierShowsSLAs(tier) && (
            <ServiceLevelsSection
              tier={tier}
              register={register}
              errors={errors}
              currentUnits={currentUnits}
            />
          )}

          {tierShowsQuality(tier) && (
            <QualitySection
              tier={tier}
              quality={quality}
              fieldNames={fields.map((f) => f.name)}
              onChange={setQuality}
              error={qualityError}
            />
          )}

          <MetadataSections register={register} metadata={metadata} />

          <div className="flex justify-end gap-3 pt-2 border-t border-gray-200 dark:border-slate-700">
            <Button type="button" variant="secondary" onClick={onCancel}>
              Cancel
            </Button>
            <Button type="submit" loading={isSubmitting}>
              {defaultValues ? 'Save Changes' : 'Create Contract'}
            </Button>
          </div>
        </>
      )}

      {showWizard && !tierDone && (
        <div className="flex justify-end pt-2">
          <Button type="button" variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
        </div>
      )}
    </form>
  )
}
