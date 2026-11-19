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

const tierRequiresAllSLAs = (t: number) => t === 1
const tierRequiresFreshnessAvailability = (t: number) => t === 2
const tierShowsSLAs = (t: number) => t <= 3
const tierShowsQuality = (t: number) => t <= 3
const tierRequiresQuality = (t: number) => t === 1
const tierRequiresFields = (t: number) => t <= 2

const DURATION_UNITS = new Set(['s', 'm', 'h', 'd', 'w', 'y'])
function isValidDuration(v: string): boolean {
  if (!v) return true
  const unit = v.at(-1) ?? ''
  if (!DURATION_UNITS.has(unit)) return false
  return Number.isFinite(Number(v.slice(0, -1)))
}
function isValidAvailability(v: string): boolean {
  if (!v) return true
  if (!v.endsWith('%')) return false
  return Number.isFinite(Number(v.slice(0, -1)))
}

const schema = z
  .object({
    title: z.string().min(1, 'Title is required'),
    version: z.string().min(1, 'Version is required'),
    owner: z.string().min(1, 'Owner is required'),
    domain_id: z.string().min(1, 'Domain is required'),
    tier: z.number().int().min(1).max(4),
    status: z.enum(['draft', 'in_review', 'active', 'deprecated']),
    freshness: z.string().refine(isValidDuration, { message: 'Use a duration like 24h, 7d, 30m' }),
    availability: z.string().refine(isValidAvailability, { message: 'Use a percentage like 99.9%' }),
    retention: z.string().refine(isValidDuration, { message: 'Use a duration like 365d, 1y' }),
    latency: z.string().refine(isValidDuration, { message: 'Use a duration like 1h, 30m' }),
    purpose: z.string(),
    usage: z.string(),
    limitations: z.string(),
  })
  .superRefine((data, ctx) => {
    if (data.tier === 1) {
      if (!data.freshness) ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'Required for Tier 1', path: ['freshness'] })
      if (!data.availability) ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'Required for Tier 1', path: ['availability'] })
      if (!data.retention) ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'Required for Tier 1', path: ['retention'] })
      if (!data.latency) ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'Required for Tier 1', path: ['latency'] })
    }
    if (data.tier === 2) {
      if (!data.freshness) ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'Required for Tier 2', path: ['freshness'] })
      if (!data.availability) ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'Required for Tier 2', path: ['availability'] })
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

function normalizeDefaults(v?: DataContract): FormValues {
  if (!v) {
    return {
      title: '', version: '1.0.0', owner: '', domain_id: '',
      tier: 4, status: 'draft',
      freshness: '', availability: '', retention: '', latency: '',
      purpose: '', usage: '', limitations: '',
    }
  }
  return {
    title: v.title, version: v.version, owner: v.owner, domain_id: v.domain_id,
    tier: v.tier, status: v.status,
    freshness: v.servicelevels.freshness, availability: v.servicelevels.availability,
    retention: v.servicelevels.retention, latency: v.servicelevels.latency,
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
  if (tierRequiresQuality(tier) && quality.length === 0) {
    setQualityError('At least one quality rule is required for Tier 1')
    valid = false
  } else {
    setQualityError(null)
  }
  return valid
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
}: {
  tier: number
  register: UseFormRegister<FormValues>
  errors: FieldErrors<FormValues>
}) {
  const needsAll = tierRequiresAllSLAs(tier)
  const needsFreshAvail = needsAll || tierRequiresFreshnessAvailability(tier)
  return (
    <div className="space-y-3">
      <SectionHeader
        label="Service Levels"
        required={needsFreshAvail}
        optional={!needsFreshAvail}
      />
      <div className="grid grid-cols-2 gap-3">
        <Input
          label={`Freshness${needsFreshAvail ? ' *' : ''}`}
          placeholder="e.g. 24h"
          error={errors.freshness?.message}
          {...register('freshness')}
        />
        <Input
          label={`Availability${needsFreshAvail ? ' *' : ''}`}
          placeholder="e.g. 99.9%"
          error={errors.availability?.message}
          {...register('availability')}
        />
        <Input
          label={`Retention${needsAll ? ' *' : ''}`}
          placeholder="e.g. 365d"
          error={errors.retention?.message}
          {...register('retention')}
        />
        <Input
          label={`Latency${needsAll ? ' *' : ''}`}
          placeholder="e.g. 1h"
          error={errors.latency?.message}
          {...register('latency')}
        />
      </div>
    </div>
  )
}

function QualitySection({
  tier,
  quality,
  onChange,
  error,
}: {
  tier: number
  quality: QualityRule[]
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
        dimension · column (opt.) · operator · threshold · description
      </p>
      <QualityRules rules={quality} onChange={onChange} />
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

  const handleFormSubmit = (values: FormValues) => {
    // Both run, so a message the user has since fixed never lingers on screen.
    const arraysValid = validateFormArrays(values.tier, fields, quality, setFieldsError, setQualityError)
    const metadataValid = metadata.validate()
    if (!arraysValid || !metadataValid) return

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
      servicelevels: tierShowsSLAs(values.tier)
        ? {
            freshness: values.freshness,
            availability: values.availability,
            retention: values.retention,
            latency: values.latency,
          }
        : { freshness: '', availability: '', retention: '', latency: '' },
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
                </select>
              </div>
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
            <ServiceLevelsSection tier={tier} register={register} errors={errors} />
          )}

          {tierShowsQuality(tier) && (
            <QualitySection
              tier={tier}
              quality={quality}
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
