# ODCS Quality Rules and SLA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store quality rules as ODCS library metrics and service levels as structured properties, end to end (database, API, mapper, form, detail page), and prove with `datacontract test` that every library rule the platform emits runs against real data.

**Architecture:** A pure domain function decides which rules `datacontract-cli 1.2.9` can run, and both the API schemas and `from_odcs` use it. A pure mapper module converts one rule or the service levels to and from ODCS, and `odcs.py` calls it. Old rows are converted by one idempotent SQL migration. The change ships expand, migrate, contract: the backend first accepts both shapes, the frontend switches with a temporary read shim, the migration converts the data, and the last task deletes the old shapes.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, asyncpg, pytest (`asyncio_mode=auto`), jsonschema (dev), React 18, TypeScript, react-hook-form, zod, Vitest, Testing Library, PostgreSQL 16.1, Atlas, `datacontract-cli[csv]==1.2.9` through `uvx`.

**Spec:** `docs/superpowers/specs/2026-11-01-odcs-adoption-design.md`, sections "Decisions Made During Planning (2026-11-02)", which win over the rest, "Plan 4", "Shared Interfaces", "ODCS Mapping (Plan 1)", "Validation" and "Repository Rules". Plans 1, 2 and 3 have shipped: `odcs.py`, `contract_document.py` and the vendored JSON Schema exist, and contracts carry description, team members, support, servers and field attributes.

## Global Constraints

- Target standard: ODCS `v3.2.0`. Executing tool: `uvx --from "datacontract-cli[csv]==1.2.9" datacontract`. On Windows, set `PYTHONUTF8=1` first, or Rich crashes with `UnicodeEncodeError` while printing the result.
- Stored rule, in `models.quality[]`: `type` (`library` or `text`), `dimension` (`accuracy`, `completeness`, `conformity`, `consistency`, `coverage`, `timeliness`, `uniqueness`), `column`, `metric` (`nullValues`, `missingValues`, `invalidValues`, `duplicateValues`, `rowCount`, or null for `text`), `operator` (`mustBe`, `mustNotBe`, `mustBeGreaterThan`, `mustBeGreaterOrEqualTo`, `mustBeLessThan`, `mustBeLessOrEqualTo`, or null for `text`), `value` (a number, or null for `text`), `unit` (`rows`, `percent`, or null), `valid_values`, `description`.
- Stored service levels, in the `servicelevels` column (the name does not change): `{"properties": [{"property", "value", "unit"}]}`.
- `to_odcs(contract: DataContract) -> dict[str, Any]` and `from_odcs(doc: dict[str, Any]) -> ParsedContract` keep their signatures and stay pure. `from_odcs` raises `OdcsParseError` and drops no value silently.
- Invariant of this plan: every `library` rule the platform stores or emits runs under `datacontract-cli 1.2.9`. This comes from the spec goal "Quality rules use ODCS library metrics, so a tool can execute them".
- `jsonschema` stays a dev dependency. Schema tests use `tests/fixtures/odcs/odcs-json-schema-v3.2.0.json` with `jsonschema.Draft201909Validator`. The file declares draft 2019-09.
- Branch from `develop` after Plans 1 to 3 are merged. Commits and the PR carry no Claude or Claude Code attribution of any kind.
- Backend tests: `.venv\Scripts\python.exe -m pytest tests/ -q`. Lint: `.venv\Scripts\ruff.exe check backend` and `.venv\Scripts\ruff.exe format backend`. Never pass test paths to ruff, because it rewrites them.
- Frontend, from `frontend/`: `npm test`, `npm run lint`, `npm run build`.
- `git commit` needs `.venv\Scripts` first on `PATH`. In PowerShell: `$env:PATH = "$PWD\.venv\Scripts;$env:PATH"`.
- CI gates: cyclomatic complexity of 15 or less per function (ruff `C90` and ESLint `complexity`), and coverage of at least 80% for the backend and the frontend.
- Entities and pure logic hold no I/O. GitHub push failures stay warn-only.
- Migration SQL never contains two opening braces in a row, because Atlas renders the directory as a Go template (`data "template_dir"` in `database/atlas.hcl`). It has no explicit `BEGIN`/`COMMIT`, because Atlas manages the transaction.

## Review Focus

These are the five inputs the spec implies but does not name that are most likely to hurt a user. Each one is pinned by a test in the task that owns the code.

1. A contract synced from GitHub carries an SLA property the four inputs do not show, such as `frequency`. Saving the form must keep it (Task 7, `keeps properties the form does not show`).
2. A field is renamed or removed while a rule still names it. The form must block the save with a message naming the column, instead of sending a rule the API rejects (Task 6, `blocks saving a rule whose column was removed`).
3. A stale client sends the old `servicelevels` shape. The API must answer 422 instead of storing an empty SLA, which Pydantic's default `extra="ignore"` would do silently (Task 5 `extra="forbid"`, Task 9 `test_old_service_level_shape_is_rejected`).
4. The migration failed at deploy (`entrypoint.sh` only warns), or an old revision wrote an old-shape row during the swap. The detail page and the form must still render (Task 7, `survives an unmigrated row`).
5. Typing a comma in the valid values box. A controlled input that parses on every keystroke eats the comma and makes a second value impossible to type (Task 6, `keeps a typed comma in valid values until blur`).

## Verified Tool Behaviour

Run on this machine on 2026-11-01 and 2026-11-02. The scratch files are throwaway, so this section is the record.

**Execution proof.** Contract: ODCS `v3.2.0` with `rowCount mustBeGreaterOrEqualTo 5 rows`, `duplicateValues mustBe 0 rows` on `order_id`, `nullValues mustBeLessOrEqualTo 1 percent` on `customer_id`, `invalidValues mustBe 0 rows` with `arguments.validValues: [open, paid, shipped]` on `status`, `nullValues mustBe 0 rows` on `amount`, and a schema-level `text` rule. Server: `{server: local, type: local, path: <csv>, format: csv}`.

| Command (`PYTHONUTF8=1`) | Outcome |
|---|---|
| `uvx --from "datacontract-cli[csv]==1.2.9" datacontract lint pass.odcs.yaml` | `Data contract is valid against ODCS v3.2.0`, exit 0 |
| `... datacontract test pass.odcs.yaml --output pass.json --output-format json` | 11 checks passed, `Data contract is valid`, exit 0 |
| `... datacontract test fail.odcs.yaml --output fail.json --output-format json` | exit 1: `row_count(orders) was 4, expected >= 5`; `missing_count(customer_id) was 75.0% (3 of 4 rows), expected <= 1%`; `duplicate_count(order_id) was 2, expected = 0`; `invalid_count(status) was 2, expected = 0`; the `amount` rule passed |
| The same contract after the real migration SQL and a prototype of this plan's mapper | lint exit 0; test on good data exit 0 (5 checks); test on bad data exit 1 (`50.0% (2 of 4 rows)`, `duplicate_count(id) was 1, expected <= 0`); the CSV fixtures had CRLF line endings |
| `uvx --from "datacontract-cli==1.2.9" ...` (no extra) | exit 1, `The 'local' backend is not installed. Install it with: pip install 'datacontract-cli[duckdb]'`. `[csv]` pulls `[duckdb]`. Parquet needs `[parquet]`. |

**Server fields.** For a local file, ODCS `LocalServer` requires `path` and `format` (`csv`, `parquet`, `json`, `delta`). A relative `path` resolves against the current directory, not the contract's directory (`IO Error: No files found`), so the harness writes an absolute path.

**Metric, operator and unit matrix.** 270 runs, one rule per contract, with thresholds chosen so that `rows` and `percent` give different results:
- All six operators work as defined for all five metrics with `rows` or no unit.
- `percent` works for `nullValues`, `missingValues` and `invalidValues`.
- `percent` on `duplicateValues` or `rowCount` is not executed. The check reports `warning`, the reason `'unit:percent' has to be combined with 'nullValues', 'missingValues' or 'invalidValues'`, and the run still exits 0.
- `lint` gives the same warning with exit 0 (`Data contract has warnings`), and the JSON Schema accepts the rule.

**Other behaviour that shapes this plan:**
- Two library rules with the same metric on the same column, or two `rowCount` rules: `Error evaluating check: Duplicate column name '<model>__<field>__field_null_values' in result set`. Every batched check of the model fails with it, `rowCount` included, and the second rule never gets a result. Two `duplicateValues` rules overwrite each other's result.
- `nullValues`, `missingValues` and `invalidValues` at schema level, or `rowCount` at property level: `warning`, not executed.
- `duplicateValues` at schema level with no `arguments.properties`: `failed`, `Column 'None' not found`.
- `invalidValues`: takes its valid values from `arguments.validValues`.
  - Without arguments: `warning`.
  - With `validValues: []`: every row counts as invalid.
  - Strings work on `string`, `integer`, `number`, `boolean`, `date` and `timestamp` columns when they cast to the column type.
  - A string that does not cast (`abc` on an integer column, `soon` on a date column), or a number on a string column, raises `Conversion Error` and fails every batched check of the model.
- `missingValues` without `arguments.missingValues` counts nulls only, exactly like `nullValues`.
- A rule with two operators fails lint: `must match exactly one of 8 definitions, but matches several`.
- `slaProperties`: the CLI only checks `freshness` and `retention`, and only when `element` is `model.field`. With no `element`, nothing about SLAs runs. Its freshness units are `d`, `h` and `m` (minutes), while its retention reads `m` as months.

**Atlas and Postgres** (measured with `arigaio/atlas:latest`, which reported v1.3.7, a pre-release build, and a throwaway `postgres:16.1` container; the commands below use the pinned release tag `arigaio/atlas:1.3.6`, as Plan 3's "Settled Decisions" explains):
- The migration below was applied with `entrypoint.sh`'s exact flags (`migrate apply --env azure --url ... --revisions-schema public --allow-dirty`) as the `admin` role production uses: exit 0, `1 migration, 3 sql statements`.
- Run a second time with `psql`: `UPDATE 0`, `UPDATE 0`, and an identical table hash.
- Seeded with 37 rows covering every case in Task 8, it produced rules and service levels that pass this plan's Pydantic models, the JSON Schema and the round trip, with 0 problems.
- A migration file with a version older than the last applied one fails with `migration file ... was added out of order`, and `entrypoint.sh` only logs a warning.
- `template_dir` does not enforce `atlas.sum`: apply succeeds with a stale or garbage sum. `atlas migrate validate --dir file://migrations` does enforce it (`checksum mismatch`).
- The `atlas.sum` committed on `develop` was generated from CRLF working copies: the real tool reproduces rows 1 to 8 only from CRLF bytes. Its last row came from an LF file. Git and the Docker image hold LF. Plan 3 Task 1 fixed this (spec decision 9): migrations are `eol=lf` in `.gitattributes`, the sum is hashed from LF content, and CI runs `atlas migrate validate`.
- The compose `backend` container never applies migrations. `entrypoint.sh` uses `sslmode=require`, and the compose `db` answers `pq: SSL is not enabled on the server` followed by `WARNING: Migrations failed`.

## Decisions Where the Spec Is Silent or Conflicts

Each of these is also listed for the coordinator in the report that comes with this plan.

1. **Only runnable library rules.**
   - Column: `rowCount` takes no column. The four column metrics need one, and it must name a declared field.
   - Unit: `percent` only with `nullValues`, `missingValues` and `invalidValues`.
   - Valid values: `invalidValues` needs a non-empty `valid_values` that casts to the field type (`integer`, `float`, `date`, `timestamp`).
   - Value: no negative values, and no `percent` value above 100.
   - The spec's migration sentence "A `uniqueness` rule the same way with `duplicateValues`" would write `duplicateValues ... percent`, which never runs. So a uniqueness rule becomes `duplicateValues mustBeLessOrEqualTo 0 rows` only when T is 100, which has the same meaning. Any other T becomes `text`.
2. **One library rule per (metric, column).** The API rejects a second one. The migration turns the later ones into `text`. A range such as "row count between 100 and 120" therefore cannot be expressed: the spec's operator list has no `mustBeBetween`, and two rules collide.
3. **The migration converts only when the threshold is a percentage of a declared column.** T must be between 0 and 100. A bare `0 < T <= 1`, such as `0.99` in the existing router test fixture, may be a fraction, and `100 - T` would turn it into "99.01% of the rows may be null". Those rules become `text`. An unknown column also becomes `text`, with the old column kept in the description.
4. **`valid_values` is `list[str]`.** Strings run on every column type when they cast. `from_odcs` stringifies numbers.
5. **`dimension` may be null.** The JSON Schema does not require it. A rule read from ODCS without one, and an unreadable legacy rule, would otherwise have no value to store.
6. **Service levels follow ODCS where they can without losing data.**
   - Units (spec decision 4): `%`, the unit in the ODCS SLA example (`sla-extensions.odcs.yaml`), and the ISO symbol `min` for minutes instead of `m`, which datacontract-cli reads as months for retention. Plan 1 already writes both. `from_odcs` accepts `percent` and `m` as aliases, as the spec requires, so a file written by hand or by another tool still syncs.
   - Property names: the four keys stay `freshness`, `availability`, `retention` and `latency`. ODCS lists `latency` as "preferred to freshness", but `property` is an open string, existing rows hold both keys (for example `sales.yaml` has `freshness: 24h` and `latency: 1h`), and `freshness` is the only freshness name the CLI can check.
   - Values: a number with a unit, or text with no unit.
7. **`from_odcs` is strict** (spec decision 5). A rule or SLA key the stored shape cannot hold raises `OdcsParseError` naming it. That covers `mustBeBetween`, `sql`, `custom`, `arguments.pattern`, `arguments.missingValues`, `arguments.properties`, `id`, `severity`, `customProperties`, `element` and `driver`. Sync reports the file in `errors` and keeps the database row. The one exception is spec decision 6: a Plan 1 `type: text` rule whose custom properties are all Plan 1's `dmplt*` keys is read as a `type: text` rule that keeps its `dimension` and `description`. Its `dmplt*` values go into the description as the same `[legacy rule: …]` suffix the Task 8 migration writes, so sync and the migration store the same text (Task 9). The allowed keys stay in Plan 1's constants in `odcs.py` (Task 3).
8. **The new Pydantic models forbid extra keys**, so the old shape cannot pass as an empty new one (Review Focus 3).
9. **The `servicelevels` column default changes** to `{"properties": []}`. The spec does not mention it, but the default is in the old shape.
10. **Round trip ignores rule order across columns.** `to_odcs` groups rules under their property, so `from_odcs(to_odcs(c))` returns the same rules but possibly reordered across columns. Order within one column is kept.
11. **Migration version `20261101000004`**, following "N = plan number". Atlas refuses an out-of-order file, so the version must be the greatest in the directory when this plan ships (Task 8 Step 1).
12. **CD deploys the backend before the frontend** (Task 9), so a new frontend never talks to an old backend. An old backend would silently drop `properties` and blank the SLA.
13. **`slaProperties` carries no `element`.** The spec's stored shape has none, so the CLI checks no SLA. The proof covers quality rules, which is what the spec claims.

## Task Order: Keeping the App Working

Nothing deploys from the branch, because CD runs only on a `v*.*.*` tag. Even so, every commit leaves a working app: old rows, old clients and new clients all work at each step.

| After task | Backend accepts | Backend emits ODCS for | Frontend sends | Frontend reads | Stored rows |
|---|---|---|---|---|---|
| 1-2 | old | old | old | old | old |
| 3-4 | old | old and new | old | old | old |
| 5 | old and new | old and new | old | old | old |
| 6 | old and new | old and new | new rules, old SLA | both, through a shim | mixed per row |
| 7 | old and new | old and new | new | both, through a shim | mixed per row |
| 8 | old and new | old and new | new | both | new once the migration runs |
| 9 | new only | new only | new | new | new |

At the release, Task 9's CD change deploys the backend first. The new container applies the migration before it serves. An old frontend that is still loaded gets 422 on save, because of `extra="forbid"`, and writes nothing. The one remaining gap is an old backend revision accepting an old-shape write while the new revision starts. The Release Notes check finds it and the idempotent migration fixes it.

## File Structure

**Create:**
- `backend/domain/quality_rules.py`: which rules can run, as a pure function.
- `backend/use_cases/data_contract/odcs_quality.py`: one rule, and the service levels, to and from ODCS.
- `database/migrations/20261101000004_odcs_quality_and_sla.sql`: the data migration.
- `tests/quality_rule_builders.py`: `library_rule()` and `text_rule()`, shared by backend tests.
- `tests/unit/test_quality_rules.py`
- `tests/unit/use_cases/data_contract/test_odcs_quality.py`
- `tests/unit/use_cases/data_contract/test_odcs_quality_contract.py`
- `tests/integration/__init__.py`
- `tests/integration/test_contract_execution.py`
- `tests/integration/test_odcs_quality_migration.py`
- `tests/fixtures/odcs/orders/pass/orders.csv`
- `tests/fixtures/odcs/orders/fail/orders.csv`
- `frontend/src/lib/qualityRules.ts` and `qualityRules.test.ts`
- `frontend/src/lib/serviceLevels.ts` and `serviceLevels.test.ts`
- `frontend/src/lib/contractFormat.ts` and `contractFormat.test.ts` (temporary, deleted in Task 9)
- `frontend/src/pages/DataContracts/QualityRules.test.tsx`

**Modify:** `backend/use_cases/data_contract/odcs.py`, `backend/interface/schemas/data_contract.py`, `database/migrations/atlas.sum`, `frontend/src/types/index.ts`, `frontend/src/hooks/useDataContracts.ts`, `frontend/src/pages/DataContracts/QualityRules.tsx`, `DataContractForm.tsx`, `DataContractDetail.tsx`, `.github/workflows/ci.yml`, `.github/workflows/cd.yml`, `tests/unit/test_data_contract_schemas.py`, `tests/unit/interface/test_routers.py`, `tests/unit/use_cases/data_contract/test_sync_from_github.py`.

**Modify, created by earlier plans:** `frontend/src/pages/DataContracts/DataContractForm.test.tsx` and `DataContractDetail.test.tsx` (Plan 3 Tasks 6 and 7: reuse their mocks, `contract` and `base` fixtures, `renderForm` and `renderDetail`); `tests/fixtures/odcs/sample_contract.py`, `tests/unit/use_cases/data_contract/test_odcs_emit.py` and `test_odcs_parse.py` (Plan 1, old-shape cases retired in Tasks 3 and 9); `tests/unit/use_cases/data_contract/test_odcs_metadata.py` (Plan 3, Task 9).

---

### Task 1: Which rules can run

**Files:**
- Create: `backend/domain/quality_rules.py`
- Create: `tests/quality_rule_builders.py`
- Test: `tests/unit/test_quality_rules.py`

**Interfaces:**
- Consumes: nothing.
- Produces:

```python
QUALITY_DIMENSIONS = ("accuracy", "completeness", "conformity", "consistency", "coverage", "timeliness", "uniqueness")
QUALITY_METRICS = ("nullValues", "missingValues", "invalidValues", "duplicateValues", "rowCount")
QUALITY_OPERATORS = ("mustBe", "mustNotBe", "mustBeGreaterThan", "mustBeGreaterOrEqualTo", "mustBeLessThan", "mustBeLessOrEqualTo")
QUALITY_UNITS = ("rows", "percent")
PERCENT_METRICS = ("nullValues", "missingValues", "invalidValues")

def find_quality_rule_problems(rules: list[dict[str, Any]], fields: list[dict[str, Any]]) -> list[str]: ...
```

`rules` are stored-shape dicts with all nine keys, and `fields` are `models.fields[]` dicts (`name`, `type`). The function returns at most one message per rule, then one per (metric, column) collision. Each message starts with `quality rule {n}: `, counting from 1, and an empty list means valid. `tests/quality_rule_builders.py` provides `library_rule(**overrides)` (default: library, completeness, column `email`, `nullValues`, `mustBe`, value 0, `rows`, `valid_values=[]`, description `""`) and `text_rule(**overrides)` (default: text, consistency, column `""`, null metric, operator, value and unit, `valid_values=[]`, description `"Totals reconcile with the ledger."`).

- [ ] **Step 1: Write the builders and the failing tests**

```python
FIELDS = [{"name": "id", "type": "integer"}, {"name": "email", "type": "string"},
          {"name": "joined", "type": "date"}]
lib, txt = library_rule, text_rule

RUNNABLE = [
    lib(), lib(unit=None), lib(dimension=None),
    lib(unit="percent", operator="mustBeLessOrEqualTo", value=1),
    lib(metric="missingValues", unit="percent"),
    lib(metric="invalidValues", valid_values=["a@x.io"], unit="percent"),
    lib(metric="invalidValues", column="id", valid_values=["1", "2"]),
    lib(metric="invalidValues", column="joined", valid_values=["2026-01-01"]),
    lib(metric="duplicateValues", column="id"),
    lib(metric="rowCount", column="", operator="mustBeGreaterOrEqualTo", value=5),
    txt(), txt(column="email"),
    *[lib(operator=op) for op in QUALITY_OPERATORS],
]

@pytest.mark.parametrize("rule", RUNNABLE)
def test_accepts_rules_the_tool_runs(rule):
    assert find_quality_rule_problems([rule], FIELDS) == []

@pytest.mark.parametrize(("rule", "fragment"), [
    (lib(metric="duplicateValues", column="id", unit="percent"), "percent"),
    (lib(metric="rowCount", column="", unit="percent"), "percent"),
    (lib(metric="rowCount", column="id"), "whole table"),
    (lib(column=""), "needs a column"),
    (lib(metric="duplicateValues", column=""), "needs a column"),
    (lib(metric="invalidValues", valid_values=[]), "valid_values"),
    (lib(valid_values=["x"]), "valid_values"),
    (lib(metric="invalidValues", column="id", valid_values=["1", "abc"]), "'abc'"),
    (lib(metric="invalidValues", column="joined", valid_values=["soon"]), "'soon'"),
    (lib(column="ghost"), "'ghost'"),
    (txt(column="ghost"), "'ghost'"),
    (lib(value=None), "value"), (lib(value="0"), "value"), (lib(value=True), "value"),
    (lib(value=-1), "negative"),
    (lib(unit="percent", value=101), "100"),
    (lib(metric="sql"), "metric"), (lib(operator="mustBeBetween"), "operator"),
    (lib(unit="ms"), "unit"), (lib(dimension="freshness"), "dimension"),
    (lib(type="sql"), "type"),
    (txt(description="  "), "description"),
    (txt(metric="nullValues"), "text rule"),
])
def test_rejects_rules_the_tool_cannot_run(rule, fragment):
    problems = find_quality_rule_problems([rule], FIELDS)
    assert len(problems) == 1
    assert problems[0].startswith("quality rule 1: ")
    assert fragment in problems[0]

def test_rejects_second_rule_with_same_metric_and_column():
    rules = [lib(), lib(operator="mustBeLessThan", value=5)]
    assert find_quality_rule_problems(rules, FIELDS) == [
        "quality rule 2: email already has a nullValues rule;"
        " datacontract-cli 1.2.9 cannot run two"
    ]

def test_same_metric_on_another_column_and_text_rules_are_accepted():
    rules = [lib(), lib(column="id"), txt(column="email"), txt(column="email")]
    assert find_quality_rule_problems(rules, FIELDS) == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_quality_rules.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'backend.domain.quality_rules'`.

- [ ] **Step 3: Implement `find_quality_rule_problems` in `backend/domain/quality_rules.py`**

Check in this order, keeping only the first problem of each rule:
1. enum membership: `type`, `dimension` (null allowed), `metric`, `operator`, `unit`
2. the text rule shape: non-blank description, null metric, operator, value and unit, empty `valid_values`
3. the library rule shape: `value` is an `int` or `float` and not a `bool`, and is not negative; `percent` is at most 100; column presence per metric; `percent` only with `PERCENT_METRICS`; `valid_values` is non-empty exactly when the metric is `invalidValues`
4. a non-empty column is a declared field
5. `valid_values` casts with `{"integer": int, "float": float, "date": date.fromisoformat, "timestamp": datetime.fromisoformat}`, keyed by the field's `type`

Then add collision messages for library rules whose `(metric, column)` was already seen. An empty column reads `the table`, as in `the table already has a rowCount rule`. Split the checks into private helpers so that each function stays at complexity 15 or less.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_quality_rules.py -q` and `.venv\Scripts\ruff.exe check backend`
Expected: all pass. Ruff prints `All checks passed!`

- [ ] **Step 5: Commit**

```bash
git add backend/domain/quality_rules.py tests/quality_rule_builders.py tests/unit/test_quality_rules.py
git commit -m "feat(contracts): decide which quality rules datacontract-cli can run"
```

### Task 2: Map one rule and the service levels to and from ODCS

**Files:**
- Create: `backend/use_cases/data_contract/odcs_quality.py`
- Test: `tests/unit/use_cases/data_contract/test_odcs_quality.py`

**Interfaces:**
- Consumes: `QUALITY_OPERATORS` (Task 1).
- Produces (raises plain `ValueError`, and Task 3 wraps it into `OdcsParseError`. The module must not import `odcs.py`, because `odcs.py` imports it):

```python
def rule_to_odcs(rule: dict[str, Any]) -> dict[str, Any]: ...
def rule_from_odcs(item: dict[str, Any], column: str) -> dict[str, Any]: ...
def sla_to_odcs(servicelevels: dict[str, Any]) -> list[dict[str, Any]]: ...
def sla_from_odcs(items: list[dict[str, Any]]) -> dict[str, Any]: ...
```

Mapping:
- `rule_to_odcs` writes keys in this order: `type`; `dimension` (omitted when null); for a library rule, `metric`, then `<operator>: value`, then `unit` (omitted when null), then `arguments: {"validValues": [...]}` (only for `invalidValues`); and `description` (omitted when empty).
- `rule_from_odcs` accepts only `type`, `dimension`, `metric`, `unit`, `arguments`, `description` and the six operators, and raises naming any other key.
  - A missing `type` means `library` when `metric` is present, otherwise `text`. `type: sql` or `type: custom` raises `quality type '<t>' is not supported`.
  - A library rule needs exactly one operator (`needs exactly one operator`).
  - `arguments` may hold only `validValues`, and each value becomes `str(v)`. A `None` raises.
  - It always returns all nine keys.
- `sla_to_odcs` writes one `{"property", "value", "unit"}` entry per property, with `unit` omitted when null.
- `sla_from_odcs` accepts only `property`, `value` and `unit`.
  - A `None` value raises `slaProperties entry <property> has no storable value`, Plan 1's message, which Plan 1's `test_parse_errors` still pins. A missing `property` raises `KeyError`, which Plan 1's wrapper in `from_odcs` reports as `malformed ODCS document`.
  - An `int` or `float` that is not a `bool` is kept. Anything else becomes `str(value)`, because YAML parses an unquoted timestamp into a `datetime` that `json.dumps` cannot store.
  - Unit aliases: `{"percent": "%", "m": "min"}`.

- [ ] **Step 1: Write the failing tests**

```python
VALIDATOR = jsonschema.Draft201909Validator(json.loads(
    (Path(__file__).parents[3] / "fixtures/odcs/odcs-json-schema-v3.2.0.json").read_text(encoding="utf-8")))

def _doc(property_rules=(), schema_rules=(), sla=()):  # minimal valid ODCS around the items
    doc = {"apiVersion": "v3.2.0", "kind": "DataContract", "id": "11111111-1111-4111-8111-111111111111",
           "name": "t", "version": "1.0.0", "status": "active",
           "schema": [{"name": "t", "logicalType": "object", "physicalType": "table",
                       "quality": list(schema_rules),
                       "properties": [{"name": "email", "logicalType": "string", "quality": list(property_rules)}]}]}
    if sla:
        doc["slaProperties"] = list(sla)
    return doc

def test_null_values_rule_is_valid_odcs():
    item = rule_to_odcs(library_rule(operator="mustBeLessOrEqualTo", value=1, unit="percent"))
    assert item == {"type": "library", "dimension": "completeness", "metric": "nullValues",
                    "mustBeLessOrEqualTo": 1, "unit": "percent"}
    assert list(VALIDATOR.iter_errors(_doc([item]))) == []

def test_invalid_values_carry_valid_values_as_arguments():
    item = rule_to_odcs(library_rule(metric="invalidValues", valid_values=["open", "paid"]))
    assert item["arguments"] == {"validValues": ["open", "paid"]}

def test_text_rule_has_no_metric_keys():
    assert rule_to_odcs(text_rule()) == {"type": "text", "dimension": "consistency",
                                         "description": "Totals reconcile with the ledger."}

ROUND_TRIP = [
    library_rule(metric=m, operator=op, unit=u, column="" if m == "rowCount" else "email",
                 valid_values=["a"] if m == "invalidValues" else [])
    for m in QUALITY_METRICS for op in QUALITY_OPERATORS
    for u in ("rows", None, *(("percent",) if m in PERCENT_METRICS else ()))
] + [text_rule(), text_rule(column="email", dimension=None)]

@pytest.mark.parametrize("rule", ROUND_TRIP)
def test_rule_round_trip(rule):
    assert rule_from_odcs(rule_to_odcs(rule), rule["column"]) == rule

def test_type_defaults_follow_odcs():
    assert rule_from_odcs({"metric": "nullValues", "mustBe": 0}, "email")["type"] == "library"
    assert rule_from_odcs({"description": "x"}, "")["type"] == "text"

@pytest.mark.parametrize(("item", "fragment"), [
    ({"type": "sql", "query": "SELECT 1", "mustBe": 0}, "sql"),
    ({"type": "custom", "engine": "soda"}, "custom"),
    ({"metric": "rowCount", "mustBeBetween": [1, 2]}, "mustBeBetween"),
    ({"metric": "rowCount", "mustBeGreaterThan": 0, "mustBeLessThan": 9}, "exactly one operator"),
    ({"metric": "rowCount"}, "exactly one operator"),
    ({"metric": "invalidValues", "mustBe": 0, "arguments": {"pattern": "^a"}}, "pattern"),
    ({"metric": "missingValues", "mustBe": 0, "arguments": {"missingValues": ["N/A"]}}, "missingValues"),
    # from_odcs strips a Plan 1 text rule's dmplt* properties before calling this (Task 9).
    ({"type": "text", "description": "x",
      "customProperties": [{"property": "dmpltOperator", "value": ">="}]}, "customProperties"),
    ({"metric": "nullValues", "mustBe": 0, "severity": "error"}, "severity"),
])
def test_rule_from_odcs_refuses_what_it_cannot_store(item, fragment):
    with pytest.raises(ValueError, match=fragment):
        rule_from_odcs(item, "email")

def test_sla_round_trip_is_valid_odcs():
    sl = {"properties": [{"property": "freshness", "value": 24, "unit": "h"},
                         {"property": "availability", "value": 99.9, "unit": "%"},
                         {"property": "retention", "value": "P1D", "unit": None}]}
    items = sla_to_odcs(sl)
    assert items[2] == {"property": "retention", "value": "P1D"}
    assert list(VALIDATOR.iter_errors(_doc(sla=items))) == []
    assert sla_from_odcs(items) == sl

def test_sla_from_odcs_normalises_units_and_scalars():
    parsed = sla_from_odcs([
        {"property": "availability", "value": 99, "unit": "percent"},
        {"property": "latency", "value": 30, "unit": "m"},
        {"property": "generalAvailability", "value": datetime(2022, 5, 12, 9, 30, tzinfo=timezone.utc)},
    ])
    assert [p["unit"] for p in parsed["properties"]] == ["%", "min", None]
    assert isinstance(parsed["properties"][2]["value"], str)
    json.dumps(parsed)

@pytest.mark.parametrize("item", [{"property": "latency", "value": None},
                                  {"property": "latency", "value": 4, "element": "t.c"}])
def test_sla_from_odcs_refuses_what_it_cannot_store(item):
    with pytest.raises(ValueError):
        sla_from_odcs([item])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/use_cases/data_contract/test_odcs_quality.py -q`
Expected: `ModuleNotFoundError: No module named 'backend.use_cases.data_contract.odcs_quality'`.

- [ ] **Step 3: Implement the four functions in `backend/use_cases/data_contract/odcs_quality.py`** as listed under Mapping.

- [ ] **Step 4: Run the tests to verify they pass**

Run: the same pytest command, then `.venv\Scripts\ruff.exe check backend`
Expected: all pass, and ruff is clean.

- [ ] **Step 5: Commit**

```bash
git add backend/use_cases/data_contract/odcs_quality.py tests/unit/use_cases/data_contract/test_odcs_quality.py
git commit -m "feat(contracts): map library quality rules and SLA properties to ODCS"
```

### Task 3: Emit and parse the new shape in `to_odcs`, `from_odcs` and sync

**Files:**
- Modify: `backend/use_cases/data_contract/odcs.py` (only the quality and SLA code paths, and the key-set constants)
- Test: `tests/unit/use_cases/data_contract/test_odcs_quality_contract.py`
- Test: `tests/unit/use_cases/data_contract/test_sync_from_github.py` (add tests)
- Modify: Plan 1's `tests/fixtures/odcs/sample_contract.py` and `tests/unit/use_cases/data_contract/test_odcs_parse.py` (Step 4)

**Interfaces:**
- Consumes: Task 2's four functions, Task 1's `find_quality_rule_problems` and `QUALITY_OPERATORS`, and Plan 1's `to_odcs`, `from_odcs`, `OdcsParseError`, `ParsedContract`, `_reject_unknown`, `_RULE_KEYS`, `_RULE_CUSTOM_KEYS` and `_SLA_ENTRY_KEYS`.
- Produces: `to_odcs` emits a new-shape rule (`"type" in rule`) through `rule_to_odcs`, and new-shape service levels (`"properties" in servicelevels`) through `sla_to_odcs`. Old shapes still go through Plan 1's code until Task 9. `from_odcs` returns new-shape rules and service levels, and raises `OdcsParseError` for anything Task 1 or Task 2 rejects. Rules come back in document order: each property's rules in property order, then the schema object's rules.

- [ ] **Step 1: Find the code paths to change**

Run: `grep -n "dmplt\|slaProperties\|quality\|servicelevels" backend/use_cases/data_contract/odcs.py`
Expected: Plan 1's per-rule emit and parse code, the property-versus-schema placement, and the SLA emit and parse code. Change nothing else in the file.

- [ ] **Step 2: Write the failing tests**

Add `orders_contract() -> DataContract` to `tests/quality_rule_builders.py`. It returns a fresh instance on every call, so tests can change `.models` freely, and Task 4 and Task 9 use it too. Build its fields with `SchemaField(name=..., type=...).model_dump()`, so that Plan 3's field attributes come with their defaults. Fields: `order_id` (integer, `nullable=False`, `primary_key=True`), `customer_id` (string), `status` (string), `amount` (float). Rules:
- `rowCount mustBeGreaterOrEqualTo 5 rows`, schema level
- `duplicateValues mustBe 0 rows` on `order_id`
- `nullValues mustBeLessOrEqualTo 1 percent` on `customer_id`
- `invalidValues mustBe 0 rows` on `status`, with `["open", "paid", "shipped"]`
- `nullValues mustBe 0 rows` on `amount`
- a schema-level text rule

Title `Customer Orders` (schema name `customer_orders`), tier 2, status `active`. `servicelevels`: freshness 24 h, availability 99.9 %, retention 1 y, latency 30 min.

```python
def test_emitted_contract_is_valid_odcs_without_custom_properties():
    doc = to_odcs(orders_contract())
    assert list(VALIDATOR.iter_errors(doc)) == []
    props = {p["name"]: p for p in doc["schema"][0]["properties"]}
    assert props["customer_id"]["quality"] == [{"type": "library", "dimension": "completeness",
        "metric": "nullValues", "mustBeLessOrEqualTo": 1, "unit": "percent"}]
    assert [q["metric"] for q in doc["schema"][0]["quality"] if q["type"] == "library"] == ["rowCount"]
    assert doc["slaProperties"][3] == {"property": "latency", "value": 30, "unit": "min"}
    assert "dmplt" not in json.dumps(doc)

def test_round_trip_returns_the_same_rules_and_service_levels():
    contract = orders_contract()
    parsed = from_odcs(to_odcs(contract))
    key = lambda r: json.dumps(r, sort_keys=True)
    assert sorted(parsed.models["quality"], key=key) == sorted(contract.models["quality"], key=key)
    assert parsed.servicelevels == contract.servicelevels

@pytest.mark.parametrize(("mutate", "fragment"), [
    (lambda d: d["schema"][0]["properties"][0]["quality"].append({"metric": "rowCount", "mustBeBetween": [1, 2]}), "mustBeBetween"),
    (lambda d: d["schema"][0]["quality"].append({"metric": "nullValues", "mustBe": 0}), "needs a column"),
    (lambda d: d["slaProperties"].append({"property": "latency", "value": 1, "unit": "h", "driver": "analytics"}), "driver"),
])
def test_from_odcs_refuses_what_the_platform_cannot_store(mutate, fragment):
    doc = to_odcs(orders_contract())
    mutate(doc)
    with pytest.raises(OdcsParseError, match=fragment):
        from_odcs(doc)

def test_old_shape_still_emits_until_contraction():  # deleted in Task 9
    old = orders_contract()
    old.models = {**old.models, "quality": [{"dimension": "completeness", "column": "customer_id",
                  "operator": ">=", "threshold": "99%", "description": ""}]}
    old.servicelevels = {"freshness": "24h", "availability": "", "retention": "", "latency": ""}
    assert list(VALIDATOR.iter_errors(to_odcs(old))) == []
```

In `test_sync_from_github.py`, using the module's `use_case`, `github` and `repo` fixtures:
- `test_sync_stores_library_rules_and_structured_sla`: feed `yaml.safe_dump(to_odcs(orders_contract()))`, then assert `repo.upsert.call_args.kwargs["servicelevels"] == orders_contract().servicelevels` and that the stored `quality` holds the five library rules and the text rule.
- `test_sync_reports_unsupported_rule_and_keeps_row`: add `mustBeBetween` to a property's rules, then assert `result["errors"][0]["error"]` contains `mustBeBetween` and `repo.upsert.assert_not_called()`.

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/use_cases/data_contract -q`
Expected: the new tests fail (Plan 1 still emits `type: text` with `dmplt*` custom properties), and Plan 1's existing tests pass.

- [ ] **Step 4: Change `odcs.py`**

- `to_odcs`: keep Plan 1's placement, where a rule whose column names a field sits under that property and any other rule sits on the schema object. Convert each rule with `rule_to_odcs(rule) if "type" in rule else <Plan 1's converter>(rule)`. Convert service levels with `sla_to_odcs(sl) if "properties" in sl else <Plan 1's SLA code>`, and keep Plan 1's choice of emitting or omitting an empty `slaProperties`.
- `from_odcs`: an item whose `customProperties` holds a `property` starting with `dmplt` still goes through Plan 1's reader (temporary, so Plan 1's rule round trips keep their order by `dmpltPosition`). Every other item goes through `rule_from_odcs(item, column)`, with `column` set to the property name or `""`, in document order: each property's rules in property order, then the schema object's. `slaProperties` goes through `sla_from_odcs(doc.get("slaProperties") or [])`, so a document without it gives `{"properties": []}`. Then call `find_quality_rule_problems` on the rules having a `type` key and the parsed `models["fields"]`, and raise `OdcsParseError("; ".join(problems))` when the list is non-empty. Turn each `ValueError` from Task 2 into `raise OdcsParseError(str(exc)) from exc`.
- Key sets (spec decision 5). Extend `_RULE_KEYS` with `metric`, `unit`, `arguments` and the six names in `QUALITY_OPERATORS`; Plan 1's `customProperties` stays in it for spec decision 6. `_RULE_CUSTOM_KEYS` keeps Plan 1's five `dmplt*` keys and now means the custom properties a Plan 1 text rule may carry: nothing is added, because this plan writes no custom property. `_SLA_ENTRY_KEYS` already equals the three keys `sla_from_odcs` accepts, so nothing is added either. `from_odcs` checks every rule item against `_RULE_KEYS` and every SLA entry against `_SLA_ENTRY_KEYS` with Plan 1's `_reject_unknown` before calling Task 2's functions, so these constants stay the one list a later plan extends. `rule_from_odcs` and `sla_from_odcs` keep their own checks, because Task 2's tests call them directly.
- Plan 1's tests of the old parse output. `from_odcs` now returns new-shape service levels for every document, so in the same step:
  - `tests/fixtures/odcs/sample_contract.py`: `make_contract`'s default `servicelevels` becomes `{"properties": []}`, and `sample_contract()`'s becomes `{"properties": [{"property": "freshness", "value": 24, "unit": "h"}, {"property": "availability", "value": 99.9, "unit": "%"}, {"property": "retention", "value": "one year", "unit": None}]}`. `sla_to_odcs` emits exactly the `slaProperties` already in `EXPECTED_YAML`, so that constant does not change. Its rules stay in the old shape until Task 9.
  - `test_odcs_parse.py`: delete `test_round_trip_sla_value`, `test_sla_unit_aliases_are_read`, `test_sla_key_outside_the_four_is_kept`, the `value: True` case of `test_parse_errors` (Task 2 stores it as the string `"True"`), and `test_rule_outside_the_stored_format_is_rejected` (both rules are now accepted, or rejected with Task 1's message). Task 2's tests cover these inputs in the new shape. The `None`, `driver` and `malformed` cases keep passing.
  - `test_odcs_emit.py` keeps its old-shape SLA tests until Task 9: `to_odcs` still emits that shape.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/ -q` and `.venv\Scripts\ruff.exe check backend`
Expected: all pass, Plan 1's tests included.

- [ ] **Step 6: Commit**

```bash
git add backend/use_cases/data_contract/odcs.py tests/unit/use_cases/data_contract tests/fixtures/odcs/sample_contract.py tests/quality_rule_builders.py
git commit -m "feat(contracts): emit and parse ODCS library rules and structured SLA"
```

### Task 4: Prove the emitted rules execute

**Files:**
- Create: `tests/fixtures/odcs/orders/pass/orders.csv`
- Create: `tests/fixtures/odcs/orders/fail/orders.csv`
- Create: `tests/integration/__init__.py` (empty)
- Create: `tests/integration/test_contract_execution.py`

**Interfaces:**
- Consumes: `to_odcs` (Task 3), `orders_contract()` (Task 3, in `tests/quality_rule_builders.py`), `QUALITY_METRICS`, `QUALITY_UNITS`, `PERCENT_METRICS` and `find_quality_rule_problems` (Task 1), and `empty_server` and `server_problems` from Plan 3's `backend/domain/contract_metadata.py`.
- Produces: nothing used by later tasks. CI runs it in the existing `test` job, where `astral-sh/setup-uv` puts `uvx` on `PATH`.

The server comes from the platform (spec decision 7): the test stores a `local` row in `contract.servers` through Plan 3's keys, checks that `server_problems` accepts it, and lets `to_odcs` emit it. Nothing is added to the ODCS document by hand. Every verdict, lint included, comes from the JSON report's `result` (spec decision 2).

- [ ] **Step 1: Add the fixtures (the exact data used in Verified Tool Behaviour)**

`pass/orders.csv`:

```
order_id,customer_id,status,amount
1,c1,open,10.5
2,c2,paid,20.0
3,c3,open,30.0
4,c4,paid,40.0
5,c5,shipped,50.0
6,c6,paid,60.0
7,c7,open,70.0
8,c8,paid,80.0
9,c9,shipped,90.0
10,c10,open,100.0
```

`fail/orders.csv`:

```
order_id,customer_id,status,amount
1,c1,open,10.5
1,,paid,20.0
3,,BOGUS,30.0
3,,WRONG,40.0
```

- [ ] **Step 2: Write the tests**

```python
CLI = ["uvx", "--from", "datacontract-cli[csv]==1.2.9", "datacontract"]
FIXTURES = Path(__file__).parents[1] / "fixtures/odcs/orders"
pytestmark = pytest.mark.skipif(shutil.which("uvx") is None, reason="uvx is not installed")

def _on_local_server(data):  # a server row stored through Plan 3's keys, emitted by to_odcs
    contract = orders_contract()
    contract.servers = [{**empty_server(), "server": "local", "type": "local",
                         "path": (FIXTURES / data / "orders.csv").as_posix(), "format": "csv"}]
    return contract

def _cli(tmp_path, command, doc):
    path = tmp_path / "contract.odcs.yaml"
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    args = [*CLI, command, str(path), "--output", str(tmp_path / "result.json"),
            "--output-format", "json"]
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", timeout=600,
                          env={**os.environ, "PYTHONUTF8": "1"})

def _report(tmp_path):
    return json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))

def _quality_checks(tmp_path):
    result = _report(tmp_path)
    return result["result"], {(c["type"], c["field"]): c for c in result["checks"]
                              if c["category"] == "quality"}

def test_lint_accepts_the_emitted_contract_without_warnings(tmp_path):
    contract = _on_local_server("pass")
    assert server_problems(contract.servers[0]) == []
    doc = to_odcs(contract)
    assert doc["servers"][0]["type"] == "local"
    proc = _cli(tmp_path, "lint", doc)
    assert _report(tmp_path)["result"] == "passed", proc.stdout

def test_rules_pass_on_good_data(tmp_path):
    proc = _cli(tmp_path, "test", to_odcs(_on_local_server("pass")))
    overall, checks = _quality_checks(tmp_path)
    assert proc.returncode == 0, proc.stdout
    assert overall == "passed"
    assert {k: c["result"] for k, c in checks.items()} == {
        ("row_count", None): "passed", ("field_duplicate_values", "order_id"): "passed",
        ("field_null_values", "customer_id"): "passed", ("field_invalid_values", "status"): "passed",
        ("field_null_values", "amount"): "passed"}

def test_rules_fail_on_bad_data(tmp_path):
    proc = _cli(tmp_path, "test", to_odcs(_on_local_server("fail")))
    overall, checks = _quality_checks(tmp_path)
    assert proc.returncode == 1
    assert overall == "failed"
    assert "was 4, expected >= 5" in checks[("row_count", None)]["reason"]
    assert "75.0% (3 of 4 rows)" in checks[("field_null_values", "customer_id")]["reason"]
    assert "was 2, expected = 0" in checks[("field_duplicate_values", "order_id")]["reason"]
    assert "was 2, expected = 0" in checks[("field_invalid_values", "status")]["reason"]
    assert checks[("field_null_values", "amount")]["result"] == "passed"

def test_every_unit_the_api_accepts_is_executed(tmp_path):
    allowed = {(m, u) for m in QUALITY_METRICS for u in QUALITY_UNITS
               if u == "rows" or m in PERCENT_METRICS}
    rules = [
        library_rule(metric="nullValues", column="customer_id"),
        library_rule(metric="nullValues", column="amount", unit="percent"),
        library_rule(metric="missingValues", column="customer_id"),
        library_rule(metric="missingValues", column="amount", unit="percent"),
        library_rule(metric="invalidValues", column="status", valid_values=["open", "paid", "shipped"]),
        library_rule(metric="invalidValues", column="order_id", unit="percent",
                     valid_values=[str(i) for i in range(1, 11)]),
        library_rule(metric="duplicateValues", column="order_id"),
        library_rule(metric="rowCount", column="", operator="mustBeGreaterThan"),
    ]
    assert {(r["metric"], r["unit"]) for r in rules} == allowed
    contract = _on_local_server("pass")
    contract.models = {**contract.models, "quality": rules}
    assert find_quality_rule_problems(rules, contract.models["fields"]) == []
    _cli(tmp_path, "test", to_odcs(contract))
    _, checks = _quality_checks(tmp_path)
    assert len(checks) == len(rules)
    assert all(c["result"] in ("passed", "failed") for c in checks.values())
```

- [ ] **Step 3: Run the tests**

Run: `.venv\Scripts\python.exe -m pytest tests/integration/test_contract_execution.py -v`
Expected: 4 passed. The first run downloads about 60 MB into the uv cache.

- [ ] **Step 4: Check that the proof can fail**

Temporarily change the `customer_id` rule's unit in `orders_contract()` to `rows`, then run `test_rules_fail_on_bad_data`.
Expected: FAIL on the `75.0%` assertion. Restore the unit.

- [ ] **Step 5: Commit**

```bash
git add tests/integration tests/fixtures/odcs/orders
git commit -m "test(contracts): prove emitted ODCS rules run under datacontract test"
```

### Task 5: API schemas accept the new shape (expand)

**Files:**
- Modify: `backend/interface/schemas/data_contract.py`
- Test: `tests/unit/test_data_contract_schemas.py`
- Test: `tests/unit/interface/test_routers.py`

**Interfaces:**
- Consumes: `find_quality_rule_problems` (Task 1).
- Produces:

```python
class QualityRule(BaseModel):            # model_config = ConfigDict(extra="forbid")
    type: Literal["library", "text"]
    dimension: Literal["accuracy", "completeness", "conformity", "consistency",
                       "coverage", "timeliness", "uniqueness"] | None = None
    column: str = ""
    metric: Literal["nullValues", "missingValues", "invalidValues",
                    "duplicateValues", "rowCount"] | None = None
    operator: Literal["mustBe", "mustNotBe", "mustBeGreaterThan", "mustBeGreaterOrEqualTo",
                      "mustBeLessThan", "mustBeLessOrEqualTo"] | None = None
    value: int | float | None = None
    unit: Literal["rows", "percent"] | None = None
    valid_values: list[str] = []
    description: str = ""

class ServiceLevelProperty(BaseModel):   # extra="forbid"; a str value must not be blank
    property: str = Field(min_length=1)
    value: int | float | str
    unit: str | None = None

class ServiceLevels(BaseModel):          # extra="forbid"
    properties: list[ServiceLevelProperty] = []

class LegacyQualityRule(BaseModel): ...    # today's QualityRule, renamed; deleted in Task 9
class LegacyServiceLevels(BaseModel): ...  # today's ServiceLevels, renamed; deleted in Task 9

class ModelsSection(BaseModel):
    fields: list[SchemaField] = []
    quality: list[QualityRule | LegacyQualityRule] = []
    # model_validator(mode="after"): find_quality_rule_problems on the QualityRule items
    # and fields; raise ValueError("; ".join(problems))
```

`DataContractCreateModel.servicelevels: ServiceLevels | LegacyServiceLevels = Field(default_factory=ServiceLevels)`. `DataContractUpdateModel.servicelevels: ServiceLevels | LegacyServiceLevels | None = None`.

- [ ] **Step 1: Write the failing tests**

```python
def test_new_rule_and_service_levels_are_accepted():
    m = DataContractCreateModel(title="x", owner="o", domain_id=DOMAIN_ID, tier=2,
        models={"fields": [{"name": "email", "type": "string"}],
                "quality": [library_rule(unit="percent", operator="mustBeLessOrEqualTo", value=1)]},
        servicelevels={"properties": [{"property": "freshness", "value": 24, "unit": "h"}]})
    assert m.models.model_dump()["quality"][0]["metric"] == "nullValues"
    assert m.servicelevels.model_dump() == {"properties": [{"property": "freshness", "value": 24, "unit": "h"}]}

def test_unrunnable_rule_is_rejected_with_its_reason():
    with pytest.raises(ValidationError, match="percent"):
        ModelsSection(fields=[{"name": "id", "type": "integer"}],
                      quality=[library_rule(metric="duplicateValues", column="id", unit="percent")])

def test_service_levels_forbid_unknown_keys():
    with pytest.raises(ValidationError):
        ServiceLevels.model_validate({"properties": [], "freshness": "24h"})

def test_blank_service_level_value_is_rejected():
    with pytest.raises(ValidationError):
        ServiceLevels.model_validate({"properties": [{"property": "freshness", "value": " "}]})

def test_old_shapes_are_still_accepted_until_contraction():  # deleted in Task 9
    m = DataContractCreateModel(title="x", owner="o", domain_id=DOMAIN_ID, tier=2,
        servicelevels={"freshness": "24h", "availability": "", "retention": "", "latency": ""})
    assert isinstance(m.servicelevels, LegacyServiceLevels)
```

In `test_routers.py`, mirroring `test_create_data_contract`:
- `test_create_with_library_rule_and_structured_sla`: assert 201 and `mock_uc.execute.call_args.kwargs["servicelevels"] == {"properties": [{"property": "freshness", "value": 24, "unit": "h"}]}`.
- `test_create_rejects_two_rules_on_same_metric_and_column`: assert 422 and `"cannot run two" in resp.text`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_data_contract_schemas.py tests/unit/interface/test_routers.py -q`
Expected: the new tests fail. The existing tests pass.

- [ ] **Step 3: Implement the models in `backend/interface/schemas/data_contract.py`** as listed under Interfaces.

- [ ] **Step 4: Run all backend tests**

Run: `.venv\Scripts\python.exe -m pytest tests/ -q` and `.venv\Scripts\ruff.exe check backend`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/interface/schemas/data_contract.py tests/unit/test_data_contract_schemas.py tests/unit/interface/test_routers.py
git commit -m "feat(api): accept ODCS library quality rules and structured service levels"
```

### Task 6: Quality rules editor and detail card

**Files:**
- Modify: `frontend/src/types/index.ts` (the rule types only)
- Modify: `frontend/src/pages/DataContracts/QualityRules.tsx`
- Modify: `frontend/src/pages/DataContracts/DataContractForm.tsx` (`QualitySection`, `validateFormArrays`)
- Modify: `frontend/src/pages/DataContracts/DataContractDetail.tsx` (`QualityRulesCard`)
- Modify: `frontend/src/hooks/useDataContracts.ts` (`useDataContract`)
- Create: `frontend/src/lib/qualityRules.ts` and `frontend/src/lib/qualityRules.test.ts`
- Create: `frontend/src/lib/contractFormat.ts` and `frontend/src/lib/contractFormat.test.ts`
- Test: `frontend/src/pages/DataContracts/QualityRules.test.tsx`
- Test: `frontend/src/pages/DataContracts/DataContractForm.test.tsx`
- Test: `frontend/src/pages/DataContracts/DataContractDetail.test.tsx`

**Interfaces:**
- Consumes: the API shape from Task 5.
- Produces:

```ts
// types/index.ts
export type QualityDimension = 'accuracy' | 'completeness' | 'conformity' | 'consistency' | 'coverage' | 'timeliness' | 'uniqueness'
export type QualityMetric = 'nullValues' | 'missingValues' | 'invalidValues' | 'duplicateValues' | 'rowCount'
export type QualityOperator = 'mustBe' | 'mustNotBe' | 'mustBeGreaterThan' | 'mustBeGreaterOrEqualTo' | 'mustBeLessThan' | 'mustBeLessOrEqualTo'
export interface QualityRule {
  type: 'library' | 'text'; dimension: QualityDimension | null; column: string
  metric: QualityMetric | null; operator: QualityOperator | null; value: number | null
  unit: 'rows' | 'percent' | null; valid_values: string[]; description: string
}
// lib/qualityRules.ts
export const DIMENSIONS: readonly QualityDimension[]
export const METRICS: readonly QualityMetric[]
export const OPERATORS: readonly QualityOperator[]
export const PERCENT_METRICS: readonly QualityMetric[]
export function emptyRule(): QualityRule      // library, completeness, '', nullValues, mustBe, 0, rows, [], ''
export function withMetric(rule: QualityRule, metric: QualityMetric): QualityRule
export function withType(rule: QualityRule, type: QualityRule['type']): QualityRule
export function qualityProblem(rules: QualityRule[], fieldNames: string[]): string | null
export function describeCheck(rule: QualityRule): string
// lib/contractFormat.ts (temporary, deleted in Task 9)
export function normalizeContract(raw: DataContract): DataContract
// QualityRules.tsx
interface QualityRulesProps { rules: QualityRule[]; fieldNames: string[]; onChange: (rules: QualityRule[]) => void }
```

Behaviour:
- `withMetric` sets the metric. `rowCount` clears `column`. A `percent` unit falls back to `rows` when the metric is not in `PERCENT_METRICS`. Any metric other than `invalidValues` clears `valid_values`.
- `withType('text')` nulls `metric`, `operator`, `value` and `unit` and clears `valid_values`. `withType('library')` takes those four from `emptyRule()` and keeps `dimension`, `column` and `description`.
- `qualityProblem` mirrors Task 1's structural checks, without the cast check, which the API reports. It returns the first problem as `Rule <n>: <message>`. The messages these tests pin: `column '<c>' is not a schema field`, `<column> already has a <metric> rule`, `invalidValues needs valid values`, `a text rule needs a description`.
- `describeCheck` uses the symbols `=`, `≠`, `>`, `≥`, `<` and `≤`: `nullValues ≤ 1 percent`, `invalidValues = 0 rows (valid: open, paid)`, `rowCount ≥ 5` (no unit when null), and `—` for a text rule.
- `normalizeContract` turns each rule without a `type` key into a text rule. Its dimension maps `freshness→timeliness`, `validity→conformity`, `integrity→consistency` and keeps `completeness` and `uniqueness`. Its column is `''`. Its description is `` `${old.description} [legacy rule: dimension=… column=… operator=… threshold=…]`.trim() ``. `useDataContract` passes it as `select`.
- The editor inputs carry `aria-label`s `Rule type`, `Dimension`, `Metric`, `Column`, `Operator`, `Value`, `Unit`, `Valid values` and `Description`.
  - Metric, Operator, Value, Unit and Valid values appear only for a library rule, and Valid values only for `invalidValues`.
  - Column is a `<select>` with an empty option plus `fieldNames`, and also the rule's current column when it is not among them, so a dangling value stays visible.
  - The Unit select disables `percent` outside `PERCENT_METRICS`.
  - The valid values input is uncontrolled (`defaultValue={rule.valid_values.join(', ')}`) and commits `split(',').map(trim).filter(Boolean)` on blur.
- `QualitySection` passes `fieldNames={fields.map((f) => f.name)}`. `validateFormArrays` sets the quality error to `qualityProblem(quality, fieldNames)` when the tier shows quality.
- The detail card's columns are Type, Dimension, Column, Check (from `describeCheck`) and Description.

- [ ] **Step 1: Write the failing tests**

```ts
// qualityRules.test.ts
it('clears the column when the metric becomes rowCount', () =>
  expect(withMetric({ ...emptyRule(), column: 'email' }, 'rowCount').column).toBe(''))
it('falls back to rows when percent cannot run', () =>
  expect(withMetric({ ...emptyRule(), unit: 'percent' }, 'duplicateValues').unit).toBe('rows'))
it('drops valid values when the metric is not invalidValues', () =>
  expect(withMetric({ ...emptyRule(), metric: 'invalidValues', valid_values: ['a'] }, 'nullValues').valid_values).toEqual([]))
it('reports a rule whose column is no longer a field', () =>
  expect(qualityProblem([{ ...emptyRule(), column: 'mail' }], ['email'])).toBe("Rule 1: column 'mail' is not a schema field"))
it('reports the second rule on the same metric and column', () =>
  expect(qualityProblem([{ ...emptyRule(), column: 'email' }, { ...emptyRule(), column: 'email' }], ['email']))
    .toBe('Rule 2: email already has a nullValues rule'))
it('requires valid values for invalidValues', () =>
  expect(qualityProblem([{ ...emptyRule(), column: 'email', metric: 'invalidValues' }], ['email']))
    .toBe('Rule 1: invalidValues needs valid values'))
it('requires a description on a text rule', () =>
  expect(qualityProblem([withType(emptyRule(), 'text')], [])).toBe('Rule 1: a text rule needs a description'))
it('describes a check', () =>
  expect(describeCheck({ ...emptyRule(), operator: 'mustBeLessOrEqualTo', value: 1, unit: 'percent' }))
    .toBe('nullValues ≤ 1 percent'))
// contractFormat.test.ts
it('shows an old rule as a text rule that keeps its values', () => { /* old completeness >= 99% →
  type 'text', dimension 'completeness', description containing '[legacy rule: dimension=completeness' */ })
// QualityRules.test.tsx (one rule, so getByLabelText is unique)
it('offers only schema fields as columns')            // Column options: '', 'email', 'id'
it('keeps a typed comma in valid values until blur')  // change → 'open,' stays; blur → onChange valid_values ['open']
it('shows the stale column of a rule whose field was removed') // column 'mail', fieldNames ['email'] → select value 'mail'
it('hides metric inputs for a text rule')             // queryByLabelText('Metric') is null
// DataContractForm.test.tsx (created by Plan 3 Task 6: reuse its vi.mock of useAllDomains and useAuth,
// its `contract` fixture and renderForm(value); add a getDomainAccess mock only if the form needs one)
it('blocks saving a rule whose column was removed')   // renderForm({ ...contract, tier: 3, ... }) (no required SLA), rule column 'gone'
                                                      // → click 'Save Changes' → findByText("Rule 1: column 'gone' is not a schema field"); onSubmit not called
// DataContractDetail.test.tsx (created by Plan 3 Task 7: reuse its hook vi.mock, `base` and renderDetail(contract))
it('lists library and text rules')                    // 'nullValues ≤ 1 percent' and the text rule's description
```

Contract fixtures include Plan 3's fields with their empty defaults (`description: { purpose: '', usage: '', limitations: '' }, team_members: [], support: [], servers: []`). Plan 3's `contract` and `base` fixtures already have them. In Task 7, change the typed `contract` fixture in `DataContractForm.test.tsx` to `servicelevels: { properties: [] }`: `npm run build` runs `tsc` over all of `src`, tests included, so the old shape stops compiling once `DataContract.servicelevels` changes.

- [ ] **Step 2: Run the tests to verify they fail**

Run, from `frontend/`: `npm test`
Expected: the new suites fail (missing module or old behaviour). The existing suites pass.

- [ ] **Step 3: Implement**, as listed under Behaviour.

- [ ] **Step 4: Verify**

Run, from `frontend/`: `npm test`, `npm run lint`, `npm run build`
Expected: all pass. Lint reports no warnings, and `tsc` compiles.

- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat(ui): edit and show ODCS library quality rules"
```

### Task 7: Service level inputs and card

**Files:**
- Modify: `frontend/src/types/index.ts` (`DataContract.servicelevels`, `DataContractInput.servicelevels`)
- Modify: `frontend/src/pages/DataContracts/DataContractForm.tsx` (`schema`, `normalizeDefaults`, `ServiceLevelsSection`, `handleFormSubmit`)
- Modify: `frontend/src/pages/DataContracts/DataContractDetail.tsx` (`ServiceLevelsCard`)
- Modify: `frontend/src/lib/contractFormat.ts` and its test (add the SLA)
- Create: `frontend/src/lib/serviceLevels.ts` and `frontend/src/lib/serviceLevels.test.ts`
- Test: `frontend/src/pages/DataContracts/DataContractForm.test.tsx`
- Test: `frontend/src/pages/DataContracts/DataContractDetail.test.tsx` (add tests)

**Interfaces:**
- Consumes: Task 6's files and the API shape from Task 5.
- Produces:

```ts
export interface ServiceLevelProperty { property: string; value: number | string; unit: string | null }
export interface ServiceLevels { properties: ServiceLevelProperty[] }
// lib/serviceLevels.ts
export const SLA_KEYS = ['freshness', 'availability', 'retention', 'latency'] as const
export type SlaKey = (typeof SLA_KEYS)[number]
export const DURATION_UNITS = ['s', 'min', 'h', 'd', 'w', 'y'] as const
export const UNITS: Record<SlaKey, readonly string[]>          // availability: ['%'], others: DURATION_UNITS
export interface SlaInput { value: string; unit: string }
export function readSlaInputs(sl: ServiceLevels | undefined): Record<SlaKey, SlaInput>
export function slaInputProblem(input: SlaInput): string | null
export function toServiceLevels(inputs: Record<SlaKey, SlaInput>, previous: ServiceLevels | undefined): ServiceLevels
export function formatServiceLevel(p: ServiceLevelProperty): string   // '24 h', '99.9 %', 'P1D'
```

Behaviour:
- `readSlaInputs` reads `sl?.properties ?? []`, so an unmigrated row gives empty inputs. A missing key gets value `''` and its default unit: freshness `h`, availability `%`, retention `d`, latency `h`.
- `slaInputProblem` returns null for an empty value. A number with no unit gives `Pick a unit`. A non-number with a unit gives `Use a number, or clear the unit to keep text`. Anything else returns null.
- `toServiceLevels` drops blank inputs. A number is written as `{value: Number(v), unit}`, and text as `{value: v.trim(), unit: null}`, in `SLA_KEYS` order. It then appends every `previous` property whose name is not in `SLA_KEYS`.
- In the form, `FormValues` replaces the four strings with `freshness`, `freshnessUnit`, `availability`, `availabilityUnit`, `retention`, `retentionUnit`, `latency` and `latencyUnit`, all `z.string()`.
  - `superRefine` runs `slaInputProblem` per key, with `path: [key]`, and keeps today's Tier 1 and Tier 2 "Required" rules on the values.
  - Each key shows an `Input` (label `Freshness`, plus ` *` when required) and a unit `<select aria-label="Freshness unit">` with `UNITS[key]`, the current unit when it is not listed, and `—` for none.
  - On submit: `servicelevels: toServiceLevels(tierShowsSLAs(tier) ? inputs : blankInputs, defaultValues?.servicelevels)`. Tier 4 clears the four keys but keeps the hidden properties.
- `ServiceLevelsCard` lists `(sla?.properties ?? []).map(formatServiceLevel)` under each property name, or `No service levels` when empty.
- `normalizeContract` also converts an old `servicelevels` object (no `properties` key) with `^(\d+(?:\.\d+)?)\s*([a-zA-Z%]+)?$`, mapping `percent` to `%` and `m` to `min`, and dropping blanks.

- [ ] **Step 1: Write the failing tests**

```ts
// serviceLevels.test.ts
const blank = Object.fromEntries(SLA_KEYS.map((k) => [k, { value: '', unit: '' }])) as Record<SlaKey, SlaInput>
it('reads stored properties into inputs', () =>
  expect(readSlaInputs({ properties: [{ property: 'freshness', value: 24, unit: 'h' }] }).freshness).toEqual({ value: '24', unit: 'h' }))
it('reads an unmigrated row as empty inputs', () =>
  expect(readSlaInputs({ freshness: '24h' } as unknown as ServiceLevels).freshness.value).toBe(''))
it('writes numbers with units and text without, dropping blanks', () =>
  expect(toServiceLevels({ ...blank, freshness: { value: '12', unit: 'h' }, retention: { value: 'P1D', unit: '' } }, undefined))
    .toEqual({ properties: [{ property: 'freshness', value: 12, unit: 'h' }, { property: 'retention', value: 'P1D', unit: null }] }))
it('keeps properties the form does not show', () =>
  expect(toServiceLevels(blank, { properties: [{ property: 'frequency', value: 1, unit: 'd' }] }).properties)
    .toEqual([{ property: 'frequency', value: 1, unit: 'd' }]))
it('asks for a unit on a number', () => expect(slaInputProblem({ value: '24', unit: '' })).toBe('Pick a unit'))
it('accepts text without a unit', () => expect(slaInputProblem({ value: 'best effort', unit: '' })).toBeNull())
// DataContractForm.test.tsx
it('submits structured service levels and keeps hidden ones') // tier 2 with one field; freshness 24 h, availability 99.9 %,
  // frequency 1 d; change Freshness to '12'; Save → onSubmit's servicelevels.properties equals
  // [freshness 12 h, availability 99.9 %, frequency 1 d]
it('rejects a number without a unit')                         // pick '—' in 'Freshness unit' → 'Pick a unit'; no submit
// DataContractDetail.test.tsx
it('renders service levels')                                  // '24 h' and '99.9 %'
it('survives an unmigrated row')                              // servicelevels { freshness: '24h' } → 'No service levels'
```

- [ ] **Step 2: Run the tests to verify they fail**

Run, from `frontend/`: `npm test`
Expected: the new tests fail.

- [ ] **Step 3: Implement**, as listed under Behaviour.

- [ ] **Step 4: Verify**

Run, from `frontend/`: `npm test`, `npm run lint`, `npm run build`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat(ui): structured service level inputs following ODCS units"
```

### Task 8: Migrate existing rows

**Files:**
- Create: `database/migrations/20261101000004_odcs_quality_and_sla.sql`
- Modify: `database/migrations/atlas.sum`
- Test: `tests/integration/test_odcs_quality_migration.py`
- Modify: `.github/workflows/ci.yml` (job `test`)

**Interfaces:**
- Consumes: the stored shapes in Global Constraints.
- Produces: every row in the new shape, and the column default `{"properties": []}`.

- [ ] **Step 1: Check the version order**

Run: `ls database/migrations | sort | tail -3`
Expected: `20261101000003_data_contract_metadata.sql` is the last `.sql` file, and none sorts after `20261101000004`. Spec decision 8 fixes this file's name, so if a file does sort after it, stop and ask the owner rather than renaming. Atlas refuses out-of-order files, and `entrypoint.sh` only warns about it.

- [ ] **Step 2: Write the failing test**

Connect with `asyncpg` to `TEST_DATABASE_URL`, and skip the module when it is unset. Each test runs inside one transaction that is always rolled back.
- The fixture's DDL is `CREATE SCHEMA catalog; CREATE TABLE catalog.data_contracts (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), title TEXT NOT NULL DEFAULT 'x', models JSONB NOT NULL, servicelevels JSONB NOT NULL DEFAULT '{"freshness":"","availability":"","retention":"","latency":""}')`.
- `CREATE SCHEMA catalog` fails on a database that already has one, which keeps the test away from real data.
- The test reads the SQL file with `Path(__file__).parents[2] / "database/migrations/20261101000004_odcs_quality_and_sla.sql"`, runs it with `conn.execute(sql)`, and decodes the jsonb columns with `json.loads`.
- The helper `migrate(conn, models, servicelevels) -> tuple[dict, dict]` inserts one row, runs the SQL and returns the row.

```python
FIELDS = [{"name": "id"}, {"name": "email"}]
TEXT = object()

def old(dimension="completeness", column="email", operator=">=", threshold="99%", description=""):
    return {"dimension": dimension, "column": column, "operator": operator,
            "threshold": threshold, "description": description}

@pytest.mark.parametrize(("rule", "expected"), [
    (old(), {"type": "library", "metric": "nullValues", "operator": "mustBeLessOrEqualTo", "value": 1, "unit": "percent"}),
    (old(threshold="99.9"), {"metric": "nullValues", "value": 0.1}),
    (old(threshold=99), {"metric": "nullValues", "value": 1}),
    (old(dimension="uniqueness", column="id", threshold="100%"),
     {"type": "library", "metric": "duplicateValues", "operator": "mustBeLessOrEqualTo", "value": 0, "unit": "rows"}),
    (old(dimension="uniqueness", column="id", threshold="99"), TEXT),
    (old(threshold="0.99"), TEXT), (old(threshold="1"), TEXT), (old(threshold="150"), TEXT),
    (old(threshold="abc"), TEXT), (old(threshold="24h"), TEXT), (old(threshold=""), TEXT),
    (old(operator="<=", threshold="5"), TEXT), (old(operator="=", threshold="100"), TEXT),
    (old(column=""), TEXT), (old(column="ghost"), TEXT),
])
async def test_rule_conversion(db, rule, expected):
    models, _ = await migrate(db, {"fields": FIELDS, "quality": [rule]}, {})
    got = models["quality"][0]
    if expected is TEXT:
        assert (got["type"], got["metric"], got["value"]) == ("text", None, None)
        assert "[legacy rule: dimension=" in got["description"]
    else:
        assert {k: got[k] for k in expected} == expected
```

Also write these tests, with values taken from the verified run:
- `test_text_rule_keeps_old_values_and_maps_dimension`: `old("freshness", "id", "<=", "24h", "Daily")` gives exactly `{"type": "text", "dimension": "timeliness", "column": "id", "metric": None, "operator": None, "value": None, "unit": None, "valid_values": [], "description": "Daily [legacy rule: dimension=freshness column=id operator=<= threshold=24h]"}`.
- `test_unknown_column_moves_into_description`: `column == ""`, and `"column=ghost"` is in the description.
- `test_dimensions_are_mapped`: `validity` becomes `conformity`, `integrity` becomes `consistency`, and `completeness` and `uniqueness` stay.
- `test_second_rule_on_same_metric_and_column_becomes_text`: the first is library, the second is text with description `second [legacy rule: ...]`.
- `test_rule_already_in_new_format_wins_its_metric_and_column`: given `[old rule, new nullValues rule on email]`, the old rule becomes text and the new rule is unchanged.
- `test_rule_already_in_new_format_is_untouched`.
- `test_unreadable_entries_become_text`: `["free text rule", 7, {"type": "SodaCL", "specification": "x"}]` gives three text rules with `dimension` null and descriptions `[legacy rule: "free text rule"]`, `[legacy rule: 7]` and `[legacy rule: {"type": "SodaCL", "specification": "x"}]`. A `quality` that is an object is wrapped the same way.
- `test_models_without_quality_key_are_untouched`: `{"fields": FIELDS}` and `{"fields": FIELDS, "extra": {"keep": True}, "quality": []}` come back equal. `"quality": null` becomes `[]`.
- `test_service_levels_are_split`: `{"freshness": "24h", "availability": "99.9%", "retention": "365d", "latency": "30m"}` gives `{"properties": [{"property": "freshness", "value": 24, "unit": "h"}, {"property": "availability", "value": 99.9, "unit": "%"}, {"property": "retention", "value": 365, "unit": "d"}, {"property": "latency", "value": 30, "unit": "min"}]}`.
- `test_empty_service_levels_become_an_empty_list`: all four `""`, and `{}`, give `{"properties": []}`.
- `test_unparseable_and_extra_service_levels_are_kept`: `"best effort"` and `"P1D"` become string values with unit `None`. `"   "` and `null` are dropped. `"frequency": "1d"` follows the four keys. `"99.50 percent"` becomes `99.5` with `%`. `"30"` becomes `30` with unit `None`.
- `test_service_levels_already_in_new_format_are_untouched`.
- `test_second_run_changes_nothing`: seed the rows above, snapshot `SELECT models, servicelevels ... ORDER BY id`, run the SQL again, and compare.
- `test_new_rows_default_to_the_new_service_level_shape`: insert without `servicelevels`, then assert `{"properties": []}`.

- [ ] **Step 3: Start a throwaway Postgres and watch the test fail**

```bash
docker run --rm -d --name dmplt-migration-test -p 127.0.0.1:55439:5432 -e POSTGRES_HOST_AUTH_METHOD=trust postgres:16.1
TEST_DATABASE_URL=postgres://postgres@127.0.0.1:55439/postgres .venv/Scripts/python.exe -m pytest tests/integration/test_odcs_quality_migration.py -q
```

Expected: fails with `FileNotFoundError`, because the SQL file does not exist yet. Never point `TEST_DATABASE_URL` at the compose `db`, which holds dev data. The test refuses it anyway, because `catalog` exists there.

- [ ] **Step 4: Write `database/migrations/20261101000004_odcs_quality_and_sla.sql`**

This is the exact SQL verified in Verified Tool Behaviour. Its CTEs are the algorithm the tests above pin, and the `COALESCE` on `is_new` fixes a bug the first run caught.

```sql
-- =============================================================================
-- ODCS library quality rules and structured service levels.
--
-- models.quality[] moves from {dimension, column, operator, threshold,
-- description} to {type, dimension, column, metric, operator, value, unit,
-- valid_values, description}. servicelevels moves from four named strings to
-- {"properties": [{"property", "value", "unit"}]}.
--
-- Every library rule written here runs under datacontract-cli 1.2.9, which
-- refuses unit percent on duplicateValues and breaks on two rules sharing a
-- metric and a column. Anything else becomes a text rule that keeps its old
-- values in description.
--
-- Safe to run twice: rules and rows already in the new format are left alone.
-- Atlas renders this file as a Go template, so it must never contain two
-- opening braces in a row. Atlas manages the transaction; do NOT add explicit
-- BEGIN/COMMIT here.
-- =============================================================================

-- 1. Quality rules. Rows with no quality key are not selected and stay as they are.
WITH contract AS (
    SELECT dc.id,
           CASE jsonb_typeof(dc.models -> 'quality')
               WHEN 'array'  THEN dc.models -> 'quality'
               WHEN 'object' THEN jsonb_build_array(dc.models -> 'quality')
               ELSE '[]'::jsonb
           END AS quality,
           CASE jsonb_typeof(dc.models -> 'fields')
               WHEN 'array' THEN dc.models -> 'fields'
               ELSE '[]'::jsonb
           END AS fields
    FROM catalog.data_contracts dc
    WHERE dc.models ? 'quality'
),
item AS (
    SELECT c.id,
           e.ord,
           e.rule,
           c.fields,
           -- COALESCE: type is NULL on an old rule, and ranked sorts this DESC,
           -- where a NULL would come first and beat a rule already in the new format.
           COALESCE(
               jsonb_typeof(e.rule) = 'object'
                   AND e.rule ->> 'type' IN ('library', 'text')
                   AND e.rule ? 'dimension',
               false
           ) AS is_new,
           CASE jsonb_typeof(e.rule) WHEN 'object' THEN e.rule ELSE '{}'::jsonb END AS old
    FROM contract c
    CROSS JOIN LATERAL jsonb_array_elements(c.quality) WITH ORDINALITY AS e(rule, ord)
),
parsed AS (
    SELECT i.*,
           COALESCE(i.old ->> 'column', '') AS col,
           trim(COALESCE(i.old ->> 'description', '')) AS descr,
           EXISTS (
               SELECT 1
               FROM jsonb_array_elements(i.fields) AS f(field)
               WHERE f.field ->> 'name' = i.old ->> 'column'
           ) AS known_column,
           regexp_match(i.old ->> 'threshold', '^\s*(\d+(?:\.\d+)?)\s*(%?)\s*$') AS m
    FROM item i
),
measured AS (
    SELECT p.*,
           p.m[1]::numeric AS t,
           COALESCE(p.m[2], '') = '%' AS has_percent_sign
    FROM parsed p
),
candidate AS (
    SELECT m.*,
           CASE
               WHEN m.is_new THEN m.old ->> 'metric'
               -- 100 - T only means something for a column the contract declares,
               -- a >= rule and a percentage. A bare 0.99 or 1 may be a fraction, and
               -- 100 - T would turn it into "99% of the rows may be null".
               WHEN m.old ->> 'operator' = '>='
                    AND m.known_column
                    AND m.t BETWEEN 0 AND 100
                    AND (m.has_percent_sign OR m.t = 0 OR m.t > 1)
               THEN CASE
                        WHEN m.old ->> 'dimension' = 'completeness' THEN 'nullValues'
                        WHEN m.old ->> 'dimension' = 'uniqueness' AND m.t = 100
                        THEN 'duplicateValues'
                    END
           END AS metric,
           CASE m.old ->> 'dimension'
               WHEN 'completeness' THEN 'completeness'
               WHEN 'uniqueness'   THEN 'uniqueness'
               WHEN 'freshness'    THEN 'timeliness'
               WHEN 'validity'     THEN 'conformity'
               WHEN 'integrity'    THEN 'consistency'
           END AS dimension
    FROM measured m
),
ranked AS (
    SELECT c.*,
           row_number() OVER (
               PARTITION BY c.id, c.metric, c.col
               ORDER BY c.is_new DESC, c.ord
           ) AS metric_rank
    FROM candidate c
),
converted AS (
    SELECT r.id,
           jsonb_agg(
               CASE
                   WHEN r.is_new THEN r.rule
                   WHEN r.metric IS NOT NULL AND r.metric_rank = 1 THEN jsonb_build_object(
                       'type', 'library',
                       'dimension', r.dimension,
                       'column', r.col,
                       'metric', r.metric,
                       'operator', 'mustBeLessOrEqualTo',
                       'value', CASE r.metric
                                    WHEN 'nullValues' THEN to_jsonb(trim_scale(100 - r.t))
                                    ELSE to_jsonb(0)
                                END,
                       'unit', CASE r.metric WHEN 'nullValues' THEN 'percent' ELSE 'rows' END,
                       'valid_values', '[]'::jsonb,
                       'description', r.descr
                   )
                   ELSE jsonb_build_object(
                       'type', 'text',
                       'dimension', r.dimension,
                       'column', CASE WHEN r.known_column THEN r.col ELSE '' END,
                       'metric', NULL::text,
                       'operator', NULL::text,
                       'value', NULL::numeric,
                       'unit', NULL::text,
                       'valid_values', '[]'::jsonb,
                       'description', concat_ws(
                           ' ',
                           NULLIF(r.descr, ''),
                           CASE
                               WHEN r.old ? 'threshold' THEN format(
                                   '[legacy rule: dimension=%s column=%s operator=%s threshold=%s]',
                                   r.old ->> 'dimension', r.col,
                                   r.old ->> 'operator', r.old ->> 'threshold'
                               )
                               ELSE '[legacy rule: ' || r.rule::text || ']'
                           END
                       )
                   )
               END
               ORDER BY r.ord
           ) AS quality
    FROM ranked r
    GROUP BY r.id
)
UPDATE catalog.data_contracts dc
SET models = jsonb_set(dc.models, '{quality}', COALESCE(cv.quality, '[]'::jsonb))
FROM contract c
LEFT JOIN converted cv ON cv.id = c.id
WHERE dc.id = c.id
  AND dc.models -> 'quality' IS DISTINCT FROM COALESCE(cv.quality, '[]'::jsonb);

-- 2. Service levels. A row holding a properties key is already converted. Empty
--    strings are dropped, so a contract with no levels becomes an empty list.
UPDATE catalog.data_contracts dc
SET servicelevels = jsonb_build_object(
    'properties',
    COALESCE(
        (
            SELECT jsonb_agg(
                CASE
                    WHEN s.m IS NULL THEN jsonb_build_object(
                        'property', s.key, 'value', s.val, 'unit', NULL::text
                    )
                    ELSE jsonb_build_object(
                        'property', s.key,
                        'value', to_jsonb(trim_scale(s.m[1]::numeric)),
                        'unit', CASE s.m[2]
                                    WHEN 'percent' THEN '%'
                                    WHEN 'm' THEN 'min'
                                    ELSE s.m[2]
                                END
                    )
                END
                ORDER BY
                    array_position(
                        ARRAY['freshness', 'availability', 'retention', 'latency'], s.key
                    ) NULLS LAST,
                    s.key
            )
            FROM (
                SELECT kv.key,
                       trim(kv.value) AS val,
                       regexp_match(trim(kv.value), '^(\d+(?:\.\d+)?)\s*([a-zA-Z%]+)?$') AS m
                FROM jsonb_each_text(dc.servicelevels) AS kv
                WHERE COALESCE(trim(kv.value), '') <> ''
            ) AS s
        ),
        '[]'::jsonb
    )
)
WHERE jsonb_typeof(dc.servicelevels) = 'object'
  AND NOT dc.servicelevels ? 'properties';

-- 3. New rows must not start in the old format.
ALTER TABLE catalog.data_contracts
    ALTER COLUMN servicelevels SET DEFAULT '{"properties": []}';
```

- [ ] **Step 5: Run the test to verify it passes**

Run: the pytest command from Step 3.
Expected: all pass. Then run `pre-commit run --files database/migrations/20261101000004_odcs_quality_and_sla.sql`, with `.venv\Scripts` on `PATH`, so that no hook changes the file after it is hashed.

- [ ] **Step 6: Apply it through real Atlas with `entrypoint.sh`'s flags, from LF copies** (Git Bash, repository root)

```bash
tmp=$(mktemp -d); mkdir "$tmp/migrations"
for f in database/migrations/*.sql; do tr -d '\r' < "$f" > "$tmp/migrations/$(basename "$f")"; done
tr -d '\r' < database/atlas.hcl > "$tmp/atlas.hcl"
docker exec dmplt-migration-test createdb -U postgres atlas_check
MSYS_NO_PATHCONV=1 docker run --rm -v "$(cd "$tmp" && pwd -W):/project" -w /project \
  -e ADMIN_PASSWORD=pw -e APP_USER_PASSWORD=pw -e USER_PASSWORD=pw -e POSTGRES_PASSWORD=unused \
  -e DB_USER=postgres -e DB_PORT=5432 -e DB_NAME=atlas_check -e MIGRATIONS_DB_HOST=host.docker.internal \
  arigaio/atlas:1.3.6 migrate apply --env azure \
  --url "postgres://postgres@host.docker.internal:55439/atlas_check?sslmode=disable" \
  --revisions-schema public --allow-dirty
```

Expected: exit 0, with `-- migrating version 20261101000004` followed by `-- ok`.

- [ ] **Step 7: Regenerate `atlas.sum` from LF content and validate it** (same shell as Step 6, which set `$tmp`)

This is Plan 3 Task 1 Step 4's method (spec decision 9): hash LF copies, then validate both the copy and the working tree. Step 6 already wrote the LF copies.

```bash
MSYS_NO_PATHCONV=1 docker run --rm -v "$(cd "$tmp" && pwd -W)/migrations:/migrations" arigaio/atlas:1.3.6 migrate hash --dir file:///migrations
MSYS_NO_PATHCONV=1 docker run --rm -v "$(cd "$tmp" && pwd -W)/migrations:/migrations" arigaio/atlas:1.3.6 migrate validate --dir file:///migrations
cp "$tmp/migrations/atlas.sum" database/migrations/atlas.sum
MSYS_NO_PATHCONV=1 docker run --rm -v "$(cygpath -w "$PWD/database/migrations"):/migrations" arigaio/atlas:1.3.6 migrate validate --dir file:///migrations
git ls-files --eol database/migrations/20261101000004_odcs_quality_and_sla.sql
```

Expected: the three Atlas commands exit 0, and the new file shows `i/lf    w/lf    attr/text eol=lf` once staged (if `w/crlf`, `rm` it and `git checkout --` it). Because Plan 3 already rehashed every row from LF, `git diff database/migrations/atlas.sum` changes only the first line and adds one line, for 12 in all. With Plans 3 and 4's SQL copied verbatim, the first line is `h1:8XqZ/HztsDWFHeZ9ymp9vHREjXVqpLabobzw7Lz3muI=` and the last is `20261101000004_odcs_quality_and_sla.sql h1:CL899XdbY4t2+pv1Y/BGwWH2R5+hTQGm9XCDzZTuzyg=` (computed the way Plan 3 Step 4 explains; if Atlas disagrees, Atlas wins). CI's `migrations` job runs the same validate. `atlas` is not on `PATH` on this machine, and Docker Desktop must be running (check with `docker ps`). Pull the pinned `arigaio/atlas:1.3.6` first if it is not cached.

- [ ] **Step 8: Run the migration test in CI**

In `.github/workflows/ci.yml`, job `test`, add:

```yaml
    services:
      postgres:
        image: postgres:16.1
        env:
          POSTGRES_HOST_AUTH_METHOD: trust
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready --health-interval 5s --health-timeout 5s --health-retries 10
    env:
      TEST_DATABASE_URL: postgres://postgres@localhost:5432/postgres
```

Every other job runs without the variable and skips the module.

- [ ] **Step 9: Clean up and commit**

```bash
docker rm -f dmplt-migration-test
git add database/migrations tests/integration/test_odcs_quality_migration.py .github/workflows/ci.yml
git commit -m "feat(db): migrate quality rules and service levels to the ODCS shape"
```

### Task 9: Remove the old shapes (contract)

**Files:**
- Modify: `backend/interface/schemas/data_contract.py`
- Modify: `backend/use_cases/data_contract/odcs.py`
- Modify: `frontend/src/hooks/useDataContracts.ts`
- Delete: `frontend/src/lib/contractFormat.ts` and `frontend/src/lib/contractFormat.test.ts`
- Modify: `.github/workflows/cd.yml`
- Test: `tests/unit/test_data_contract_schemas.py`, `tests/unit/interface/test_routers.py`, `tests/unit/use_cases/data_contract/test_odcs_quality_contract.py`
- Modify (Step 4): `tests/fixtures/odcs/sample_contract.py`, `tests/unit/use_cases/data_contract/test_odcs_emit.py`, `test_odcs_parse.py`, `test_odcs_metadata.py` and `test_sync_from_github.py`

**Interfaces:**
- Consumes: everything above, and `_RULE_CUSTOM_KEYS` and `_rule_sentence` from Plan 1.
- Produces: `ModelsSection.quality: list[QualityRule]`, `servicelevels: ServiceLevels` (create) and `ServiceLevels | None` (update). `to_odcs` and `from_odcs` know only the new shape, except that `from_odcs` reads a Plan 1 text rule carrying `dmplt*` properties as a `type: text` rule that keeps its `dimension`, with a description in the migration's format: `<description> [legacy rule: dimension=<d> column=<c> operator=<o> threshold=<t>]` (spec decision 6). CD deploys the backend before the frontend.

- [ ] **Step 1: Write the failing tests and delete the expand-phase tests**

```python
def test_old_service_level_shape_is_rejected():
    with pytest.raises(ValidationError):
        DataContractCreateModel(title="x", owner="o", domain_id=DOMAIN_ID, tier=2,
            servicelevels={"freshness": "24h", "availability": "", "retention": "", "latency": ""})

def test_old_rule_shape_is_rejected():
    with pytest.raises(ValidationError):
        ModelsSection(quality=[{"dimension": "completeness", "column": "", "operator": ">=", "threshold": "99%"}])

PLAN1_CUSTOM = [{"property": "dmpltDimension", "value": "completeness"},
                {"property": "dmpltOperator", "value": ">="},
                {"property": "dmpltThreshold", "value": "99"},
                {"property": "dmpltPosition", "value": 0}]

LEGACY = "[legacy rule: dimension=completeness column={} operator=>= threshold=99]"
ON_CUSTOMER = lambda d: d["schema"][0]["properties"][1]  # customer_id
ON_SCHEMA = lambda d: d["schema"][0]

@pytest.mark.parametrize(("place", "extra", "description", "column", "expected"), [
    (ON_CUSTOMER, [], "Kept as written", "customer_id",
     "Kept as written " + LEGACY.format("customer_id")),
    (ON_CUSTOMER, [], "Completeness of column customer_id must be >= 99.", "customer_id",
     LEGACY.format("customer_id")),
    (ON_SCHEMA, [{"property": "dmpltColumn", "value": "ghost"}], "Kept as written", "",
     "Kept as written " + LEGACY.format("ghost")),
], ids=["own-description", "generated-sentence", "unknown-column"])
def test_plan1_text_rule_is_read_as_a_text_rule(place, extra, description, column, expected):
    doc = to_odcs(orders_contract())
    place(doc)["quality"] = [{"type": "text", "dimension": "completeness", "description": description,
                              "customProperties": [*PLAN1_CUSTOM, *extra]}]
    rules = [r for r in from_odcs(doc).models["quality"] if "[legacy rule:" in r["description"]]
    assert rules == [text_rule(dimension="completeness", column=column, description=expected)]

@pytest.mark.parametrize("item", [
    {"type": "text", "description": "x", "customProperties": [{"property": "cost", "value": 1}]},
    {"type": "library", "metric": "rowCount", "mustBeGreaterThan": 0, "customProperties": PLAN1_CUSTOM},
])
def test_other_custom_properties_are_refused(item):
    doc = to_odcs(orders_contract())
    doc["schema"][0]["quality"].append(item)
    with pytest.raises(OdcsParseError, match="customProperties"):
        from_odcs(doc)
```

`properties[1]` is `customer_id` in `orders_contract()`. A Plan 1 rule on the schema object sits there because its column was unknown, so its column field stays `""`, which `find_quality_rule_problems` accepts for a text rule, while the suffix keeps `column=ghost`, as the migration does for an unknown column. The `generated-sentence` case is the description Plan 1 emits for a rule stored with an empty description. The migration writes that rule's description as the suffix alone, so sync drops the sentence too. All three expected texts match what Task 8's SQL writes for the same stored rule (`test_text_rule_keeps_old_values_and_maps_dimension` pins that format).

Also add the router test `test_create_rejects_old_service_level_shape` (422). Delete `test_old_shapes_are_still_accepted_until_contraction`, `test_old_shape_still_emits_until_contraction` and the `contractFormat` tests.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/ -q`
Expected: every new test fails except the `cost` case of `test_other_custom_properties_are_refused`, which Task 3 already refuses. The `dmplt` cases fail because Task 3 still reads `dmplt` items through Plan 1's reader in the old shape.

- [ ] **Step 3: Remove the old shapes**

- Delete `LegacyQualityRule` and `LegacyServiceLevels` and narrow the unions.
- In `odcs.py`, delete the `"type" in rule` and `"properties" in servicelevels` branches added in Task 3, Plan 1's text-rule reader and its text-rule and string-SLA helpers that are now unused, and the `"type" in r` filter before `find_quality_rule_problems`. Keep `_rule_sentence`, which the next bullet uses.
- Replace Task 3's temporary `dmplt` branch with spec decision 6. An item with `type: text` whose `customProperties` is a list of entries each naming a key in `_RULE_CUSTOM_KEYS` goes to `rule_from_odcs` without its `customProperties`. Its `column` is set as for any other item: the property name, or `""` on the schema object. Its `description` becomes `_legacy_description(item, column)`. Any other item carrying `customProperties` goes to `rule_from_odcs` unchanged, which refuses it.
- `_legacy_description(item: dict[str, Any], column: str) -> str` reproduces the text branch of the Task 8 SQL exactly:
  - Values: `d`, `o` and `t` are the `dmpltDimension`, `dmpltOperator` and `dmpltThreshold` values. `c` is `column` for a rule under a property, or the `dmpltColumn` value on the schema object (`""` when absent). Each value is written with `str(v)`, and a missing value is written as `""`, as `format('%s', NULL)` does.
  - Description: `item["description"].strip(" ")`, because SQL `trim` removes spaces only. It becomes `""` when it equals `_rule_sentence(d, c, o, t)`, which is the sentence Plan 1 emits for a stored empty description.
  - Result: `" ".join(part for part in (description, f"[legacy rule: dimension={d} column={c} operator={o} threshold={t}]") if part)`, which is `concat_ws(' ', NULLIF(descr, ''), …)`.
  - The one case that cannot match: a stored rule with no `threshold` key, which the migration writes as `[legacy rule: <raw JSON>]`. The file no longer holds that JSON, so sync writes the format above with an empty threshold.
- Delete `normalizeContract`, its file and test, and the `select` in `useDataContract`.
- In `.github/workflows/cd.yml`, add `needs: deploy-backend` to the `deploy-frontend` job.

- [ ] **Step 4: Update the remaining old-shape fixtures**

Run: `grep -rn "dmplt\|threshold\|Legacy\|normalizeContract\|\"freshness\": \"" backend tests frontend/src scripts .github`
Expected hits to update:
- `tests/unit/test_data_contract_schemas.py::test_schema_field_defaults`: assert `m.servicelevels.properties == []`.
- `tests/unit/interface/test_routers.py`: the `_contract` service levels, the `test_create_data_contract` payload, and `test_yaml_with_quality_data`, which gets a library rule on a declared field and asserts `"metric: nullValues" in resp.text`.
- `tests/fixtures/odcs/sample_contract.py`, Plan 1's generator for the CI lint step: after the deletions below no test uses `make_rule`, so delete it and its imports. `sample_contract()` gets three new-shape rules, built with `library_rule` and `text_rule`, listed in the order `from_odcs` returns them so Plan 1's exact round trip holds: `nullValues mustBeLessOrEqualTo 0.5 percent` on `order_id` with description `Every order has an id`, then a schema-level text rule (`timeliness`, `Orders arrive within 24 hours.`), then `rowCount mustBeGreaterThan 0 rows`. `FULL_CONTRACT` (Plan 3) has no rules and already uses the new SLA default from Task 3.
- `tests/unit/use_cases/data_contract/test_odcs_emit.py`: rewrite `EXPECTED_YAML`'s two `quality` blocks for the new rules, in Task 2's key order; every other line stays. Delete `test_rule_placement`, `test_dimension_mapping_keeps_the_original_value`, `test_rule_without_description_gets_a_sentence`, `test_sla_value_is_split` and `test_sla_value_that_cannot_be_rebuilt_stays_a_string`, which Task 2's and Task 3's tests replace. In `test_output_is_valid_against_the_official_schema`, the `only-quality` case becomes `make_contract(models={"fields": [], "quality": [text_rule()]})` and the `partial-rule` case is deleted.
- `tests/unit/use_cases/data_contract/test_odcs_parse.py`: delete `test_round_trip_rule`, `test_round_trip_keeps_rule_order` and `test_description_differing_from_the_sentence_is_kept`. Task 2's `test_rule_round_trip` covers rules, and Decision 10 gives up order across columns.
- `tests/unit/use_cases/data_contract/test_odcs_metadata.py` (Plan 3): `_contract`'s `servicelevels` becomes `{"properties": []}`.
- `tests/unit/use_cases/data_contract/test_sync_from_github.py`: `_yaml()` (Plan 2) passes `servicelevels or {"properties": []}`.

Entity and use-case tests that only pass dicts through may keep their data. After the update, the same grep must return nothing in `frontend/src`, and in `backend` only `_RULE_CUSTOM_KEYS` and the decision-6 branch in `odcs.py`.

- [ ] **Step 5: Run the full verification**

Run: `.venv\Scripts\python.exe -m pytest tests/ -q`, `.venv\Scripts\ruff.exe check backend`, `.venv\Scripts\ruff.exe format backend`, and from `frontend/`: `npm test`, `npm run lint`, `npm run build`.
Expected: all green: the full backend suite passes. `tests/integration/test_contract_execution.py` reports 4 passed. The migration tests report skipped unless `TEST_DATABASE_URL` is set.

- [ ] **Step 6: Commit**

```bash
git add -A backend tests frontend/src .github
git commit -m "refactor(contracts): drop the pre-ODCS quality and SLA shapes"
```

## Release Notes (for the owner, not the implementer)

1. Before tagging, take a Neon branch or backup. The conversion to `text` keeps every old value, but there is no automatic rollback.
2. Tag. CD now deploys the backend, then the frontend. Check that the backend revision's log says `Migrations applied successfully`. `WARNING: Migrations failed` means the new code is running on old rows: pages render (Review Focus 4), but the YAML endpoint and GitHub pushes fail for those rows until the migration is applied.
3. Run this query. It must return 0. A non-zero count comes from an old revision writing during the swap. Fix it by running the migration file again with `psql`, which is idempotent.

```sql
SELECT count(*) FROM catalog.data_contracts dc
WHERE NOT dc.servicelevels ? 'properties'
   OR EXISTS (SELECT 1 FROM jsonb_array_elements(CASE jsonb_typeof(dc.models->'quality')
              WHEN 'array' THEN dc.models->'quality' ELSE '[]'::jsonb END) r WHERE r ? 'threshold');
```

4. Local compose: the `backend` container cannot apply migrations (`sslmode=require` against a server without SSL). Apply them by hand from `database/` with `docker run --rm --network data-mesh-network -v ${PWD}:/project -w /project --env-file ../.env arigaio/atlas:1.3.6 migrate apply --env local`. Note that `how_to_use.txt` says `local-network`, which belongs to `database/docker-compose.yaml`. This command was not run against the owner's database.
5. Central repository (`GuhBrando/dmplt_data_contract`): its three files have no quality rules (checked on 2026-11-01), and Plan 1 already writes SLA units as `%` and `min`, so their next save changes nothing there; `from_odcs` also accepts `percent` and `m`. A file that holds Plan 1's `dmplt*` text rules still syncs (spec decision 6): each rule is stored as a `type: text` rule that keeps its `dimension`, and its description gets the same `[legacy rule: …]` suffix the migration writes, so a synced row and a migrated row read the same. Saving that contract in the UI rewrites its file in the new shape. Any write to that repository needs the owner's explicit approval.
