# ODCS Contract Metadata Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Contracts carry a description, team members, support channels, servers, and per-field classification, uniqueness and physical type, from Postgres through the API and ODCS YAML to the form and the detail page.

**Architecture:** Four JSONB columns on `catalog.data_contracts`, plus three keys inside the existing `models.fields[]` JSON, which needs no schema change. A pure module, `backend/domain/contract_metadata.py`, owns the server rules so Pydantic and `from_odcs` enforce the same thing. New repository and use case parameters are required, so a forgotten caller fails with `TypeError` instead of clearing stored data.

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2.13, asyncpg, PostgreSQL 16, Atlas through its Docker image, React 18, react-hook-form, zod, Vitest, Testing Library.

**Spec:** `docs/superpowers/specs/2026-11-01-odcs-adoption-design.md` (Decisions Made During Planning, which win over the rest; Plan 3, Shared Interfaces, ODCS Mapping, Validation, Repository Rules)

**Prerequisites:** Plans 1 and 2 have shipped. Before Task 1, confirm that `backend/use_cases/data_contract/odcs.py` defines `to_odcs`, `from_odcs`, `ParsedContract` and `OdcsParseError`, that `parse_contract_document` calls `from_odcs`, that `tests/fixtures/odcs/odcs-json-schema-v3.2.0.json` exists, and that `jsonschema` is a dev dependency. If any is missing, stop and report it. Line numbers below are from `develop` at `f02160d`, so find code by name.

## Global Constraints

- Target standard: ODCS `v3.2.0`. Every contract the platform emits passes `uvx --from datacontract-cli==1.2.9 datacontract lint` and the vendored JSON Schema.
- Columns: `description JSONB NOT NULL` default `{"purpose":"","usage":"","limitations":""}`; `team_members`, `support`, `servers` `JSONB NOT NULL` default `[]`.
- `servers[].type` accepts `databricks`, `postgres`, `azure` and `local`.
- `classification` is one of `public`, `internal`, `confidential`, `restricted`, or empty.
- New API fields have defaults, so existing API clients keep working.
- Each field Plan 3 adds to `ParsedContract` has a default. `to_odcs` and `from_odcs` are pure functions with no I/O.
- Round trip: `from_odcs(to_odcs(c))` returns the values of `c`, for every combination the model allows. No value is dropped silently.
- No credential enters a contract. Server rows hold coordinates only, and error messages name keys, never values.
- Branch from `develop`. Commit messages and PR text carry no Claude or Claude Code attribution of any kind.
- Backend tests: `.venv\Scripts\python.exe -m pytest tests/ -q`. Lint with `ruff check backend`; passing test paths makes ruff rewrite those files.
- Frontend, from `frontend/`: `npm test`, `npm run lint`, `npm run build`.
- `git commit` needs `.venv\Scripts` prefixed to `PATH`, or pre-commit fails: `PATH="$PWD/.venv/Scripts:$PATH" git commit ...`.
- Layering stays as it is: entities and pure logic hold no I/O, routers orchestrate GitHub calls, and GitHub push failures stay warn-only.
- Do not update `database/schema/*.hcl`. It is out of scope and already out of date.
- Commands in `bash` blocks run in Git Bash from the repository root.

## Spec Gap: Server Keys

The spec lists six server keys and four accepted types. Run against the JSON Schema and `datacontract lint` 1.2.9, those six keys produce a valid document only for `databricks`:

| `type` | ODCS requires | Optional | JSON Schema rejects | Six spec keys alone |
|---|---|---|---|---|
| `databricks` | `catalog`, `schema` | `host` | `port`, `database`, `location`, `format`, `path` | valid |
| `postgres` | `host`, `port`, `database`, `schema` | none | `catalog`, `location`, `format`, `path` | fails: no `port`, `database` |
| `azure` | `location`, `format` | none | `host`, `catalog`, `schema`, `port`, `database`, `path` | fails: no `location`, `format` |
| `local` | `path`, `format` | none | `host`, `catalog`, `schema`, `port`, `database`, `location` | fails: no `path`, `format` |

`server`, `type` and `environment` apply to every type. The schema rejects other keys through `unevaluatedProperties: false`.

The four types and "every contract passes lint" hold together only if the internal row gains `port`, `database`, `location`, `format` and `path`, so this plan adds those five keys, as spec decision 7 settles. None holds a credential. All type-specific behaviour lives in `SERVER_RULES`. Plan 4's execution proof emits a `local` server through these keys.

## Settled Decisions

**`atlas.sum`** (spec decision 9). Docker is running here, so Task 1 regenerates the file through the container. Every Atlas command in these plans, and the CI job, uses the pinned image `arigaio/atlas:1.3.6`. This plan was measured with a cached `latest` (v1.1.7), and Plans 4 and 5 with a `latest` that reported v1.3.7. Docker Hub lists no `1.3.7` tag, and `latest` is rebuilt daily (last on 2026-11-02, after `1.3.6` on 2026-10-27), so v1.3.7 was a pre-release build. `1.3.6` is the newest release tag, checked on 2026-11-02 through `hub.docker.com/v2/repositories/arigaio/atlas/tags`. Run `docker pull arigaio/atlas:1.3.6` once before Task 1. Atlas hashes raw bytes, and two facts shape the command. The working tree is CRLF (`core.autocrlf=true` in `.git/config`) while git blobs are LF. The current `atlas.sum` also mixes both: its first eight entries were hashed from CRLF and the ninth from LF, so `atlas migrate validate` fails today on either line ending. Task 1 fixes this once for every later plan: it adds `database/migrations/*.sql text eol=lf` to `.gitattributes`, rewrites the Windows working copies as LF, hashes LF content (which matches the blobs and every Linux checkout, and rewrites every line of the file once), and adds an `atlas migrate validate` job to CI. Deployment does not read `atlas.sum`: `template_dir` renders the directory in memory, and all nine migrations applied with the stale sum. Until this plan, nothing in CI checked it. Plans 4 and 5 regenerate the file the same way.

**`schema_name`.** Confirmed on Pydantic 2.13.3: a field called `schema` works but warns `Field name "schema" in "S" shadows an attribute in parent "BaseModel"`. The name is `schema_name` in stored JSONB, in API JSON, in Pydantic and in the TypeScript `ContractServer`. The form label reads "Schema". Only `to_odcs` and `from_odcs` translate it to `schema`. No Pydantic alias, because that would give the API two names. `extra="forbid"` turns `schema` in an API body into a 422.

**Partial update.** In `update_data_contract`, `None` keeps the stored value and `[]` clears it. The check is always `is not None`, never truthiness. Sections are replaced whole, like `models` and `servicelevels`, so `{"description": {"purpose": "x"}}` blanks `usage` and `limitations`.

**Sync.** Sync keeps replace semantics: a file without these sections clears them. The file is the source of truth, `models` and `servicelevels` already behave this way, and merging would make it impossible to remove a section by editing the file. The known cost is that metadata saved through the API while a GitHub push failed (warn-only) is lost on the next sync, as `models` already is. Task 4 pins this with a test.

**Strict parsing** (spec decision 5). "No value is dropped silently" means `from_odcs` raises `OdcsParseError` for a key inside these sections that the model cannot hold: `team.members[].dateIn`, `support[].invitationUrl`, `servers[].roles`, `description.customProperties`. It also rejects what ODCS allows but the platform does not model: `type: postgresql`, a string `port`, and a `classification` outside the four values. The allowed keys stay in Plan 1's key-set constants in `odcs.py`: this plan extends `_DOCUMENT_KEYS`, `_TEAM_KEYS` and `_PROPERTY_KEYS` and adds one set per new section (Task 3 Step 4).

## Review Focus

- A contract stored before this plan has no `classification`, `unique` or `physical_type` in `models.fields[]`: `to_odcs`, the form and the detail page treat them as empty (tests in Tasks 3, 5 and 7).
- A credential pasted into a server row (a `password` key, `user:pw@host`, `?sig=` in `location`): the API returns 422, sync reports the file and skips it, and no message repeats the value (tests in Tasks 2, 3 and 4).
- The Approve button sends only `{status}`: every section stays intact, while an explicit `[]` clears one (tests in Task 4).
- Changing a server's type in the form: keys the new type does not take are cleared, or the API rejects the row (test in Task 6).
- A synced file with a `javascript:` value in `support[].url`: the detail page shows it as text, never as a link (test in Task 7).

---

## File Map

| Path | Task | Responsibility |
|---|---|---|
| `.gitattributes`, `database/migrations/20261101000003_data_contract_metadata.sql`, `atlas.sum`, `.github/workflows/ci.yml` | 1 | LF migrations, four columns, regenerated sum, validate job |
| `backend/domain/contract_metadata.py` (new) | 2 | Keys, enums, `server_problems` |
| `backend/interface/schemas/data_contract.py` | 2, 4 | API models |
| `backend/domain/entities/data_contract.py`, `backend/use_cases/data_contract/odcs.py` | 3 | Entity, ODCS mapping both ways, extended key sets |
| `tests/fixtures/odcs/sample_contract.py`, Plan 1's `test_odcs_parse.py` and `test_sync_from_github.py`, `.github/workflows/ci.yml` | 3, 4 | `FULL_CONTRACT` for CI lint, Plan 1 tests that the new keys change |
| Repository interface and implementation, `create.py`, `update.py`, `sync_from_github.py`, `routers/data_contract.py` | 4 | Persistence and pass-through |
| `frontend/src/types/index.ts`, `pages/DataContracts/ContractFields.tsx` | 5 | Field attributes |
| `pages/DataContracts/contractMetadata.ts`, `EditableRows.tsx`, `TeamMembers.tsx`, `SupportChannels.tsx`, `ContractServers.tsx` (new), `DataContractForm.tsx` | 6 | Section editors and form wiring |
| `pages/DataContracts/DataContractDetail.tsx` | 7 | Read-only cards |

---

### Task 1: LF migrations, migration, atlas.sum and the CI check

**Files:**
- Modify: `.gitattributes`
- Create: `database/migrations/20261101000003_data_contract_metadata.sql`
- Modify: `database/migrations/atlas.sum`
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Produces: columns `description`, `team_members`, `support`, `servers` on `catalog.data_contracts`. The file name follows spec decision 8: plans 4 and 5 add `20261101000004_odcs_quality_and_sla.sql` and `20261101000005_contract_versions.sql`.
- Produces: every `database/migrations/*.sql` is LF in Git and on disk, `atlas.sum` is hashed from LF content, and the CI job `migrations` runs `atlas migrate validate`. Plans 4 and 5 regenerate the sum with Step 4's commands.

- [ ] **Step 1: Make migrations LF on every checkout, and renormalize this Windows checkout**

The blobs are already LF, so `git add --renormalize` stages nothing. Only the working copies, which `core.autocrlf=true` wrote as CRLF, need rewriting. Git does not rewrite a file it considers unchanged, so delete the copies and check them out again. Run this before Step 2 creates the new file: the `rm` would delete an untracked migration.

```bash
printf '\n# Atlas hashes raw bytes, so migrations are LF on every checkout\ndatabase/migrations/*.sql text eol=lf\n' >> .gitattributes
rm database/migrations/*.sql
git checkout -- database/migrations
git ls-files --eol database/migrations
git status --short
```

Expected: every `.sql` line reads `i/lf    w/lf    attr/text eol=lf`, `atlas.sum` stays `attr/text=auto`, and `git status --short` shows ` M .gitattributes` and nothing under `database/migrations` (checked on a scratch clone of `develop` at `f02160d`). Any other Windows checkout or worktree needs the same `rm` and `git checkout -- database/migrations` pair once after it pulls this commit; until then its copies stay CRLF.

- [ ] **Step 2: Write the migration exactly as below**

No `GRANT` is needed. `app_user` holds table-level DML on `catalog.data_contracts` (`20260428000001_add_rbac.sql`), which covers new columns, and `readonly_user` has no access to this table.

```sql
-- =============================================================================
-- ODCS contract metadata: description, team members, support channels, servers.
-- Additive: NOT NULL with constant defaults, so existing rows are filled by
-- ADD COLUMN. app_user holds table-level DML on catalog.data_contracts
-- (20260428000001_add_rbac.sql), which covers new columns; no GRANT needed.
-- Atlas manages the transaction; do NOT add explicit BEGIN/COMMIT here.
-- =============================================================================

ALTER TABLE catalog.data_contracts
    ADD COLUMN description  JSONB NOT NULL DEFAULT '{"purpose":"","usage":"","limitations":""}',
    ADD COLUMN team_members JSONB NOT NULL DEFAULT '[]',
    ADD COLUMN support      JSONB NOT NULL DEFAULT '[]',
    ADD COLUMN servers      JSONB NOT NULL DEFAULT '[]';

-- =============================================================================
-- ROLLBACK (run manually if needed):
-- ALTER TABLE catalog.data_contracts
--     DROP COLUMN description,
--     DROP COLUMN team_members,
--     DROP COLUMN support,
--     DROP COLUMN servers;
-- =============================================================================
```

Then run `git add database/migrations/20261101000003_data_contract_metadata.sql` and `git ls-files --eol database/migrations/20261101000003_data_contract_metadata.sql`. If it shows `w/crlf`, your editor saved CRLF: `rm` the file and `git checkout --` it, then check again.
Expected: `i/lf    w/lf    attr/text eol=lf`.

- [ ] **Step 3: Apply it to a throwaway Postgres with an existing row**

```bash
export MSYS_NO_PATHCONV=1
docker network create odcs3net
docker run -d --name odcs3_pg --network odcs3net -e POSTGRES_DB=data_mesh_plt -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=pw postgres:16.1
for i in $(seq 1 40); do docker exec odcs3_pg pg_isready -U postgres -d data_mesh_plt >/dev/null 2>&1 && break; sleep 1; done
atlas_apply() { docker run --rm --network odcs3net -e ADMIN_PASSWORD=adm -e APP_USER_PASSWORD=app -e USER_PASSWORD=ro -v "$(cygpath -w "$PWD/database"):/database:ro" -w /database arigaio/atlas:1.3.6 migrate apply --env azure --url "postgres://postgres:pw@odcs3_pg:5432/data_mesh_plt?sslmode=disable" --revisions-schema public --allow-dirty "$@"; }
atlas_apply 9
docker exec odcs3_pg psql -U postgres -d data_mesh_plt -c "INSERT INTO catalog.domains (id,name) VALUES ('11111111-1111-1111-1111-111111111111','commerce');" -c "INSERT INTO catalog.data_contracts (title,owner,domain_id,tier) VALUES ('Old','o','11111111-1111-1111-1111-111111111111',3);"
atlas_apply
docker exec odcs3_pg psql -U postgres -d data_mesh_plt -c "SELECT title, description, team_members, support, servers FROM catalog.data_contracts;"
docker rm -f odcs3_pg; docker network rm odcs3net
```

Expected: the last apply reports `1 migration`, and the `Old` row shows `{"usage": "", "purpose": "", "limitations": ""}`, `[]`, `[]`, `[]`.

- [ ] **Step 4: Regenerate atlas.sum from an LF copy**

Plans 4 and 5 reuse these commands unchanged. The temporary copy strips CR again, which guards against a file an editor saved as CRLF after Step 1.

```bash
ATLAS_TMP="$(mktemp -d)"
cp database/migrations/*.sql "$ATLAS_TMP"/
sed -i 's/\r$//' "$ATLAS_TMP"/*.sql
MSYS_NO_PATHCONV=1 docker run --rm -v "$(cygpath -w "$ATLAS_TMP"):/migrations" arigaio/atlas:1.3.6 migrate hash --dir file:///migrations
cp "$ATLAS_TMP/atlas.sum" database/migrations/atlas.sum
MSYS_NO_PATHCONV=1 docker run --rm -v "$(cygpath -w "$ATLAS_TMP"):/migrations" arigaio/atlas:1.3.6 migrate validate --dir file:///migrations; echo "validate exit=$?"
MSYS_NO_PATHCONV=1 docker run --rm -v "$(cygpath -w "$PWD/database/migrations"):/migrations" arigaio/atlas:1.3.6 migrate validate --dir file:///migrations; echo "working tree validate exit=$?"
rm -rf "$ATLAS_TMP"
```

Expected: `validate exit=0` and `working tree validate exit=0`; the second passes because Step 1 made the working copies LF. The file has 11 lines. With the SQL above copied verbatim, the first line is `h1:9uuQfwmeG40xTCXK8sSzfkvcgWYc4zYJPeVQuonpUas=` and the last is `20261101000003_data_contract_metadata.sql h1:/j2B6Bu9qLgRVymQapRjZa8KZYAxs50amM0qgVkY4Xc=`. These two values were computed by reproducing Atlas's hash (a running SHA-256 over each file name and its bytes) after the rename; the same computation reproduces the committed `atlas.sum` and the values this step pinned under the old `20261101000001` name. If Atlas disagrees, Atlas wins: check the SQL was copied byte for byte.

- [ ] **Step 5: Validate the sum in CI**

Add this job to `.github/workflows/ci.yml`, after the `lint` job. The runner checks out LF, so it hashes the same bytes as Step 4.

```yaml
  migrations:
    name: Atlas migration checksums
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Validate atlas.sum
        run: docker run --rm -v "$PWD/database/migrations:/migrations" arigaio/atlas:1.3.6 migrate validate --dir file:///migrations
```

Run: `uvx --from actionlint-py actionlint .github/workflows/ci.yml`
Expected: no output, exit 0.

- [ ] **Step 6: Commit**

```bash
git add .gitattributes database/migrations/20261101000003_data_contract_metadata.sql database/migrations/atlas.sum .github/workflows/ci.yml
git commit -m "feat(db): add contract metadata columns" -m "Keep migrations LF through .gitattributes and regenerate atlas.sum from LF content. The previous file mixed CRLF and LF hashes and validated on neither. CI now runs atlas migrate validate."
```

---

### Task 2: Metadata rules and API schemas

**Files:**
- Create: `backend/domain/contract_metadata.py`
- Modify: `backend/interface/schemas/data_contract.py`
- Test: `tests/unit/test_contract_metadata.py` (create), `tests/unit/test_data_contract_schemas.py`

**Interfaces:**
- Produces, from `backend/domain/contract_metadata.py` (pure, no imports from `backend`):
  - `CLASSIFICATIONS = ("public", "internal", "confidential", "restricted")`
  - `SERVER_TYPES = ("databricks", "postgres", "azure", "local")`
  - `DESCRIPTION_KEYS = ("purpose", "usage", "limitations")`, `MEMBER_KEYS = ("username", "name", "role")`, `SUPPORT_KEYS = ("channel", "url", "tool", "scope")`
  - `SERVER_KEYS = ("server", "type", "environment", "host", "catalog", "schema_name", "port", "database", "location", "format", "path")`
  - `SERVER_RULES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]]`, mapping a type to its (required, optional) keys under the internal names, as in the Spec Gap table
  - `empty_description() -> dict[str, str]`; `empty_server() -> dict[str, Any]`, with every `SERVER_KEYS` key `""` except `port`, which is `None`
  - `server_problems(server: Mapping[str, Any]) -> list[str]`: one message per problem, naming keys and never repeating a value
- Produces, from the schemas module: `ContractDescription`, `TeamMember`, `SupportChannel`, `ContractServer`, and `SchemaField` with `classification`, `unique`, `physical_type`.

- [ ] **Step 1: Write the failing rules test in `tests/unit/test_contract_metadata.py`**

```python
import pytest

from backend.domain.contract_metadata import empty_server, server_problems

VALID = {
    "databricks": {"server": "prod", "type": "databricks", "catalog": "dmplt", "schema_name": "sales"},
    "postgres": {"server": "pg", "type": "postgres", "host": "db.example.com", "port": 5432,
                 "database": "sales", "schema_name": "public"},
    "azure": {"server": "lake", "type": "azure", "format": "parquet",
              "location": "abfss://orders@acct.dfs.core.windows.net/orders/*.parquet"},
    "local": {"server": "dev", "type": "local", "path": "./orders.csv", "format": "csv"},
}


def _server(kind: str, **overrides) -> dict:
    return {**empty_server(), **VALID[kind], **overrides}


@pytest.mark.parametrize("server", [*(_server(k) for k in VALID),
                                    _server("databricks", host="adb-1.2.azuredatabricks.net")])
def test_valid_server_has_no_problems(server):
    assert server_problems(server) == []


@pytest.mark.parametrize("kind, key", [
    ("databricks", "catalog"), ("databricks", "schema_name"),
    ("postgres", "host"), ("postgres", "port"), ("postgres", "database"), ("postgres", "schema_name"),
    ("azure", "location"), ("azure", "format"), ("local", "path"), ("local", "format"),
])
def test_missing_required_key_is_named(kind, key):
    assert any(key in p for p in server_problems(_server(kind, **{key: empty_server()[key]})))


@pytest.mark.parametrize("kind, key, value", [
    ("databricks", "port", 443), ("postgres", "catalog", "c"), ("azure", "host", "h.example.com"),
    ("azure", "schema_name", "s"), ("local", "schema_name", "s"), ("local", "location", "az://x/y"),
])
def test_key_the_type_does_not_take_is_named(kind, key, value):
    assert any(key in p for p in server_problems(_server(kind, **{key: value})))


@pytest.mark.parametrize("server", [
    {**empty_server(), "server": "x", "type": "s3"},
    _server("local", server=""),
    *(_server("postgres", host=h) for h in (
        "user:pw@db.example.com", "https://db.example.com", "db.example.com/path", "db.example.com?token=x")),
    *(_server("azure", location=loc) for loc in (
        "https://acct.blob.core.windows.net/c/p?sv=1&sig=abc", "abfss://u:pw@acct.dfs.core.windows.net/p",
        "just a path")),
    *(_server("postgres", port=p) for p in (0, 65536, "5432", "${DB_PORT}")),
])
def test_invalid_server_has_a_problem(server):
    assert server_problems(server)


def test_problem_text_never_contains_the_value():
    problems = server_problems(_server("postgres", host="user:not-a-real-secret@db"))
    assert "not-a-real-secret" not in " ".join(problems)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_contract_metadata.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.domain.contract_metadata'`

- [ ] **Step 3: Implement `backend/domain/contract_metadata.py`**

Rules the tests leave open: an empty value (`""` or `None`) counts as absent, both for "required" and for "does not take". `host` must fully match `[A-Za-z0-9.-]+`. `location` is checked with `urllib.parse.urlsplit`: it needs a scheme, and a password, query or fragment is a problem. An `@` alone is allowed, because `abfss://container@account...` is the normal Azure form. `port` accepts only an `int` from 1 to 65535.

- [ ] **Step 4: Run it to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_contract_metadata.py -q`
Expected: PASS

- [ ] **Step 5: Add the failing schema tests to `tests/unit/test_data_contract_schemas.py`**

```python
from typing import get_args

from backend.domain.contract_metadata import CLASSIFICATIONS, SERVER_TYPES
from backend.interface.schemas.data_contract import (
    ContractServer, DataContractUpdateModel, SchemaField, SupportChannel, TeamMember,
)


def test_create_model_defaults_new_sections():
    m = DataContractCreateModel(title="x", owner="o", domain_id=DOMAIN_ID, tier=3)
    assert m.description.model_dump() == {"purpose": "", "usage": "", "limitations": ""}
    assert m.team_members == [] and m.support == [] and m.servers == []
    u = DataContractUpdateModel()
    assert (u.description, u.team_members, u.support, u.servers) == (None, None, None, None)


def test_schema_field_attributes():
    f = SchemaField(name="a", type="string")
    assert (f.classification, f.unique, f.physical_type) == ("", False, "")
    for value in ("public", "internal", "confidential", "restricted"):
        assert SchemaField(name="a", type="string", classification=value).classification == value
    with pytest.raises(ValidationError):
        SchemaField(name="a", type="string", classification="secret")


def test_literals_match_the_domain_constants():
    assert set(get_args(SchemaField.model_fields["classification"].annotation)) == {"", *CLASSIFICATIONS}
    assert set(get_args(ContractServer.model_fields["type"].annotation)) == set(SERVER_TYPES)


@pytest.mark.parametrize("build", [
    lambda: TeamMember(username="  "),
    lambda: SupportChannel(channel=""),
    lambda: ContractServer(server=" ", type="local", path="./a", format="csv"),
    lambda: ContractServer(server="a", type="local", path="./a", format="csv", password="not-a-real-secret"),
    lambda: ContractServer(server="a", type="databricks", catalog="c", schema="s"),
])
def test_invalid_rows_are_rejected(build):
    with pytest.raises(ValidationError):
        build()


def test_server_applies_the_type_rules():
    with pytest.raises(ValidationError, match="host"):
        ContractServer(server="a", type="azure", location="az://a/b", format="csv", host="h.example.com")
```

- [ ] **Step 6: Run them to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_data_contract_schemas.py -q`
Expected: FAIL with `ImportError` on `ContractServer`

- [ ] **Step 7: Implement the schemas in `backend/interface/schemas/data_contract.py`**

- `NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]` types `TeamMember.username`, `SupportChannel.channel` and `ContractServer.server`. Every other new string field is `str = ""`, and `ContractServer.port` is `int | None = None`.
- `SchemaField` gains `classification: Literal["", "public", "internal", "confidential", "restricted"] = ""`, `unique: bool = False`, `physical_type: str = ""`.
- `ContractServer` has `model_config = ConfigDict(extra="forbid")`, `type: Literal["databricks", "postgres", "azure", "local"]`, and a `@model_validator(mode="after")` that raises `ValueError("; ".join(problems))` when `server_problems(self.model_dump())` is not empty. `support.tool` and `support.scope` stay free strings, because ODCS gives them as examples, not an enum.
- `DataContractCreateModel` gains `description: ContractDescription = Field(default_factory=ContractDescription)` and the three lists with `Field(default_factory=list)`. `DataContractUpdateModel` gains the same four as `| None = None`.

Leave `DataContractResponseModel` alone. Task 4 changes it together with `_to_response`, so router tests stay green in between.

- [ ] **Step 8: Run the tests and ruff**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_contract_metadata.py tests/unit/test_data_contract_schemas.py -q`, then `.venv/Scripts/python.exe -m ruff check backend`
Expected: PASS and `All checks passed!`

- [ ] **Step 9: Commit**

```bash
git add backend/domain/contract_metadata.py backend/interface/schemas/data_contract.py tests/unit/test_contract_metadata.py tests/unit/test_data_contract_schemas.py
git commit -m "feat(data-contract): add metadata rules and API schemas"
```

---

### Task 3: Entity and ODCS mapping

**Files:**
- Modify: `backend/domain/entities/data_contract.py`, `backend/use_cases/data_contract/odcs.py`
- Modify: `tests/fixtures/odcs/sample_contract.py`, `.github/workflows/ci.yml` (Step 7)
- Test: `tests/unit/use_cases/data_contract/test_odcs_metadata.py` (create), `tests/unit/test_data_contract_entity.py`
- Test: Plan 1's `tests/unit/use_cases/data_contract/test_odcs_parse.py` and `test_sync_from_github.py` (Step 4)

**Interfaces:**
- Consumes: `contract_metadata` from Task 2. `to_odcs`, `from_odcs`, `ParsedContract`, `OdcsParseError`, the key-set constants `_DOCUMENT_KEYS`, `_TEAM_KEYS`, `_PROPERTY_KEYS` and the helper `_reject_unknown(mapping, allowed, where)` from Plan 1. `make_contract`, `make_field` and the `__main__` block of `tests/fixtures/odcs/sample_contract.py` from Plan 1.
- Produces:
  - `DataContract(..., domain_id=None, description=None, team_members=None, support=None, servers=None)`. `None` becomes `empty_description()` or a fresh `[]`, so existing constructions keep working.
  - `ParsedContract` gains `description: dict[str, str] = field(default_factory=empty_description)` and `team_members`, `support`, `servers`, each `list[dict[str, Any]] = field(default_factory=list)`. Row dicts always hold every key, so they compare equal to what `model_dump()` stores.
  - New key sets in `odcs.py`: `_DESCRIPTION_KEYS`, `_MEMBER_KEYS`, `_SUPPORT_KEYS`, `_SERVER_KEYS`.
  - `FULL_CONTRACT`, `FIELD`, `DATABRICKS`, `POSTGRES`, `AZURE`, `LOCAL` and `SERVERS` in `tests/fixtures/odcs/sample_contract.py` after Step 7: one contract with every section, linted in CI.

- [ ] **Step 1: Write the failing test `tests/unit/use_cases/data_contract/test_odcs_metadata.py`**

```python
import json
import uuid
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

import jsonschema
import pytest

from backend.domain.contract_metadata import CLASSIFICATIONS, DESCRIPTION_KEYS, empty_server
from backend.domain.entities.data_contract import DataContract
from backend.use_cases.data_contract.odcs import OdcsParseError, from_odcs, to_odcs

NOW = datetime.now(tz=timezone.utc)
SCHEMA = json.loads(Path("tests/fixtures/odcs/odcs-json-schema-v3.2.0.json").read_text(encoding="utf-8"))
VALIDATOR = jsonschema.Draft201909Validator(SCHEMA)
SECRET = "not-a-real-secret"

DATABRICKS = {**empty_server(), "server": "prod", "type": "databricks", "environment": "prod",
              "host": "adb-1.2.azuredatabricks.net", "catalog": "dmplt", "schema_name": "sales"}
POSTGRES = {**empty_server(), "server": "pg", "type": "postgres", "environment": "dev",
            "host": "db.example.com", "port": 5432, "database": "sales", "schema_name": "public"}
AZURE = {**empty_server(), "server": "lake", "type": "azure",
         "location": "abfss://orders@acct.dfs.core.windows.net/orders/*.parquet", "format": "parquet"}
LOCAL = {**empty_server(), "server": "dev", "type": "local", "path": "./orders.csv", "format": "csv"}
SERVERS = [DATABRICKS, POSTGRES, AZURE, LOCAL]
FIELD = {"name": "order_id", "type": "string", "description": "", "nullable": False, "primary_key": True,
         "classification": "internal", "unique": True, "physical_type": "VARCHAR(36)"}


def _contract(**kw) -> DataContract:
    defaults = dict(id=uuid.uuid4(), title="Orders", version="1.0.0", owner="commerce-data",
                    domain="commerce", tier=2, status="active", models={"fields": []},
                    servicelevels={"freshness": "", "availability": "", "retention": "", "latency": ""},
                    created_at=NOW, updated_at=NOW)
    return DataContract(**{**defaults, **kw})


FULL_CONTRACT = _contract(
    models={"fields": [FIELD]},
    description={"purpose": "Orders placed", "usage": "Revenue reporting", "limitations": "Since 2020"},
    team_members=[{"username": "alice@example.com", "name": "Alice", "role": "owner"}],
    support=[{"channel": "#commerce", "url": "https://example.com/c", "tool": "slack", "scope": "interactive"}],
    servers=SERVERS,
)


def _assert_valid(doc: dict) -> None:
    assert [e.message for e in VALIDATOR.iter_errors(doc)] == []


def _prop(doc: dict) -> dict:
    return doc["schema"][0]["properties"][0]


def test_full_contract_is_valid_and_round_trips():
    doc = to_odcs(FULL_CONTRACT)
    _assert_valid(doc)
    parsed = from_odcs(doc)
    for name in ("description", "team_members", "support", "servers"):
        assert getattr(parsed, name) == getattr(FULL_CONTRACT, name)
    assert parsed.models["fields"] == FULL_CONTRACT.models["fields"]


@pytest.mark.parametrize("kw, pick, expected", [
    (dict(description={"purpose": "p", "usage": "", "limitations": ""}), lambda d: d["description"],
     {"purpose": "p"}),
    (dict(team_members=[{"username": "a", "name": "", "role": "owner"}]), lambda d: d["team"],
     {"name": "commerce-data", "members": [{"username": "a", "role": "owner"}]}),
    (dict(support=[{"channel": "c", "url": "", "tool": "email", "scope": ""}]), lambda d: d["support"],
     [{"channel": "c", "tool": "email"}]),
    (dict(servers=[DATABRICKS]), lambda d: sorted(d["servers"][0]),
     ["catalog", "environment", "host", "schema", "server", "type"]),
    (dict(servers=[AZURE]), lambda d: d["servers"],
     [{"server": "lake", "type": "azure", "location": AZURE["location"], "format": "parquet"}]),
    (dict(models={"fields": [FIELD]}), lambda d: {k: _prop(d)[k] for k in ("classification", "unique", "physicalType")},
     {"classification": "internal", "unique": True, "physicalType": "VARCHAR(36)"}),
])
def test_emitted_shape(kw, pick, expected):
    assert pick(to_odcs(_contract(**kw))) == expected


def test_empty_sections_are_omitted_and_parse_to_defaults():
    doc = to_odcs(_contract())
    assert not {"description", "support", "servers"} & doc.keys() and "members" not in doc["team"]
    parsed = from_odcs(doc)
    assert parsed.description == {"purpose": "", "usage": "", "limitations": ""}
    assert (parsed.team_members, parsed.support, parsed.servers) == ([], [], [])


def test_field_stored_before_this_plan_still_emits():
    legacy = {"name": "a", "type": "string", "description": "", "nullable": True, "primary_key": False}
    doc = to_odcs(_contract(models={"fields": [legacy]}))
    _assert_valid(doc)
    assert not {"classification", "unique", "physicalType"} & _prop(doc).keys()
    field = from_odcs(doc).models["fields"][0]
    assert (field["classification"], field["unique"], field["physical_type"]) == ("", False, "")


@pytest.mark.parametrize("server", SERVERS, ids=[s["type"] for s in SERVERS])
def test_every_server_type_validates_and_round_trips(server):
    doc = to_odcs(_contract(servers=[server]))
    _assert_valid(doc)
    assert from_odcs(doc).servers == [server]


@pytest.mark.parametrize("value", [*CLASSIFICATIONS, ""])
@pytest.mark.parametrize("unique", [True, False])
@pytest.mark.parametrize("physical", ["VARCHAR(2)", ""])
def test_field_attributes_validate_and_round_trip(value, unique, physical):
    field = {**FIELD, "classification": value, "unique": unique, "physical_type": physical}
    doc = to_odcs(_contract(models={"fields": [field]}))
    _assert_valid(doc)
    assert from_odcs(doc).models["fields"] == [field]


@pytest.mark.parametrize("keys", [c for n in range(4) for c in combinations(DESCRIPTION_KEYS, n)])
def test_description_round_trips_for_every_subset(keys):
    description = {k: ("text" if k in keys else "") for k in DESCRIPTION_KEYS}
    doc = to_odcs(_contract(description=description))
    _assert_valid(doc)
    assert from_odcs(doc).description == description


@pytest.mark.parametrize("overrides, key", [
    ({"password": SECRET}, "password"),
    ({"host": f"user:{SECRET}@db.example.com"}, "host"),
    ({"type": "s3"}, "type"),
    ({"catalog": ""}, "catalog"),
])
def test_bad_server_raises_naming_the_key_not_the_value(overrides, key):
    doc = to_odcs(_contract(servers=[DATABRICKS]))
    doc["servers"][0].update(overrides)
    with pytest.raises(OdcsParseError, match=key) as exc:
        from_odcs(doc)
    assert SECRET not in str(exc.value)


@pytest.mark.parametrize("mutate, key", [
    (lambda d: _prop(d).update(classification="secret"), "classification"),
    (lambda d: d["description"].update(customProperties=[]), "customProperties"),
    (lambda d: d["team"]["members"][0].update(dateIn="2026-01-01"), "dateIn"),
    (lambda d: d["support"][0].update(invitationUrl="https://example.com"), "invitationUrl"),
    (lambda d: d["team"].update(description="x"), "description"),
])
def test_unmodelled_value_is_not_dropped_silently(mutate, key):
    doc = to_odcs(FULL_CONTRACT)
    mutate(doc)
    with pytest.raises(OdcsParseError, match=key):
        from_odcs(doc)
```

Add to `tests/unit/test_data_contract_entity.py`:

```python
def test_metadata_defaults_are_empty_and_not_shared():
    now = datetime.now(tz=timezone.utc)
    build = lambda: DataContract(
        id=uuid.uuid4(), title="x", version="1.0.0", owner="o", domain="d", tier=4, status="draft",
        models={}, servicelevels={}, created_at=now, updated_at=now,
    )
    first, second = build(), build()
    assert first.description == {"purpose": "", "usage": "", "limitations": ""}
    assert (first.team_members, first.support, first.servers) == ([], [], [])
    first.team_members.append({"username": "a"})
    assert second.team_members == []
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/use_cases/data_contract/test_odcs_metadata.py tests/unit/test_data_contract_entity.py -q`
Expected: FAIL with `TypeError: DataContract.__init__() got an unexpected keyword argument 'description'`

- [ ] **Step 3: Add the four attributes to `DataContract`**

Use the signature in Interfaces and build a fresh value per instance.

- [ ] **Step 4: Extend Plan 1's key-set constants and the Plan 1 tests they change**

Spec decision 5: `from_odcs` stays strict through Plan 1's constants in `odcs.py`, and this plan extends them. Do not remove or bypass a check.

- `_DOCUMENT_KEYS` gains `description`, `support` and `servers`. `_TEAM_KEYS` gains `members`. `_PROPERTY_KEYS` gains `classification`, `unique` and `physicalType`.
- Add, beside them, `_DESCRIPTION_KEYS = frozenset(DESCRIPTION_KEYS)`, `_MEMBER_KEYS = frozenset(MEMBER_KEYS)`, `_SUPPORT_KEYS = frozenset(SUPPORT_KEYS)` and `_SERVER_KEYS`, which is `SERVER_KEYS` with `schema` in place of `schema_name`. Building them from the `contract_metadata` tuples keeps the two lists from drifting.

Plan 1 tests that these keys change, all in this step:

- `test_odcs_parse.py`, `test_parse_errors`: `servers` and `team.members` are now mapped. Replace `({"servers": []}, "unsupported keys: servers")` with `({"tags": []}, "unsupported keys: tags")`, and `({"team": {"name": "a", "members": []}}, "team has unsupported keys: members")` with `({"team": {"name": "a", "tags": []}}, "team has unsupported keys: tags")`.
- `test_sync_from_github.py`, `test_unsupported_odcs_key_is_reported_and_nothing_is_written`: its `servers` row is now read and fails `server_problems` with another message. Pass `tags=["x"]` instead, and assert `"unsupported keys: tags"`.
- `tests/fixtures/odcs/sample_contract.py`, `make_field`: add `classification=""`, `unique=False` and `physical_type=""` parameters and keys. `from_odcs` now always returns the eight field keys, so Plan 1's exact round trips and `test_odcs_file_is_upserted_with_the_contract_values` compare equal only if the stored fields carry them too, as the form saves them after Task 5.

- [ ] **Step 5: Extend `to_odcs` and `from_odcs` until the tests pass**

What the tests leave open:

- Read field attributes with `.get`, so rows stored before this plan work. Emit `classification`, `unique` and `physicalType` only when non-empty or true, so Plan 1's `EXPECTED_YAML` and `test_field_mapping` stay as they are.
- `members` joins the `team` object Plan 1 builds.
- Reuse Plan 1's `_reject_unknown(mapping, allowed, where)` with the Step 4 sets for `description`, `team`, members, support rows and server rows. Extend it so a value that is not a mapping raises `OdcsParseError(f"{where} must be an object")` instead of falling through to Plan 1's `malformed` wrapper. Plan 1's own `team` check runs first, so a list `team` keeps its `deprecated array` message. Do not add a second helper.
- Server rows start from `empty_server()`. Report the first entry of `server_problems` as `OdcsParseError(f"servers[{i}]: {problem}")`.
- A section that is absent or `null` gives its default.

Put each section in its own helper. Ruff enforces `max-complexity = 15`, and `to_odcs` already carries Plan 1's mapping.

- [ ] **Step 6: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/use_cases/data_contract/test_odcs_metadata.py tests/unit/test_data_contract_entity.py -q`, then `.venv/Scripts/python.exe -m pytest tests/ -q`
Expected: PASS, then the full suite passes, Plan 1's tests included.

- [ ] **Step 7: Make CI lint the new sections**

Plan 1's `odcs-lint` job in `.github/workflows/ci.yml` installs runtime dependencies only, so it cannot import this test module, which imports `jsonschema` and `pytest`.

- Move `FIELD`, `DATABRICKS`, `POSTGRES`, `AZURE`, `LOCAL`, `SERVERS` and `FULL_CONTRACT` into `tests/fixtures/odcs/sample_contract.py`, and import them in `test_odcs_metadata.py`. Build `FULL_CONTRACT` there with `make_contract(status="active", owner="commerce-data", models={"fields": [FIELD]}, description=..., team_members=..., support=..., servers=SERVERS)`, keeping the section values from Step 1.
- The module's `__main__` block takes an optional second argument: `full` writes `assemble_yaml(FULL_CONTRACT)` instead of `assemble_yaml(sample_contract())`.
- In the `odcs-lint` job's generate step, add `uv run python -m tests.fixtures.odcs.sample_contract odcs-lint/full.yaml full`. Plan 1's lint step already judges every `odcs-lint/*.yaml` by its JSON `result`.

Rerun Step 6's commands. Expected: the same result.

- [ ] **Step 8: Lint a contract generated by the real code**

```bash
OUT="$(mktemp -d)"
.venv/Scripts/python.exe -m tests.fixtures.odcs.sample_contract "$OUT/full.yaml" full
PYTHONUTF8=1 uvx --from datacontract-cli==1.2.9 datacontract lint "$OUT/full.yaml" --output "$OUT/full-lint.json" --output-format json
.venv/Scripts/python.exe -c "import json, sys; print(json.load(open(sys.argv[1]))['result'])" "$OUT/full-lint.json"
```

Expected: the last command prints `passed` (spec decision 2: the exit code is not the verdict). `PYTHONUTF8=1` is required on this machine: without it the CLI crashes with `UnicodeEncodeError` printing its result emoji to the cp1252 console, whatever the contract's validity. Lint is also weaker than the JSON Schema (it accepts `host` on an `azure` server), so the schema tests in Step 1 must stay.

- [ ] **Step 9: Run ruff, then commit**

Run: `.venv/Scripts/python.exe -m ruff check backend`
Expected: `All checks passed!`

```bash
git add backend/domain/entities/data_contract.py backend/use_cases/data_contract/odcs.py tests/fixtures/odcs/sample_contract.py tests/unit/use_cases/data_contract/test_odcs_metadata.py tests/unit/use_cases/data_contract/test_odcs_parse.py tests/unit/use_cases/data_contract/test_sync_from_github.py tests/unit/test_data_contract_entity.py .github/workflows/ci.yml
git commit -m "feat(data-contract): map contract metadata to and from ODCS"
```

---

### Task 4: Persistence, use cases, router and sync

All signature changes land in one commit, because the new parameters are required and every caller must change with them.

**Files:**
- Modify: `backend/domain/interfaces/data_contract_repository.py`, `backend/infra/repositories/data_contract_repository.py`, `backend/use_cases/data_contract/create.py`, `backend/use_cases/data_contract/update.py`, `backend/use_cases/data_contract/sync_from_github.py`, `backend/interface/routers/data_contract.py`, `backend/interface/schemas/data_contract.py`
- Test: `tests/unit/infra/test_data_contract_repository_metadata.py` (create), `tests/unit/test_data_contract_use_cases.py`, `tests/unit/interface/test_routers.py`, `tests/unit/use_cases/data_contract/test_sync_from_github.py`

The repository test file avoids the name `test_data_contract_repository.py`, which the unmerged `worktree-feat+data-contract-picker` branch adds.

**Interfaces:**
- Consumes: `DataContract` and `ParsedContract` from Task 3. API models from Task 2.
- Produces: `create`, `update` and `upsert` on `IDataContractRepository` and `PostgresDataContractRepository`, plus `execute` on the create and update use cases, each gain these required parameters after `servicelevels`:

```python
description: dict[str, Any],
team_members: list[dict[str, Any]],
support: list[dict[str, Any]],
servers: list[dict[str, Any]],
```

Every call site, checked by grep across `backend`, `scripts` and `tests`:

| Call site | Change |
|---|---|
| `create.py` `repository.create`, `update.py` `repository.update` | Pass the four |
| `sync_from_github.py` `repository.upsert` | Pass `parsed.description`, `parsed.team_members`, `parsed.support`, `parsed.servers` |
| `data_contract_repository.py` `upsert` calling `self.update` | Forward the four. Easy to miss, and it is the path sync takes for existing contracts |
| `routers/data_contract.py` `create_data_contract`, `update_data_contract` | Pass the four, the update with `None` handling |
| `tests/unit/test_data_contract_use_cases.py`, six `execute` calls | Add `**METADATA` |

`backend/interface/routers/domains.py` only reads contracts and calls `assemble_yaml`, so it needs no change. `scripts/` writes no contracts through these methods. Tests that build `DataContract` directly rely on the entity defaults from Task 3.

- [ ] **Step 1: Write the failing repository test `tests/unit/infra/test_data_contract_repository_metadata.py`**

```python
import contextlib
import json
import uuid
from datetime import datetime, timezone

from backend.infra.repositories.data_contract_repository import PostgresDataContractRepository

NOW = datetime.now(tz=timezone.utc)
DOMAIN_ID = uuid.uuid4()
NEW = dict(description={"purpose": "p", "usage": "", "limitations": ""},
           team_members=[{"username": "a", "name": "", "role": ""}],
           support=[{"channel": "c", "url": "", "tool": "", "scope": ""}],
           servers=[{"server": "s", "type": "local", "path": "./a", "format": "csv"}])
ENCODED = tuple(json.dumps(v) for v in NEW.values())
BASE = dict(title="T", version="1.0.0", owner="o", domain_id=DOMAIN_ID, tier=3, status="draft",
            models={"fields": []}, servicelevels={})


class FakeConnection:
    """Records every statement and replays one canned row."""

    def __init__(self, row=None):
        self.row = row
        self.calls = []

    def transaction(self):
        return contextlib.nullcontext()

    async def fetchrow(self, query, *args):
        self.calls.append((query, args))
        return self.row

    async def execute(self, query, *args):
        self.calls.append((query, args))
        return "INSERT 0 1"


def _row() -> dict:
    return {"id": uuid.uuid4(), "title": "T", "version": "1.0.0", "owner": "o", "domain": "d", "tier": 3,
            "status": "draft", "models": "{}", "servicelevels": "{}", "domain_id": DOMAIN_ID,
            "created_at": NOW, "updated_at": NOW, **dict(zip(NEW, ENCODED))}


async def test_get_selects_and_decodes_the_new_columns():
    db = FakeConnection(_row())
    contract = await PostgresDataContractRepository(db).get_by_id(uuid.uuid4())
    assert all(f"dc.{c}" in db.calls[0][0] for c in NEW)
    assert {k: getattr(contract, k) for k in NEW} == NEW


async def test_create_binds_the_new_sections():
    db = FakeConnection(_row())
    await PostgresDataContractRepository(db).create(**BASE, **NEW)
    query, args = db.calls[0]
    assert "$12::jsonb" in query and args[8:12] == ENCODED


async def test_update_binds_contract_id_last():
    db = FakeConnection(_row())
    cid = uuid.uuid4()
    await PostgresDataContractRepository(db).update(cid, **BASE, **NEW)
    query, args = db.calls[0]
    assert "WHERE id = $13" in query and args[8:12] == ENCODED and args[12] == cid


async def test_upsert_insert_binds_the_new_sections():
    db = FakeConnection(None)
    assert await PostgresDataContractRepository(db).upsert(uuid.uuid4(), **BASE, **NEW) is True
    query, args = db.calls[-1]
    assert "$13::jsonb" in query and args[9:13] == ENCODED


async def test_upsert_update_path_forwards_the_new_sections():
    db = FakeConnection(_row())
    assert await PostgresDataContractRepository(db).upsert(uuid.uuid4(), **BASE, **NEW) is False
    _, update_args = next(c for c in db.calls if "UPDATE" in c[0])
    assert update_args[8:12] == ENCODED
```

- [ ] **Step 2: Update and extend `tests/unit/test_data_contract_use_cases.py`**

Add `**METADATA` to the six existing `execute` calls, and add:

```python
METADATA = dict(
    description={"purpose": "p", "usage": "", "limitations": ""},
    team_members=[{"username": "a", "name": "", "role": ""}],
    support=[{"channel": "c", "url": "", "tool": "", "scope": ""}],
    servers=[{"server": "s", "type": "local", "path": "./a", "format": "csv"}],
)

@pytest.mark.asyncio
@pytest.mark.parametrize("use_case_cls, method, extra", [
    (CreateDataContractUseCase, "create", {}),
    (UpdateDataContractUseCase, "update", {"contract_id": uuid.uuid4()}),
])
async def test_use_case_passes_metadata_to_repo(use_case_cls, method, extra):
    repo = AsyncMock()
    getattr(repo, method).return_value = make_contract()
    await use_case_cls(repo).execute(**extra, title="T", version="1.0.0", owner="o", domain_id=DOMAIN_ID,
                                     tier=3, status="draft", models={"fields": []}, servicelevels={}, **METADATA)
    assert {k: getattr(repo, method).call_args.kwargs[k] for k in METADATA} == METADATA
```

- [ ] **Step 3: Extend `tests/unit/interface/test_routers.py`**

Make `_contract(**kw)` forward `description`, `team_members`, `support` and `servers` with `kw.get(...)`. Then add:

```python
STORED = dict(
    description={"purpose": "p", "usage": "u", "limitations": ""},
    team_members=[{"username": "alice", "name": "", "role": "owner"}],
    support=[{"channel": "#c", "url": "", "tool": "slack", "scope": ""}],
    servers=[{"server": "dev", "type": "local", "environment": "", "host": "", "catalog": "",
              "schema_name": "", "port": None, "database": "", "location": "", "format": "csv",
              "path": "./a.csv"}],
)


def _put(admin_client, body):
    mock_get, mock_update = AsyncMock(), AsyncMock()
    mock_get.execute.return_value = _contract(**STORED)
    mock_update.execute.return_value = _contract(**STORED)
    app.dependency_overrides[get_get_data_contract_use_case] = lambda: mock_get
    app.dependency_overrides[get_update_data_contract_use_case] = lambda: mock_update
    resp = admin_client.put(f"/api/v1/data-contracts/{CONTRACT_ID}", json=body)
    return resp, mock_update.execute.call_args


def test_update_keeps_metadata_when_body_omits_it(admin_client):
    resp, call = _put(admin_client, {"status": "active"})
    assert resp.status_code == 200
    assert {k: call.kwargs[k] for k in STORED} == STORED
    assert {k: resp.json()[k] for k in STORED} == STORED


def test_update_empty_list_clears_only_that_section(admin_client):
    _, call = _put(admin_client, {"servers": []})
    assert call.kwargs["servers"] == [] and call.kwargs["team_members"] == STORED["team_members"]


def test_update_replaces_description_whole(admin_client):
    _, call = _put(admin_client, {"description": {"purpose": "new"}})
    assert call.kwargs["description"] == {"purpose": "new", "usage": "", "limitations": ""}


def _post(admin_client, extra):
    mock_uc = AsyncMock()
    mock_uc.execute.return_value = _contract()
    app.dependency_overrides[get_create_data_contract_use_case] = lambda: mock_uc
    body = {"title": "S", "owner": "o", "domain_id": str(DOMAIN_ID), "tier": 3, **extra}
    return admin_client.post("/api/v1/data-contracts", json=body), mock_uc


def test_create_passes_metadata_and_dumps_rows(admin_client):
    resp, mock_uc = _post(admin_client, {"team_members": [{"username": "alice"}]})
    assert resp.status_code == 201
    kwargs = mock_uc.execute.call_args.kwargs
    assert kwargs["team_members"] == [{"username": "alice", "name": "", "role": ""}]
    assert kwargs["description"] == {"purpose": "", "usage": "", "limitations": ""}
    assert kwargs["servers"] == []


def test_create_rejects_a_password_on_a_server(admin_client):
    resp, mock_uc = _post(admin_client, {"servers": [{"server": "a", "type": "local", "path": "./a",
                                                      "format": "csv", "password": "not-a-real-secret"}]})
    assert resp.status_code == 422
    mock_uc.execute.assert_not_called()
```

- [ ] **Step 4: Extend `tests/unit/use_cases/data_contract/test_sync_from_github.py`**

Plan 1 Task 4 already defines `_odcs_yaml(**overrides)` in this file: it dumps `to_odcs(sample_contract())` with top-level keys replaced. The tests below use it as it is. Do not define a second helper with that name.

Plan 1's `test_odcs_file_is_upserted_with_the_contract_values` compares the whole `upsert` keyword dict, so add the four new keys to its expected dict: `"description": contract.description`, `"team_members": contract.team_members`, `"support": contract.support`, `"servers": contract.servers`.

```python
async def test_sync_passes_metadata_to_upsert(use_case, github, repo):
    github.list_all_yaml_contents.return_value = [("c/o.yaml", _odcs_yaml(
        description={"purpose": "p"},
        team={"name": "alice", "members": [{"username": "a"}]},
        support=[{"channel": "c"}],
        servers=[{"server": "dev", "type": "local", "path": "./a", "format": "csv"}],
    ))]
    result = await use_case.execute()
    assert result["errors"] == []
    kwargs = repo.upsert.call_args.kwargs
    assert kwargs["description"] == {"purpose": "p", "usage": "", "limitations": ""}
    assert kwargs["team_members"] == [{"username": "a", "name": "", "role": ""}]
    assert kwargs["support"] == [{"channel": "c", "url": "", "tool": "", "scope": ""}]
    assert kwargs["servers"][0]["path"] == "./a"


async def test_sync_file_without_sections_clears_them(use_case, github, repo):
    existing = _contract()
    existing.team_members = [{"username": "a", "name": "", "role": ""}]
    existing.servers = [{"server": "dev", "type": "local", "path": "./a", "format": "csv"}]
    repo.get_by_id.return_value = existing
    github.list_all_yaml_contents.return_value = [("c/o.yaml", _odcs_yaml())]
    result = await use_case.execute()
    assert result["errors"] == []
    kwargs = repo.upsert.call_args.kwargs
    assert kwargs["description"] == {"purpose": "", "usage": "", "limitations": ""}
    assert (kwargs["team_members"], kwargs["support"], kwargs["servers"]) == ([], [], [])


async def test_sync_reports_a_server_with_a_secret_and_skips_the_file(use_case, github, repo):
    github.list_all_yaml_contents.return_value = [("c/o.yaml", _odcs_yaml(
        servers=[{"server": "dev", "type": "local", "path": "./a", "format": "csv",
                  "password": "not-a-real-secret"}],
    ))]
    result = await use_case.execute()
    assert result["errors"][0]["path"] == "c/o.yaml" and "password" in result["errors"][0]["error"]
    assert "not-a-real-secret" not in str(result)
    repo.upsert.assert_not_called()
```

- [ ] **Step 5: Run the four test files to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/infra/test_data_contract_repository_metadata.py tests/unit/test_data_contract_use_cases.py tests/unit/interface/test_routers.py tests/unit/use_cases/data_contract/test_sync_from_github.py -q`
Expected: FAIL with `TypeError` on the new keyword arguments, and `KeyError` on `description` in the router tests.

- [ ] **Step 6: Implement the change through every layer**

- Repository, abstract and concrete: apply the signature. `_SELECT` and `_row_to_entity` gain the four columns, each decoded with `json.loads`. In `create`, `update` and the `upsert` insert, the four follow `servicelevels` as `::jsonb` placeholders bound with `json.dumps`. The placeholder numbers are the ones the tests assert, and `upsert` forwards the four to `self.update`.
- Use cases: add the four to `execute` and pass them on. Sync passes the four from `parsed`.
- `DataContractResponseModel` gains `description: dict[str, Any]` and `team_members`, `support`, `servers` as `list[dict[str, Any]]`, with no default. This is the same loose shape as `models`, so an old stored row cannot turn a read into a 500.
- Router: `_to_response` adds the four. Add `_rows(rows: Sequence[BaseModel]) -> list[dict[str, Any]]`. `create_data_contract` passes `body.description.model_dump()` and `_rows(...)`. `update_data_contract` follows the existing pattern, for example `team_members=_rows(body.team_members) if body.team_members is not None else existing.team_members`.

- [ ] **Step 7: Run the full backend suite and ruff**

Run: `.venv/Scripts/python.exe -m pytest tests/ -q`, then `.venv/Scripts/python.exe -m ruff check backend`
Expected: all tests pass and `All checks passed!`

- [ ] **Step 8: Check the SQL against real Postgres**

The repository tests use a fake connection, which cannot catch a bind count or `jsonb` cast error. Run `SMOKE="$(mktemp -d)"`, then write this to `$SMOKE/smoke.py`, outside the repository:

```python
import asyncio
import sys
import uuid

import asyncpg

from backend.infra.repositories.data_contract_repository import PostgresDataContractRepository

DESCRIPTION = {"purpose": "p", "usage": "", "limitations": ""}
TEAM = [{"username": "alice", "name": "", "role": "owner"}]
SUPPORT = [{"channel": "#c", "url": "", "tool": "slack", "scope": ""}]
SERVERS = [{"server": "prod", "type": "databricks", "catalog": "c", "schema_name": "s"}]


async def main() -> None:
    db = await asyncpg.connect(sys.argv[1])
    domain = await db.fetchval("INSERT INTO catalog.domains (name) VALUES ('smoke') RETURNING id")
    repo = PostgresDataContractRepository(db)
    base = dict(version="1.0.0", owner="o", domain_id=domain, tier=3, status="draft",
                models={"fields": []}, servicelevels={})
    full = dict(description=DESCRIPTION, team_members=TEAM, support=SUPPORT, servers=SERVERS)
    created = await repo.create(title="A", **base, **full)
    assert (created.description, created.team_members, created.support, created.servers) == (
        DESCRIPTION, TEAM, SUPPORT, SERVERS)
    updated = await repo.update(created.id, title="B", **base, **{**full, "team_members": [], "servers": []})
    assert updated.team_members == [] and updated.servers == [] and updated.support == SUPPORT
    new_id = uuid.uuid4()
    assert await repo.upsert(new_id, title="C", **base, **full) is True
    assert await repo.upsert(new_id, title="D", **base, **{**full, "support": []}) is False
    assert (await repo.get_by_id(new_id)).support == []
    assert len(await repo.list()) == 2 and len(await repo.list_by_domain_id(domain)) == 2
    await db.close()
    print("repository smoke OK")


asyncio.run(main())
```

Then run it. Docker assigns the host port, because a fixed one may be taken on this machine:

```bash
export MSYS_NO_PATHCONV=1
docker network create odcs3net
docker run -d --name odcs3_pg --network odcs3net -p 127.0.0.1:0:5432 -e POSTGRES_DB=data_mesh_plt -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=pw postgres:16.1
for i in $(seq 1 40); do docker exec odcs3_pg pg_isready -U postgres -d data_mesh_plt >/dev/null 2>&1 && break; sleep 1; done
PORT=$(docker port odcs3_pg 5432/tcp | head -1 | sed 's/.*://')
docker run --rm --network odcs3net -e ADMIN_PASSWORD=adm -e APP_USER_PASSWORD=app -e USER_PASSWORD=ro -v "$(cygpath -w "$PWD/database"):/database:ro" -w /database arigaio/atlas:1.3.6 migrate apply --env azure --url "postgres://postgres:pw@odcs3_pg:5432/data_mesh_plt?sslmode=disable" --revisions-schema public --allow-dirty
PYTHONPATH="$(cygpath -w "$PWD")" .venv/Scripts/python.exe "$(cygpath -w "$SMOKE/smoke.py")" "postgres://postgres:pw@127.0.0.1:$PORT/data_mesh_plt"
docker rm -f odcs3_pg; docker network rm odcs3net
```

Expected: `repository smoke OK`

- [ ] **Step 9: Commit**

```bash
git add backend/domain/interfaces/data_contract_repository.py backend/infra/repositories/data_contract_repository.py backend/use_cases/data_contract/create.py backend/use_cases/data_contract/update.py backend/use_cases/data_contract/sync_from_github.py backend/interface/routers/data_contract.py backend/interface/schemas/data_contract.py tests/unit/infra/test_data_contract_repository_metadata.py tests/unit/test_data_contract_use_cases.py tests/unit/interface/test_routers.py tests/unit/use_cases/data_contract/test_sync_from_github.py
git commit -m "feat(data-contract): persist and expose contract metadata"
```

---

### Task 5: Field attributes in the form

**Files:**
- Modify: `frontend/src/types/index.ts`, `frontend/src/pages/DataContracts/ContractFields.tsx`, `frontend/src/pages/DataContracts/DataContractForm.tsx`
- Test: `frontend/src/pages/DataContracts/ContractFields.test.tsx` (create; no test files exist in this folder yet)

**Interfaces:**
- Produces:
  - `export type FieldClassification = '' | 'public' | 'internal' | 'confidential' | 'restricted'`
  - `SchemaField` gains `classification: FieldClassification`, `unique: boolean`, `physical_type: string`
  - `export function withFieldDefaults(field: SchemaField): SchemaField` in `ContractFields.tsx`, returning `{ ...emptyField(), ...field }`

- [ ] **Step 1: Write the failing test `ContractFields.test.tsx`**

```tsx
import { render, screen, fireEvent, within } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import ContractFields, { withFieldDefaults } from './ContractFields'
import type { SchemaField } from '../../types'

const field: SchemaField = {
  name: 'order_id', type: 'string', description: '', nullable: false, primary_key: true,
  classification: '', unique: false, physical_type: '',
}

describe('ContractFields', () => {
  it('reports physical type, classification and unique changes', () => {
    const onChange = vi.fn()
    render(<ContractFields fields={[field]} onChange={onChange} />)
    fireEvent.change(screen.getByPlaceholderText('Physical type'), { target: { value: 'VARCHAR(36)' } })
    expect(onChange.mock.lastCall![0][0].physical_type).toBe('VARCHAR(36)')
    fireEvent.change(screen.getByLabelText('Classification'), { target: { value: 'restricted' } })
    expect(onChange.mock.lastCall![0][0].classification).toBe('restricted')
    fireEvent.click(screen.getByLabelText('Unique'))
    expect(onChange.mock.lastCall![0][0].unique).toBe(true)
  })

  it('offers the four classifications plus empty', () => {
    render(<ContractFields fields={[field]} onChange={vi.fn()} />)
    const options = within(screen.getByLabelText('Classification')).getAllByRole('option')
    expect(options.map((o) => (o as HTMLOptionElement).value)).toEqual(
      ['', 'public', 'internal', 'confidential', 'restricted'],
    )
  })

  it('gives added and stored fields empty attributes', () => {
    const onChange = vi.fn()
    render(<ContractFields fields={[]} onChange={onChange} />)
    fireEvent.click(screen.getByRole('button', { name: /add field/i }))
    expect(onChange.mock.lastCall![0][0]).toMatchObject({ classification: '', unique: false, physical_type: '' })
    const stored = { name: 'a', type: 'string', description: '', nullable: true, primary_key: false } as SchemaField
    expect(withFieldDefaults(stored)).toMatchObject({ name: 'a', classification: '', unique: false, physical_type: '' })
  })
})
```

- [ ] **Step 2: Run it to verify it fails**

Run, from `frontend/`: `npx vitest run src/pages/DataContracts/ContractFields.test.tsx`
Expected: FAIL, `withFieldDefaults` is not a function.

- [ ] **Step 3: Implement the types, `ContractFields.tsx` and the form normalization**

Add three cells to the same 12-column grid so they wrap onto a second line: an input with placeholder `Physical type` (`col-span-5`), a `select` with `aria-label="Classification"` whose empty option reads `unclassified` (`col-span-4`), and a checkbox labelled `Unique` (`col-span-3`). In `DataContractForm.tsx`, `getInitialFields` returns `v.models.fields.map(withFieldDefaults)`, so a stored field keeps controlled inputs and is saved with all eight keys.

- [ ] **Step 4: Verify**

Run, from `frontend/`: `npx vitest run src/pages/DataContracts/ContractFields.test.tsx`, then `npm run lint`, then `npm run build`
Expected: PASS, no lint warnings, and the build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/pages/DataContracts/ContractFields.tsx frontend/src/pages/DataContracts/ContractFields.test.tsx frontend/src/pages/DataContracts/DataContractForm.tsx
git commit -m "feat(frontend): edit field classification, uniqueness and physical type"
```

---

### Task 6: Metadata sections in the form

**Files:**
- Create: `frontend/src/pages/DataContracts/contractMetadata.ts`, `EditableRows.tsx`, `TeamMembers.tsx`, `SupportChannels.tsx`, `ContractServers.tsx`
- Modify: `frontend/src/types/index.ts`, `frontend/src/pages/DataContracts/DataContractForm.tsx`
- Test: `frontend/src/pages/DataContracts/contractMetadata.test.ts`, `ContractServers.test.tsx`, `DataContractForm.test.tsx` (all new)

**Interfaces:**
- Produces, in `types/index.ts`:

```ts
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
```

  `DataContract` and `DataContractInput` gain `description: ContractDescription`, `team_members: TeamMember[]`, `support: SupportChannel[]`, `servers: ContractServer[]`.
- Produces, in `contractMetadata.ts`:
  - `export type ServerKey = 'host' | 'catalog' | 'schema_name' | 'port' | 'database' | 'location' | 'format' | 'path'`
  - `SERVER_TYPE_KEYS: Record<ServerType, { required: ServerKey[]; optional: ServerKey[] }>`, mirroring `SERVER_RULES` in the backend, which stays authoritative
  - `SERVER_KEY_LABELS: Record<ServerKey, string>`: `Host`, `Catalog`, `Schema`, `Port`, `Database`, `Location`, `Format`, `Path`
  - `emptyServer(): ContractServer`, with type `databricks`
  - `withServerType(server: ContractServer, type: ServerType): ContractServer`
  - `metadataError(members: TeamMember[], support: SupportChannel[], servers: ContractServer[]): string | null`
- Produces, in `EditableRows.tsx`, a generic default export with props `rows: T[]`, `onChange: (rows: T[]) => void`, `emptyRow: () => T`, `addLabel: string`, `emptyText: string`, `renderRow: (row: T, index: number, patch: (p: Partial<T>) => void) => ReactNode`. `TeamMembers`, `SupportChannels` and `ContractServers` each take `rows` and `onChange`. Leave `ContractFields` and `QualityRules` as they are.

- [ ] **Step 1: Write the failing helper test `contractMetadata.test.ts`**

```ts
import { describe, it, expect } from 'vitest'
import { emptyServer, metadataError, withServerType } from './contractMetadata'

describe('withServerType', () => {
  it('clears keys the new type does not take and keeps shared ones', () => {
    const server = { ...emptyServer(), server: 'prod', host: 'h', catalog: 'c', schema_name: 's' }
    expect(withServerType(server, 'azure')).toMatchObject({ type: 'azure', server: 'prod', host: '', catalog: '', schema_name: '' })
    expect(withServerType(server, 'postgres')).toMatchObject({ host: 'h', schema_name: 's', catalog: '' })
    expect(withServerType({ ...server, type: 'postgres', port: 5432 }, 'local').port).toBeNull()
  })
})

describe('metadataError', () => {
  it('is null when every row is complete or absent, and names the first incomplete row', () => {
    expect(metadataError([], [], [])).toBeNull()
    expect(metadataError([{ username: '', name: 'x', role: '' }], [], [])).toBe('Team member 1 needs a username')
    expect(metadataError([], [{ channel: ' ', url: '', tool: '', scope: '' }], [])).toBe('Support channel 1 needs a channel')
    expect(metadataError([], [], [emptyServer()])).toBe('Server 1 needs a name')
    expect(metadataError([], [], [{ ...emptyServer(), server: 'a', type: 'postgres', host: 'h' }]))
      .toBe('Server 1 (postgres) needs Port, Database, Schema')
  })
})
```

- [ ] **Step 2: Run it to verify it fails**

Run, from `frontend/`: `npx vitest run src/pages/DataContracts/contractMetadata.test.ts`
Expected: FAIL, cannot resolve `./contractMetadata`.

- [ ] **Step 3: Implement the types and `contractMetadata.ts`, then rerun**

`withServerType` resets every `ServerKey` absent from the new type's `required` and `optional` lists, to `''` and `port` to `null`.
Expected after the rerun: PASS

- [ ] **Step 4: Write the failing component test `ContractServers.test.tsx`**

```tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import ContractServers from './ContractServers'
import { emptyServer } from './contractMetadata'

const row = (over = {}) => ({ ...emptyServer(), server: 'prod', ...over })

describe('ContractServers', () => {
  it('shows only the keys of the selected type', () => {
    render(<ContractServers rows={[row({ type: 'azure' })]} onChange={vi.fn()} />)
    expect(screen.getByPlaceholderText('Location')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Format')).toBeInTheDocument()
    expect(screen.queryByPlaceholderText('Host')).toBeNull()
    expect(screen.queryByPlaceholderText('Schema')).toBeNull()
  })

  it('clears keys the new type does not take', () => {
    const onChange = vi.fn()
    render(<ContractServers rows={[row({ host: 'h', catalog: 'c', schema_name: 's' })]} onChange={onChange} />)
    fireEvent.change(screen.getByLabelText('Server type'), { target: { value: 'azure' } })
    expect(onChange.mock.lastCall![0][0]).toMatchObject({ type: 'azure', host: '', catalog: '', schema_name: '' })
  })

  it('stores port as a number and blank as null', () => {
    const onChange = vi.fn()
    render(<ContractServers rows={[row({ type: 'postgres', port: 5432 })]} onChange={onChange} />)
    fireEvent.change(screen.getByPlaceholderText('Port'), { target: { value: '6543' } })
    expect(onChange.mock.lastCall![0][0].port).toBe(6543)
    fireEvent.change(screen.getByPlaceholderText('Port'), { target: { value: '' } })
    expect(onChange.mock.lastCall![0][0].port).toBeNull()
  })
})
```

- [ ] **Step 5: Write the failing form test `DataContractForm.test.tsx`**

```tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import DataContractForm from './DataContractForm'
import { emptyServer } from './contractMetadata'
import type { DataContract } from '../../types'

vi.mock('../../hooks/useDomains', () => ({
  useAllDomains: () => ({ data: [{ id: 'd1', name: 'commerce', owner_id: 'u1', members: [] }], isLoading: false }),
}))
vi.mock('../../contexts/AuthContext', () => ({ useAuth: () => ({ user: { id: 'u1', role: 'PLATFORM_ADMIN' } }) }))

const contract: DataContract = {
  id: 'c1', title: 'Orders', version: '1.0.0', owner: 'alice', domain: 'commerce', domain_id: 'd1',
  tier: 4, status: 'draft', models: { fields: [], quality: [] },
  servicelevels: { freshness: '', availability: '', retention: '', latency: '' },
  description: { purpose: 'p', usage: '', limitations: '' },
  team_members: [{ username: 'alice', name: '', role: 'owner' }],
  support: [{ channel: '#c', url: '', tool: 'slack', scope: '' }],
  servers: [{ ...emptyServer(), server: 'prod', catalog: 'c', schema_name: 's' }],
  created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
}

const renderForm = (value = contract) => {
  const onSubmit = vi.fn()
  render(<DataContractForm defaultValues={value} onSubmit={onSubmit} onCancel={vi.fn()} isSubmitting={false} />)
  return onSubmit
}

describe('DataContractForm metadata', () => {
  it('shows every section at tier 4 and keeps stored metadata on an untouched save', async () => {
    const onSubmit = renderForm()
    for (const label of ['Description', 'Team Members', 'Support', 'Servers']) {
      expect(screen.getByRole('heading', { name: label })).toBeInTheDocument()
    }
    fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }))
    await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce())
    expect(onSubmit.mock.calls[0][0]).toMatchObject({
      description: contract.description, team_members: contract.team_members,
      support: contract.support, servers: contract.servers,
    })
  })

  it('submits an edited description', async () => {
    const onSubmit = renderForm()
    fireEvent.change(screen.getByLabelText('Usage'), { target: { value: 'reporting' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }))
    await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce())
    expect(onSubmit.mock.calls[0][0].description).toEqual({ purpose: 'p', usage: 'reporting', limitations: '' })
  })

  it('blocks submit and names the row when a server is incomplete', async () => {
    const onSubmit = renderForm({ ...contract, servers: [{ ...emptyServer(), server: 'prod' }] })
    fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }))
    expect(await screen.findByText('Server 1 (databricks) needs Catalog, Schema')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })
})
```

- [ ] **Step 6: Run both to verify they fail**

Run, from `frontend/`: `npx vitest run src/pages/DataContracts/ContractServers.test.tsx src/pages/DataContracts/DataContractForm.test.tsx`
Expected: FAIL, cannot resolve `./ContractServers`, and missing headings in the form.

- [ ] **Step 7: Implement the editors and wire them into the form**

- `EditableRows` keeps the `idsRef` key pattern and the add, remove and empty-state markup from `QualityRules.tsx`.
- Placeholders: `TeamMembers` uses `Username`, `Name`, `Role`. `SupportChannels` uses `Channel`, `URL`, `Tool (slack, teams, email...)`, `Scope (interactive, issues...)`, as plain inputs because ODCS does not close those lists. `ContractServers` uses `Server name`, `Environment`, then a `select` with `aria-label="Server type"` whose change goes through `withServerType`, then one input per key in `SERVER_TYPE_KEYS[row.type]`, with its `SERVER_KEY_LABELS` value as placeholder. `port` is `type="number"`.
- `DataContractForm`: add `purpose`, `usage`, `limitations` to the zod schema and `normalizeDefaults` as `z.string()`. Hold `teamMembers`, `support` and `servers` in state, and keep a `metadataFormError` that `handleFormSubmit` sets from `metadataError(...)` after `validateFormArrays`, returning early when it is set. Add the four values to the payload.
- Render for every tier, after Quality Rules: `SectionHeader label="Description" optional` with three `Textarea` components from `components/ui/Input`, labelled `Purpose`, `Usage`, `Limitations` (`rows={2}`). Then `Team Members`, `Support` and `Servers`, each `optional`. Show `metadataFormError` above the buttons in the style of `fieldsError`.

- [ ] **Step 8: Verify**

Run, from `frontend/`: `npm test`, then `npm run lint`, then `npm run build`
Expected: all pass, with no lint warnings (`complexity` limit is 15) and a successful build.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/pages/DataContracts/contractMetadata.ts frontend/src/pages/DataContracts/contractMetadata.test.ts frontend/src/pages/DataContracts/EditableRows.tsx frontend/src/pages/DataContracts/TeamMembers.tsx frontend/src/pages/DataContracts/SupportChannels.tsx frontend/src/pages/DataContracts/ContractServers.tsx frontend/src/pages/DataContracts/ContractServers.test.tsx frontend/src/pages/DataContracts/DataContractForm.tsx frontend/src/pages/DataContracts/DataContractForm.test.tsx
git commit -m "feat(frontend): edit contract description, team, support and servers"
```

---

### Task 7: Detail page and final verification

**Files:**
- Modify: `frontend/src/pages/DataContracts/DataContractDetail.tsx`, `frontend/src/pages/DataContracts/contractMetadata.ts`
- Test: `frontend/src/pages/DataContracts/DataContractDetail.test.tsx` (create), `contractMetadata.test.ts`

**Interfaces:**
- Consumes: types and `emptyServer` from Task 6.
- Produces, in `contractMetadata.ts`: `safeUrl(url: string): string | null`, which returns the url only when it matches `/^(https?:|mailto:)/i`, and `serverLocation(server: ContractServer): string`, with one format per type as the test pins.

- [ ] **Step 1: Add the failing helper tests to `contractMetadata.test.ts`**

```ts
import { safeUrl, serverLocation } from './contractMetadata'

describe('safeUrl', () => {
  it.each(['https://example.com', 'http://example.com', 'mailto:a@example.com', 'HTTPS://example.com'])(
    'keeps %s', (url) => expect(safeUrl(url)).toBe(url),
  )
  it.each(['javascript:alert(1)', ' javascript:alert(1)', 'data:text/html,x', ''])(
    'refuses %j', (url) => expect(safeUrl(url)).toBeNull(),
  )
})

describe('serverLocation', () => {
  it('formats each type', () => {
    const base = emptyServer()
    expect(serverLocation({ ...base, host: 'h', catalog: 'c', schema_name: 's' })).toBe('h / c.s')
    expect(serverLocation({ ...base, catalog: 'c', schema_name: 's' })).toBe('c.s')
    expect(serverLocation({ ...base, type: 'postgres', host: 'h', port: 5432, database: 'd', schema_name: 's' })).toBe('h:5432/d.s')
    expect(serverLocation({ ...base, type: 'azure', location: 'az://a/b', format: 'csv' })).toBe('az://a/b (csv)')
    expect(serverLocation({ ...base, type: 'local', path: './a.csv', format: 'csv' })).toBe('./a.csv (csv)')
  })
})
```

- [ ] **Step 2: Write the failing page test `DataContractDetail.test.tsx`**

```tsx
import { render, screen } from '@testing-library/react'
import { beforeEach, describe, it, expect, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import DataContractDetail from './DataContractDetail'
import { emptyServer } from './contractMetadata'
import {
  useDataContract, useDataContractYaml, useDeleteDataContract, useUpdateDataContract,
} from '../../hooks/useDataContracts'

vi.mock('../../hooks/useDataContracts', () => ({
  useDataContract: vi.fn(), useDataContractYaml: vi.fn(), useDeleteDataContract: vi.fn(), useUpdateDataContract: vi.fn(),
}))
vi.mock('./DataContractForm', () => ({ default: () => null }))

const base = {
  id: 'c1', title: 'Orders', version: '1.0.0', owner: 'alice', domain: 'commerce', domain_id: 'd1',
  tier: 4, status: 'draft', models: { fields: [], quality: [] },
  servicelevels: { freshness: '', availability: '', retention: '', latency: '' },
  description: { purpose: '', usage: '', limitations: '' }, team_members: [], support: [], servers: [],
  created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
}

function renderDetail(contract: object) {
  vi.mocked(useDataContract).mockReturnValue({ data: { ...base, ...contract }, isLoading: false, error: null } as never)
  render(
    <MemoryRouter initialEntries={['/data-contracts/c1']}>
      <Routes><Route path="/data-contracts/:id" element={<DataContractDetail />} /></Routes>
    </MemoryRouter>,
  )
}

describe('DataContractDetail metadata', () => {
  beforeEach(() => {
    const mutation = { mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false, isError: false, error: null }
    vi.mocked(useUpdateDataContract).mockReturnValue(mutation as never)
    vi.mocked(useDeleteDataContract).mockReturnValue(mutation as never)
    vi.mocked(useDataContractYaml).mockReturnValue({ data: undefined, isFetching: false } as never)
  })

  it('shows description, team, support and servers', () => {
    renderDetail({
      description: { purpose: 'Orders placed', usage: '', limitations: '' },
      team_members: [{ username: 'alice@example.com', name: 'Alice', role: 'owner' }],
      support: [{ channel: '#commerce', url: 'https://example.com/c', tool: 'slack', scope: 'issues' }],
      servers: [{ ...emptyServer(), server: 'prod', environment: 'prod', catalog: 'dmplt', schema_name: 'sales' }],
    })
    expect(screen.getByText('Orders placed')).toBeInTheDocument()
    expect(screen.getByText('alice@example.com')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'https://example.com/c' })).toHaveAttribute('href', 'https://example.com/c')
    expect(screen.getByText('dmplt.sales')).toBeInTheDocument()
  })

  it('hides sections the contract does not have', () => {
    renderDetail({})
    for (const heading of ['Description', 'Team Members', 'Support', 'Servers']) {
      expect(screen.queryByRole('heading', { name: heading })).toBeNull()
    }
  })

  it('shows a javascript: support url as text, not a link', () => {
    renderDetail({ support: [{ channel: 'c', url: 'javascript:alert(1)', tool: '', scope: '' }] })
    expect(screen.getByText('javascript:alert(1)')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /javascript/ })).toBeNull()
  })

  it('shows field attributes, and renders a stored field without them', () => {
    renderDetail({ models: { fields: [
      { name: 'email', type: 'string', description: '', nullable: true, primary_key: false,
        classification: 'restricted', unique: true, physical_type: 'VARCHAR(255)' },
      { name: 'legacy', type: 'string', description: '', nullable: true, primary_key: false },
    ] } })
    expect(screen.getByText('restricted')).toBeInTheDocument()
    expect(screen.getByText('VARCHAR(255)')).toBeInTheDocument()
    expect(screen.getByText('legacy')).toBeInTheDocument()
  })
})
```

- [ ] **Step 3: Run them to verify they fail**

Run, from `frontend/`: `npx vitest run src/pages/DataContracts/contractMetadata.test.ts src/pages/DataContracts/DataContractDetail.test.tsx`
Expected: FAIL, `safeUrl` is not a function, and the metadata text is not found.

- [ ] **Step 4: Implement the helpers and the page**

- `SchemaFieldsCard` gains `Physical`, `Classification` and `Unique` columns, showing `—` for an empty or missing value.
- Add `DescriptionCard` (filled keys only), `TeamCard`, `SupportCard` and `ServersCard`. Each returns `null` when empty, as `QualityRulesCard` does, and its `h2` text is exactly `Description`, `Team Members`, `Support` or `Servers`.
- `SupportCard` renders the url as `<a target="_blank" rel="noopener noreferrer">` only when `safeUrl` returns a value, and as text otherwise. `ServersCard` columns are Server, Type, Environment and Location, the last from `serverLocation`.
- Page order: Info, Description, Schema Fields, Quality Rules, Service Levels, Team Members, Support, Servers.

- [ ] **Step 5: Run the whole frontend and backend checks**

Run, from `frontend/`: `npm test`, `npm run lint`, `npm run build`. Then, from the root: `.venv/Scripts/python.exe -m pytest tests/ -q` and `.venv/Scripts/python.exe -m ruff check backend`
Expected: everything passes, with no lint warnings and `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/DataContracts/DataContractDetail.tsx frontend/src/pages/DataContracts/DataContractDetail.test.tsx frontend/src/pages/DataContracts/contractMetadata.ts frontend/src/pages/DataContracts/contractMetadata.test.ts
git commit -m "feat(frontend): show contract metadata on the detail page"
```
