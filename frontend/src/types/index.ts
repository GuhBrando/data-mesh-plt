export interface ServiceLevelProperty {
  property: string
  value: number | string
  unit: string | null
}
// ODCS slaProperties. Numbers carry a unit; text carries none.
export interface ServiceLevels {
  properties: ServiceLevelProperty[]
}

export type QualityDimension =
  | 'accuracy'
  | 'completeness'
  | 'conformity'
  | 'consistency'
  | 'coverage'
  | 'timeliness'
  | 'uniqueness'
export type QualityMetric = 'nullValues' | 'missingValues' | 'invalidValues' | 'duplicateValues' | 'rowCount'
export type QualityOperator =
  | 'mustBe'
  | 'mustNotBe'
  | 'mustBeGreaterThan'
  | 'mustBeGreaterOrEqualTo'
  | 'mustBeLessThan'
  | 'mustBeLessOrEqualTo'

// An ODCS quality rule: a library metric datacontract-cli can run, or free text.
export interface QualityRule {
  type: 'library' | 'text'
  dimension: QualityDimension | null
  column: string
  metric: QualityMetric | null
  operator: QualityOperator | null
  value: number | null
  unit: 'rows' | 'percent' | null
  valid_values: string[]
  description: string
}

export type FieldClassification = '' | 'public' | 'internal' | 'confidential' | 'restricted'

export interface SchemaField {
  name: string
  type: 'string' | 'integer' | 'float' | 'boolean' | 'date' | 'timestamp'
  description: string
  nullable: boolean
  primary_key: boolean
  classification: FieldClassification
  unique: boolean
  physical_type: string
}

export interface ContractDescription { purpose: string; usage: string; limitations: string }
export interface TeamMember { username: string; name: string; role: string }
export interface SupportChannel { channel: string; url: string; tool: string; scope: string }
export type ServerType = 'databricks' | 'postgres' | 'azure' | 'local'
export interface ContractServer {
  server: string
  type: ServerType
  environment: string
  host: string
  catalog: string
  schema_name: string   // written as `schema` in ODCS; the API uses schema_name
  port: number | null
  database: string
  location: string
  format: string
  path: string
}

// One immutable history row; its ODCS YAML is fetched on demand.
export interface ContractVersion {
  version: string
  created_by: string | null
  created_at: string
}

export interface DataContract {
  id: string
  title: string
  version: string
  owner: string
  domain: string        // read-only joined name from API — do not send to server
  domain_id: string
  tier: 1 | 2 | 3 | 4
  status: 'draft' | 'in_review' | 'active' | 'deprecated' | 'retired'
  models: { fields: SchemaField[]; quality?: QualityRule[] }
  servicelevels: ServiceLevels
  description: ContractDescription
  team_members: TeamMember[]
  support: SupportChannel[]
  servers: ContractServer[]
  created_at: string
  updated_at: string
}

export interface DataContractInput {
  title: string
  version: string
  owner: string
  domain_id: string
  tier: number
  status: string
  models: { fields: SchemaField[]; quality?: QualityRule[] }
  servicelevels: ServiceLevels
  description: ContractDescription
  team_members: TeamMember[]
  support: SupportChannel[]
  servers: ContractServer[]
}

export interface DataProduct {
  id: string
  name: string
  description: string
  data_contracts_id: string
  repo_url?: string | null   // provisioned GitHub repo URL; null until backend provisions it
  created_at: string
  updated_at: string
}

export interface User {
  id: string
  username: string
  email: string
  role: string
}

export interface Domain {
  id: string
  name: string
  description: string
  owner_id: string
  created_at: string
  updated_at: string
}

export interface DomainMember {
  user_id: string
  username: string
  role: 'maintainer' | 'member'
}

export interface DomainWithMembers extends Domain {
  owner_username: string
  members: DomainMember[]
  contract_count: number
}

export type DomainAccess = 'admin' | 'owner' | 'maintainer' | 'member' | 'none'

export interface DomainInput {
  name: string
  description: string
  owner_id: string
}

export interface DataProductFormData {
  name: string
  description: string
  data_contracts_id: string
}

export interface UserFormData {
  username: string
  email: string
}
