# ODPS Plan 2 — Every Other ODPS Field Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the data product every remaining ODPS v1.1.0 field (structured description, version, type, tenant, tags, synonyms, context, team, support, custom properties, authoritative definitions, management ports, and the extra port fields), drop `data_contracts_id` and the `platform.control_*` tables, and add the "More ODPS fields" section to the product form.

**Architecture:** The descriptive ODPS sections are JSONB columns stored as validated: the API models follow the ODPS JSON Schema definitions field by field, in snake_case, and the aggregate carries the sections without interpreting them. Management ports are a table owned by the product, written with it in one batched statement and read with it in the same query. The contract's ODCS row models and editors (team members, support channels, editable rows) move to shared modules used by both contracts and products.

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2, asyncpg, PostgreSQL 16, Atlas, React 18, react-hook-form, zod 4, Vitest.

**Spec:** `docs/superpowers/specs/2026-11-24-odps-adoption-design.md` (Decisions, Calls 6–7 and 11, Engineering Principles, Standard Notes, Target Data Model, Plan 2). ODPS structures: `schema/odps-json-schema-v1.1.0.json` at tag `v1.1.0`, SHA-256 `b7eae1af15b3c6b18e5dffaa2119212acb38ec73286933c76d16c8712e0d90d1` (plan 3 vendors it).

**Starting point:** branch `feat/odps-2-product-metadata`, stacked on `feat/odps-1-ports-status-domain` (PR #57). **Release gate (call 11):** this branch merges into `develop` only after a release containing plan 1 is deployed everywhere, local databases included.

## Global Constraints

- Migration version `20261124000002`. It stops with a clear error while any `data_products.data_contracts_id` is set, and while `platform.control_ports` or `platform.control_port_types` hold rows.
- JSONB columns default to `'[]'` or `'{}'`, never `NULL`. Keys inside JSONB are the API's snake_case names; plan 3 maps them to ODPS camelCase.
- Each API model mirrors one ODPS definition, every field optional unless the schema requires it, `extra="forbid"`, dumped with `exclude_none=True`. Required by the schema, therefore required here: `custom_properties[].property` and `value`, `authoritative_definitions[].type` and `url`, `synonyms[].synonym`, `support[].channel` and `url`, `team.members[].username`, `management_ports[].name` and `content`, `context.verified_statements[].question`, `context.constraints[].constraint`.
- Where ODPS places a field: `synonyms`, `context`, `sbom` on the product (except `sbom`) and on outputs only; `tags`, `custom_properties`, `authoritative_definitions` on the product and every port kind.
- `management_ports[].type` is `rest` or `topic`, default `rest` (database check). `content` is free text; the UI suggests `discoverability`, `observability`, `control`, `dictionary`.
- Product `type` is free text; the UI suggests `sourceAligned`, `aggregate`, `consumerAligned`. Product `version` is free text; the UI suggests semver.
- Variables: any string may hold `${VAR}` or `${VAR:-default}`; nothing substitutes it, and validation accepts it where it would otherwise check the value (support URLs).
- `description` becomes `{"purpose", "usage", "limitations", "authoritative_definitions", "custom_properties"}`; the old text becomes `purpose`.
- Plan 1's backfill (`scripts/backfill_output_ports.py`, `BackfillOutputPortsUseCase`, `LegacyProduct`, `list_legacy_products`, the `entrypoint.sh` line) is deleted.
- Fixed number of queries per request whatever the number of ports or management ports; each new repository write gets an `n1` test.
- Same CI gates, commands and repository rules as plan 1 (ruff `C90` ≤ 15, coverage ≥ 80 %, mutation ≥ 70 %, `atlas.sum` recipe, no attribution, `.venv\Scripts` on `PATH` to commit). Throwaway compose stacks **must** set their own default network name.

## Review Focus

1. A product synced or edited before plan 2 has `description` as text; after the migration every read returns an object. A product whose text was empty must still read (purpose `""`). Test: `test_text_description_becomes_purpose` (Task 1).
2. An edit that changes nothing must not lose nested ODPS fields the form does not show (a team member's `date_in`, a support channel's `invitation_url`). Test: `submits nested ODPS fields it does not edit unchanged` (Task 6).
3. A support URL written as `${SUPPORT_URL}` is accepted and returned verbatim; `javascript:` is still refused. Test: `test_support_url_accepts_a_variable_and_refuses_javascript` (Task 4).
4. Two management ports with one name are a readable `422`, not a `500`. Test: `test_duplicate_management_port_is_a_rule_error` (Task 3).
5. The migration on a database where the plan 1 backfill has not run stops with a message that says what to do, and changes nothing. Test: `test_migration_stops_while_a_legacy_link_remains` (Task 1).

---

### Task 1: Migration

**Files:** Create `database/migrations/20261124000002_odps_product_metadata.sql`; modify `database/migrations/atlas.sum`, `tests/integration/odps_schema.py` (control tables in `BASE_DDL`, `run_plan_2`, `migrated` runs both plans); create `tests/integration/test_odps_metadata_migration.py`.

**Interfaces — Produces:** columns `data_products.(version, type, tenant, description JSONB, tags, synonyms, context, team, support, custom_properties, authoritative_definitions)`; `data_product_ports.(tags, custom_properties, synonyms, context, sbom)` with `chk_dpp_output_only` extended; table `catalog.data_product_management_ports` with `uq_dmp_name`, `chk_dmp_type`.

- [ ] **Step 1: Failing tests**

```python
async def test_text_description_becomes_purpose(conn): ...    # 'Old text' -> {"purpose": "Old text", "usage": "", "limitations": ""}; '' -> purpose ""
async def test_new_sections_default_to_empty(db): ...          # tags/synonyms/support/... '[]', context/team '{}', version/type/tenant NULL
async def test_migration_stops_while_a_legacy_link_remains(conn): ...  # RaiseError "run the ODPS plan 1 backfill"; data_contracts_id still there
async def test_data_contracts_id_is_gone(db): ...
async def test_control_tables_are_gone(db): ...
async def test_migration_stops_when_control_tables_hold_rows(conn): ...
async def test_input_port_refuses_synonyms_context_and_sbom(db, field): ...   # chk_dpp_output_only, parametrized
async def test_input_port_takes_tags_and_custom_properties(db): ...
async def test_management_port_type_is_rest_or_topic(db): ...  # default 'rest'; 'grpc' -> chk_dmp_type
async def test_management_port_names_are_unique_per_product(db): ...   # uq_dmp_name
async def test_deleting_a_product_deletes_its_management_ports(db): ...
```

- [ ] **Step 2:** run, expect FAIL (file missing). **Step 3:** write the migration:

```sql
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM catalog.data_products WHERE data_contracts_id IS NOT NULL) THEN
        RAISE EXCEPTION 'data products still linked by data_contracts_id: run the ODPS plan 1 backfill (start the backend on plan 1 once) before this migration';
    END IF;
    IF EXISTS (SELECT 1 FROM platform.control_ports) OR EXISTS (SELECT 1 FROM platform.control_port_types) THEN
        RAISE EXCEPTION 'platform control-port tables hold rows; move them to catalog.data_product_management_ports before this migration';
    END IF;
END $$;
ALTER TABLE catalog.data_products DROP COLUMN data_contracts_id;
DROP TABLE platform.control_ports, platform.control_port_types;

ALTER TABLE catalog.data_products
    ALTER COLUMN description TYPE JSONB USING jsonb_build_object(
        'purpose', description, 'usage', '', 'limitations', ''),
    ALTER COLUMN description SET DEFAULT '{"purpose": "", "usage": "", "limitations": ""}',
    ADD COLUMN version TEXT, ADD COLUMN type TEXT, ADD COLUMN tenant TEXT,
    ADD COLUMN tags JSONB NOT NULL DEFAULT '[]', ADD COLUMN synonyms JSONB NOT NULL DEFAULT '[]',
    ADD COLUMN context JSONB NOT NULL DEFAULT '{}', ADD COLUMN team JSONB NOT NULL DEFAULT '{}',
    ADD COLUMN support JSONB NOT NULL DEFAULT '[]',
    ADD COLUMN custom_properties JSONB NOT NULL DEFAULT '[]',
    ADD COLUMN authoritative_definitions JSONB NOT NULL DEFAULT '[]';

ALTER TABLE catalog.data_product_ports
    ADD COLUMN tags JSONB NOT NULL DEFAULT '[]',
    ADD COLUMN custom_properties JSONB NOT NULL DEFAULT '[]',
    ADD COLUMN synonyms JSONB NOT NULL DEFAULT '[]',
    ADD COLUMN context JSONB NOT NULL DEFAULT '{}',
    ADD COLUMN sbom JSONB NOT NULL DEFAULT '[]',
    DROP CONSTRAINT chk_dpp_output_only,
    ADD CONSTRAINT chk_dpp_output_only CHECK (
        role = 'output' OR (type IS NULL AND description IS NULL
            AND input_contracts = '[]' AND synonyms = '[]' AND context = '{}' AND sbom = '[]'));

CREATE TABLE catalog.data_product_management_ports (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    data_product_id UUID NOT NULL REFERENCES catalog.data_products(id) ON DELETE CASCADE,
    name TEXT NOT NULL, content TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'rest', url TEXT, channel TEXT, description TEXT,
    deprecated BOOLEAN NOT NULL DEFAULT false,
    tags JSONB NOT NULL DEFAULT '[]', custom_properties JSONB NOT NULL DEFAULT '[]',
    authoritative_definitions JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT data_product_management_ports_pkey PRIMARY KEY (id),
    CONSTRAINT chk_dmp_type CHECK (type IN ('rest', 'topic')),
    CONSTRAINT uq_dmp_name UNIQUE (data_product_id, name)
);
```

- [ ] **Step 4:** run, expect PASS; plan 1's migration tests still pass on `before_plan_1 + run_plan_1`. **Step 5:** regenerate `atlas.sum`, validate with `arigaio/atlas:1.3.6`. **Step 6:** commit `feat(db): ODPS product metadata, management ports, drop data_contracts_id (ODPS plan 2)`.

---

### Task 2: Aggregate and removal of the plan 1 backfill

**Files:** Modify `backend/domain/entities/data_product.py`, `tests/unit/test_data_product_aggregate.py`; delete `backend/use_cases/data_product/backfill.py`, `scripts/backfill_output_ports.py`, their tests, the `entrypoint.sh` line, `LegacyProduct` and `list_legacy_products` (interface, repository, tests, `n1` parameter).

**Interfaces — Produces:**
- `@dataclass(frozen=True) ManagementPort(name: str, content: str, type: str = "rest", url: str | None = None, channel: str | None = None, description: str | None = None, deprecated: bool = False, tags: tuple[str, ...] = (), custom_properties: tuple[dict, ...] = (), authoritative_definitions: tuple[dict, ...] = (), id: UUID | None = None)`
- `InputPort` gains `tags: tuple[str, ...] = ()`, `custom_properties: tuple[dict, ...] = ()`. `OutputPort` gains those plus `synonyms: tuple[dict, ...] = ()`, `context: dict = field(default_factory=dict)` (hash=False), `sbom: tuple[dict, ...] = ()`.
- `PRODUCT_SECTIONS = ("version", "type", "tenant", "tags", "synonyms", "context", "team", "support", "custom_properties", "authoritative_definitions")`; `DataProduct.__init__` takes them keyword-only with empty defaults (`None` for the three texts, `()` for lists, `{}` for objects), `description: dict` (default `empty_product_description()`), and `management_ports: Iterable[ManagementPort] = ()`.
- `DataProduct.revised(**fields)` takes every editable field (`EDITABLE_FIELDS`) and keeps identity and read-only fields; the retired rule is unchanged.
- `empty_product_description() -> dict` in the same module: `{"purpose": "", "usage": "", "limitations": ""}`.

- [ ] **Step 1: Failing tests** — `test_sections_default_to_empty`, `test_revised_carries_every_editable_field`, `test_management_ports_are_kept_as_a_tuple`, `test_description_defaults_to_the_three_texts`; the existing aggregate tests updated for `description` as a dict.
- [ ] **Step 2:** FAIL. **Step 3:** implement; delete the backfill code and its tests. **Step 4:** aggregate and use-case tests PASS. **Step 5:** commit `feat(domain): ODPS product sections and management ports; drop the plan 1 backfill`.

---

### Task 3: Repository

**Files:** Modify `backend/infra/repositories/data_product_repository.py`, `tests/integration/test_data_product_repository.py`, `tests/unit/infra/test_data_product_repository.py`, `tests/unit/test_n1_detection.py`.

- Product row: insert and update write the ten sections and `description` as JSON; read parses them. `replace` no longer touches `data_contracts_id`.
- Ports: the replace statement gains the five JSONB columns (as `text[]` cast to `jsonb`, like `authoritative_definitions`).
- Management ports: a second statement of the same shape keyed by `name` (`ON CONFLICT ON CONSTRAINT uq_dmp_name`), deleting names left out; read as a second `LEFT JOIN LATERAL json_agg` in `_SELECT` (one query still).
- Error map additions: `chk_dmp_type` → `Management port type must be rest or topic`; duplicate management port names (cardinality) → `Two management ports share the name {name}; each needs its own`; `chk_dpp_output_only` message adds synonyms, context and SBOM.

- [ ] **Step 1: Failing tests** — integration: `test_sections_round_trip`, `test_variables_are_stored_verbatim` (`"${ENV}"` in version, tenant, a support URL), `test_management_ports_round_trip_and_keep_ids`, `test_management_ports_left_out_are_deleted`, `test_duplicate_management_port_is_a_rule_error`, `test_output_port_extras_round_trip`; unit: `chk_dmp_type` mapping; `n1`: `add` and `replace` cost `(2, 0, 1, 1)` with one and five ports and management ports (row, ports, management ports, read-back).
- [ ] **Step 2:** FAIL. **Step 3:** implement. **Step 4:** PASS with `TEST_DATABASE_URL`. **Step 5:** commit `feat(catalog): persist ODPS product sections and management ports`.

---

### Task 4: API and use cases

**Files:** Create `backend/interface/schemas/odps.py` (shared ODPS/ODCS row models); modify `backend/interface/schemas/data_contract.py` (imports `TeamMember`, `SupportChannel` from the shared module instead of defining them), `backend/interface/schemas/data_product.py`, `backend/interface/routers/data_product.py`, `backend/use_cases/data_product/save.py`, `backend/domain/contract_metadata.py` (`support_url_problem(url, allow_variables=False)`), and their tests.

**Interfaces — Produces** (in `schemas/odps.py`, every model `extra="forbid"`):
- `CustomProperty(property: NonEmptyStr, value: Any, description: str | None, vendor: str | None, id: str | None)` — `value` required and not `None`.
- `AuthoritativeDefinition(type: NonEmptyStr, url: NonEmptyStr, description: str | None, id: str | None)`.
- `_Annotated` mixin: `tags: list[str] = []`, `custom_properties: list[CustomProperty] = []`, `authoritative_definitions: list[AuthoritativeDefinition] = []`.
- `TeamMember(username: NonEmptyStr, name, role, description, date_in, date_out, replaced_by_username, id)` + annotations — the contract keeps using `username`, `name`, `role` (its form sends only those; extra optional fields default to `None`, so contract payloads are unchanged).
- `SupportChannel(channel: NonEmptyStr, url: str = "", tool, scope, description, invitation_url, id)` + annotations, URL checked by `support_url_problem` — the contract's model. `ProductSupportChannel(SupportChannel)`: `url` required non-empty and `${VAR}` accepted.
- `Team(name, description, members: list[TeamMember], id)` + annotations; `Synonym(synonym: NonEmptyStr, description, locale, source, status, id, custom_properties)`; `VerifiedStatement(question: NonEmptyStr, answer, id)` + annotations; `ContextConstraint(constraint: NonEmptyStr, id)` + annotations; `Context(instructions: str | None, verified_statements: list[VerifiedStatement] = [], constraints: list[ContextConstraint] = [])`; `Sbom(type, url, id)` + annotations; `ProductDescription(purpose: str = "", usage: str = "", limitations: str = "", authoritative_definitions, custom_properties)`; `ManagementPortModel(name: NonEmptyStr, content: NonEmptyStr, type: str = "rest", url, channel, description, deprecated: bool = False, id)` + annotations.
- `DataProductWriteModel` gains `description: ProductDescription`, the ten sections and `management_ports`; port models gain their fields. Responses echo them.
- `save.py` passes the sections through unchanged (the aggregate does not read them); its field list becomes `EDITABLE_FIELDS`.

- [ ] **Step 1: Failing tests** — `test_support_url_accepts_a_variable_and_refuses_javascript`, `test_product_support_needs_a_url`, `test_custom_property_needs_a_value`, `test_unknown_ods_key_is_refused` (`team.members[0].colour`), `test_input_port_refuses_synonyms` (422 from the model), `test_create_passes_every_section_to_the_use_case`, `test_response_echoes_sections_and_management_ports`, `test_readme_uses_the_purpose`; contract router tests unchanged and green.
- [ ] **Step 2:** FAIL. **Step 3:** implement. **Step 4:** full backend suite PASS. **Step 5:** commit `feat(api): every ODPS product field on the data product API`.

---

### Task 5: Frontend model and shared row editors

**Files:** Move `frontend/src/pages/DataContracts/{EditableRows,TeamMembers,SupportChannels}.tsx` to `frontend/src/components/rows/` (update imports in contracts, products and `rowEditors.test.tsx`); modify `frontend/src/types/index.ts`, `frontend/src/lib/products.ts` (+ test), `frontend/src/test/fixtures.ts`.

**Interfaces — Produces:** TS types mirroring Task 4 (`ProductDescription`, `CustomProperty`, `AuthoritativeDefinition`, `Synonym`, `ProductContext`, `Team`, `ProductSupport`, `Sbom`, `ManagementPort`), `DataProduct`/`DataProductInput` with the sections; `toInput` keeps the sections and management ports (dropping only ids and read-only fields of ports); `PRODUCT_TYPES = ['sourceAligned', 'aggregate', 'consumerAligned']`, `MANAGEMENT_CONTENTS = ['discoverability', 'observability', 'control', 'dictionary']`.

- [ ] Steps: failing `toInput` test for sections and management ports → move components (tests still pass) → implement types → PASS → commit `refactor(frontend): share the ODCS row editors; ODPS product types`.

---

### Task 6: "More ODPS fields" and management ports in the form

**Files:** Create `frontend/src/pages/DataProducts/MoreFields.tsx` (+ test); modify `DataProductForm.tsx` (+ test), `PortEditors.tsx` (+ test).

The short path stays: Name, Domain, Status, Description (bound to `description.purpose`), Outputs, Inputs. Below, a collapsed **More ODPS fields** disclosure (`<details>`), with five groups, each with one line saying what it is for:
- *About* — version (placeholder `1.0.0`), type (datalist of `PRODUCT_TYPES`), tenant, usage, limitations, tags (comma-separated), synonyms (rows: synonym, status, source).
- *People* — team name, team description, members (shared `TeamMembers`), support (shared `SupportChannels`, URL required).
- *For AI agents* — instructions (textarea), constraints (rows), verified statements (rows: question, answer).
- *Links* — authoritative definitions (rows: type, url, description), custom properties (rows: property, value).
- *Management ports* — rows: name, content (datalist `MANAGEMENT_CONTENTS`), type (`rest`/`topic`), url, channel, description.
Each output row gains a "More" toggle with tags, SBOM links (rows: type, url) and context instructions; each input row gains tags. Zod: required fields of these rows only; objects are `looseObject`, so fields the form does not show round-trip.

- [ ] Steps: failing tests (`the short path does not show the ODPS sections until opened`, `edits each group and submits it`, `submits nested ODPS fields it does not edit unchanged`, `a support channel needs a URL`, `a management port needs a name and a content`, `an output carries tags, SBOM links and context`) → implement → PASS → commit `feat(frontend): More ODPS fields and management ports in the product form`.

---

### Task 7: Screens that read the new fields

**Files:** modify `DataProductDetail.tsx` (About shows purpose, usage and limitations; a "Details" panel lists version, type, tenant, tags, team, support and management ports when filled), `pages/DataProducts/index.tsx` and `dashboard/overview.ts` (`description.purpose`), their tests.

- [ ] Steps: failing tests → implement → full frontend gate (`test:coverage`, `lint`, `build`) → commit `feat(frontend): show the ODPS sections on the product page`.

---

### Task 8: End to end

- [ ] Isolated compose stack (own network): database migrated to plan 1 with one legacy product; start the backend on plan 1's image once (backfill), then on this branch: plan 2 migrates; a second fresh database left at the plan 1 schema with a legacy link refuses plan 2 with the backfill message.
- [ ] API scenario: create a product with every section, `${VAR}` values and two management ports; read it back verbatim; edit it keeping ids.
- [ ] Backend and frontend gates; push; open the PR against `feat/odps-1-ports-status-domain`, noting the release gate in its description.
