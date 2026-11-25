# ODPS Plan 1 — Ports, Status, Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the one-contract data product into an ODPS product with input and output ports, an ODPS status and its own domain, with rules 1–4, a contract usage endpoint, existing products migrated, and the screens to use it day to day.

**Architecture:** `DataProduct` becomes the aggregate root that owns `InputPort` and `OutputPort` value objects and checks its own invariants in memory. Ports live in `catalog.data_product_ports`, written with their product in one batched statement and read with it in one query that also carries each port's contract summary and lineage. References to contracts are a composite foreign key to `catalog.contract_versions`; the repository turns every constraint violation into a `DataProductRuleError`. A command run by `entrypoint.sh` gives each existing product its output port before the app serves.

**Tech Stack:** Python 3.12, FastAPI, asyncpg, PostgreSQL 16, Atlas, React 18, react-hook-form, zod 4, TanStack Query, Vitest.

**Spec:** `docs/superpowers/specs/2026-11-24-odps-adoption-design.md` (Decisions, Calls Made by the Designer, Engineering Principles, Target Data Model, Rules and Where They Live, API, UI/UX, Plan 1).

**Starting point:** `develop` at `c0e25a6`. Branch `feat/odps-1-ports-status-domain`.

## Global Constraints

- Product status values, exactly: `proposed`, `draft`, `active`, `deprecated`, `retired`. New products default to `draft`; migrated products are `active`. `retired` is terminal.
- `deprecated` on the product is derived: `status in ("deprecated", "retired")`. Ports keep their own `deprecated` flag.
- Rule 1: a product has at least one output port. Message: `A data product needs at least one output`.
- Rule 2: `contract_id` is optional on any port.
- Rule 3: a port with `contract_id` must point at an existing `(contract_id, version)` in `catalog.contract_versions`. Message: `Version {version} of contract {title} does not exist`, or `Contract {contract_id} does not exist`.
- Rule 4: an input port cannot be *written* pointing at a `retired` contract; `deprecated` gives a warning. Only ports that are new or changed by the request are checked.
- `input_contracts` on an output port may only cite `(contract_id, version)` pairs of the product's own input ports.
- A port's version is pinned; when a port names a contract and no version, the version is the contract's current one.
- Ports are matched on update by `(role, name, version)` so they keep their `id`.
- Validation errors: HTTP `422`, `detail` is a list of `{"msg": <message>}`, one per broken rule. Warnings: `warnings: list[str]` on a successful write.
- Migration version `20261124000001`. The backfill command is deleted by Plan 2.
- Names are ODPS names everywhere: `InputPort`, `OutputPort`, `contract_id`, `version`, `input_contracts`, `produced_by`, `consumed_by`. No "binding", "link", "dependency".
- A request runs a fixed number of queries whatever the number of ports; every new repository method gets an `n1` test.
- CI gates: ruff `C90` ≤ 15, Python and React coverage ≥ 80 %, mutation ≥ 70 % (`backend/domain/entities/`, `backend/use_cases/`).
- Backend tests: `.venv\Scripts\python.exe -m pytest tests/ -q`; DB tests need `TEST_DATABASE_URL=postgres://postgres@127.0.0.1:55439/postgres` from `docker run -d --rm --name odps-pg -e POSTGRES_HOST_AUTH_METHOD=trust -p 127.0.0.1:55439:5432 postgres:16.1`.
- Frontend, from `frontend/`: `npm test`, `npm run lint`, `npm run build`.
- Lint with `.venv\Scripts\ruff check backend` (never pass `tests/` paths). `git commit` needs `.venv\Scripts` first on `PATH`.
- `atlas.sum`: copy `database/migrations` to a scratch dir, run `MSYS_NO_PATHCONV=1 docker run --rm -v "<copy>:/migrations" arigaio/atlas:latest migrate hash --dir file:///migrations`, copy `atlas.sum` back. Never mount the real dir.
- Commit messages and PR text carry no Claude or Claude Code attribution of any kind.

## Review Focus

1. An edit re-sends an input port whose contract was retired after the port was created (for example, the user only renames the product). It must save; only new or changed input ports are checked. Test: `test_unchanged_input_on_a_retired_contract_still_saves` (Task 4).
2. A port names a contract id that does not exist. It must be a `422` saying so, not a `500`. Test: `test_unknown_contract_is_a_rule_error` (Task 3).
3. The same port is sent twice (an output added twice, "Switch" clicked twice). The upsert raises a cardinality error, not the unique one; it must still be a readable `422`. Test: `test_duplicate_port_key_is_a_rule_error` (Task 3), and the form's duplicate message (Task 7).
4. An external input (no contract, `version` NULL) survives an edit with its `id` intact, under the `NULLS NOT DISTINCT` key. Test: `test_replace_keeps_port_ids_including_null_versions` (Task 3).
5. A legacy contract title with accents or no letters becomes a usable port name in the backfill: `Exposição de Crédito` → `exposicao-de-credito`, `???` → `output`. Test: `test_port_name_from_title` (Task 2) and `test_backfill_names_the_port_from_the_contract_title` (Task 4).

## Decisions Made While Planning

Measured on `postgres:16.1` while writing this plan:

- **Replace ports in one statement.** A data-modifying CTE deletes the rows whose key is not in the incoming set and upserts the rest with `ON CONFLICT ON CONSTRAINT uq_dpp_key DO UPDATE`. With `UNIQUE NULLS NOT DISTINCT`, a port with `version` NULL is matched and keeps its `id` across writes.
- **Duplicate keys in one payload** fail the upsert with `21000 cardinality_violation` ("cannot affect row a second time"), never with `uq_dpp_key`. The repository maps `asyncpg.CardinalityViolationError` to the duplicate-port message; the unique key stays the owner of the rule.
- **Unknown version** fails with `23503` on `fk_dpp_contract_version`. The repository then runs one lookup (error path only, inside the use case transaction after the savepoint rolled back) to name every missing reference with its contract title.
- **Deleting a contract a port uses** fails with `23503` on the same constraint, raised from `contract_versions` by the cascade; the immutability trigger lets the cascade through first. Nothing is deleted.
- **Index on `data_product_id`:** the key `(data_product_id, role, name, version)` already has a btree led by `data_product_id`, so no second index is created (no redundancy). `(contract_id, version)` gets its own index.
- **Backfill through the aggregate.** `replace` always writes `data_contracts_id = NULL`, since Plan 1 removes the field from the API. The backfill builds each legacy product as a `DataProduct` with one output port and calls `replace`; no special write path exists.
- **Baselines in one statement.** `add_baseline_version` becomes `add_baseline_versions(baselines)`, an `unnest` insert with `ON CONFLICT DO NOTHING`, so the product save writes the baselines of all referenced contracts in one query. Versioning passes a one-element list.
- **Read model on the ports.** The ports carry, read-only (`compare=False`), the contract summary (`title`, `status`, current `version`, `domain`) and the products on the other side of the same contract version: `produced_by` on inputs, `consumed_by` on outputs. The product page needs one request.
- **Status validation lives in the aggregate** (plus the DB check as backstop); the API takes `status: str`, so the rule is written once in backend code.
- **Domain delete** now also fails when products use the domain (`ON DELETE RESTRICT`); its message says so.
- **Slug.** One `slugify` in `backend/domain/naming.py` (NFKD, ASCII, hyphens) serves the GitHub repo name and the backfill port name; the router's private copy is deleted.

---

### Task 1: Migration

**Files:**
- Create: `database/migrations/20261124000001_odps_ports_status_domain.sql`
- Modify: `database/migrations/atlas.sum`
- Create: `tests/integration/odps_schema.py` (shared DDL + fixture helper)
- Create: `tests/integration/test_odps_ports_migration.py`

**Interfaces:**
- Produces: tables and constraint names used by Task 3: `catalog.data_product_ports` with `uq_dpp_key`, `fk_dpp_contract_version`, `chk_dpp_role`, `chk_dpp_contract_version`, `chk_dpp_output_only`; `catalog.data_products.domain_id`, `.status` (`chk_dp_status`).
- Produces: `tests/integration/odps_schema.py: BASE_DDL: str`, `async def migrated(conn) -> None` (runs `BASE_DDL` then the migration file).

- [ ] **Step 1: Write the migration**

```sql
-- 1. The product's own domain, from its current contract.
ALTER TABLE catalog.data_products
    ADD COLUMN domain_id UUID REFERENCES catalog.domains(id) ON DELETE RESTRICT;
UPDATE catalog.data_products p SET domain_id = dc.domain_id
FROM catalog.data_contracts dc WHERE dc.id = p.data_contracts_id;
ALTER TABLE catalog.data_products ALTER COLUMN domain_id SET NOT NULL;
CREATE INDEX idx_data_products_domain ON catalog.data_products(domain_id);

-- 2. ODPS status: existing products are live, new ones start as draft.
ALTER TABLE catalog.data_products
    ADD COLUMN status TEXT NOT NULL DEFAULT 'active'
    CONSTRAINT chk_dp_status
    CHECK (status IN ('proposed', 'draft', 'active', 'deprecated', 'retired'));
ALTER TABLE catalog.data_products ALTER COLUMN status SET DEFAULT 'draft';

-- 3. The single contract becomes an output port (backfill command); Plan 2 drops it.
ALTER TABLE catalog.data_products ALTER COLUMN data_contracts_id DROP NOT NULL;

-- 4. Ports.
CREATE TABLE catalog.data_product_ports (
    id              UUID        NOT NULL DEFAULT gen_random_uuid(),
    data_product_id UUID        NOT NULL
                    REFERENCES catalog.data_products(id) ON DELETE CASCADE,
    role            TEXT        NOT NULL,
    name            TEXT        NOT NULL,
    version         TEXT,
    contract_id     UUID,
    type            TEXT,
    description     TEXT,
    deprecated      BOOLEAN     NOT NULL DEFAULT false,
    authoritative_definitions JSONB NOT NULL DEFAULT '[]',
    input_contracts JSONB       NOT NULL DEFAULT '[]',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT data_product_ports_pkey PRIMARY KEY (id),
    CONSTRAINT chk_dpp_role CHECK (role IN ('input', 'output')),
    CONSTRAINT chk_dpp_contract_version CHECK (contract_id IS NULL OR version IS NOT NULL),
    CONSTRAINT chk_dpp_output_only CHECK (
        role = 'output'
        OR (type IS NULL AND description IS NULL AND input_contracts = '[]'::jsonb)),
    -- Its btree, led by data_product_id, also serves lookups by product.
    CONSTRAINT uq_dpp_key UNIQUE NULLS NOT DISTINCT (data_product_id, role, name, version),
    -- MATCH SIMPLE: skipped when contract_id is NULL, so a free version stays free.
    CONSTRAINT fk_dpp_contract_version FOREIGN KEY (contract_id, version)
        REFERENCES catalog.contract_versions(contract_id, version) ON DELETE RESTRICT
);
CREATE INDEX idx_dpp_contract ON catalog.data_product_ports(contract_id, version);

-- 5. The platform data-port tables were never used; stop if that is not true.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM platform.product_port_binding)
       OR EXISTS (SELECT 1 FROM platform.data_ports)
       OR EXISTS (SELECT 1 FROM platform.data_ports_type) THEN
        RAISE EXCEPTION 'platform data-port tables hold rows; move them to catalog.data_product_ports before this migration';
    END IF;
END $$;
DROP TABLE platform.product_port_binding, platform.data_ports, platform.data_ports_type;
DROP TYPE platform.port_role_type, platform.binding_status;
```

Header comment as in `20261101000005`: Atlas owns the transaction; grants come from `ALTER DEFAULT PRIVILEGES` (`20260428000001`, `20260401000001`). Footer: a `ROLLBACK` block in comments.

- [ ] **Step 2: Write `tests/integration/odps_schema.py`** with `BASE_DDL` holding, in the shapes the earlier migrations leave: roles `admin`/`app_user` (as in `test_contract_versions_migration.py`), schemas `catalog` and `platform`, `catalog.domains (id, name)`, `catalog.data_contracts (id, title, version, owner, domain_id, tier, status, models, servicelevels, description, team_members, support, servers, created_at, updated_at)` with JSONB defaults, `catalog.contract_versions` (by running `20261101000005_contract_versions.sql` after a `chk_dc_status` constraint), `catalog.data_products (id, name, description, data_contracts_id NOT NULL REFERENCES data_contracts ON DELETE RESTRICT, repo_url, created_at, updated_at)`, and the platform enums and three tables from `20260326000001_create_ddl.sql`. `migrated(conn)` executes `BASE_DDL` then the Plan 1 file. Tests use it inside a rolled-back transaction, as the other migration tests do.

- [ ] **Step 3: Write the failing migration tests** in `tests/integration/test_odps_ports_migration.py` (skipped without `TEST_DATABASE_URL`):

```python
async def test_existing_product_takes_its_contracts_domain_and_is_active(db): ...
    # product inserted before the migration -> domain_id == contract.domain_id, status == "active"
async def test_new_product_defaults_to_draft(db): ...
async def test_unknown_status_is_refused(db): ...                  # CheckViolationError chk_dp_status
async def test_port_without_contract_keeps_a_free_version(db): ...  # version "x" accepted, contract_id NULL
async def test_port_on_a_missing_contract_version_is_refused(db): ...  # ForeignKeyViolationError fk_dpp_contract_version
async def test_contract_port_needs_a_version(db): ...              # CheckViolationError chk_dpp_contract_version
async def test_input_port_refuses_output_only_fields(db): ...      # type="tables" on role input -> chk_dpp_output_only
async def test_deleting_a_used_contract_fails_and_keeps_history(db): ...
    # ForeignKeyViolationError on fk_dpp_contract_version; contract and version rows still there
async def test_deleting_a_product_deletes_its_ports(db): ...
async def test_platform_data_port_tables_are_gone(db): ...         # to_regclass(...) is None for the three
async def test_migration_stops_when_platform_data_ports_hold_rows(db_before): ...
    # BASE_DDL, insert a data_ports_type row, run the file -> RaiseError matching "hold rows"
```

- [ ] **Step 4: Run them, expect FAIL** (file missing): `$env:TEST_DATABASE_URL="postgres://postgres@127.0.0.1:55439/postgres"; .venv\Scripts\python.exe -m pytest tests/integration/test_odps_ports_migration.py -q`.
- [ ] **Step 5: Add the migration file, rerun, expect PASS.**
- [ ] **Step 6: Regenerate `atlas.sum`** with the recipe in Global Constraints; `git diff database/migrations/atlas.sum` shows the total hash line and one new line.
- [ ] **Step 7: Commit** `feat(db): data product ports, ODPS status and domain (ODPS plan 1)`.

---

### Task 2: The aggregate

**Files:**
- Create: `backend/domain/naming.py`
- Rewrite: `backend/domain/entities/data_product.py`
- Create: `tests/unit/test_data_product_aggregate.py`
- Modify: `tests/unit/test_entities.py` (drop the old `DataProduct` test)

**Interfaces:**
- Produces, `backend/domain/naming.py`: `slugify(text: str) -> str` — NFKD, drop combining marks, lowercase, runs of non-`[a-z0-9]` to `-`, strip `-`.
- Produces, `backend/domain/entities/data_product.py`:
  - `PRODUCT_STATUSES = ("proposed", "draft", "active", "deprecated", "retired")`, `RETIRED_PRODUCT = "retired"`
  - `@dataclass(frozen=True) ContractRef(contract_id: UUID, version: str)`
  - `@dataclass(frozen=True) ContractSummary(title: str, status: str, version: str, domain: str)`
  - `@dataclass(frozen=True) ProductRef(id: UUID, name: str, status: str)`
  - `@dataclass(frozen=True) InputPort(name: str, contract_id: UUID | None = None, version: str | None = None, deprecated: bool = False, authoritative_definitions: tuple[dict[str, str], ...] = (), id: UUID | None = None, contract: ContractSummary | None = field(default=None, compare=False), produced_by: tuple[ProductRef, ...] = field(default=(), compare=False))`
  - `@dataclass(frozen=True) OutputPort(name, contract_id=None, version=None, type: str | None = None, description: str | None = None, deprecated=False, authoritative_definitions=(), input_contracts: tuple[ContractRef, ...] = (), id=None, contract=field(..., compare=False), consumed_by: tuple[ProductRef, ...] = field(default=(), compare=False))`
  - `@dataclass(frozen=True) PortUsage(product_id: UUID, product_name: str, domain: str, status: str, role: str, port_name: str, contract_id: UUID, version: str)`
  - `class DataProductRuleError(Exception)` with `.messages: list[str]`, `str()` = messages joined by `"; "`.
  - `class DataProduct` — keyword-only `__init__(*, name, description, domain_id, status="draft", input_ports=(), output_ports=(), id=None, domain="", repo_url=None, created_at=None, updated_at=None)`; stores ports as tuples; raises `DataProductRuleError` with every broken rule. `deprecated` property. `revised(*, name, description, domain_id, status, input_ports, output_ports) -> DataProduct` keeps `id`, `domain`, `repo_url`, `created_at`, `updated_at` and refuses to leave `retired`.

- [ ] **Step 1: Write the failing tests**

```python
def test_port_name_from_title():
    assert slugify("Exposição de Crédito") == "exposicao-de-credito"
    assert slugify("  Orders / EU  ") == "orders-eu"
    assert slugify("???") == ""

def test_a_product_needs_an_output():
    with pytest.raises(DataProductRuleError) as e:
        DataProduct(name="P", description="d", domain_id=D)
    assert e.value.messages == ["A data product needs at least one output"]

def test_status_must_be_an_odps_value():  # "live" -> message lists the five values
def test_new_products_are_drafts():        # DataProduct(...).status == "draft"
@pytest.mark.parametrize("status, deprecated", [("draft", False), ("active", False), ("deprecated", True), ("retired", True), ("proposed", False)])
def test_deprecated_follows_status(status, deprecated): ...

def test_input_contracts_must_cite_own_inputs():
    # output cites (C2, "1.0.0") while the only input is (C1, "1.0.0")
    # -> one message naming the output and "C2" "1.0.0"
def test_input_contracts_may_cite_an_own_input(): ...   # no error
def test_external_input_cannot_be_cited():  # input without contract; output cites (C1, "1.0.0") -> error
def test_all_broken_rules_are_reported_together(): ...  # bad status + no output -> 2 messages

def test_revised_keeps_identity_and_read_fields(): ...  # id, created_at, repo_url, domain kept; name changed
def test_a_retired_product_cannot_leave_retired():
    # revised(status="active") -> ["A retired data product cannot change status"]
def test_a_retired_product_can_still_be_edited(): ...   # revised(status="retired", name="New") ok

def test_ports_compare_without_read_fields():
    assert InputPort("a", C1, "1.0.0") == InputPort("a", C1, "1.0.0", produced_by=(ProductRef(P, "x", "active"),))
```

- [ ] **Step 2: Run, expect FAIL** (import error).
- [ ] **Step 3: Implement** `naming.py` and `data_product.py`. Messages, exactly:
  - `A data product needs at least one output`
  - `Status must be one of: proposed, draft, active, deprecated, retired`
  - `Output {name} is built from version {version} of contract {contract_id}, which is not one of this product's inputs`
  - `A retired data product cannot change status`
- [ ] **Step 4: Run, expect PASS**; `ruff check backend`.
- [ ] **Step 5: Commit** `feat(domain): DataProduct aggregate with ODPS ports and status`.

---

### Task 3: Repositories

**Files:**
- Rewrite: `backend/domain/interfaces/data_product_repository.py`, `backend/infra/repositories/data_product_repository.py`
- Modify: `backend/domain/interfaces/data_contract_repository.py`, `backend/infra/repositories/data_contract_repository.py`, `backend/domain/entities/contract_version.py`, `backend/use_cases/data_contract/versioning.py`, `backend/infra/repositories/domain_repository.py`
- Create: `tests/integration/test_data_product_repository.py`, `tests/unit/infra/test_data_product_repository.py`
- Modify: `tests/unit/infra/test_contract_versions_repository.py`, `tests/unit/use_cases/data_contract/test_versioning.py`, `tests/unit/test_n1_detection.py`

**Interfaces:**
- Consumes: Task 1 constraint names; Task 2 types.
- Produces, `backend/domain/entities/contract_version.py`: `class ContractBaseline(NamedTuple): contract_id: UUID; version: str; yaml_content: str; created_at: datetime`.
- Produces, `IDataContractRepository`: `list_by_ids(contract_ids: list[UUID]) -> list[DataContract]`; `add_baseline_versions(baselines: list[ContractBaseline]) -> None` (replaces `add_baseline_version`; no query for `[]`).
- Produces, `versioning.py`: `baseline(contract: DataContract, document: dict | None = None) -> ContractBaseline` (document defaults to `to_odcs(contract)`; `created_at = contract.updated_at`).
- Produces, `IDataProductRepository`:
  - `transaction() -> AbstractAsyncContextManager[Any]`
  - `add(product: DataProduct) -> DataProduct` — inserts row and ports, returns the stored product (read back).
  - `replace(product: DataProduct) -> DataProduct | None` — updates the row (`data_contracts_id = NULL`, `updated_at = now()`), replaces ports by key, returns it read back; `None` when the id does not exist.
  - `get_by_id(product_id) -> DataProduct | None`, `list() -> list[DataProduct]` (newest `updated_at` first)
  - `delete(product_id) -> bool`, `update_repo_url(product_id, repo_url) -> None` (unchanged)
  - `list_port_usage(contract_ids: list[UUID]) -> list[PortUsage]` (no query for `[]`)
  - `list_legacy_products() -> list[LegacyProduct]`, with `class LegacyProduct(NamedTuple): id, name, description, domain_id, status, contract_id` in the interface module (Plan 2 deletes both).
  - Every write raises `DataProductRuleError` for constraint violations, never `asyncpg` errors.

- [ ] **Step 1: Write the failing SQL round-trip tests** in `tests/integration/test_data_product_repository.py`, on `migrated(conn)` from Task 1 with `PostgresDataProductRepository(conn)`:

```python
async def test_add_then_get_round_trips_every_port_field(db): ...
    # output with contract, type, description, input_contracts; external input with authoritative_definitions
async def test_read_carries_the_contract_summary(db): ...       # title, status, current version, domain name
async def test_input_lists_the_products_that_produce_it(db): ... # produced_by = (ProductRef(producer...),)
async def test_output_lists_the_products_that_consume_it(db): ... # consumed_by, own product excluded
async def test_replace_keeps_port_ids_including_null_versions(db): ...
async def test_replace_drops_ports_left_out_and_clears_the_legacy_link(db): ...
async def test_replace_of_a_missing_product_returns_none(db): ...
async def test_unknown_contract_version_is_a_rule_error(db):
    # messages == ["Version 9.9.9 of contract Orders does not exist"]
async def test_unknown_contract_is_a_rule_error(db):
    # messages == [f"Contract {cid} does not exist"]
async def test_duplicate_port_key_is_a_rule_error(db):
    # two outputs "x" v None -> ["Two outputs share the name x and version (none); each port needs its own"]
async def test_a_failed_write_leaves_the_transaction_usable(db): ...  # inside conn.transaction(), then a SELECT works
async def test_list_port_usage_returns_both_roles(db): ...
async def test_list_legacy_products_lists_only_linked_rows(db): ...
async def test_contract_delete_reports_the_ports_using_it(db):
    # PostgresDataContractRepository(conn).delete(cid) -> ValueError "2 data product ports use it"
async def test_add_baseline_versions_writes_all_and_keeps_existing(db): ...
async def test_domain_delete_mentions_products(db): ...
```

- [ ] **Step 2: Write the failing mocked-db tests** in `tests/unit/infra/test_data_product_repository.py` (error mapping without a database: `CardinalityViolationError`, `CheckViolationError` with `constraint_name="chk_dpp_output_only"`, an unmapped `IntegrityConstraintViolationError` re-raised) and `n1` tests in `tests/unit/test_n1_detection.py`, one per new method, each asserting the same fixed number of DB calls for a product with one port and with five: `add` and `replace` (row write, one ports statement, one read-back), and one call each for `get_by_id`, `list`, `list_port_usage`, `list_legacy_products`, `list_by_ids`, `add_baseline_versions`.
- [ ] **Step 3: Run, expect FAIL.**
- [ ] **Step 4: Implement.** The decisions the SQL encodes:

Read (one query for `get_by_id` and `list`):

```sql
SELECT p.id, p.name, p.description, p.domain_id, d.name AS domain, p.status,
       p.repo_url, p.created_at, p.updated_at, COALESCE(ports.items, '[]') AS ports
FROM catalog.data_products p
JOIN catalog.domains d ON d.id = p.domain_id
LEFT JOIN LATERAL (
    SELECT json_agg(json_build_object(
        'id', pt.id, 'role', pt.role, 'name', pt.name, 'version', pt.version,
        'contract_id', pt.contract_id, 'type', pt.type, 'description', pt.description,
        'deprecated', pt.deprecated,
        'authoritative_definitions', pt.authoritative_definitions,
        'input_contracts', pt.input_contracts,
        'contract', CASE WHEN dc.id IS NOT NULL THEN json_build_object(
            'title', dc.title, 'status', dc.status, 'version', dc.version, 'domain', cd.name) END,
        'counterparts', COALESCE(other.items, '[]')
    ) ORDER BY pt.role, pt.name, pt.created_at DESC) AS items
    FROM catalog.data_product_ports pt
    LEFT JOIN catalog.data_contracts dc ON dc.id = pt.contract_id
    LEFT JOIN catalog.domains cd ON cd.id = dc.domain_id
    LEFT JOIN LATERAL (
        SELECT json_agg(DISTINCT jsonb_build_object('id', op.id, 'name', op.name, 'status', op.status)) AS items
        FROM catalog.data_product_ports o
        JOIN catalog.data_products op ON op.id = o.data_product_id
        WHERE o.contract_id = pt.contract_id AND o.version = pt.version
          AND o.role <> pt.role AND o.data_product_id <> pt.data_product_id
    ) other ON true
    WHERE pt.data_product_id = p.id
) ports ON true
```

`counterparts` fills `produced_by` on inputs and `consumed_by` on outputs.

Replace ports (one statement; `add` uses the same statement after inserting the row):

```sql
WITH incoming AS (
    SELECT * FROM unnest($2::text[], $3::text[], $4::text[], $5::uuid[], $6::text[],
                         $7::text[], $8::bool[], $9::text[], $10::text[])
        AS u(role, name, version, contract_id, type, description, deprecated,
             authoritative_definitions, input_contracts)
), removed AS (
    DELETE FROM catalog.data_product_ports p
    WHERE p.data_product_id = $1 AND NOT EXISTS (
        SELECT 1 FROM incoming i WHERE i.role = p.role AND i.name = p.name
          AND i.version IS NOT DISTINCT FROM p.version)
)
INSERT INTO catalog.data_product_ports (data_product_id, role, name, version, contract_id,
    type, description, deprecated, authoritative_definitions, input_contracts)
SELECT $1, role, name, version, contract_id, type, description, deprecated,
       authoritative_definitions::jsonb, input_contracts::jsonb FROM incoming
ON CONFLICT ON CONSTRAINT uq_dpp_key DO UPDATE SET
    contract_id = EXCLUDED.contract_id, type = EXCLUDED.type,
    description = EXCLUDED.description, deprecated = EXCLUDED.deprecated,
    authoritative_definitions = EXCLUDED.authoritative_definitions,
    input_contracts = EXCLUDED.input_contracts, updated_at = now();
```

The row write and the ports statement run in `async with self.db.transaction()` (a savepoint inside the use case transaction). Error mapping, one dict from constraint name to a message builder plus the cardinality case:

| Violation | Message |
|---|---|
| `fk_dpp_contract_version`, `chk_dpp_contract_version` | one per missing reference, from the lookup below |
| `CardinalityViolationError` | `Two {inputs\|outputs} share the name {name} and version {version or "(none)"}; each port needs its own` — the first duplicate found in `product`'s ports |
| `chk_dpp_output_only` | `Only outputs can have a type, a description or input contracts` |
| `chk_dp_status` | the status message from Task 2 |
| `data_products_domain_id_fkey` | `Domain {domain_id} does not exist` |

Missing-reference lookup (error path only):

```sql
SELECT r.contract_id, r.version, dc.title
FROM unnest($1::uuid[], $2::text[]) AS r(contract_id, version)
LEFT JOIN catalog.data_contracts dc ON dc.id = r.contract_id
WHERE NOT EXISTS (SELECT 1 FROM catalog.contract_versions v
                  WHERE v.contract_id = r.contract_id AND v.version = r.version)
```

`list_port_usage`: one join of ports, products, domains filtered by `contract_id = ANY($1)`, ordered by role, product name, version. `list_legacy_products`: `WHERE data_contracts_id IS NOT NULL`. Contract delete: on `ForeignKeyViolationError`, count ports by `contract_id` and raise `ValueError("Cannot delete this contract: {n} data product port{s} use it. Remove those ports first.")`. Domain delete message: `Cannot delete this domain because data contracts or data products still use it. Move or remove them first.`

- [ ] **Step 5: Update `versioning.apply_evolution`** to `await repository.add_baseline_versions([baseline(previous, previous_doc)])` and its tests to the new call; update `test_contract_versions_repository.py` for `add_baseline_versions` (`unnest`, `ON CONFLICT (contract_id, version) DO NOTHING`, no call for `[]`).
- [ ] **Step 6: Run unit and integration tests, expect PASS**; `ruff check backend`.
- [ ] **Step 7: Commit** `feat(catalog): persist data product ports with lineage and contract usage`.

---

### Task 4: Use cases

**Files:**
- Create: `backend/use_cases/data_product/save.py`, `backend/use_cases/data_product/contract_ports.py`, `backend/use_cases/data_product/backfill.py`
- Delete: `backend/use_cases/data_product/create.py`, `backend/use_cases/data_product/update.py`
- Modify: `backend/use_cases/data_product/get.py`, `list.py`, `delete.py` (type hints only if needed)
- Create: `tests/unit/use_cases/data_product/__init__.py`, `test_save.py`, `test_contract_ports.py`, `test_backfill.py`
- Modify: `tests/unit/use_cases/test_remaining_use_cases.py` (drop the old product create/update tests)

**Interfaces:**
- Consumes: Task 2 types; Task 3 repository methods; `versioning.baseline`.
- Produces, `save.py`:
  - `class SavedProduct(NamedTuple): product: DataProduct; warnings: list[str]`
  - `class CreateDataProductUseCase(products: IDataProductRepository, contracts: IDataContractRepository)`, `execute(*, name, description, domain_id, status, input_ports: list[InputPort], output_ports: list[OutputPort]) -> SavedProduct`
  - `class UpdateDataProductUseCase(products, contracts)`, `execute(product_id: UUID, *, <same fields>) -> SavedProduct | None`
- Produces, `contract_ports.py`: `class ListContractPortsUseCase(products, contracts)`, `execute(contract_id) -> list[PortUsage] | None` (`None` only when there is no usage and the contract does not exist).
- Produces, `backfill.py`: `class BackfillOutputPortsUseCase(products, contracts)`, `execute() -> int` (products migrated).

Save, in one `products.transaction()`, with a fixed number of queries:
1. (update) `previous = products.get_by_id(id)`; `None` → return `None`.
2. `contracts.list_by_ids(every contract_id on any port)`.
3. Fill `version` with the contract's current version where a port names a known contract and no version.
4. *Fresh* ports: those whose `(role, name, version, contract_id)` is not on `previous` (all ports on create).
5. Problems: the aggregate's (`DataProduct(...)` or `previous.revised(...)`) plus rule 4 for fresh inputs on a `retired` contract — `Input {name} cannot use contract {title}: it is retired`. Any → `DataProductRuleError(all)`.
6. `contracts.add_baseline_versions([baseline(c) for each contract on a fresh port])`.
7. `products.list_port_usage(contract ids of fresh outputs)` for the warnings.
8. `products.add(product)` or `products.replace(product)`.

Warnings, fresh ports only, exactly:
- `Input {name} uses contract {title}, which is deprecated`
- `Contract {title} is already published by {product names, ", "-joined}` (other products' output usage)
- `Contract {title} belongs to domain {contract.domain}, not to this product's domain`

- [ ] **Step 1: Write the failing tests** (`contract_repo` fixture from `conftest.py` for the transaction; an `AsyncMock` products repo with `transaction = MagicMock()`):

```python
async def test_create_fills_the_contracts_current_version(): ...
async def test_create_refuses_a_retired_input_contract(): ...      # messages == ["Input cad cannot use contract Cadastro: it is retired"]
async def test_retired_output_contract_is_allowed(): ...
async def test_rule_errors_and_aggregate_errors_come_together(): ... # no output + retired input -> 2 messages
async def test_deprecated_input_is_a_warning(): ...
async def test_output_published_elsewhere_is_a_warning(): ...      # usage of another product's output
async def test_own_output_usage_is_not_a_warning(): ...            # update: usage row of the same product
async def test_output_from_another_domain_is_a_warning(): ...
async def test_baselines_cover_contracts_of_fresh_ports_only(): ...
async def test_unchanged_input_on_a_retired_contract_still_saves(): ...   # Review Focus 1
async def test_update_of_a_missing_product_returns_none(): ...
async def test_update_cannot_reactivate_a_retired_product(): ...
async def test_unknown_contract_is_left_to_the_database(): ...     # not in list_by_ids -> no fill, no rule 4, repository called
async def test_save_runs_in_one_transaction(): ...
async def test_contract_ports_none_only_for_a_missing_contract(): ...
async def test_contract_ports_skips_the_existence_check_when_used(): ...
async def test_backfill_names_the_port_from_the_contract_title(): ...    # "Exposição de Crédito" -> "exposicao-de-credito"; "???" -> "output"
async def test_backfill_writes_the_baseline_then_replaces_the_product(): ... # status kept, type "tables", version = contract.version
async def test_backfill_is_a_no_op_when_nothing_is_linked(): ...
async def test_backfill_uses_one_transaction_per_product(): ...
```

And `n1` tests: `CreateDataProductUseCase` with five ports calls `list_by_ids`, `add_baseline_versions`, `list_port_usage`, `add` once each.

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement**; keep each function under complexity 15 (split fill, freshness, problems, warnings into module-level helpers).
- [ ] **Step 4: Run, expect PASS**; `ruff check backend`.
- [ ] **Step 5: Commit** `feat(products): save products with ports, rule 4 and warnings; backfill command`.

---

### Task 5: API, backfill wiring

**Files:**
- Rewrite: `backend/interface/schemas/data_product.py`
- Modify: `backend/interface/routers/data_product.py`, `backend/interface/dependencies.py`
- Create: `scripts/backfill_output_ports.py`
- Modify: `entrypoint.sh`
- Rewrite: `tests/unit/interface/test_data_product_router.py`
- Create: `tests/unit/scripts/test_backfill_output_ports.py`

**Interfaces:**
- Consumes: Task 4 use cases.
- Produces, schemas: `ContractRefModel(contract_id: UUID, version: str)`, `AuthoritativeDefinitionModel(type: str = Field(min_length=1), url: str = Field(min_length=1))`, `InputPortModel(name: str = Field(min_length=1), contract_id: UUID | None = None, version: str | None = None, deprecated: bool = False, authoritative_definitions: list[AuthoritativeDefinitionModel] = [])`, `OutputPortModel(... + type: str | None = None, description: str | None = None, input_contracts: list[ContractRefModel] = [])`, `DataProductWriteModel(name: str, description: str, domain_id: UUID, status: str = "draft", input_ports: list[InputPortModel] = [], output_ports: list[OutputPortModel] = [])`; response models add `id`, `contract: ContractSummaryModel | None`, `produced_by` / `consumed_by: list[ProductRefModel]`; `DataProductResponseModel(id, name, description, domain_id, domain, status, deprecated, input_ports, output_ports, repo_url, created_at, updated_at, warnings: list[str] = [])`; `PortUsageResponseModel(product_id, product_name, domain, status, role, port_name, version)`.
- Produces, routes: `POST /data-products` and `PUT /data-products/{id}` take `DataProductWriteModel` (PUT is a full replace); `DataProductRuleError` → `422` with `detail=[{"msg": m} ...]`. `GET /data-contracts/{contract_id}/ports` → `list[PortUsageResponseModel]`, `404 Data contract not found`.
- Produces, dependencies: `get_create_data_product_use_case`, `get_update_data_product_use_case` (both repositories), `get_list_contract_ports_use_case`.

- [ ] **Step 1: Write the failing router tests** (keep the existing GitHub provisioning tests, rewritten for the new payload and `product.domain`):

```python
def test_create_returns_ports_and_warnings(admin_client): ...       # 201, output_ports[0]["contract"], warnings
def test_create_rule_error_is_422_with_one_msg_per_rule(admin_client): ...
def test_create_without_outputs_reaches_the_aggregate(admin_client): ... # body without output_ports -> use case called, its error -> 422
def test_put_is_a_full_replace(admin_client): ...                    # use case gets every field
def test_response_has_no_data_contracts_id(admin_client): ...
def test_repo_name_uses_the_products_domain(admin_client): ...       # "dp-risco-..." from product.domain, no contract lookup
def test_contract_ports_lists_usage(admin_client): ...
def test_contract_ports_404_for_unknown_contract(admin_client): ...
def test_deprecated_is_derived_in_the_response(admin_client): ...
```

And `tests/unit/scripts/test_backfill_output_ports.py`: `main()` opens one connection with the app settings, runs the use case, prints `Backfilled output ports for N data products`, closes the connection.

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.** The router keeps the warn-only GitHub calls; `_ensure_product_repo(github, product, product_repo)` uses `product.domain` and `slugify`; delete `_resolve_domain_name` and the router's `_slugify`. `_build_scaffold` reads `product.domain`.
- [ ] **Step 4: Wire `entrypoint.sh`** after `unset ...`, before `exec`:

```bash
# Gives every pre-ODPS product its output port before the app serves (ODPS plan 1).
uv run python -m scripts.backfill_output_ports
```

- [ ] **Step 5: Run, expect PASS**; full backend suite: `.venv\Scripts\python.exe -m pytest tests/ -q`, with `TEST_DATABASE_URL` set.
- [ ] **Step 6: Commit** `feat(api): ODPS ports on the data product API and contract usage endpoint`.

---

### Task 6: Frontend model

**Files:**
- Modify: `frontend/src/types/index.ts`, `frontend/src/lib/contracts.ts`, `frontend/src/index.css`, `frontend/src/lib/domains.ts`, `frontend/src/hooks/useDataProducts.ts`, `frontend/src/hooks/useDataContracts.ts`, `frontend/src/test/fixtures.ts`
- Create: `frontend/src/lib/products.ts`, `frontend/src/lib/products.test.ts`
- Modify: `frontend/src/lib/domains.test.ts`

**Interfaces:**
- Produces, types: `ProductStatus`, `ContractRef`, `AuthoritativeDefinition`, `ContractSummary`, `ProductRef`, `InputPort`, `OutputPort`, `DataProduct` (`domain_id`, `domain`, `status`, `deprecated`, `input_ports`, `output_ports`, `warnings?`), `DataProductInput` (replaces `DataProductFormData`), `PortUsage` — field names as in Task 5.
- Produces, `lib/contracts.ts`: `STATUS_LABELS` gains `proposed: 'Proposed'`; `type GlyphStatus = ContractStatus | ProductStatus` for `StatusGlyph`.
- Produces, `lib/products.ts`:
  - `PRODUCT_STATUSES: ProductStatus[]` (`['proposed','draft','active','deprecated','retired']`)
  - `slugify(text: string): string` (same rule as the backend)
  - `toInput(p: DataProduct): DataProductInput` (drops `id`, `contract`, `produced_by`, `consumed_by`)
  - `newerVersion(port: InputPort | OutputPort): string | null` (the contract's current version when it differs from the port's)
  - `isMajorMove(from: string, to: string): boolean`
  - `publishOutput(p, index, { deprecateOld }): DataProductInput` and `switchInput(p, index): DataProductInput` — add the new-version row after the old one (outputs copy `type`, `description`, `input_contracts`)
  - `removablePort(p, role, index): boolean` (output: no `consumed_by`; input: no output's `input_contracts` cites it)
  - `removePort(p, role, index): DataProductInput`
  - `producersByContract(products: DataProduct[]): Map<string, ProductRef[]>`
- Produces, `lib/domains.ts`: `selectableDomains(domains, user, keepId?): DomainWithMembers[]` (membership filter, admin all, `keepId` kept).
- Produces, hooks: `useCreateDataProduct` / `useUpdateDataProduct` take `DataProductInput` and also invalidate `['data-contracts']`; `useContractPorts(contractId)` at key `['data-contracts', id, 'ports']`.

- [ ] **Step 1: Write the failing tests** in `products.test.ts` / `domains.test.ts`: slug cases from Review Focus 5; `newerVersion` null when equal or no contract; `isMajorMove('1.2.0','2.0.0')` true, `('1.2.0','1.3.0')` false, non-semver false; `publishOutput` adds `v1.1.0` after the old row and marks the old one deprecated only when asked; `switchInput` keeps the contract; `removablePort` for each role; `toInput` strips read fields; `producersByContract` groups outputs; `selectableDomains` membership, admin and `keepId`.
- [ ] **Step 2: Run `npm test`, expect FAIL.**
- [ ] **Step 3: Implement**; add `.st-proposed::before` (dotted border in `--warn`) to `index.css`.
- [ ] **Step 4: Run, expect PASS.** (Type errors in pages are fixed in Tasks 7–9; `npm run build` runs at the end of Task 9.)
- [ ] **Step 5: Commit** `feat(frontend): ODPS product types, version moves and domain choices`.

---

### Task 7: Product form

**Files:**
- Rewrite: `frontend/src/pages/DataProducts/DataProductForm.tsx`, `frontend/src/pages/DataProducts/DataProductForm.test.tsx`
- Create: `frontend/src/pages/DataProducts/PortEditors.tsx`, `frontend/src/pages/DataProducts/PortEditors.test.tsx`
- Modify: `frontend/src/pages/DataProducts/ContractPicker.tsx` (optional `detail?: (c: DataContract) => ReactNode`, label prop), `frontend/src/pages/DataContracts/EditableRows.tsx` (optional `addActions?: ReactNode` replacing the add button; `aria-label="Remove"`)

**Interfaces:**
- Consumes: Task 6.
- Produces: `DataProductForm({ defaultValues?: DataProduct, onSubmit(values: DataProductInput), onCancel, isSubmitting, warnings?: string[] })`; `OutputPortsEditor({ rows, onChange, inputs, error })`, `InputPortsEditor({ rows, onChange, error })`.

Form layout (spec "Screens"): Name, Domain (select from `selectableDomains`, preselected when exactly one), Status (select, default Draft), Description; **Outputs · at least one** (`EditableRows`, starts with one empty row on create; per row: name, type with `tables` suggested, a "Choose contract" button opening `ContractPicker` in a `Modal` over `useSelectableContracts`, version shown read-only once picked, "Built from" checkboxes over the inputs that have a contract; a row without contract shows a `Not consumable` badge with **Add a contract**); **Inputs** with **+ From a contract** (picker over every contract from `useDataContracts`, `detail` shows the producing products from `producersByContract(useDataProducts())`; picking fills name `slugify(title)` and version) and **+ External source** (name + link URL, stored as `authoritative_definitions: [{type: 'implementation', url}]`). Rows of the same name sort together, newest version first. Zod mirrors only: name ≥ 3, description ≥ 10, domain required, outputs ≥ 1 with `A data product needs at least one output` shown on the Outputs section, port name required, no two ports of one kind with the same name and version (`Two outputs share the name x and version 1.0.0`). Server warnings render under the form in a warn-toned list.

- [ ] **Step 1: Write the failing tests:** create shows one empty output and Draft; submitting with no output name shows the rule-1 message on the Outputs section; picking an output contract fills its version and title; an output without contract shows "Not consumable"; "From a contract" fills name and version and shows "produced by"; "External source" submits `authoritative_definitions`; duplicate outputs show the duplicate message and do not submit; edit mode keeps port ids and pinned versions in the payload; warnings render; the domain list honours membership and preselects a single domain; `EditableRows` `addActions` and `aria-label="Remove"`.
- [ ] **Step 2: Run, expect FAIL.** **Step 3: Implement.** **Step 4: Run, expect PASS**; `npm run lint`.
- [ ] **Step 5: Commit** `feat(frontend): product form with ODPS outputs and inputs`.

---

### Task 8: Product page lineage and contract usage

**Files:**
- Create: `frontend/src/pages/DataProducts/ProductLineage.tsx`, `ProductLineage.test.tsx`
- Modify: `frontend/src/pages/DataProducts/DataProductDetail.tsx` (+ its three tests)
- Create: `frontend/src/pages/DataContracts/ContractUsage.tsx`, `ContractUsage.test.tsx`
- Modify: `frontend/src/pages/DataContracts/DataContractDetail.tsx` (+ test)

**Interfaces:**
- Consumes: Task 6 helpers and hooks.
- Produces: `ProductLineage({ product, onChange(input: DataProductInput), saving })`; `ContractUsage({ contract })`.

Product page: header shows the product's `DomainChip` and `StatusGlyph` (no contract tier); the "Data contract" panel is replaced by the lineage strip *Inputs → product → Outputs* (stacked under 720 px). Inputs show contract title, version, "by {producer}" or "External source" with its link; a deprecated or retired input contract is flagged. Outputs show version, "{n} consumers", or "No contract — not consumable". Actions: `v{x} available → Publish` (output) / `→ Switch` (input), a confirm `Modal` for a MAJOR move with "Mark the old output deprecated" checked by default on Publish, and `Remove` on rows `removablePort` allows. Each action is one `PUT` through `useUpdateDataProduct`; errors show inline. Contract page: a "Usage" panel in the right rail, from `useContractPorts`, listing *Produced by* and *Consumed by* (product, port, version) with `⚠ pinned to an older version` when the version is not the contract's current one, and an empty state.

- [ ] **Step 1: Write the failing tests:** lineage renders both sides and the product; "Publish" sends the PUT with the new row and the old one deprecated; a MAJOR move asks first; "Switch" adds the input row; "Remove" appears only when allowed; deprecated input flagged; usage panel groups producers and consumers and flags pinned-older rows; empty usage state.
- [ ] **Step 2: Run, expect FAIL.** **Step 3: Implement.** **Step 4: Run, expect PASS**; `npm run lint`.
- [ ] **Step 5: Commit** `feat(frontend): lineage on the product page and usage on the contract page`.

---

### Task 9: Marketplace and overview

**Files:**
- Modify: `frontend/src/pages/DataProducts/index.tsx` (+ `DataProductsList.test.tsx`, `DataProductsList.states.test.tsx`, `Marketplace.test.tsx`)
- Modify: `frontend/src/pages/dashboard/overview.ts`, `frontend/src/pages/Dashboard.tsx` (+ `overview.test.ts`, `Dashboard.test.tsx`)

Marketplace rows are products alone (no contract join): `DomainChip` of the product's domain, `StatusGlyph` of its status, "{n} outputs · {m} inputs"; filters by domain (from the products) and by status (chips like the domain filter, `aria-label="Filter by status"`); the text filter also matches port names. Subtitle: `{n} data products from {d} domains.` Overview: recent product rows show the product's domain and status, no tier or owner; domain cards count products by `domain_id`.

- [ ] **Step 1: Write the failing tests** for both filters together, the status glyph, port counts, the overview rows and domain counts.
- [ ] **Step 2: Run, expect FAIL.** **Step 3: Implement.** **Step 4:** `npm test`, `npm run test:coverage` (≥ 80 %), `npm run lint`, `npm run build` all pass.
- [ ] **Step 5: Commit** `feat(frontend): marketplace filters by domain and status`.

---

### Task 10: End to end

- [ ] **Step 1:** Fresh-volume compose stack (recipe in project memory: override file with `name: dmplt-fresh`, own volume, no host ports clash), seeded with one contract and one pre-ODPS product inserted *before* starting the backend on this branch (`data_contracts_id` set); start the backend; its log shows `Backfilled output ports for 1 data products`; a second start shows `0`.
- [ ] **Step 2:** In the browser: create a product with two outputs (one without contract), one contract input and one external input; see the lineage strip; open the input contract and see its usage panel; bump that contract's version and use "Switch"; try to delete the contract and see the 409 message.
- [ ] **Step 3:** Backend suite with `TEST_DATABASE_URL`, `ruff check backend`, `ruff format --check .`, frontend `npm test`, `npm run lint`, `npm run build`.
- [ ] **Step 4:** Push and open the PR against `develop`.
