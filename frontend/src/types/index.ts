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
  // What the signed-in user may do; on the detail only (the list sends null).
  permissions?: ContractPermissions | null
}

export interface ContractPermissions {
  edit: boolean
  delete: boolean
  transitions: DataContract['status'][]
  manage_stakeholders: boolean
}

// A person invited to read a draft contract before it is published.
export interface Stakeholder {
  user_id: string
  username: string
  role: string // platform role
  assigned_by_username: string
  assigned_at: string
}

// The status is not part of the input: it moves with POST /data-contracts/{id}/status.
export interface DataContractInput {
  title: string
  version: string
  owner: string
  domain_id: string
  tier: number
  models: { fields: SchemaField[]; quality?: QualityRule[] }
  servicelevels: ServiceLevels
  description: ContractDescription
  team_members: TeamMember[]
  support: SupportChannel[]
  servers: ContractServer[]
}

// ODPS product status (Open Data Product Standard v1.1.0).
export type ProductStatus = 'proposed' | 'draft' | 'active' | 'deprecated' | 'retired'

// ODPS inputContracts entry: a contract version an output is built from.
export interface ContractRef { contract_id: string; version: string }

// ODPS v1.1.0 structures, in the API's snake_case. Optional fields may be absent.
export interface CustomProperty { property: string; value: unknown; description?: string | null; vendor?: string | null; id?: string | null }
export interface AuthoritativeDefinition { type: string; url: string; description?: string | null; id?: string | null }
// The three lists ODPS attaches to most of its objects.
export interface Annotated {
  tags?: string[]
  custom_properties?: CustomProperty[]
  authoritative_definitions?: AuthoritativeDefinition[]
}
export interface ProductDescription {
  purpose: string
  usage: string
  limitations: string
  authoritative_definitions?: AuthoritativeDefinition[]
  custom_properties?: CustomProperty[]
}
export interface Synonym {
  synonym: string
  description?: string | null
  locale?: string | null
  source?: string | null
  status?: string | null
  id?: string | null
  custom_properties?: CustomProperty[]
}
export interface VerifiedStatement extends Annotated { question: string; answer?: string | null; id?: string | null }
export interface ContextConstraint extends Annotated { constraint: string; id?: string | null }
export interface ProductContext {
  instructions?: string | null
  verified_statements?: VerifiedStatement[]
  constraints?: ContextConstraint[]
}
export interface ProductTeamMember extends Annotated {
  username: string
  name?: string
  role?: string
  description?: string | null
  date_in?: string | null
  date_out?: string | null
  replaced_by_username?: string | null
  id?: string | null
}
export interface ProductTeam extends Annotated {
  name?: string | null
  description?: string | null
  members?: ProductTeamMember[]
  id?: string | null
}
export interface ProductSupport extends Annotated {
  channel: string
  url: string
  tool?: string
  scope?: string
  description?: string | null
  invitation_url?: string | null
  id?: string | null
}
export interface Sbom extends Annotated { type?: string | null; url?: string | null; id?: string | null }
export interface ManagementPort extends Annotated {
  id?: string
  name: string
  content: string
  type: string            // rest or topic
  url?: string | null
  channel?: string | null
  description?: string | null
  deprecated: boolean
}
// Read-only: the referenced contract as it is now.
export interface ContractSummary { title: string; status: DataContract['status']; version: string; domain: string }
// Read-only: another product seen from a port (lineage).
export interface ProductRef { id: string; name: string; status: ProductStatus }

export interface InputPort {
  id?: string
  name: string
  contract_id: string | null
  version: string | null   // with a contract, the pinned contract version
  deprecated: boolean
  authoritative_definitions: AuthoritativeDefinition[]
  tags: string[]
  custom_properties: CustomProperty[]
  contract?: ContractSummary | null
  produced_by?: ProductRef[]
}

export interface OutputPort {
  id?: string
  name: string
  contract_id: string | null
  version: string | null
  type: string | null
  description: string | null
  deprecated: boolean
  authoritative_definitions: AuthoritativeDefinition[]
  input_contracts: ContractRef[]
  tags: string[]
  custom_properties: CustomProperty[]
  synonyms: Synonym[]
  context: ProductContext
  sbom: Sbom[]
  contract?: ContractSummary | null
  consumed_by?: ProductRef[]
}

// The ODPS sections a product carries besides its name, domain, status and ports.
export interface ProductSections {
  version: string | null
  type: string | null
  tenant: string | null
  tags: string[]
  synonyms: Synonym[]
  context: ProductContext
  team: ProductTeam
  support: ProductSupport[]
  custom_properties: CustomProperty[]
  authoritative_definitions: AuthoritativeDefinition[]
}

export interface DataProduct extends ProductSections {
  id: string
  name: string
  description: ProductDescription
  domain_id: string
  domain: string             // read-only joined name
  status: ProductStatus
  deprecated: boolean        // derived from status
  input_ports: InputPort[]
  output_ports: OutputPort[]
  management_ports: ManagementPort[]
  repo_url?: string | null   // provisioned GitHub repo URL; null until backend provisions it
  created_at: string
  updated_at: string
  warnings?: string[]        // only on a successful write
}

// One port that references a contract, seen from the contract.
export interface PortUsage {
  product_id: string
  product_name: string
  domain: string
  status: ProductStatus
  role: 'input' | 'output'
  port_name: string
  version: string
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

// What POST and PUT take: the whole product, ports included.
export interface DataProductInput extends ProductSections {
  name: string
  description: ProductDescription
  domain_id: string
  status: ProductStatus
  input_ports: InputPort[]
  output_ports: OutputPort[]
  management_ports: ManagementPort[]
}

export interface UserFormData {
  username: string
  email: string
}
