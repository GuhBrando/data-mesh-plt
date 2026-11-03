# ODCS Versioning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every data contract an immutable ODCS version history, enforce semver on `active` and `deprecated` contracts in the update path and in sync, add the terminal `retired` status, and show the history on the detail page.

**Architecture:** The pure module `backend/domain/contract_evolution.py` decides what a change is worth. The thin `backend/use_cases/data_contract/versioning.py` applies that decision to `DataContract` entities and writes snapshots. The create, update and sync use cases run lock, write, check and snapshot inside one `repository.transaction()`, so a rejected change rolls back. Routers keep pushing to GitHub after the commit.

**Tech Stack:** Python 3.12, FastAPI, asyncpg, PostgreSQL 16, Atlas, React 18, TanStack Query, Vitest.

**Spec:** `docs/superpowers/specs/2026-11-01-odcs-adoption-design.md` (sections Decisions Made During Planning, which win over the rest, Plan 5, Shared Interfaces, ODCS Mapping, Validation, Repository Rules). Policy source: `README.md`, section "Política de Evolução".

**Starting point:** Plans 1 to 4 are merged into `develop`: `to_odcs` emits full ODCS documents and `parse_contract_document` calls `from_odcs`. Line numbers below refer to `develop` at `f02160d` and will have moved, so locate code by symbol.

## Global Constraints

- Version strings must match `^\d+\.\d+\.\d+$`.
- Rules apply only to contracts in `active` or `deprecated` status. Drafts change freely.
- A change of content with no version change is rejected, and so is a bump smaller than the change requires. Rejected requests return `409` with a message naming the changes.
- The same check applies in sync, where a violation is reported in `errors` and the file is skipped.
- A snapshot is the ODCS YAML. It is written when a contract is created and whenever its version changes.
- Status gains `retired`, which is terminal, and the `chk_dc_status` constraint changes with it.
- `classify_change(old: dict, new: dict) -> ChangeKind` is a pure function in `backend/domain/contract_evolution.py`.
- Layering stays as it is: entities and pure logic hold no I/O, routers orchestrate GitHub calls, and GitHub push failures stay warn-only.
- Branch from `develop`. An unmerged branch, `worktree-feat+data-contract-picker`, changes `DataProductForm` and adds repository tests.
- Commit messages and PR text carry no Claude or Claude Code attribution of any kind.
- Backend tests: `.venv\Scripts\python.exe -m pytest tests/ -q`.
- Frontend, from `frontend/`: `npm test`, `npm run lint`, `npm run build`.
- `git commit` needs `.venv\Scripts` prefixed to `PATH`, or pre-commit fails: `$env:PATH = "$PWD\.venv\Scripts;$env:PATH"`.
- Lint with `.venv\Scripts\ruff check backend`. Passing test paths makes ruff rewrite those files. CI also runs `ruff format --check .`.
- Migrations are SQL files in `database/migrations/`, named as in spec decision 8, and `atlas.sum` is regenerated from LF content with Plan 3 Task 1 Step 4's commands (spec decision 9). CI's `migrations` job validates it. `atlas` is not on `PATH` on this machine.
- `database/schema/*.hcl` is out of date and stays untouched.
- Stage explicit paths only. `frontend/package-lock.json` is dirty in the main checkout and is not part of this work.

## Review Focus

1. A GitHub push failed earlier (warn-only), so the file is behind the database. The next sync must report the file and leave the contract alone, not roll it back. Test: `test_file_behind_database_is_reported_and_skipped` (Task 5).
2. A contract stored before this plan has a version such as `1.0`. Approve, Request Changes and saves that leave the version alone keep working. Test: `test_unchanged_legacy_version_passes` (Task 4).
3. The edit form re-submits an unchanged `active` contract, and Pydantic adds defaults the stored JSON lacks. That is no change, so no bump is demanded. Test: `test_resubmitted_form_defaults_are_not_a_change` (Task 4).
4. A retired contract's file stays in the central repository and every sync re-reads it. An identical file produces no error and no write. Test: `test_retired_contract_with_unchanged_file_is_silent` (Task 5).
5. A contract older than this plan has no snapshot. `GET /versions` returns `[]`, the page shows an empty state, and the first bump also captures the old version. Tests: `test_list_versions_empty_for_contract_without_history` (Task 6), `test_first_bump_without_history_captures_the_old_version_first` (Task 4), `empty history shows the empty state` (Task 7).

## Decisions

Every result below was measured on `postgres:16.1` with real Atlas and asyncpg while writing this plan, unless it says otherwise.

**Atomicity.** `get_db_connection` is cached per request by FastAPI, so all repositories in a request share one connection. A new port method `transaction()` returns `self.db.transaction()`, and the use case wraps its whole sequence in it. The nested `self.db.transaction()` inside `repository.update` becomes a savepoint. Verified: a failing snapshot insert after the `UPDATE` left the contract row unchanged.

**Check after write.** `to_odcs` needs the joined domain name, and a `PUT` can change `domain_id`. So the use case writes first, reads the joined entity back, compares it with the locked `current`, and raises to roll back. No in-memory candidate is built and no extra domain lookup is needed.

**Immutability and grants.** The brief's target, INSERT and SELECT only for the app role, is not possible for the role the app really uses:

- The app connects as `admin`, never as `app_user`. `backend/infra/config.py` defaults `DB_USER` to `admin` and reads `ADMIN_PASSWORD`, and `.env_example` and `.github/workflows/cd.yml` set `DB_USER=admin`.
- `entrypoint.sh` runs migrations with that same role, so on azure `admin` owns new tables. This is inferred from those two files; the Neon instance itself was not inspected.
- An FK cascade runs with the privileges of the child table's owner. Removing DELETE from the owner breaks `DELETE /data-contracts/{id}`.
- `ALTER DEFAULT PRIVILEGES` in `20260428000001_add_rbac.sql` and `20260401000001_fix_admin_schema_grants.sql` gives every new `catalog` table full DML to both roles, so the migration must REVOKE, not GRANT.

| Grants on `catalog.contract_versions` | Owner `admin` (azure) | Owner `postgres` (local DB today) |
|---|---|---|
| REVOKE UPDATE, DELETE, TRUNCATE from `admin`, `app_user` | Parent delete **fails**: `permission denied for table contract_versions` | Parent delete works |
| Chosen: below | Parent delete works, direct UPDATE and DELETE fail | Same |

The local result would have hidden the production failure. Chosen: `REVOKE UPDATE, TRUNCATE` from both roles, `REVOKE DELETE` from `app_user`, and a `BEFORE UPDATE OR DELETE` trigger that lets cascades through by `pg_trigger_depth() > 1`. The trigger also stops superusers, which matters because a fresh compose volume with `DB_USER=admin` makes `admin` the bootstrap superuser, and superusers ignore REVOKE. Final ACLs: `admin=ardxt`, `app_user=ar`. The trigger and the grants guard against application bugs and slips. They are not a security boundary, because an owner can re-grant or disable a trigger.

`created_by` has no FK. The convention `REFERENCES iam.users ON DELETE SET NULL` is an UPDATE on a history row, and it made user deletion fail in testing. This matches the spec, which marks only `contract_id` as an FK.

**First history row.** SQL cannot produce a snapshot: the YAML comes from `to_odcs`, and reimplementing the mapper in SQL would drift from it. The migration does no backfill. The first version change of a contract without history writes two rows in one transaction: a baseline of the old version, then the new version. The baseline uses `ON CONFLICT DO NOTHING` (needs no UPDATE privilege, verified), `created_by` NULL, and `created_at = previous.updated_at`. Using `updated_at` is deliberate: `now()` is the transaction start, so both rows would tie and sort unpredictably. Until that first change, `GET /versions` returns `[]`.

**Delete.** `contract_id` cascades, as the spec says. Deleting a contract therefore erases its "immutable" history. That is a real tension, and this plan follows the spec. Deletion is limited by the existing FK from `catalog.data_products`, and the Git history of the central repository remains, subject to warn-only pushes. After a delete, `GET /versions` returns 404.

**Concurrency.** The unique constraint alone is not enough. Without a lock, with `existing` read before the transaction as the router does today:

| Scenario, active contract at 1.0.0 | No lock | With `SELECT ... FOR UPDATE OF dc` |
|---|---|---|
| T1 and T2 both target 1.1.0, different content | T2 gets `UniqueViolationError` | T2 re-reads 1.1.0, policy returns 409 |
| T1 targets 1.1.0, T2 targets 1.0.1 | **Both succeed: version moves back to 1.0.1 and T1's content is lost** | T2 re-reads 1.1.0, policy returns 409 |
| Draft at 1.1.0 moves back to 1.0.0, already in history | `UniqueViolationError` | Same, and the rollback leaves the row at 1.1.0 |

So the check runs under a row lock, and `add_version` still maps `asyncpg.UniqueViolationError` to `ContractVersionConflictError`, which the router turns into 409. The constraint stays as the backstop. The router's early read remains for merging partial bodies. A stale merge on a governed contract fails the check under the lock with a clean 409.

**Content keys.** `classify_change` uses a deny-list, so a key a later plan emits counts as PATCH rather than being ignored.

- Not content: `apiVersion`, `kind`, `id`, `version`, `status`, `schema[0].name`. The first three cannot differ between two versions of one contract. `version` and `status` changing alone are not content changes. `schema[0].name` is the slug of the title, which `name` already covers.
- Content: every other key, including `name`, `domain`, `team`, `description`, `support`, `servers`, `customProperties` (tier), `slaProperties`, and all of `schema[0]` except its `name`.
- `schema[0]` is paired by position, never by name. Pairing by name would make a title change look like a removed table, which is how `datacontract changelog` reports it.
- Lists are compared without regard to order. Absent, `None`, `False`, `""`, `[]` and `{}` are equal. `0` is a value.

**Policy mapping.** MAJOR: property removed or renamed (a rename is seen as remove plus add), `logicalType` changed, `required` turned on. MINOR: property added, `required`, `unique` or `primaryKey` turned off. PATCH: everything else, including `unique` or `primaryKey` turned on, `physicalType`, descriptions, quality rules and SLA values, because the spec's MAJOR list is closed. "Change of semantic meaning" from the README cannot be detected from a document.

**Status transitions.** `previous.status` decides whether rules apply, so an `active` contract set to `draft` with new content in the same request is still checked. Only leaving `retired` is forbidden.

| Actor, retired contract | Behaviour |
|---|---|
| `PUT` | Always 409, even with an identical body. No write. |
| Sync, file identical in content, version and status | Skipped: no write, no error, not counted. |
| Sync, file differs | Reported in `errors`, skipped. |
| `DELETE` and all reads | Work as for any contract. |

Status-only updates and any `active` to `deprecated` to `retired` path stay allowed. `to_odcs` emits `retired` unchanged, and ODCS lists it as a status (lint passes). No backend code reads contract status, so data products can still reference a retired contract.

**Version validation.** `validate_new_version(version, previous)` runs in the use cases, not in Pydantic, because only there can an unchanged legacy value pass. A `PUT` that omits or repeats `1.0` keeps working, and any new value must be semver. It raises `ValueError`, so the API returns 400 and sync reports it in `errors`. A version lower than the current one on a governed contract is rejected even with no content change, and order is numeric (`1.10.0` is above `1.9.0`).

**`atlas.sum`** (spec decision 9). Facts measured with `arigaio/atlas:latest`, which reported v1.3.7 (a pre-release build), before Plan 3. Every command below uses the pinned release tag `arigaio/atlas:1.3.6`, as Plan 3's "Settled Decisions" explains:

- `atlas migrate validate` failed on `develop` in both forms: at L10 on a CRLF checkout, at L2 on an LF checkout. The committed file was mixed: 8 files hashed as CRLF, the newest as LF. A new file keeps LF on disk until Git rewrites it, and that is how the mix happened.
- `atlas migrate apply` through `template_dir` recomputes the sum in memory and succeeded with the stale file, so `atlas.sum` is not enforced at deploy. The image holds LF bytes (Linux CI checkout).

Plan 3 Task 1 fixed this once: `database/migrations/*.sql text eol=lf` in `.gitattributes`, every hash regenerated from LF content, and an `atlas migrate validate` job in CI. Task 1 here regenerates the sum the same way, so this plan adds one line and changes the first.

**Known limitations** (spec decision 13), accepted and not fixed by any task here: moving an `active` contract to `draft`, editing it, and moving it back bypasses the policy; a snapshot can differ from later edits made at the same version; the MAJOR list is closed; `GET /data-contracts` returns full contracts to consumers. Do not add code for them. Task 8 Step 7 documents them in the README's "Política de Evolução".

---

## File Structure

| File | Responsibility |
|---|---|
| Create `database/migrations/20261101000005_contract_versions.sql` | Table, status constraint, grants, trigger |
| Modify `database/migrations/atlas.sum` | Checksums |
| Create `backend/domain/contract_evolution.py` | `ChangeKind`, classification, bump rules, policy errors. Pure. |
| Create `backend/domain/entities/contract_version.py` | `ContractVersion` entity |
| Modify `backend/domain/interfaces/data_contract_repository.py` | Transaction, lock and history ports |
| Modify `backend/infra/repositories/data_contract_repository.py` | Their Postgres implementation |
| Create `backend/use_cases/data_contract/versioning.py` | Applies the policy to entities, writes snapshots |
| Modify `backend/use_cases/data_contract/create.py`, `update.py`, `sync_from_github.py` | Transactional flows |
| Create `backend/use_cases/data_contract/list_versions.py`, `get_version_yaml.py` | Read use cases |
| Modify `backend/interface/routers/data_contract.py`, `schemas/data_contract.py`, `dependencies.py` | HTTP surface |
| Modify `frontend/src/types/index.ts`, `hooks/useDataContracts.ts`, `pages/DataContracts/DataContractDetail.tsx`, `DataContractForm.tsx` | History list, retired status |
| Modify `README.md`, section "Política de Evolução" | Known limitations (spec decision 13) |

---

### Task 1: Migration and `atlas.sum`

**Files:**
- Create: `database/migrations/20261101000005_contract_versions.sql`
- Modify: `database/migrations/atlas.sum`

**Interfaces:**
- Produces: table `catalog.contract_versions (contract_id, version, yaml_content, created_by, created_at)`, primary key `contract_versions_pkey`, status value `retired`.

Docker Desktop is stopped by default here, and `docker` then fails with `failed to connect to the docker API`. Start it with `& 'C:\Program Files\Docker\Docker\Docker Desktop.exe'` and wait for `docker info` to succeed. The project's `postgres_db` and `backend` containers come up with it (`restart: always`); leave them alone.

- [ ] **Step 1: Confirm the filename sorts last**

Run: `(Get-ChildItem database\migrations\*.sql | Sort-Object Name | Select-Object -Last 1).Name`
Expected: `20261101000004_odcs_quality_and_sla.sql`, from Plan 4. Spec decision 8 fixes this plan's name, so if any file sorts at or after `20261101000005_contract_versions.sql`, stop and ask the owner rather than renaming.

- [ ] **Step 2: Write the migration**

Exact content, verified on both ownership modes. `template_dir` renders every migration as a Go template, so do not add `{{`.

```sql
-- =============================================================================
-- Immutable contract version history and the terminal `retired` status.
-- Atlas manages the transaction; do NOT add explicit BEGIN/COMMIT here.
-- =============================================================================

-- 1. `retired` joins the accepted statuses.
ALTER TABLE catalog.data_contracts DROP CONSTRAINT chk_dc_status;
ALTER TABLE catalog.data_contracts
    ADD CONSTRAINT chk_dc_status
    CHECK (status IN ('draft', 'in_review', 'active', 'deprecated', 'retired'));

-- 2. History table. The primary key is the unique rule on (contract_id, version).
--    created_by has no FK on purpose: ON DELETE SET NULL is an UPDATE, which the
--    trigger below rejects, so deleting a user would fail.
CREATE TABLE catalog.contract_versions (
    contract_id  UUID        NOT NULL
                 REFERENCES catalog.data_contracts(id) ON DELETE CASCADE,
    version      TEXT        NOT NULL,
    yaml_content TEXT        NOT NULL,
    created_by   UUID,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT contract_versions_pkey PRIMARY KEY (contract_id, version)
);

-- 3. Grants. ALTER DEFAULT PRIVILEGES hands every new catalog table to both roles
--    with UPDATE and DELETE, so they are taken back here. DELETE stays on admin:
--    where admin owns this table (azure), ON DELETE CASCADE runs as the owner and
--    fails without it. The trigger below covers direct deletes.
REVOKE UPDATE, TRUNCATE ON catalog.contract_versions FROM admin, app_user;
REVOKE DELETE ON catalog.contract_versions FROM app_user;

-- 4. Immutability for every role, including the owner and superusers. A cascade
--    from catalog.data_contracts runs inside the RI trigger, at depth 2.
CREATE FUNCTION catalog.reject_contract_version_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' AND pg_trigger_depth() > 1 THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'catalog.contract_versions rows are immutable (%)', TG_OP;
END $$;

CREATE TRIGGER trg_contract_versions_immutable
    BEFORE UPDATE OR DELETE ON catalog.contract_versions
    FOR EACH ROW EXECUTE FUNCTION catalog.reject_contract_version_change();

-- =============================================================================
-- ROLLBACK (run manually if needed):
-- DROP TABLE catalog.contract_versions;
-- DROP FUNCTION catalog.reject_contract_version_change();
-- UPDATE catalog.data_contracts SET status = 'deprecated' WHERE status = 'retired';
-- ALTER TABLE catalog.data_contracts DROP CONSTRAINT chk_dc_status;
-- ALTER TABLE catalog.data_contracts ADD CONSTRAINT chk_dc_status
--     CHECK (status IN ('draft', 'in_review', 'active', 'deprecated'));
-- =============================================================================
```

- [ ] **Step 3: Check the new file is LF in Git and on disk**

```powershell
$m = "database\migrations\20261101000005_contract_versions.sql"
git add $m
git ls-files --eol $m
```
Expected: `i/lf    w/lf    attr/text eol=lf`, from Plan 3's `.gitattributes` rule. If it shows `w/crlf`, your editor saved CRLF: run `Remove-Item $m; git checkout -- $m` and check again.

- [ ] **Step 4: Regenerate and validate `atlas.sum` from LF content**

Run Plan 3 Task 1 Step 4's commands, in Git Bash from the repository root:

```bash
ATLAS_TMP="$(mktemp -d)"
cp database/migrations/*.sql "$ATLAS_TMP"/
sed -i 's/\r$//' "$ATLAS_TMP"/*.sql
MSYS_NO_PATHCONV=1 docker run --rm -v "$(cygpath -w "$ATLAS_TMP"):/migrations" arigaio/atlas:1.3.6 migrate hash --dir file:///migrations
cp "$ATLAS_TMP/atlas.sum" database/migrations/atlas.sum
MSYS_NO_PATHCONV=1 docker run --rm -v "$(cygpath -w "$ATLAS_TMP"):/migrations" arigaio/atlas:1.3.6 migrate validate --dir file:///migrations; echo "validate exit=$?"
MSYS_NO_PATHCONV=1 docker run --rm -v "$(cygpath -w "$PWD/database/migrations"):/migrations" arigaio/atlas:1.3.6 migrate validate --dir file:///migrations; echo "working tree validate exit=$?"
rm -rf "$ATLAS_TMP"
git diff --stat -- database/migrations/atlas.sum
```
Expected: `validate exit=0` and `working tree validate exit=0`, and `atlas.sum` gains one line for the new file while its first line changes, for 13 lines. With Plans 3, 4 and 5's SQL copied verbatim, the first line is `h1:7bYvQUrLGrKuyxwn9ivD+vJNncOvnpKzhYL8+3lGyIg=` and the last is `20261101000005_contract_versions.sql h1:uQBeED0rCqneNlYHkTd+IevbQ0dw6GcjXFMk3yo0gzw=` (computed the way Plan 3's Step 4 explains; if Atlas disagrees, Atlas wins).

- [ ] **Step 5: Start a throwaway Postgres where `admin` owns the tables**

This is the azure arrangement, the one where the wrong grants fail. Never point these commands at `postgres_db`.

```powershell
docker network create plan5-net
docker run -d --name plan5-pg --network plan5-net -p 127.0.0.1:55433:5432 -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=plan5 -e POSTGRES_DB=postgres postgres:16.1
docker exec plan5-pg pg_isready -h localhost -U postgres
docker exec plan5-pg psql -U postgres -c "CREATE ROLE admin LOGIN PASSWORD 'plan5' CREATEROLE;" -c "CREATE DATABASE data_mesh_plt OWNER admin;"
```
Expected: repeat `pg_isready` until it prints `accepting connections`, then `CREATE ROLE` and `CREATE DATABASE`.

- [ ] **Step 6: Apply every migration the way `entrypoint.sh` does**

```powershell
docker run --rm --network plan5-net -v "${PWD}\database:/project" -w /project -e ADMIN_PASSWORD=plan5 -e APP_USER_PASSWORD=plan5 -e USER_PASSWORD=plan5 arigaio/atlas:1.3.6 migrate apply --env azure --url "postgres://admin:plan5@plan5-pg:5432/data_mesh_plt?sslmode=disable" --revisions-schema public --allow-dirty
```
Expected: exit 0, and the output includes `migrating version 20261101000005`.

- [ ] **Step 7: Probe as `admin`**

Pipe this into `docker exec -e PGPASSWORD=plan5 -i plan5-pg psql -h localhost -U admin -d data_mesh_plt -At`:

```sql
INSERT INTO catalog.domains (id, name) VALUES ('00000000-0000-0000-0000-00000000000d', 'probe');
INSERT INTO catalog.data_contracts (id, title, domain_id, status) VALUES ('00000000-0000-0000-0000-00000000000c', 'probe', '00000000-0000-0000-0000-00000000000d', 'retired');
INSERT INTO catalog.contract_versions (contract_id, version, yaml_content) VALUES ('00000000-0000-0000-0000-00000000000c', '1.0.0', 'y');
INSERT INTO catalog.contract_versions (contract_id, version, yaml_content) VALUES ('00000000-0000-0000-0000-00000000000c', '1.0.0', 'y2') ON CONFLICT (contract_id, version) DO NOTHING;
INSERT INTO catalog.contract_versions (contract_id, version, yaml_content) VALUES ('00000000-0000-0000-0000-00000000000c', '1.0.0', 'y3');
UPDATE catalog.contract_versions SET yaml_content = 'tampered';
DELETE FROM catalog.contract_versions;
TRUNCATE catalog.contract_versions;
SELECT yaml_content FROM catalog.contract_versions;
UPDATE catalog.data_contracts SET status = 'bogus' WHERE title = 'probe';
SELECT pg_get_userbyid(relowner), relacl FROM pg_class WHERE oid = 'catalog.contract_versions'::regclass;
DELETE FROM catalog.data_contracts WHERE title = 'probe';
SELECT count(*) FROM catalog.contract_versions;
```

Expected, in order (`CONTEXT` and `DETAIL` lines omitted):

```
INSERT 0 1
INSERT 0 1
INSERT 0 1
INSERT 0 0
ERROR:  duplicate key value violates unique constraint "contract_versions_pkey"
ERROR:  permission denied for table contract_versions
ERROR:  catalog.contract_versions rows are immutable (DELETE)
ERROR:  permission denied for table contract_versions
y
ERROR:  new row for relation "data_contracts" violates check constraint "chk_dc_status"
admin|{admin=ardxt/admin,app_user=ar/admin}
DELETE 1
0
```

- [ ] **Step 8: Remove the container**

Run: `docker rm -f plan5-pg; docker network rm plan5-net`
Expected: both names printed. Task 8 recreates them.

- [ ] **Step 9: Commit**

```powershell
git add database/migrations/20261101000005_contract_versions.sql database/migrations/atlas.sum
git commit -m "feat(db): add immutable contract version history and retired status"
```

---

### Task 2: `classify_change` and the evolution policy

**Files:**
- Create: `backend/domain/contract_evolution.py`
- Test: `tests/unit/test_contract_evolution.py`

**Interfaces:**
- Produces, all from `backend.domain.contract_evolution`:

```python
RETIRED_STATUS = "retired"
GOVERNED_STATUSES = frozenset({"active", "deprecated"})

class ChangeKind(IntEnum):
    NONE = 0; PATCH = 1; MINOR = 2; MAJOR = 3

@dataclass(frozen=True)
class ContractChange:
    kind: ChangeKind
    description: str

class ContractEvolutionError(Exception): ...          # surfaces as HTTP 409
class RetiredContractError(ContractEvolutionError): ...
class ContractVersionConflictError(ContractEvolutionError): ...

def is_semver(version: str) -> bool: ...
def describe_changes(old: dict, new: dict) -> list[ContractChange]: ...
def classify_change(old: dict, new: dict) -> ChangeKind: ...
def version_bump(old: str, new: str) -> ChangeKind: ...
def is_unchanged(old: dict, new: dict) -> bool: ...
def evolution_violation(old: dict, new: dict) -> str | None: ...
```

`ContractEvolutionError` must not derive from `ValueError`: the routers map `ValueError` to 400.

- [ ] **Step 1: Write the failing tests**

`BASE` is the shape `to_odcs` emits after Plans 1 to 4. Add one `pytest.param(..., id=<case>)` per row of the table below to `test_classify_change`, with the mutation applied to a deep copy of `BASE`.

```python
BASE = {
    "apiVersion": "v3.2.0", "kind": "DataContract",
    "id": "11111111-1111-1111-1111-111111111111",
    "name": "Sales Orders", "version": "1.0.0", "status": "active",
    "domain": "commerce", "team": {"name": "commerce-team"},
    "description": {"purpose": "Orders placed"},
    "customProperties": [{"property": "tier", "value": 2}],
    "schema": [{
        "name": "sales_orders", "logicalType": "object", "physicalType": "table",
        "properties": [
            {"name": "order_id", "logicalType": "string", "description": "Order key",
             "required": True, "primaryKey": True},
            {"name": "amount", "logicalType": "number", "description": "Gross value",
             "required": False,
             "quality": [{"type": "library", "metric": "nullValues",
                          "mustBeLessOrEqualTo": 1, "unit": "percent",
                          "dimension": "completeness"}]},
            {"name": "placed_at", "logicalType": "timestamp",
             "description": "Placement time", "required": True},
        ],
    }],
    "slaProperties": [{"property": "freshness", "value": 24, "unit": "h"},
                      {"property": "availability", "value": 99.9, "unit": "%"}],
}

@pytest.mark.parametrize("old, new, expected", CASES)
def test_classify_change(old, new, expected):
    assert classify_change(old, new) is expected
```

Verified cases. Every row ran through the prototype of this module, and every row was also run through `uvx --from datacontract-cli==1.2.9 datacontract changelog <old> <new>`. That tool reports what changed, not a severity, so it confirms the change set and the verdict is ours. Set `PYTHONUTF8=1` to run it on Windows.

| Case | Old to new | Verdict | `changelog` reports |
|---|---|---|---|
| `none-identical` | No change | NONE | Nothing |
| `none-version-only` | `version` to `1.0.1` | NONE | Updated `version`; not content, by design |
| `none-status-only` | `status` to `deprecated` | NONE | Updated `status`; not content, by design |
| `none-reorder` | `properties` and `slaProperties` reversed | NONE | Nothing |
| `none-empties` | `amount.required` key dropped, `order_id` gains `unique: false` and `classification: ""` | NONE | Key-level Removed and Added; we treat absent, false and empty as equal |
| `major-remove` | `amount` removed | MAJOR | Removed `amount` |
| `major-rename` | `amount` renamed `gross_amount` | MAJOR | Removed `amount`, Added `gross_amount` |
| `major-type` | `amount.logicalType` to `string` | MAJOR | Updated `amount` |
| `major-required-on` | `amount.required` to true | MAJOR | Updated `amount.required`, False to True |
| `major-drop-schema` | `schema` key removed | MAJOR | Removed `schema` |
| `major-beats-minor` | `amount` removed, `channel` added | MAJOR | Removed and Added |
| `minor-add` | `channel` added, optional | MINOR | Added `channel` |
| `minor-add-required` | `channel` added, `required: true` | MINOR | Added `channel` |
| `minor-relax-required` | `placed_at.required` to false | MINOR | Updated `placed_at` |
| `minor-relax-unique` | `amount.unique` from true to absent | MINOR | Removed `amount.unique` |
| `minor-first-schema` | Old document has no `schema` | MINOR | Added `schema` |
| `patch-description` | `amount.description` changed | PATCH | Updated `amount` |
| `patch-title` | `name` and `schema[0].name` changed | PATCH | Updated `name`, Added and Removed the schema object; it keys by name, we pair by position |
| `patch-owner` | `team.name` changed | PATCH | Updated `team` |
| `patch-tier` | `tier` value 2 to 1 | PATCH | Updated `customProperties.tier` |
| `patch-sla` | `freshness` value 24 to 48 | PATCH | Updated `slaProperties.freshness` |
| `patch-quality` | `mustBeLessOrEqualTo` 1 to 5 | PATCH | Updated `quality.[0]` |
| `patch-unique-on` | `amount.unique` absent to true | PATCH | Added `amount.unique` |
| `patch-domain` | `domain` changed | PATCH | Updated `domain` |

Edge rows, same parametrisation, prototype only:

| Case | Old to new | Verdict |
|---|---|---|
| `zero-is-a-value` | Quality `mustBeLessOrEqualTo: 0` to key removed | PATCH |
| `none-quality-reorder` | Two quality rules swapped | NONE |
| `none-no-schema` | No `schema` on either side | NONE |
| `patch-unknown-key` | `tags: ["x"]` added at top level | PATCH |
| `none-identity-keys` | `apiVersion`, `kind`, `id` all differ | NONE |
| `patch-pk-on` | `amount.primaryKey` to true | PATCH |
| `minor-pk-off` | `order_id.primaryKey` removed | MINOR |
| `patch-physical-type` | `amount.physicalType` added | PATCH |

Bump matrix, each row verified. `test_evolution_violation` sets `old["status"]` and `old["version"]`, gives `new` the version in the row, and asserts `(evolution_violation(old, new) is None) == allowed`. Copy `old`'s status into `new` unless the row changes it.

| Change | Status | Old to new version | Allowed |
|---|---|---|---|
| Add `x` | `active` | 1.0.0 to 1.0.0 | No |
| Add `x` | `active` | 1.0.0 to 1.0.1 | No |
| Add `x` | `active` | 1.0.0 to 1.1.0 | Yes |
| Add `x` | `active` | 1.0.0 to 2.0.0 | Yes |
| Remove `amount` | `active` | 1.0.0 to 1.1.0 | No |
| Remove `amount` | `active` | 1.0.0 to 2.0.0 | Yes |
| Remove `amount` | `deprecated` | 1.0.0 to 1.1.0 | No |
| Remove `amount` | `draft` | 1.0.0 to 1.0.0 | Yes |
| Remove `amount` | `proposed` | 1.0.0 to 1.0.0 | Yes |
| None | `active` | 1.0.0 to 1.0.0 | Yes |
| None | `active` | 1.0.0 to 1.0.1 | Yes |
| None | `active` | 1.1.0 to 1.0.0 | No |
| Add `x` | `active` | 1.9.0 to 1.10.0 | Yes |
| Remove `amount` | `active` | 1.0 to 1.1.0 | Yes |
| Add `x` | `active` | 1.0 to 1.0 | No |
| Status to `deprecated` | `active` | 1.0 to 1.0 | Yes |

`_remove_amount(**top)` returns a deep copy of `BASE` without the `amount` property, with `top` applied to the top-level keys.

```python
def test_rejection_names_the_changes_that_force_the_bump():
    message = evolution_violation(BASE, _remove_amount(version="1.1.0"))
    assert message == (
        "Contract changes require a MAJOR version bump"
        " (current 1.0.0, requested 1.1.0): property 'amount' removed"
    )

def test_rejection_of_a_lower_version():
    old = {**BASE, "version": "1.1.0"}
    assert evolution_violation(old, {**BASE, "version": "1.0.0"}) == (
        "Version 1.0.0 is lower than the current version 1.1.0"
    )

@pytest.mark.parametrize("version, expected", [
    ("1.0.0", True), ("10.20.30", True), ("0.0.0", True), ("01.2.3", True),
    ("1.0", False), ("v1.0.0", False), ("1.0.0-rc1", False), ("1.0.0\n", False),
    ("", False), ("١.٠.٠", False), (" 1.0.0", False),
])
def test_is_semver(version, expected):
    assert is_semver(version) is expected

def test_version_bump_kinds():
    assert version_bump("1.2.3", "1.2.4") is ChangeKind.PATCH
    assert version_bump("1.2.3", "1.3.0") is ChangeKind.MINOR
    assert version_bump("1.2.3", "2.0.0") is ChangeKind.MAJOR
    assert version_bump("1.2.3", "1.2.3") is ChangeKind.NONE
    assert version_bump("1.2.3", "1.2.2") is ChangeKind.NONE
    assert version_bump("1.0", "1.0.0") is ChangeKind.MAJOR

def test_is_unchanged():
    assert is_unchanged(BASE, copy.deepcopy(BASE))
    assert not is_unchanged(BASE, {**BASE, "version": "1.0.1"})
    assert not is_unchanged(BASE, {**BASE, "status": "deprecated"})
    assert not is_unchanged(BASE, {**BASE, "name": "Other"})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_contract_evolution.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.domain.contract_evolution'`.

- [ ] **Step 3: Implement the module, standard library only**

The tests fix `is_semver`, `classify_change`, `version_bump`, `is_unchanged` and both messages. What they leave open:

- `is_semver`: use `re.fullmatch` with `re.ASCII`. A plain `^...$` lets `1.0.0\n` and non-ASCII digits through.
- Normalise both documents once, at the top of `describe_changes`. Recurse. In dicts, drop keys whose normalised value is `None`, `False`, `""`, `[]` or `{}`, testing `value is False` so `0` survives. Sort every list by `json.dumps(item, sort_keys=True, default=str)`.
- The schema object is the first element of `doc.get("schema", [])`, or `{}`. Index its properties by `name`.
- Change descriptions, which end up in the 409 message:
  - `property '<n>' removed` (MAJOR) and `property '<n>' added` (MINOR).
  - `property '<n>' logicalType changed from <a> to <b>` (MAJOR).
  - `property '<n>' <flag> turned on` and `property '<n>' <flag> turned off`, for `required`, `unique` and `primaryKey`.
  - PATCH entries: `property '<n>' <key> changed`; `schema <key> changed` for schema keys other than `name` and `properties`; `<key> changed` for top-level keys other than the non-content keys and `schema`.
- `evolution_violation`, in this order:
  1. Return `None` if `old["status"]` is not governed.
  2. If both versions are semver and `new` is lower, return the lower-version message.
  3. Return `None` if `version_bump(...)` is at least the required kind.
  4. Otherwise return the bump message, naming only the changes of the required kind, joined by `; `.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_contract_evolution.py -q`
Expected: all pass.

- [ ] **Step 5: Lint and commit**

```powershell
.venv\Scripts\ruff check backend
.venv\Scripts\ruff format backend/domain/contract_evolution.py
git add backend/domain/contract_evolution.py tests/unit/test_contract_evolution.py
git commit -m "feat(contracts): classify contract changes by the evolution policy"
```

---

### Task 3: Repository transaction, lock and history

**Files:**
- Create: `backend/domain/entities/contract_version.py`
- Modify: `backend/domain/interfaces/data_contract_repository.py`
- Modify: `backend/infra/repositories/data_contract_repository.py`
- Modify: `tests/conftest.py`
- Test: `tests/unit/infra/test_contract_versions_repository.py`. The unmerged branch owns `test_data_contract_repository.py`, so do not use that name.

**Interfaces:**
- Consumes: `ContractVersionConflictError` from Task 2.
- Produces on `IDataContractRepository`, all abstract:

```python
def transaction(self) -> AbstractAsyncContextManager[Any]: ...
async def get_by_id_for_update(self, contract_id: uuid.UUID) -> DataContract | None: ...
async def add_version(self, contract_id: uuid.UUID, version: str, yaml_content: str,
                      created_by: uuid.UUID | None) -> None: ...
async def add_baseline_version(self, contract_id: uuid.UUID, version: str,
                               yaml_content: str, created_at: datetime) -> None: ...
async def list_versions(self, contract_id: uuid.UUID) -> list[ContractVersion]: ...
async def get_version_yaml(self, contract_id: uuid.UUID, version: str) -> str | None: ...
```

- Produces `ContractVersion(contract_id, version, created_by, created_at)`: a plain class like `ContractStakeholder`. It holds no YAML, so the list query stays light.
- Produces the fixture `contract_repo` in `tests/conftest.py`: an `AsyncMock` whose `transaction` is a `MagicMock`. A bare `AsyncMock` fails under `async with` with `TypeError: 'coroutine' object does not support the asynchronous context manager protocol`.

- [ ] **Step 1: Add the fixture and write the failing tests**

```python
# tests/conftest.py
@pytest.fixture
def contract_repo() -> AsyncMock:
    """Repository double whose transaction() works in `async with`."""
    repo = AsyncMock()
    repo.transaction = MagicMock()
    return repo
```

```python
# tests/unit/infra/test_contract_versions_repository.py
CONTRACT_ID = uuid.uuid4()

def _db() -> MagicMock:
    db = MagicMock()
    db.execute, db.fetch, db.fetchrow, db.fetchval = (AsyncMock() for _ in range(4))
    return db

async def test_add_version_maps_unique_violation_to_conflict():
    db = _db()
    db.execute.side_effect = asyncpg.UniqueViolationError("duplicate key")
    with pytest.raises(ContractVersionConflictError, match="1.1.0"):
        await PostgresDataContractRepository(db).add_version(CONTRACT_ID, "1.1.0", "y", None)

async def test_add_baseline_version_keeps_an_existing_row():
    db, at = _db(), datetime.now(tz=timezone.utc)
    await PostgresDataContractRepository(db).add_baseline_version(CONTRACT_ID, "1.0.0", "y", at)
    sql, *params = db.execute.call_args.args
    assert "ON CONFLICT (contract_id, version) DO NOTHING" in sql
    assert params == [CONTRACT_ID, "1.0.0", "y", at]

async def test_get_by_id_for_update_locks_only_the_contract_row():
    db = _db()
    db.fetchrow.return_value = None
    assert await PostgresDataContractRepository(db).get_by_id_for_update(CONTRACT_ID) is None
    assert "FOR UPDATE OF dc" in db.fetchrow.call_args.args[0]

async def test_list_versions_is_newest_first_and_skips_the_yaml():
    db = _db()
    db.fetch.return_value = []
    await PostgresDataContractRepository(db).list_versions(CONTRACT_ID)
    sql = db.fetch.call_args.args[0]
    assert "ORDER BY created_at DESC, version DESC" in sql
    assert "yaml_content" not in sql

async def test_get_version_yaml_is_none_for_an_unknown_version():
    db = _db()
    db.fetchval.return_value = None
    assert await PostgresDataContractRepository(db).get_version_yaml(CONTRACT_ID, "9.9.9") is None

def test_transaction_comes_from_the_connection():
    db = _db()
    assert PostgresDataContractRepository(db).transaction() is db.transaction.return_value
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/infra/test_contract_versions_repository.py -q`
Expected: FAIL with `AttributeError` on the new methods. The module imports fine because Step 1 adds nothing to the interface yet.

- [ ] **Step 3: Implement the entity, the port and the Postgres methods**

The tests fix the SQL fragments and which connection method each call uses. What they leave open:

- `get_by_id_for_update` reuses `_SELECT`. `OF dc` keeps the join from locking the domain row.
- `add_version` raises `ContractVersionConflictError(f"Version {version} already exists for this contract")`, and `created_at` comes from the column default.
- `list_versions` selects `contract_id, version, created_by, created_at`. The `version DESC` key only makes the order deterministic.

`IDataContractRepository` has no subclass outside `PostgresDataContractRepository`, so the new abstract methods break nothing.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/ -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
.venv\Scripts\ruff check backend
git add backend/domain/entities/contract_version.py backend/domain/interfaces/data_contract_repository.py backend/infra/repositories/data_contract_repository.py tests/conftest.py tests/unit/infra/test_contract_versions_repository.py
git commit -m "feat(contracts): add transaction, row lock and history to the repository"
```

---

### Task 4: Snapshots and enforcement in create and update

**Files:**
- Create: `backend/use_cases/data_contract/versioning.py`
- Modify: `backend/use_cases/data_contract/create.py`, `update.py`
- Modify: `backend/interface/routers/data_contract.py`: `create_data_contract`, `update_data_contract`
- Modify: `backend/interface/schemas/data_contract.py`: `DataContractUpdateModel.status`
- Test: `tests/unit/use_cases/data_contract/test_versioning.py`
- Test: `tests/unit/test_data_contract_use_cases.py`, `tests/unit/interface/test_routers.py`

**Interfaces:**
- Consumes: `evolution_violation`, `is_semver`, `ContractEvolutionError`, `RetiredContractError`, `RETIRED_STATUS` (Task 2); the repository methods and `contract_repo` (Task 3); `to_odcs`, `assemble_yaml` (Plan 1).
- Produces, in `backend/use_cases/data_contract/versioning.py`:

```python
def validate_new_version(version: str, previous: DataContract | None) -> None: ...
def enforce_evolution(previous: DataContract, current: DataContract) -> None: ...
async def record_version(repository: IDataContractRepository,
                         previous: DataContract | None, current: DataContract,
                         created_by: uuid.UUID | None) -> None: ...
```

- Produces: `created_by: uuid.UUID | None = None` as the last parameter of `CreateDataContractUseCase.execute` and `UpdateDataContractUseCase.execute`.
- `record_version` calls `add_baseline_version` and `add_version` with positional arguments in signature order. The tests assert positional calls.

- [ ] **Step 1: Write the failing use case tests**

Helpers for `tests/unit/use_cases/data_contract/test_versioning.py`:

```python
CID, DOMAIN_ID, USER_ID = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
NOW = datetime.now(tz=timezone.utc)
EARLIER = NOW - timedelta(days=1)
FIELD = {"name": "id", "type": "string", "description": "", "nullable": False,
         "primary_key": True}
WITH_AMOUNT = {"fields": [FIELD, {**FIELD, "name": "amount", "primary_key": False}],
               "quality": []}
NO_FIELDS = {"fields": [], "quality": []}

def _contract(**kw) -> DataContract:
    defaults = dict(id=CID, title="T", version="1.0.0", owner="o", domain="d",
                    domain_id=DOMAIN_ID, tier=3, status="active",
                    models={"fields": [FIELD], "quality": []},
                    servicelevels={"properties": []}, created_at=NOW, updated_at=NOW)
    return DataContract(**{**defaults, **kw})

async def _put(repo, before: DataContract, after: DataContract) -> DataContract | None:
    """`before` is the locked row; the repository's update returns `after`."""
    repo.get_by_id_for_update.return_value = before
    repo.update.return_value = after
    return await UpdateDataContractUseCase(repo).execute(
        contract_id=CID, title=after.title, version=after.version, owner=after.owner,
        domain_id=DOMAIN_ID, tier=after.tier, status=after.status, models=after.models,
        servicelevels=after.servicelevels, created_by=USER_ID)
```

Each row is one async test taking `contract_repo`. It runs `await _put(contract_repo, before, after)` and asserts the last column. "Raises `X`, `"m"`" means `pytest.raises(X, match="m")`, and every raising row also asserts `contract_repo.add_version.assert_not_called()`.

| Test | `before` | `after` | Assert |
|---|---|---|---|
| `test_status_only_update_keeps_working_without_a_snapshot` | `_contract()` | `_contract(status="deprecated")` | Returns `after`; `add_version` and `add_baseline_version` not called |
| `test_content_change_without_bump_on_active_is_rejected` | `_contract()` | `_contract(models=WITH_AMOUNT)` | Raises `ContractEvolutionError`, `"property 'amount' added"` |
| `test_bump_smaller_than_the_change_is_rejected` | `_contract()` | `_contract(models=NO_FIELDS, version="1.1.0")` | Raises `ContractEvolutionError`, `"require a MAJOR version bump"` |
| `test_deprecated_contract_is_governed` | `_contract(status="deprecated")` | `_contract(status="deprecated", models=WITH_AMOUNT)` | Raises `ContractEvolutionError` |
| `test_draft_changes_freely` | `_contract(status="draft")` | `_contract(status="draft", models=NO_FIELDS)` | Returns `after` |
| `test_previous_status_decides_when_rules_apply` | `_contract()` | `_contract(status="draft", models=WITH_AMOUNT)` | Raises `ContractEvolutionError` |
| `test_bump_writes_the_snapshot_inside_the_transaction` | `_contract()` | `_contract(version="1.1.0", models=WITH_AMOUNT)` | `transaction.assert_called_once()`; `add_version.assert_called_once_with(CID, "1.1.0", assemble_yaml(after), USER_ID)` |
| `test_first_bump_without_history_captures_the_old_version_first` | `_contract(updated_at=EARLIER)` | `_contract(version="1.1.0", models=WITH_AMOUNT)` | `add_baseline_version.assert_called_once_with(CID, "1.0.0", assemble_yaml(before), EARLIER)`, and it comes before `add_version` in `contract_repo.method_calls` |
| `test_retired_contract_rejects_every_update` | `_contract(status="retired")` | The same object | Raises `RetiredContractError`, `"retired"`; `update` not called |
| `test_any_status_can_become_retired` | `_contract()` | `_contract(status="retired")` | Returns `after`; `add_version` not called |
| `test_new_version_must_be_semver` | `_contract()` | `_contract(version="1.1")` | Raises `ValueError`, `"MAJOR.MINOR.PATCH"`; `update` not called |
| `test_unchanged_legacy_version_passes` | `_contract(version="1.0")` | `_contract(version="1.0", status="deprecated")` | Returns `after` |
| `test_resubmitted_form_defaults_are_not_a_change` | `_contract()` | `_contract(models={"fields": [{**FIELD, "classification": "", "unique": False, "physical_type": ""}], "quality": []})` | Returns `after` |

Three tests call the use cases directly:

- `test_missing_contract_returns_none`: `get_by_id_for_update` returns `None`. `execute` returns `None`, and `update` is not called.
- `test_create_writes_the_first_snapshot_without_a_baseline`: `create` returns `created = _contract(status="draft")`. `add_version.assert_called_once_with(CID, "1.0.0", assemble_yaml(created), USER_ID)` holds, and `add_baseline_version` is not called.
- `test_create_rejects_a_non_semver_version`: `version="1.0"` raises `ValueError` matching `"MAJOR.MINOR.PATCH"`, and `create` is not called.

In `tests/unit/test_data_contract_use_cases.py`, change `test_create_calls_repository`, `test_create_passes_title_to_repo`, `test_update_calls_repository` and `test_update_passes_title_to_repo` to take `contract_repo` instead of a local `AsyncMock()`. A bare `AsyncMock` cannot enter `transaction()`. Set `contract_repo.get_by_id_for_update.return_value = make_contract(status="draft")` in the two update tests. Give `make_contract` a `servicelevels` value `to_odcs` accepts after Plan 4, if it does not already have one.

- [ ] **Step 2: Write the failing router tests**

Add to `tests/unit/interface/test_routers.py`. Override `get_get_data_contract_use_case` (returning `_contract()`), the create and update use case dependencies, and `get_github_client` (an `AsyncMock`), as `test_update_data_contract` does. `VIOLATION = "Contract changes require a MAJOR version bump (current 1.0.0, requested 1.0.1): property 'amount' removed"`.

| Test | Use case stub | Request | Assert |
|---|---|---|---|
| `test_update_policy_rejection_returns_409_and_skips_github`, parametrised over `ContractEvolutionError(VIOLATION)`, `ContractVersionConflictError("Version 1.1.0 already exists for this contract")` and `RetiredContractError("retired")` | `execute.side_effect = error` | `PUT {"version": "1.0.1"}` | 409; `detail == str(error)`; `github.push.assert_not_called()` |
| `test_update_invalid_version_returns_400` | `side_effect = ValueError("Version '1.1' must match MAJOR.MINOR.PATCH")` | `PUT {"version": "1.1"}` | 400 |
| `test_status_only_put_merges_the_stored_fields` | `return_value = _contract()` | `PUT {"status": "active"}` | 200; call kwargs: `status == "active"`, `version == "1.0.0"`, `models == _contract().models`, `created_by == USER_ID` |
| `test_update_accepts_retired_status` | `return_value = _contract()` | `PUT {"status": "retired"}` | 200 |
| `test_create_rejects_retired_status` | None | `POST`, valid body with `"status": "retired"` | 422 |
| `test_create_passes_the_user_to_the_snapshot` | As `test_create_data_contract` | As `test_create_data_contract` | `execute.call_args.kwargs["created_by"] == USER_ID` |

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/use_cases/data_contract/test_versioning.py tests/unit/interface/test_routers.py tests/unit/test_data_contract_use_cases.py -q`
Expected: FAIL.
- The use case tests fail with `TypeError: ... got an unexpected keyword argument 'created_by'`.
- The 409 router tests error on the uncaught `ContractEvolutionError`.
- `test_update_accepts_retired_status` returns 422.

- [ ] **Step 4: Implement `versioning.py`**

The tests fix the behaviour of all three functions. `validate_new_version` raises `ValueError(f"Version '{version}' must match MAJOR.MINOR.PATCH")`.

- [ ] **Step 5: Implement the use cases**

`CreateDataContractUseCase.execute`, after the title check: `validate_new_version(version, None)`, then inside `async with self.repository.transaction():` call `create` and `record_version(self.repository, None, contract, created_by)`.

`UpdateDataContractUseCase.execute`, after the title check, inside `async with self.repository.transaction():`

1. `current = await self.repository.get_by_id_for_update(contract_id)`. Return `None` if it is `None`.
2. If `current.status == RETIRED_STATUS`, raise `RetiredContractError(f"Contract {contract_id} is retired and cannot be changed")`.
3. `validate_new_version(version, current)`.
4. `updated = await self.repository.update(...)`, unchanged arguments.
5. `enforce_evolution(current, updated)`. Raising here rolls back step 4.
6. `await record_version(self.repository, current, updated, created_by)`.
7. Return `updated`.

- [ ] **Step 6: Implement the router and schema changes**

- `update_data_contract`: pass `created_by=current_user.id`, and add `except ContractEvolutionError as e: raise HTTPException(status_code=409, detail=str(e))` before the existing `except ValueError`. The GitHub push stays after the `try`, so a rejected request never reaches GitHub.
- `create_data_contract`: pass `created_by=current_user.id`.
- `DataContractUpdateModel.status`: add `"retired"` to the `Literal`. `DataContractCreateModel.status` keeps its four values, because a contract is not born retired.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/ -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```powershell
.venv\Scripts\ruff check backend
git add backend/use_cases/data_contract/versioning.py backend/use_cases/data_contract/create.py backend/use_cases/data_contract/update.py backend/interface/routers/data_contract.py backend/interface/schemas/data_contract.py tests/unit/use_cases/data_contract/test_versioning.py tests/unit/test_data_contract_use_cases.py tests/unit/interface/test_routers.py
git commit -m "feat(contracts): snapshot versions and enforce semver on update"
```

---

### Task 5: Enforcement in sync

**Files:**
- Modify: `backend/use_cases/data_contract/sync_from_github.py`
- Modify: `backend/use_cases/data_contract/odcs.py`
- Modify: `backend/interface/routers/data_contract.py`: `sync_data_contracts_from_github`
- Test: `tests/unit/use_cases/data_contract/test_sync_from_github.py`, `tests/unit/interface/test_routers.py`
- Test: Plan 1's `tests/unit/use_cases/data_contract/test_odcs_parse.py` and `test_odcs_emit.py` (status cases)

**Interfaces:**
- Consumes: `validate_new_version`, `enforce_evolution`, `record_version` (Task 4); `is_unchanged`, `RetiredContractError`, `RETIRED_STATUS` (Task 2); `to_odcs`, `from_odcs`, `parse_contract_document`, `_DB_STATUSES` (Plan 1); `_yaml(...)` in `test_sync_from_github.py`, which Plan 2 Task 7 made emit ODCS.
- Produces: `SyncFromGitHubUseCase.execute(created_by: uuid.UUID | None = None) -> dict[str, Any]`, same return shape.

- [ ] **Step 1: Adapt the fixture and write the failing tests**

Change the `repo` fixture so the file-level tests reach the new flow, and give `_contract` a `status` parameter, `models={"fields": []}` and `servicelevels={"properties": []}`:

```python
@pytest.fixture
def repo(contract_repo):
    contract_repo.get_by_id_for_update.return_value = None   # new contract by default
    contract_repo.get_by_id.return_value = _contract()       # the read after upsert
    contract_repo.upsert.return_value = True
    return contract_repo
```

`test_domain_mismatch_adds_error` and any other test that sets `repo.get_by_id` to simulate an existing contract now sets `repo.get_by_id_for_update`.

Define `FIELD` as in Task 4, and `USER_ID = uuid.uuid4()`. Each row is one test:
- `get_by_id_for_update` returns "Stored".
- `get_by_id`, the read after upsert, returns "After upsert".
- `upsert` returns `False` when Stored is a contract.
- `github.list_all_yaml_contents` returns `[("c/o.yaml", <File>)]`.

`result` is `await use_case.execute()`, and `errors` is `result["errors"]`.

| Test | Stored | After upsert | File | Assert |
|---|---|---|---|---|
| `test_new_contract_writes_the_first_snapshot` | `None` | `_contract()` | `_yaml()`, run with `execute(created_by=USER_ID)` | `add_version.assert_called_once_with(CONTRACT_ID, "1.0.0", ANY, USER_ID)`; `add_baseline_version` not called |
| `test_version_change_writes_a_snapshot` | `_contract(status="active")` | `_contract(status="active", version="1.0.1")` | `_yaml(version="1.0.1", status="active")` | `result == {"created": 0, "updated": 1, "errors": []}`; `add_version` called once |
| `test_unchanged_file_writes_no_snapshot` | `_contract(status="active")` | `_contract(status="active")` | `_yaml(status="active")` | `result["updated"] == 1`; `add_version` not called |
| `test_breaking_change_without_bump_is_reported_and_skipped` | `_contract(status="active", models={"fields": [FIELD]})` | `_contract(status="active", models={"fields": []})` | `_yaml(status="active")` | `result["updated"] == 0`; `errors[0]["path"] == "c/o.yaml"`; `"require a MAJOR version bump" in errors[0]["error"]`; `add_version` not called |
| `test_file_behind_database_is_reported_and_skipped` | `_contract(status="active", version="1.1.0")` | `_contract(status="active", version="1.0.0")` | `_yaml(status="active")` | `"lower than the current version 1.1.0" in errors[0]["error"]` |
| `test_retired_contract_with_unchanged_file_is_silent` | `stored = _contract(status="retired")` | Unused | `assemble_yaml(stored)` | `result == {"created": 0, "updated": 0, "errors": []}`; `upsert` not called |
| `test_retired_contract_with_changed_file_is_reported` | `_contract(status="retired")` | Unused | `_yaml(status="active")` | `"is retired" in errors[0]["error"]`; `upsert` not called |
| `test_invalid_version_is_reported_before_any_write` | `None`, and `domain_repo.find_by_name` returns `None` | Unused | `_yaml(version="1.0")` | `"MAJOR.MINOR.PATCH" in errors[0]["error"]`; `domain_repo.create` and `upsert` not called |

Three more:

- `test_one_rejected_file_does_not_stop_the_others`: three files `a.yaml`, `b.yaml`, `c.yaml` with fresh ids, `b.yaml` having `version="bad"`. Then `result["created"] == 2` and `[e["path"] for e in errors] == ["b.yaml"]`.
- `test_retired_round_trips_through_odcs`: `from_odcs(to_odcs(_contract(status="retired"))).status == "retired"`.
- Plan 1's tests that enumerate statuses, since the spec's round trip covers "every combination the model allows": add `"retired"` to the statuses of `test_round_trip_status_and_tier` in `test_odcs_parse.py`, and `("retired", "retired")` to `test_status_mapping` in `test_odcs_emit.py`. `test_parse_errors` in `test_odcs_parse.py` has the case `({"status": "retired"}, "status 'retired'")`, which stops raising once `retired` is accepted: change it to `({"status": "bogus"}, "status 'bogus'")`.
- `test_sync_passes_the_admin_id`, in `test_routers.py`: override `get_github_client` with an `AsyncMock` and `monkeypatch.setattr(SyncFromGitHubUseCase, "execute", AsyncMock(return_value={"created": 0, "updated": 0, "errors": []}))`. Then `POST /api/v1/data-contracts/sync` returns 200 and `execute.call_args.kwargs["created_by"] == USER_ID`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/use_cases/data_contract/test_sync_from_github.py tests/unit/interface/test_routers.py -q`
Expected: FAIL.
- `test_retired_round_trips_through_odcs` raises `OdcsParseError` if Plan 1's status check predates `retired`.
- The other tests fail on the unexpected `created_by` argument or on missing `add_version` calls.

- [ ] **Step 3: Accept `retired` in `from_odcs`**

Spec, Parsing errors: `from_odcs` rejects "a status the database does not accept". The database now accepts `retired`, so add `"retired"` to Plan 1's `_DB_STATUSES` constant in `odcs.py` (spec decision 5). Plan 1 builds the status error message from that constant, so the message lists `retired` with no second edit. Change nothing else there.

- [ ] **Step 4: Move the per-file work into `_sync_file`**

`execute` keeps its loop and its `except Exception` branch, and calls `_sync_file(path, content, created_by) -> bool | None`, counting `True` as created and `False` as updated. `None` counts nothing. The extraction keeps `execute` under ruff's complexity limit of 15.

`_sync_file`:

1. Parse the YAML and call `parse_contract_document`, as Plan 1 left it. Keep Plan 1's missing-domain handling and message.
2. Inside `async with self.repository.transaction():`
   1. `current = await self.repository.get_by_id_for_update(parsed.id)`. This replaces the `get_by_id` read.
   2. Keep the domain-mismatch check on `current`, with its existing text.
   3. If `current` is retired: return `None` when `is_unchanged(to_odcs(current), data)`. Otherwise raise `RetiredContractError(f"Contract {parsed.id} is retired; its file changed and was ignored")`.
   4. `validate_new_version(parsed.version, current)`.
   5. `domain_id = await self._resolve_domain_id(parsed.domain_name)`. It now runs in the transaction, so a rejected file leaves no new domain behind.
   6. `was_created = await self.repository.upsert(...)`, unchanged arguments.
   7. `stored = await self.repository.get_by_id(parsed.id)`.
   8. If `current` exists: `enforce_evolution(current, stored)`.
   9. `await record_version(self.repository, current, stored, created_by)`.
   10. Return `was_created`.

Any raise inside the transaction rolls that file back and lands in the existing `except Exception`, which adds `{"path": path, "error": str(exc)}`. Other files are unaffected. Move the domain-mismatch `errors.append` and `continue` to a `raise ValueError(<same text>)` so the output does not change.

- [ ] **Step 5: Pass the admin's id from the router**

In `sync_data_contracts_from_github`, rename `_: User = Depends(_admin_only)` to `current_user`, and call `use_case.execute(created_by=current_user.id)`.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/ -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```powershell
.venv\Scripts\ruff check backend
git add backend/use_cases/data_contract/sync_from_github.py backend/use_cases/data_contract/odcs.py backend/interface/routers/data_contract.py tests/unit/use_cases/data_contract/test_sync_from_github.py tests/unit/use_cases/data_contract/test_odcs_parse.py tests/unit/use_cases/data_contract/test_odcs_emit.py tests/unit/interface/test_routers.py
git commit -m "feat(contracts): enforce the evolution policy in GitHub sync"
```

---

### Task 6: Version read endpoints

**Files:**
- Create: `backend/use_cases/data_contract/list_versions.py`, `backend/use_cases/data_contract/get_version_yaml.py`
- Modify: `backend/interface/dependencies.py`, `backend/interface/schemas/data_contract.py`, `backend/interface/routers/data_contract.py`
- Test: `tests/unit/interface/test_routers.py`, `tests/unit/use_cases/data_contract/test_version_reads.py`

**Interfaces:**
- Consumes: `get_by_id`, `list_versions`, `get_version_yaml` (Task 3).
- Produces:

```python
class ListContractVersionsUseCase:      # None means the contract does not exist
    async def execute(self, contract_id: uuid.UUID) -> list[ContractVersion] | None: ...

class GetContractVersionYamlUseCase:
    async def execute(self, contract_id: uuid.UUID, version: str) -> str | None: ...

class ContractVersionResponseModel(BaseModel):
    version: str
    created_by: uuid.UUID | None
    created_at: datetime
```

- Produces: `get_list_contract_versions_use_case`, `get_get_contract_version_yaml_use_case` in `dependencies.py`.
- Produces: `GET /api/v1/data-contracts/{contract_id}/versions` (200 JSON, newest first) and `GET /api/v1/data-contracts/{contract_id}/versions/{version}/yaml` (200 `text/plain`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/use_cases/data_contract/test_version_reads.py
async def test_list_versions_is_none_for_an_unknown_contract(contract_repo):
    contract_repo.get_by_id.return_value = None
    assert await ListContractVersionsUseCase(contract_repo).execute(uuid.uuid4()) is None
    contract_repo.list_versions.assert_not_called()

async def test_list_versions_returns_the_repository_rows(contract_repo):
    contract_repo.get_by_id.return_value = MagicMock()
    contract_repo.list_versions.return_value = []
    assert await ListContractVersionsUseCase(contract_repo).execute(uuid.uuid4()) == []

async def test_get_version_yaml_passes_the_version_through(contract_repo):
    contract_repo.get_version_yaml.return_value = "apiVersion: v3.2.0\n"
    cid = uuid.uuid4()
    assert await GetContractVersionYamlUseCase(contract_repo).execute(cid, "1.0.0") == "apiVersion: v3.2.0\n"
    contract_repo.get_version_yaml.assert_called_once_with(cid, "1.0.0")
```

Router tests in `tests/unit/interface/test_routers.py` override the two new use case dependencies, plus `get_stakeholder_repository` for the consumer rows. Define `_versions() = [ContractVersion(CONTRACT_ID, "1.1.0", USER_ID, NOW), ContractVersion(CONTRACT_ID, "1.0.0", None, NOW)]`. "List" and "YAML" are paths under `/api/v1/data-contracts/{CONTRACT_ID}/`: `versions` and `versions/1.0.0/yaml`.

| Test | Client and stub | Request | Assert |
|---|---|---|---|
| `test_list_versions` | Admin; list returns `_versions()` | `GET` List | 200; versions in order `["1.1.0", "1.0.0"]`; `json[1]["created_by"] is None`; no `yaml_content` key |
| `test_list_versions_empty_for_contract_without_history` | Admin; list returns `[]` | `GET` List | 200 and `[]` |
| `test_list_versions_unknown_contract_is_404` | Admin; list returns `None` | `GET` List | 404 |
| `test_get_version_yaml` | Admin; YAML returns `"apiVersion: v3.2.0\nversion: 1.0.0\n"` | `GET` YAML | 200; body identical; `content-type` starts with `text/plain` |
| `test_get_version_yaml_unknown_version_is_404` | Admin; YAML returns `None` | `GET` YAML | 404 |
| `test_version_reads_forbidden_for_non_stakeholder_consumer`, parametrised over both paths | `consumer_client`; `is_stakeholder` returns `False` | `GET` | 403; neither use case ran |
| `test_version_reads_allowed_for_stakeholder_consumer`, parametrised over both paths | `consumer_client`; `is_stakeholder` returns `True`; stubs as in the 200 rows | `GET` | 200 |

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/use_cases/data_contract/test_version_reads.py tests/unit/interface/test_routers.py -q`
Expected: FAIL with `ModuleNotFoundError` for the new use cases.

- [ ] **Step 3: Implement the use cases, dependencies, schema and routes**

Each route takes `stakeholder_repo=Depends(get_stakeholder_repository)` and `current_user: User = Depends(get_current_user)`, and calls `_require_contract_read_access(contract_id, current_user, stakeholder_repo)` first, exactly like `get_data_contract_yaml`, whose docstring requires it. The 404 details are `Data contract not found` and `Contract version not found`. The YAML route returns `PlainTextResponse(content, media_type="text/plain")` with the stored text untouched. Starlette's default `{version}` converter accepts dots.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/ -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
.venv\Scripts\ruff check backend
git add backend/use_cases/data_contract/list_versions.py backend/use_cases/data_contract/get_version_yaml.py backend/interface/dependencies.py backend/interface/schemas/data_contract.py backend/interface/routers/data_contract.py tests/unit/use_cases/data_contract/test_version_reads.py tests/unit/interface/test_routers.py
git commit -m "feat(api): expose contract version history"
```

---

### Task 7: History list and `retired` in the frontend

**Files:**
- Modify: `frontend/src/types/index.ts`, `frontend/src/hooks/useDataContracts.ts`
- Modify: `frontend/src/pages/DataContracts/DataContractDetail.tsx`, `frontend/src/pages/DataContracts/DataContractForm.tsx`
- Test: `frontend/src/pages/DataContracts/DataContractDetail.test.tsx`, `frontend/src/pages/DataContracts/DataContractForm.test.tsx`

**Interfaces:**
- Consumes: the two endpoints from Task 6.
- Produces:

```ts
export interface ContractVersion { version: string; created_by: string | null; created_at: string }
export function useContractVersions(id: string): UseQueryResult<ContractVersion[], Error>
export function useContractVersionYaml(id: string, version: string | null): UseQueryResult<string, Error>
```

- [ ] **Step 1: Write the failing tests**

`DataContractDetail.test.tsx` exists already: Plan 3 Task 7 created it, and Plan 4 added to it. It mocks `../../hooks/useDataContracts` and `./DataContractForm`, renders through `MemoryRouter` at `/data-contracts/c1`, and has a `base` contract (id `c1`, version `1.0.0`), `renderDetail(contract)` and the mutation stubs in `beforeEach`. Reuse them:
- Add `useContractVersions: vi.fn()` and `useContractVersionYaml: vi.fn()` to its `vi.mock` factory, and call `mockVersions([])` in its `beforeEach`, so the earlier tests keep rendering once the page calls the new hook.
- Give `renderDetail`'s parameter a default of `{}`.
- `mockVersions(rows)` makes `useContractVersions` return `{ data: rows, isLoading: false, isError: false }`, and `useContractVersionYaml` return `{ data: undefined, isFetching: false }` unless the test overrides it.
- `T1` and `T2` are two ISO timestamps, `T1` the earlier.

`DataContractForm.test.tsx` also exists from Plan 3 Task 6, with its mocks and the `contract` fixture. Its `renderForm(value)` always passes `defaultValues`, so the test below renders the form directly for the create case.

```tsx
describe('DataContractDetail version history', () => {
  it('lists versions in the order the API returns and marks the current one', () => {
    mockVersions([{ version: '1.1.0', created_by: null, created_at: T2 },
                  { version: '1.0.0', created_by: null, created_at: T1 }])
    renderDetail({ version: '1.1.0' })
    const rows = screen.getAllByTestId('version-row')
    expect(rows[0]).toHaveTextContent('1.1.0')
    expect(rows[0]).toHaveTextContent('current')
    expect(rows[1]).toHaveTextContent('1.0.0')
    expect(rows[1]).not.toHaveTextContent('current')
  })

  it('empty history shows the empty state', () => {
    mockVersions([])
    renderDetail()
    expect(screen.getByText('No history yet. It starts at the next version change.')).toBeInTheDocument()
  })

  it('shows a message when the history cannot load', () => {
    vi.mocked(useContractVersions).mockReturnValue({ data: undefined, isLoading: false, isError: true } as never)
    renderDetail()
    expect(screen.getByText('Could not load version history.')).toBeInTheDocument()
  })

  it('opens the YAML of the chosen version', async () => {
    mockVersions([{ version: '1.0.0', created_by: null, created_at: T1 }])
    vi.mocked(useContractVersionYaml).mockReturnValue({ data: 'version: 1.0.0', isFetching: false } as never)
    renderDetail()
    await userEvent.click(screen.getByRole('button', { name: 'View YAML for version 1.0.0' }))
    expect(vi.mocked(useContractVersionYaml)).toHaveBeenLastCalledWith('c1', '1.0.0')
    expect(screen.getByText('version: 1.0.0')).toBeInTheDocument()
  })

  it('hides Edit on a retired contract and keeps Delete', () => {
    mockVersions([])
    renderDetail({ status: 'retired' })
    expect(screen.queryByRole('button', { name: /edit/i })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument()
  })
})
```

`DataContractForm.test.tsx`, reusing Plan 3's mocks and `contract`:

```tsx
it('offers Retired only when editing', () => {
  const props = { onSubmit: vi.fn(), onCancel: vi.fn(), isSubmitting: false }
  const { unmount } = render(<DataContractForm defaultValues={contract} {...props} />)
  expect(screen.getByRole('option', { name: 'Retired' })).toBeInTheDocument()
  unmount()
  render(<DataContractForm {...props} />)
  expect(screen.queryByRole('option', { name: 'Retired' })).not.toBeInTheDocument()
})
```

- [ ] **Step 2: Run the tests to verify they fail**

From `frontend/`, run: `npm test -- src/pages/DataContracts`
Expected: FAIL. The mocked hooks do not exist, and the option is absent.

- [ ] **Step 3: Implement the types and hooks**

- `types/index.ts`: add `'retired'` to `DataContract.status`, and add `ContractVersion`.
- `useDataContracts.ts`: add `versions: (id) => ['data-contracts', id, 'versions']` and `versionYaml: (id, version) => ['data-contracts', id, 'versions', version, 'yaml']` to `KEYS`. `useContractVersions` calls `get<ContractVersion[]>` on `/data-contracts/${id}/versions`, `enabled: !!id`. `useContractVersionYaml` calls `getText` on `/data-contracts/${id}/versions/${encodeURIComponent(version)}/yaml`, `enabled: !!id && !!version`. `useUpdateDataContract` already invalidates `KEYS.one(id)`, whose prefix covers both new keys, so it needs no change.

- [ ] **Step 4: Implement the page and the form**

- `DataContractDetail.tsx`: add `VersionHistoryCard({ contractId, currentVersion, onView })` after `ServiceLevelsCard` in the same `Card` style, titled `Version History`. Each row has `data-testid="version-row"`, the version in `font-mono`, a `Badge` reading `current` when it equals `contract.version`, `formatDateTime(created_at)`, and a secondary small `Button` with `aria-label={`View YAML for version ${v.version}`}`.
- Show the empty text and the error text exactly as the tests have them.
- Add `const [openVersion, setOpenVersion] = useState<string | null>(null)` and a second `Modal` titled `` `Version ${openVersion}` ``, using the same `<pre>` and `Spinner` as the existing YAML modal.
- Render the Edit button only when `contract.status !== 'retired'`.
- `STATUS_COLORS` already falls back to `gray`, so it needs no entry.
- `DataContractForm.tsx`: add `'retired'` to the zod enum, and render `<option value="retired">Retired</option>` only when `defaultValues` is set. Add no zod rule for the version: the backend owns it, must let an unchanged legacy value through, and its 400 and 409 messages already show through `updateMutation.error.message`.

- [ ] **Step 5: Run tests, lint and build**

From `frontend/`, run: `npm test`, `npm run lint`, `npm run build`
Expected: all pass, with `--max-warnings 0` clean.

- [ ] **Step 6: Commit**

```powershell
git add frontend/src/types/index.ts frontend/src/hooks/useDataContracts.ts frontend/src/pages/DataContracts/DataContractDetail.tsx frontend/src/pages/DataContracts/DataContractForm.tsx frontend/src/pages/DataContracts/DataContractDetail.test.tsx frontend/src/pages/DataContracts/DataContractForm.test.tsx
git commit -m "feat(ui): show contract version history and the retired status"
```

---

### Task 8: End-to-end verification on Postgres

The repository has no integration tests, and every test above mocks the database. This task proves the wiring: the real lock query, the transaction, the cascade as owner. Its only repository change is Step 7, which documents the known limitations in the README (spec decision 13).

**Files:**
- Modify: `README.md`, section "Política de Evolução" (Step 7). The request script lives in the session scratch directory.

**Interfaces:**
- Consumes: the running API and the throwaway database from Task 1.

- [ ] **Step 1: Recreate the database**

Repeat Task 1, Steps 5 and 6.
Expected: exit 0.

- [ ] **Step 2: Set the environment and start the API**

`GITHUB_TOKEN` must be set to a non-empty invalid value. In PowerShell, assigning `""` deletes the variable, `load_dotenv` then loads the real token from `.env`, and this run would push to the central contracts repository.

```powershell
$env:DB_USER="admin"; $env:ADMIN_PASSWORD="plan5"; $env:DB_HOST="127.0.0.1"; $env:MIGRATIONS_DB_HOST="127.0.0.1"
$env:DB_PORT="55433"; $env:DB_NAME="data_mesh_plt"; $env:DB_SSL_MODE="disable"
$env:JWT_SECRET_KEY="plan5-smoke-secret-key-at-least-32-bytes"  # gitleaks:allow (throwaway local smoke-test value)
$env:GITHUB_TOKEN="invalid"; $env:GITHUB_REPO="invalid/invalid"
$env:PLATFORM_ADMIN_USER="smoke@example.com"; $env:PLATFORM_ADMIN_PASS="Smoke-Pass-123!"
.venv\Scripts\python.exe scripts\seed_admin.py
.venv\Scripts\python.exe -m uvicorn backend.main:app --port 8765
```
Expected: the seed succeeds, then `Application startup complete`. Run uvicorn in the background and keep its log.

- [ ] **Step 3: Run the request sequence**

Write an `httpx` script in the scratch directory. It logs in through `POST /api/v1/auth/login`, creates a domain through `POST /api/v1/domains`, then asserts:

| # | Request on `/api/v1/data-contracts` | Expected |
|---|---|---|
| 1 | `POST`: `draft`, `1.0.0`, field `id` | 201 |
| 2 | `GET /{id}/versions` | 200, one row `1.0.0` |
| 3 | `PUT {"status": "active"}` | 200, still one row |
| 4 | `PUT` models adding `amount`, version omitted | 409, detail contains `property 'amount' added` |
| 5 | Same, `"version": "1.0.1"` | 409, detail contains `require a MINOR version bump` |
| 6 | Same, `"version": "1.1.0"` | 200, rows `1.1.0` then `1.0.0` |
| 7 | `GET /{id}/versions/1.0.0/yaml` | 200, contains `apiVersion: v3.2.0`, no `amount` |
| 8 | `PUT {"version": "1.2"}` | 400 |
| 9 | 10 rounds of `asyncio.gather` on two `PUT`s from the same state: one adds a field with a MINOR bump, the other edits a description with a PATCH bump | Every status is 200 or 409, never 500, and the stored version never decreases |
| 10 | `PUT {"status": "retired"}`, then `PUT {"title": "X"}` | 200, then 409 |
| 11 | `DELETE /{id}` | 204 |
| 12 | `GET /{id}/versions` | 404 |

Expected: every row holds, and the uvicorn log shows `GitHub push failed` warnings only. Those warnings are the invalid token doing its job.

- [ ] **Step 4: Confirm nothing is left**

Run: `docker exec plan5-pg psql -U postgres -d data_mesh_plt -Atc "select count(*) from catalog.contract_versions"`
Expected: `0`, or only rows of contracts other than the one deleted in row 11.

- [ ] **Step 5: Tear down**

Stop uvicorn, then run `docker rm -f plan5-pg; docker network rm plan5-net`. Close the shell, or clear the variables set in Step 2, so nothing later inherits them.
Expected: both names printed.

- [ ] **Step 6: Run the full gates**

```powershell
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\ruff check backend
.venv\Scripts\ruff format --check backend
```
From `frontend/`: `npm test`, `npm run lint`, `npm run build`.
Then write `assemble_yaml` of a `retired` `DataContract` to `retired.yaml` in the scratch directory with a short script, and run `uvx --from datacontract-cli==1.2.9 datacontract lint retired.yaml --output retired-lint.json --output-format json`.
Expected: all pass, and `retired-lint.json` has `"result": "passed"`. Judge the report, not the exit code or the printed text (spec decision 2): lint exits 0 with `result: warning`. On Windows, set `$env:PYTHONUTF8="1"` before `datacontract`, or it fails on a console encoding error.

- [ ] **Step 7: Document the known limitations in the README**

Spec decision 13 accepts four limitations and documents them instead of fixing them. In `README.md`, section `## Política de Evolução`, insert this block after the paragraph that ends "com base no atributo `tier` do produto." and before the `---` that closes the section. The text is exact. The heading ends in `\`, the hard line break Plan 1 Task 5 put on the README's other bold headings, because the `trailing-whitespace` hook strips a two-space break.

```markdown
**Limitações conhecidas**\
A plataforma aplica esta política com quatro limitações, aceitas e documentadas em vez de corrigidas:

- As regras valem apenas para contratos `active` ou `deprecated`. Mover um contrato `active` para `draft`, editá-lo e devolvê-lo a `active` contorna a política.
- O histórico grava um snapshot só quando a versão muda. Edições feitas depois, na mesma versão, podem divergir do snapshot dessa versão.
- A lista de mudanças MAJOR é fechada: remover ou renomear uma propriedade, mudar seu `logicalType` ou torná-la obrigatória. A plataforma não detecta mudança de significado semântico, e qualquer outra alteração conta como MINOR ou PATCH.
- `GET /data-contracts` devolve os contratos completos também para consumidores.
```

Run, in Git Bash: `grep -n 'Limita.* conhecidas' README.md`, then `grep -c '  $' README.md`
Expected: one line, inside the section (after the `## Política de Evolução` line and before `## Decisões de Design e Trade-offs`), then `0`.

- [ ] **Step 8: Commit**

```powershell
git add README.md
git commit -m "docs: document the known limitations of the contract evolution policy"
```
