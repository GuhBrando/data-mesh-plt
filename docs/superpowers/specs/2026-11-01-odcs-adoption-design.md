# ODCS Adoption Design

**Date:** 2026-11-01
**Status:** Draft
**Target standard:** Open Data Contract Standard (ODCS) `v3.2.0`
**Baseline:** `develop` at `f02160d`, 217 backend tests passing

---

## Overview

The README says contracts are ODCS, but the platform emits something else.
`backend/use_cases/data_contract/yaml_builder.py` writes
`dataContractSpecification: 0.9.3`, which is the older Data Contract Specification
(DCS), and the output does not conform to DCS either: `datacontract lint` (CLI 1.2.9)
reports 6 validation errors on a contract produced by the real `assemble_yaml`.

The contract also lacks what would make it usable outside the platform: it does not
say where the data lives, its quality rules cannot be executed, and it has no version
history.

This design makes the platform produce, read and evolve real ODCS contracts. It is
delivered as five independent plans. Each leaves the platform working.

---

## Decisions Made During Planning (2026-11-02)

The five plans were written separately and surfaced facts this spec did not have.
Where this section and the rest of the spec disagree, this section wins.

1. **Tests must not reach GitHub.** `admin_client` in `test_routers.py` does not
   override `get_github_client` and `.env` holds a token, so the test command can
   commit to the central repository. The guard in `tests/conftest.py` is the first
   task of plan 1. Plan 2 only checks that it is present.
2. **The lint gate reads the JSON report.** `datacontract lint` exits 0 with
   `result: warning` for a missing `apiVersion` or a wrong `kind`, and on Windows it
   exits 1 on a pass unless `PYTHONUTF8=1` is set. Gates run with
   `--output-format json` and require `result == "passed"`. The JSON Schema unit
   tests stay as well, because the CLI accepts things the schema rejects.
3. **The vendored schema comes from the `v3.2.0` tag** (`?ref=v3.2.0`), with SHA-256
   `edb41f33ec46e84780e99872ab2bd67f074959d2bf3e9c9fc54e61f8982b0d93`. The default
   branch holds a later, different copy.
4. **SLA units follow the ODCS example:** `%` for percentages and `min` for minutes.
   The CLI reads `m` as months. Reading also accepts `percent` and `m`. A string is
   split into `value` and `unit` only when rebuilding gives back the same string;
   otherwise it stays a string.
5. **Reading is strict.** Plan 1's `from_odcs` rejects any key the model cannot hold,
   through key-set constants. Every later plan that adds a key extends them: plan 3
   extends `_DOCUMENT_KEYS`, `_TEAM_KEYS` and `_PROPERTY_KEYS` and adds sets for its
   new sections, plan 4 extends `_RULE_KEYS` (its custom-property and SLA-entry sets
   gain nothing, since SLA entries still reject `element` and `driver`), and plan 5
   adds `retired` to `_DB_STATUSES`.
6. **Rule order** is kept in plan 1 by a fifth custom property, `dmpltPosition`. Plan 4
   removes all `dmplt*` properties from what it writes, but still reads a plan 1 text
   rule carrying them, as a `type: text` rule that keeps its description followed by the
   same `[legacy rule: …]` suffix the SQL migration writes, so both paths store the
   same text.
7. **Servers keep all four types.** Only `databricks` is valid with the six keys listed
   under plan 3, so plan 3 adds the non-secret keys `port`, `database`, `location`,
   `format` and `path`. Plan 4's execution proof uses a `local` server emitted by the
   platform, not one injected by hand.
8. **Migration versions are `2026110100000N`, where N is the plan number:**
   `20261101000003_data_contract_metadata.sql`, `20261101000004_odcs_quality_and_sla.sql`
   and `20261101000005_contract_versions.sql`.
9. **`atlas.sum` is fixed once, in plan 3's first task.** The committed file mixes
   hashes of CRLF and LF copies, so `atlas migrate validate` already fails on
   `develop`. Plan 3 adds `database/migrations/*.sql text eol=lf` to `.gitattributes`,
   regenerates every hash from LF content with the `arigaio/atlas` image, and adds an
   `atlas migrate validate` step to CI. Plans 4 and 5 regenerate the same way.
10. **Quality rules are limited to what executes** (measured with CLI 1.2.9):
    - `percent` only on `nullValues`, `missingValues` and `invalidValues`.
    - An empty column only on `rowCount`.
    - At most one rule per metric and column.
    - `invalidValues` takes a non-empty list in `arguments.validValues`, and each
      value must cast to the column type.
    - The data migration converts `uniqueness` only when T is 100, to
      `duplicateValues` at most 0 rows.
    - A threshold that is not a percentage between 0 and 100 becomes `type: text`.
11. **Versioning grants.** The app connects as `admin`, which owns the tables on
    azure, so "INSERT and SELECT only" would break the cascading delete. Plan 5 uses
    a partial REVOKE plus a `BEFORE UPDATE OR DELETE` trigger that lets the cascade
    through. Updates lock the contract row with `SELECT ... FOR UPDATE`, so two
    concurrent bumps cannot move the version backwards. A non-semver version already
    stored may stay as it is; any new value must be semver.
12. **Central repository.** `sales.yaml` and `updated.yaml` are output of
    `test_routers.py` and share one id. The owner decides whether to delete them
    before converting. The conversion runs only after a release tag that contains
    plan 1 is deployed.
13. **Known limitations, accepted and documented rather than fixed:**
    - Moving an `active` contract to `draft`, editing it, and moving it back bypasses
      the policy.
    - A snapshot can differ from later edits made at the same version.
    - The MAJOR list is closed.
    - `GET /data-contracts` returns full contracts to consumers.

    Plan 5 writes the first three into the README's "Política de Evolução".

---

## Goals

- Every contract the platform emits passes `datacontract lint` as ODCS `v3.2.0`.
- A contract survives a round trip: emit, parse, and get the same contract back.
- The contract says who owns it, how to get help, and where the data is.
- Quality rules use ODCS library metrics, so a tool can execute them.
- Version history is immutable and breaking changes require a MAJOR bump.

## Non-goals

- Data products: ODPS, input ports, output ports, the `product.yaml` format.
- The `dmplt-tech-scaffolds` repository and running contracts on Databricks.
- Replacing direct commits with pull requests, webhooks, and approval workflows.
- Tier-driven rules. Tier stays a stored attribute.
- Several tables in one contract. A contract has at most one `schema[]` object.
- MCP, authentication, and the missing role checks on the data product routes.
- Updating `database/schema/*.hcl`, which is already out of date with the migrations.

---

## Plans

Execution order. A later plan may assume every earlier plan has shipped.

| # | Plan file (`docs/superpowers/plans/`) | Delivers | Schema change |
|---|---|---|---|
| 1 | `2026-11-01-odcs-1-serialization.md` | Valid ODCS output, ODCS parsing, legacy DCS reading in sync, lint in CI | None |
| 2 | `2026-11-01-odcs-2-central-repo-migration.md` | Central repo files converted, lint workflow there, legacy reader removed | None |
| 3 | `2026-11-01-odcs-3-contract-metadata.md` | Description, team members, support, servers, field attributes | Additive |
| 4 | `2026-11-01-odcs-4-quality-and-sla.md` | ODCS library quality rules and structured SLA | Breaking, with data migration |
| 5 | `2026-11-01-odcs-5-versioning.md` | Immutable version history, semver enforcement, `retired` status | Additive |

---

## Shared Interfaces

These names are fixed so that plans written separately fit together.

**`backend/use_cases/data_contract/odcs.py`** (created by plan 1)

```python
ODCS_API_VERSION = "v3.2.0"

class OdcsParseError(ValueError): ...

@dataclass(frozen=True)
class ParsedContract:
    id: uuid.UUID
    title: str
    version: str
    owner: str
    domain_name: str
    tier: int
    status: str
    models: dict[str, Any]
    servicelevels: dict[str, Any]

def to_odcs(contract: DataContract) -> dict[str, Any]: ...
def from_odcs(doc: dict[str, Any]) -> ParsedContract: ...
```

Plan 3 adds fields to `ParsedContract`, each with a default. `to_odcs` and `from_odcs`
are pure functions with no I/O.

**`backend/use_cases/data_contract/yaml_builder.py`** keeps
`assemble_yaml(contract: DataContract) -> str`. It becomes a thin call to `to_odcs`
followed by `yaml.dump`, and existing callers do not change.

**`backend/use_cases/data_contract/legacy_dcs.py`** (created by plan 1, deleted by
plan 2) exposes `from_legacy_dcs(doc: dict[str, Any]) -> ParsedContract`.

**`backend/use_cases/data_contract/contract_document.py`** (created by plan 1) exposes
`parse_contract_document(doc: dict[str, Any]) -> ParsedContract`. It dispatches on the
presence of `dataContractSpecification`, and `SyncFromGitHubUseCase` calls it instead
of reading keys itself. Plan 2 removes the legacy branch and keeps plan 1's "not a YAML
mapping" check before calling `from_odcs`.

---

## ODCS Mapping (Plan 1)

| Internal | ODCS | Rule |
|---|---|---|
| none | `apiVersion` | Constant `v3.2.0` |
| none | `kind` | Constant `DataContract` |
| `id` | `id` | UUID as string |
| `title` | `name` | Unchanged |
| `version` | `version` | Unchanged |
| `status` | `status` | `in_review` maps to `proposed` and back; others identical |
| `domain` | `domain` | Joined domain name |
| `owner` | `team.name` | Team object, not the deprecated array |
| `tier` | `customProperties[property=tier].value` | Integer. Missing on read means 4 |
| `models.fields[]` | `schema[0].properties[]` | See below |
| `models.quality[]` | `quality[]` | See below |
| `servicelevels.*` | `slaProperties[]` | See below |

**Schema object.** `schema[0]` has `name` set to the snake_case slug of the title
(`contract` if the slug is empty), `logicalType: object`, and `physicalType: table`.
Omit `schema` entirely when the contract has no fields and no quality rules.

**Fields.** `name` and `description` are copied. `type` becomes `logicalType`, with
`float` mapping to `number` and all others identical. `required` is `not nullable`.
`primary_key` becomes `primaryKey`.

**Quality rules, plan 1 only.** Plan 1 must not change the stored rule format, so each
rule is emitted as `type: text` with its original values kept in `customProperties`:
`dmpltDimension`, `dmpltOperator`, `dmpltThreshold`, and `dmpltColumn` when the column
is not a known field. The ODCS `dimension` is mapped: `completeness` and `uniqueness`
are identical, `freshness` becomes `timeliness`, `validity` becomes `conformity`,
`integrity` becomes `consistency`. A rule with a known column sits under that property.
Any other rule sits on the schema object. `description` is the rule's description, or a
generated sentence when it is empty, because a `text` rule with no description says
nothing.

**Service levels.** `freshness`, `availability`, `retention` and `latency` each become
one `slaProperties` entry with `property` set to the key. A value matching
`^(\d+(?:\.\d+)?)\s*([a-zA-Z%]+)?$` is split into numeric `value` and `unit` when
rebuilding gives back the same string (decision 4). Any other value is kept as a string
`value` with no `unit`. Empty
strings are omitted. Parsing rebuilds the original string.

**Parsing errors.** `from_odcs` raises `OdcsParseError` with a specific message for: an
`apiVersion` not starting with `v3.`, `kind` other than `DataContract`, more than one
`schema[]` object, a `logicalType` the internal model cannot hold (`time`, `object`,
`array`), and a status the database does not accept. No value is dropped silently.
A missing `domain` keeps the existing sync behaviour and its error message.

---

## Plan 2: Central Repository

The contracts repository is `GuhBrando/dmplt_data_contract`. It holds three files in
the legacy format: `contracts/commerce/sales.yaml`, `contracts/commerce/updated.yaml`
and `contracts/riscos/test.yaml`.

- `scripts/migrate_contracts_to_odcs.py` reads each file through `GitHubClient`,
  converts it with `from_legacy_dcs` and `to_odcs`, and prints the result. It only
  writes when passed `--apply`, and refuses a file that fails validation.
- Add a workflow to that repository running `datacontract lint` on every changed
  `contracts/**/*.yaml`, on pull requests and pushes.
- Remove `legacy_dcs.py` only after the files are converted.

Any step that writes to that repository is marked as requiring the owner's explicit
approval at execution time.

---

## Plan 3: Contract Metadata

New columns on `catalog.data_contracts`:

| Column | Type | Default |
|---|---|---|
| `description` | `JSONB NOT NULL` | `{"purpose":"","usage":"","limitations":""}` |
| `team_members` | `JSONB NOT NULL` | `[]` |
| `support` | `JSONB NOT NULL` | `[]` |
| `servers` | `JSONB NOT NULL` | `[]` |

| Internal | ODCS |
|---|---|
| `description.purpose`, `.usage`, `.limitations` | `description.*`, empty values omitted |
| `team_members[]`: `username`, `name`, `role` | `team.members[]` |
| `support[]`: `channel`, `url`, `tool`, `scope` | `support[]` |
| `servers[]`: `server`, `type`, `environment`, `host`, `catalog`, `schema_name`, `port`, `database`, `location`, `format`, `path` | `servers[]`, with `schema_name` written as `schema`; which keys a type needs follows the standard (decision 7) |
| `models.fields[].classification` | `classification`, one of `public`, `internal`, `confidential`, `restricted`, or empty |
| `models.fields[].unique` | `unique` |
| `models.fields[].physical_type` | `physicalType` |

`servers[].type` accepts `databricks`, `postgres`, `azure` and `local`. New fields have
defaults, so existing API clients keep working. The contract form and the detail page
expose all of them.

---

## Plan 4: Quality Rules and SLA

**Quality rule, stored in `models.quality[]`:**

| Field | Values |
|---|---|
| `type` | `library` or `text` |
| `dimension` | The ODCS enum: `accuracy`, `completeness`, `conformity`, `consistency`, `coverage`, `timeliness`, `uniqueness` |
| `column` | Field name, or empty for the whole table |
| `metric` | `nullValues`, `missingValues`, `invalidValues`, `duplicateValues`, `rowCount`, or null for `text` |
| `operator` | `mustBe`, `mustNotBe`, `mustBeGreaterThan`, `mustBeGreaterOrEqualTo`, `mustBeLessThan`, `mustBeLessOrEqualTo`, or null for `text` |
| `value` | Number, or null for `text` |
| `unit` | `rows`, `percent`, or null |
| `valid_values` | List for `invalidValues`, otherwise empty |
| `description` | Free text, required for `text` |

**Service levels, stored in `servicelevels`:** `{"properties": [{"property", "value",
"unit"}]}`. The column name does not change.

**Data migration.** Existing rows are converted by SQL. A `completeness` rule with a
column and `>= T` becomes `nullValues`, `mustBeLessOrEqualTo`, `100 - T`, `percent`.
A `uniqueness` rule the same way with `duplicateValues`. Everything else becomes
`type: text` with its old values written into `description`, and old dimensions are
mapped as in plan 1.

The plan proves the rules execute: `datacontract test` runs a contract emitted by the
platform against a small local fixture dataset, once passing and once failing.
The `dmplt*` custom properties from plan 1 are removed from the mapper.

---

## Plan 5: Versioning

New table `catalog.contract_versions`: `contract_id` (FK, cascade on delete), `version`,
`yaml_content TEXT`, `created_by UUID NULL`, `created_at`, unique on
`(contract_id, version)`. Rows are never updated. A snapshot is the ODCS YAML, so
history does not depend on the internal model.

A snapshot is written when a contract is created and whenever its version changes.

`classify_change(old: dict, new: dict) -> ChangeKind` compares two `to_odcs` documents
and returns `NONE`, `PATCH`, `MINOR` or `MAJOR`. It lives in
`backend/domain/contract_evolution.py` as a pure function, following the README's
evolution policy:

- MAJOR: a property removed or renamed, `logicalType` changed, `required` turned on.
- MINOR: a property added, a constraint relaxed.
- PATCH: any other content change.

Rules apply only to contracts in `active` or `deprecated` status. Drafts change freely.
A change of content with no version change is rejected, and so is a bump smaller than
the change requires. Rejected requests return `409` with a message naming the changes.
The same check applies in sync, where a violation is reported in `errors` and the file
is skipped.

Version strings must match `^\d+\.\d+\.\d+$`. Status gains `retired`, which is
terminal, and the `chk_dc_status` constraint changes with it.

Endpoints, using the same read authorization as contract detail:
`GET /api/v1/data-contracts/{id}/versions` and
`GET /api/v1/data-contracts/{id}/versions/{version}/yaml`. The detail page lists the
history.

---

## Validation

- **Unit tests** validate `to_odcs` output against the official JSON Schema, vendored
  verbatim at `tests/fixtures/odcs/odcs-json-schema-v3.2.0.json` from
  `schema/odcs-json-schema-v3.2.0.json` in `bitol-io/open-data-contract-standard`.
  `jsonschema` is a dev dependency only.
- **CI** runs `uvx --from datacontract-cli==1.2.9 datacontract lint --output-format json`
  on a contract generated by the real code and requires `result == "passed"`
  (decision 2). Locally on Windows, set `PYTHONUTF8=1`.
- **Round trip**: `from_odcs(to_odcs(c))` returns the values of `c`, for every
  combination the model allows.

---

## Repository Rules

- Branch from `develop`. An unmerged branch, `worktree-feat+data-contract-picker`,
  changes `DataProductForm` and adds repository tests.
- Commit messages and PR text carry no Claude or Claude Code attribution of any kind.
- Backend tests: `.venv\Scripts\python.exe -m pytest tests/ -q`.
- Frontend, from `frontend/`: `npm test`, `npm run lint`, `npm run build`.
- `git commit` needs `.venv\Scripts` prefixed to `PATH`, or pre-commit fails.
- Lint with `ruff check backend`. Passing test paths makes ruff rewrite those files.
- Migrations are SQL files in `database/migrations/`, named as in decision 8, and
  `atlas.sum` is regenerated with them as in decision 9. `atlas` is not on `PATH`
  on this machine; use the `arigaio/atlas` image through Docker.
- Layering stays as it is: entities and pure logic hold no I/O, routers orchestrate
  GitHub calls, and GitHub push failures stay warn-only.
