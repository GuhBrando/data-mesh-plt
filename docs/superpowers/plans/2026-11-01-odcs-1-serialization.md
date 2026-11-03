# ODCS Serialization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the platform emit valid ODCS `v3.2.0`, read ODCS back without loss, keep syncing legacy files, and lint a generated contract in CI.

**Architecture:** A new pure module, `odcs.py`, maps `DataContract` to an ODCS document and back. `assemble_yaml` becomes a thin call to it, and `SyncFromGitHubUseCase` reads files through `parse_contract_document`, which routes legacy files to `legacy_dcs.py`. The stored `models` and `servicelevels` formats do not change. `assemble_yaml` switches last, so sync can already read ODCS when the first ODCS file is pushed.

**Tech Stack:** Python 3.12+, PyYAML, `jsonschema` (dev only), uv, `datacontract-cli` 1.2.9 through `uvx`, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-11-01-odcs-adoption-design.md`. This is Plan 1. Read "Decisions Made During Planning (2026-11-02)", which wins over the rest of the spec, then "Plans", "Shared Interfaces", "ODCS Mapping (Plan 1)", "Validation" and "Repository Rules".

## Global Constraints

- Constants: `apiVersion` is `v3.2.0`, `kind` is `DataContract`.
- No database or API change. The stored `models` and `servicelevels` formats stay as they are.
- `to_odcs` and `from_odcs` are pure functions with no I/O.
- `assemble_yaml(contract: DataContract) -> str` keeps its signature. Existing callers do not change.
- A contract has at most one `schema[]` object.
- `jsonschema` is a dev dependency only.
- Layering stays as it is: entities and pure logic hold no I/O, routers orchestrate GitHub calls, and GitHub push failures stay warn-only.
- Branch from `develop`. Stage explicit paths: the working tree holds unrelated changes (`frontend/package-lock.json`, `.agents/`, the spec).
- Commit messages and PR text carry no Claude or Claude Code attribution of any kind.
- No test reaches GitHub (spec decision 1). Task 1 blanks `GITHUB_TOKEN` in `tests/conftest.py`. Until Task 1 is committed, run only the tests a step names: a full run with the token in `.env` can push to the contracts repository.
- Backend tests: `.venv\Scripts\python.exe -m pytest tests/ -q`.
- `git commit` needs `.venv\Scripts` prefixed to `PATH`, or pre-commit fails. In PowerShell: `$env:PATH = "$PWD\.venv\Scripts;$env:PATH"`.
- Lint with `ruff check backend`. Passing test paths makes ruff rewrite those files. Line length is 88 and maximum complexity is 15.

## Review Focus

- An SLA string that matches the regex but cannot be rebuilt (`24 h`, `1.50h`, `007`, `5percent`, `30min`, `24h\n`) must come back byte for byte: Task 2 `test_sla_value_that_cannot_be_rebuilt_stays_a_string`, Task 3 `test_round_trip_sla_value`.
- Quality rules in any order, mixing column rules and table rules, must come back in the same order: Task 3 `test_round_trip_keeps_rule_order`.
- A file edited by hand in the central repository with a key the platform cannot hold (`servers`, `tags`, an extra custom property) must be reported, not stripped on the next push: Task 4 `test_unsupported_odcs_key_is_reported_and_nothing_is_written`.
- An empty or non-mapping YAML file in the central repository must produce one readable error and must not stop the other files: Task 4 `test_non_mapping_file_is_reported_and_the_next_file_still_syncs`.
- A rule with an empty description must come back empty, and a description edited by hand must be kept: Task 3 `test_round_trip_rule` and `test_description_differing_from_the_sentence_is_kept`.

## Decisions Beyond the Spec

The spec leaves these open or conflicts with itself. Each one was prototyped against the JSON Schema and `datacontract lint`.

1. **Schema source is pinned to the tag.** The repository's default branch is `dev`, and its copy differs from the released file by one token (`anyOf` for `oneOf` in `DataQualityOperators`, commit `448f7b9332`, after the release). Fetch with `?ref=v3.2.0`.
2. **`dmpltPosition` is added to every rule.** Rules are split between properties and the schema object, so list order is lost otherwise, and the round trip must return the same list. Plan 4 removes it with the other `dmplt*` properties from what it writes, and still reads a rule carrying them as a `type: text` rule (spec decision 6).
3. **An SLA value is split only when it can be rebuilt** (spec decision 4). The spec says a matching value is split and that parsing rebuilds the original. `24 h` and `1.50h` cannot satisfy both, so they stay a string `value`. Every value in the central repository today (`24h`, `99%`, `365d`, `1h`) is split. Units follow the ODCS example: a stored `%` is written as `%` and a stored `m` (minutes, as the form's `30m`) as `min`, because the CLI reads `m` as months. Reading also accepts `percent` and `m`. A stored `30min` or `5percent` stays a string, because rebuilding gives `30m` and `5%`.
4. **A generated description is recognised by comparison.** On read, a description equal to the sentence regenerated from the rule's values becomes empty. A description typed to be identical to that sentence also comes back empty, and the emitted ODCS stays the same.
5. **"No value is dropped silently" covers every key.** `from_odcs` rejects any key outside the mapping, at each level. The allowed keys are module constants, so plans 3 to 5 extend them when they add mappings (spec decision 5). See Task 3.
6. **Any `logicalType` outside the six the model holds is rejected,** including `map`, `vector` and a missing one. The spec lists only `time`, `object` and `array`, but `v3.2.0` also has `map` and `vector`.
7. **Accents are folded in the schema slug,** so `Pedidos de Exportação` gives `pedidos_de_exportacao`, not `pedidos_de_exporta_o`.
8. **`schema[0].name` and `schema[0].physicalType` are derived.** `from_odcs` reads and ignores them, because the model has no place for them and the next emit regenerates them.

## File Structure

| Path | Change | Responsibility |
|---|---|---|
| `tests/conftest.py` | Modify | Blank `GITHUB_TOKEN` before any backend import |
| `tests/unit/infra/test_suite_isolation.py` | Create | The suite cannot build a real `GitHubClient` |
| `backend/use_cases/data_contract/odcs.py` | Create | `to_odcs`, `from_odcs`, `ParsedContract`, `OdcsParseError` |
| `backend/use_cases/data_contract/legacy_dcs.py` | Create | `from_legacy_dcs`, deleted by plan 2 |
| `backend/use_cases/data_contract/contract_document.py` | Create | `parse_contract_document` |
| `backend/use_cases/data_contract/yaml_builder.py` | Modify | Thin call to `to_odcs` plus `yaml.dump` |
| `backend/use_cases/data_contract/sync_from_github.py` | Modify | Reads through `parse_contract_document` |
| `tests/fixtures/odcs/odcs-json-schema-v3.2.0.json` | Create | Official schema, verbatim |
| `tests/fixtures/odcs/sample_contract.py` | Create | Test builders and the contract CI lints |
| `tests/unit/use_cases/data_contract/test_odcs_emit.py` | Create | `to_odcs` and the expected YAML |
| `tests/unit/use_cases/data_contract/test_odcs_parse.py` | Create | `from_odcs`, round trip, parse errors |
| `tests/unit/use_cases/data_contract/test_contract_document.py` | Create | Dispatch and legacy reader |
| `tests/unit/use_cases/data_contract/test_sync_from_github.py` | Modify | Legacy marker in helpers, ODCS sync tests |
| `pyproject.toml`, `uv.lock` | Modify | `jsonschema` dev dependency |
| `.github/workflows/ci.yml` | Modify | `odcs-lint` job |
| `README.md` | Modify | ODCS reference link |

---

### Task 1: Keep the test suite away from the central repository

Spec decision 1. `admin_client` in `tests/unit/interface/test_routers.py` does not override `get_github_client`, and `.env` holds a token, so a full `pytest` run can push to and delete from `GuhBrando/dmplt_data_contract`. Run only the test this task names until Step 5. Plan 2 only checks that this guard is present.

**Files:**
- Modify: `tests/conftest.py`
- Test: `tests/unit/infra/test_suite_isolation.py`

**Interfaces:**
- Consumes: `GITHUB_TOKEN` from `backend/infra/config.py`, bound at import from the environment after `load_dotenv()`, and `get_github_client()` from `backend/interface/dependencies.py`, which returns `None` for an empty token.
- Produces: a suite in which `get_github_client()` returns `None` unless a test overrides it, pinned by `test_test_suite_cannot_build_a_real_github_client`.

- [ ] **Step 1: Create the branch**

```bash
git switch develop
git switch -c feat/odcs-1-serialization
```

- [ ] **Step 2: Write the failing test**

Create `tests/unit/infra/test_suite_isolation.py`:

```python
from backend.infra import config
from backend.interface.dependencies import get_github_client


def test_test_suite_cannot_build_a_real_github_client():
    assert config.GITHUB_TOKEN == ""
    assert get_github_client() is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/infra/test_suite_isolation.py -q`
Expected: FAIL on a machine whose `.env` holds a token. On a machine without one it passes, so note that and continue.

- [ ] **Step 4: Blank the token in `tests/conftest.py`, directly after the `JWT_SECRET_KEY` block**

Use assignment, not `setdefault`: `load_dotenv()` leaves an existing variable alone, even an empty one.

```python
# Keep the suite away from the real contracts repository. Router tests that do not
# override get_github_client would otherwise push to and delete from GITHUB_REPO
# with the token in .env.
os.environ["GITHUB_TOKEN"] = ""
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/infra/test_suite_isolation.py -q`
Expected: PASS

- [ ] **Step 6: Run the full suite and confirm the central repository did not move**

Run: `gh api repos/GuhBrando/dmplt_data_contract/commits/main --jq .sha`, then `.venv\Scripts\python.exe -m pytest tests/ -q`, then the `gh api` command again.
Expected: `218 passed`, and both `gh api` outputs are identical.

- [ ] **Step 7: Commit**

```powershell
git add tests/conftest.py tests/unit/infra/test_suite_isolation.py
$env:PATH = "$PWD\.venv\Scripts;$env:PATH"; git commit -m "test: stop the suite reaching the contracts repository"
```

---

### Task 2: Emit ODCS with `to_odcs`

**Files:**
- Create: `backend/use_cases/data_contract/odcs.py`
- Create: `tests/fixtures/__init__.py`, `tests/fixtures/odcs/__init__.py` (both empty)
- Create: `tests/fixtures/odcs/odcs-json-schema-v3.2.0.json`
- Create: `tests/fixtures/odcs/sample_contract.py`
- Test: `tests/unit/use_cases/data_contract/test_odcs_emit.py`
- Modify: `pyproject.toml:43`, `uv.lock`

**Interfaces:**
- Consumes: `DataContract` from `backend/domain/entities/data_contract.py`.
- Produces: in `odcs.py`, `ODCS_API_VERSION`, `OdcsParseError`, `ParsedContract` and `to_odcs(contract: DataContract) -> dict[str, Any]`, exactly as in the spec's Shared Interfaces. Internal helpers Task 3 reuses: `_rule_sentence(dimension: Any, column: str, operator: Any, threshold: Any) -> str` and `_sla_text(value: Any, unit: str | None) -> str`. In `sample_contract.py`: `SAMPLE_ID`, `make_contract(**overrides)`, `make_field(...)`, `make_rule(...)`, `sample_contract()`, `emit(contract) -> dict`.

- [ ] **Step 1: Add the dependency and regenerate the lock**

In `pyproject.toml`, add `"jsonschema>=4.26.0",` as the last item of the `dev` extra, after `"pip>=26.2",`.

Run: `uv lock`
Expected: `Added` lines for exactly `attrs`, `jsonschema`, `jsonschema-specifications`, `referencing` and `rpds-py`, and no `Updated` line.

Run: `uv sync --extra dev`, then `uv lock --check`
Expected: both exit 0. CI and the dockerfile do not use `--locked`, so a stale lock would not fail anywhere. It has to be committed here.

- [ ] **Step 2: Vendor the schema**

Run in Git Bash, not PowerShell, because PowerShell 5.1 `>` re-encodes the file:

```bash
mkdir -p tests/fixtures/odcs
touch tests/fixtures/__init__.py tests/fixtures/odcs/__init__.py
gh api -H "Accept: application/vnd.github.raw" \
  "repos/bitol-io/open-data-contract-standard/contents/schema/odcs-json-schema-v3.2.0.json?ref=v3.2.0" \
  > tests/fixtures/odcs/odcs-json-schema-v3.2.0.json
sha256sum tests/fixtures/odcs/odcs-json-schema-v3.2.0.json
```

Expected: `edb41f33ec46e84780e99872ab2bd67f074959d2bf3e9c9fc54e61f8982b0d93`

- [ ] **Step 3: Write the test fixtures**

Create `tests/fixtures/odcs/sample_contract.py`:

```python
"""Contracts for the ODCS tests. CI lints what `sample_contract` emits."""

import uuid
from datetime import datetime, timezone
from typing import Any

import yaml

from backend.domain.entities.data_contract import DataContract
from backend.use_cases.data_contract.odcs import to_odcs

NOW = datetime(2026, 11, 1, tzinfo=timezone.utc)
SAMPLE_ID = uuid.UUID("3f2a1c9e-8b7d-4e6f-a5c4-1d2e3f4a5b6c")


def make_field(name="id", type="string", description="", nullable=True, primary_key=False):
    return {"name": name, "type": type, "description": description,
            "nullable": nullable, "primary_key": primary_key}


def make_rule(dimension="completeness", column="", operator=">=", threshold="99",
              description=""):
    return {"dimension": dimension, "column": column, "operator": operator,
            "threshold": threshold, "description": description}


def make_contract(**overrides) -> DataContract:
    values = {
        "id": SAMPLE_ID, "title": "Orders", "version": "1.0.0", "owner": "alice",
        "domain": "commerce", "tier": 2, "status": "draft",
        "models": {"fields": [], "quality": []},
        "servicelevels": dict.fromkeys(
            ["freshness", "availability", "retention", "latency"], ""
        ),
        "created_at": NOW, "updated_at": NOW,
    }
    return DataContract(**{**values, **overrides})


def sample_contract() -> DataContract:
    return make_contract(
        title="Customer Orders", version="1.2.0", owner="sales-team",
        status="in_review",
        models={
            "fields": [
                make_field("order_id", "string", "Order identifier", False, True),
                make_field("amount", "float", "Order total in BRL"),
                make_field("created_at", "timestamp", nullable=False),
            ],
            "quality": [
                make_rule("freshness", "", "<=", "24h"),
                make_rule("completeness", "order_id", ">=", "99.5",
                          "Every order has an id"),
                make_rule("validity", "currency", "=", "BRL", "Only BRL orders"),
            ],
        },
        servicelevels={"freshness": "24h", "availability": "99.9%",
                       "retention": "one year", "latency": ""},
    )


def emit(contract: DataContract) -> dict[str, Any]:
    """`to_odcs` output after a trip through YAML, like a file in the repository."""
    return yaml.safe_load(yaml.dump(to_odcs(contract), sort_keys=False))
```

- [ ] **Step 4: Write the failing test**

Create `tests/unit/use_cases/data_contract/test_odcs_emit.py`:

```python
import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from backend.use_cases.data_contract.odcs import to_odcs
from tests.fixtures.odcs.sample_contract import (
    emit,
    make_contract,
    make_field,
    make_rule,
    sample_contract,
)

SCHEMA = Path(__file__).parents[3] / "fixtures/odcs/odcs-json-schema-v3.2.0.json"
VALIDATOR = jsonschema.Draft201909Validator(
    json.loads(SCHEMA.read_text(encoding="utf-8"))
)

EXPECTED_YAML = """\
apiVersion: v3.2.0
kind: DataContract
id: 3f2a1c9e-8b7d-4e6f-a5c4-1d2e3f4a5b6c
name: Customer Orders
version: 1.2.0
status: proposed
domain: commerce
team:
  name: sales-team
schema:
- name: customer_orders
  logicalType: object
  physicalType: table
  properties:
  - name: order_id
    description: Order identifier
    logicalType: string
    required: true
    primaryKey: true
    quality:
    - type: text
      dimension: completeness
      description: Every order has an id
      customProperties:
      - property: dmpltDimension
        value: completeness
      - property: dmpltOperator
        value: '>='
      - property: dmpltThreshold
        value: '99.5'
      - property: dmpltPosition
        value: 1
  - name: amount
    description: Order total in BRL
    logicalType: number
    required: false
    primaryKey: false
  - name: created_at
    description: ''
    logicalType: timestamp
    required: true
    primaryKey: false
  quality:
  - type: text
    dimension: timeliness
    description: Freshness of the table must be <= 24h.
    customProperties:
    - property: dmpltDimension
      value: freshness
    - property: dmpltOperator
      value: <=
    - property: dmpltThreshold
      value: 24h
    - property: dmpltPosition
      value: 0
  - type: text
    dimension: conformity
    description: Only BRL orders
    customProperties:
    - property: dmpltDimension
      value: validity
    - property: dmpltOperator
      value: '='
    - property: dmpltThreshold
      value: BRL
    - property: dmpltColumn
      value: currency
    - property: dmpltPosition
      value: 2
slaProperties:
- property: freshness
  value: 24
  unit: h
- property: availability
  value: 99.9
  unit: '%'
- property: retention
  value: one year
customProperties:
- property: tier
  value: 2
"""


def _custom(rule: dict) -> dict:
    return {entry["property"]: entry["value"] for entry in rule["customProperties"]}


def test_representative_contract_maps_to_expected_document():
    assert to_odcs(sample_contract()) == yaml.safe_load(EXPECTED_YAML)


@pytest.mark.parametrize(
    "contract",
    [
        sample_contract(),
        make_contract(),
        make_contract(title="", owner=""),
        make_contract(models={"fields": [], "quality": [make_rule(column="ghost")]}),
        make_contract(models={"fields": [make_field()], "quality": []}),
        make_contract(models={"quality": [{"dimension": "not-in-the-model"}]}),
    ],
    ids=["sample", "empty", "blank", "only-quality", "only-fields", "partial-rule"],
)
def test_output_is_valid_against_the_official_schema(contract):
    assert list(VALIDATOR.iter_errors(emit(contract))) == []


def test_schema_validator_rejects_a_legacy_document():
    assert list(VALIDATOR.iter_errors({"dataContractSpecification": "0.9.3"}))


@pytest.mark.parametrize(
    ("status", "expected"),
    [("draft", "draft"), ("in_review", "proposed"), ("active", "active"),
     ("deprecated", "deprecated")],
)
def test_status_mapping(status, expected):
    assert to_odcs(make_contract(status=status))["status"] == expected


def test_field_mapping():
    field = make_field("a", "float", "text", nullable=False, primary_key=True)
    doc = to_odcs(make_contract(models={"fields": [field], "quality": []}))
    assert doc["schema"][0]["properties"] == [
        {"name": "a", "description": "text", "logicalType": "number",
         "required": True, "primaryKey": True}
    ]


def test_schema_omitted_without_fields_and_quality():
    assert "schema" not in to_odcs(make_contract())


@pytest.mark.parametrize(
    ("title", "expected"),
    [("Customer Orders", "customer_orders"),
     ("Pedidos de Exportação", "pedidos_de_exportacao"),
     ("  --- ", "contract"), ("", "contract")],
)
def test_schema_name_is_a_snake_case_slug(title, expected):
    models = {"fields": [make_field()], "quality": []}
    doc = to_odcs(make_contract(title=title, models=models))
    assert doc["schema"][0]["name"] == expected


@pytest.mark.parametrize(
    ("field", "column", "under_property", "dmplt_column"),
    [("id", "id", True, None), ("id", "ghost", False, "ghost"),
     ("id", "", False, None), ("", "", False, None)],
)
def test_rule_placement(field, column, under_property, dmplt_column):
    models = {"fields": [make_field(field)], "quality": [make_rule(column=column)]}
    schema = to_odcs(make_contract(models=models))["schema"][0]
    prop = schema["properties"][0]
    owner, other = (prop, schema) if under_property else (schema, prop)
    assert "quality" not in other
    assert owner["quality"][0]["type"] == "text"
    assert _custom(owner["quality"][0]).get("dmpltColumn") == dmplt_column


@pytest.mark.parametrize(
    ("dimension", "expected"),
    [("completeness", "completeness"), ("uniqueness", "uniqueness"),
     ("freshness", "timeliness"), ("validity", "conformity"),
     ("integrity", "consistency")],
)
def test_dimension_mapping_keeps_the_original_value(dimension, expected):
    models = {"fields": [], "quality": [make_rule(dimension=dimension)]}
    rule = to_odcs(make_contract(models=models))["schema"][0]["quality"][0]
    assert rule["dimension"] == expected
    assert _custom(rule)["dmpltDimension"] == dimension


def test_rule_without_description_gets_a_sentence():
    models = {"fields": [], "quality": [make_rule("freshness", "", "<=", "24h"),
                                        make_rule("validity", "ghost", "=", "BRL")]}
    rules = to_odcs(make_contract(models=models))["schema"][0]["quality"]
    assert rules[0]["description"] == "Freshness of the table must be <= 24h."
    assert rules[1]["description"] == "Validity of column ghost must be = BRL."


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("24h", {"value": 24, "unit": "h"}),
     ("99.9%", {"value": 99.9, "unit": "%"}),
     ("365d", {"value": 365, "unit": "d"}),
     ("100.0%", {"value": 100.0, "unit": "%"}),
     ("30m", {"value": 30, "unit": "min"}),
     ("24", {"value": 24})],
)
def test_sla_value_is_split(raw, expected):
    doc = to_odcs(make_contract(servicelevels={"freshness": raw}))
    assert doc["slaProperties"] == [{"property": "freshness", **expected}]


@pytest.mark.parametrize(
    "raw", ["hourly", "24 h", "1.50h", "007", "5percent", "30min", "24h\n", "٣h"]
)
def test_sla_value_that_cannot_be_rebuilt_stays_a_string(raw):
    doc = to_odcs(make_contract(servicelevels={"freshness": raw}))
    assert doc["slaProperties"] == [{"property": "freshness", "value": raw}]


def test_empty_sla_values_are_omitted():
    assert "slaProperties" not in to_odcs(make_contract())
```

- [ ] **Step 5: Run it to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/use_cases/data_contract/test_odcs_emit.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'backend.use_cases.data_contract.odcs'`.

- [ ] **Step 6: Implement `to_odcs` in `backend/use_cases/data_contract/odcs.py`**

Define `ODCS_API_VERSION`, `OdcsParseError` and `ParsedContract` as the spec's Shared Interfaces fix them. `to_odcs(contract: DataContract) -> dict[str, Any]` follows the spec's "ODCS Mapping (Plan 1)", with this key order, which `EXPECTED_YAML` pins:

- Document: `apiVersion`, `kind`, `id`, `name`, `version`, `status`, `domain`, `team`, `schema`, `slaProperties`, `customProperties`.
- Schema object: `name`, `logicalType`, `physicalType`, `properties`, `quality`.
- Property: `name`, `description`, `logicalType`, `required`, `primaryKey`, `quality`.
- Rule: `type`, `dimension`, `description`, `customProperties`, the last in the order `dmpltDimension`, `dmpltOperator`, `dmpltThreshold`, `dmpltColumn`, `dmpltPosition`.

Rules for the choices the mapping leaves open:

- `description` and `required`/`primaryKey` are always written, even when empty or false. `quality`, `properties`, `schema` and `slaProperties` are omitted when empty.
- A column is known only when it is non-empty and equals a field name. `dmpltColumn` is written only for a non-empty unknown column. `dmpltPosition` is the rule's index in `models.quality`.
- A stored dimension outside the five mapped ones gets no ODCS `dimension`, and keeps `dmpltDimension`.
- Read stored rules and fields with `.get`, and `models` with `.get("fields") or []`. Rows synced from legacy files can be partial, and `GET /yaml` calls this outside any `try`.
- SLA entries iterate `contract.servicelevels.items()`, skip falsy values, and pass `str(raw)` to `_to_sla_entry`.
- `_schema_name`: fold accents with `unicodedata.normalize("NFKD", title).encode("ascii", "ignore")`, lowercase, replace `[^a-z0-9]+` with `_`, strip `_`, fall back to `contract`.

These are exact, because Task 3 depends on them. The two unit maps implement spec decision 4: ODCS gets `%` and `min`, and `percent` and `m` are read as aliases.

```python
_SLA_VALUE = re.compile(r"(\d+(?:\.\d+)?)\s*([a-zA-Z%]+)?")
_ODCS_UNIT = {"m": "min"}
_STORED_UNIT = {"min": "m", "percent": "%"}


def _rule_sentence(dimension: Any, column: str, operator: Any, threshold: Any) -> str:
    target = f"column {column}" if column else "the table"
    return f"{str(dimension).capitalize()} of {target} must be {operator} {threshold}."


def _sla_text(value: Any, unit: str | None) -> str:
    return f"{value}{_STORED_UNIT.get(unit, unit) or ''}"


def _to_sla_entry(key: str, raw: str) -> dict[str, Any]:
    match = _SLA_VALUE.fullmatch(raw)
    if match:
        number, unit = match.groups()
        value = float(number) if "." in number else int(number)
        odcs_unit = _ODCS_UNIT.get(unit, unit)
        if _sla_text(value, odcs_unit) == raw:
            entry: dict[str, Any] = {"property": key, "value": value}
            if odcs_unit:
                entry["unit"] = odcs_unit
            return entry
    return {"property": key, "value": raw}
```

- [ ] **Step 7: Run the tests and lint**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/use_cases/data_contract/test_odcs_emit.py -q`
Expected: `43 passed`.

Run: `.venv\Scripts\python.exe -m ruff check backend`, then `.venv\Scripts\python.exe -m ruff format backend/use_cases/data_contract/odcs.py`
Expected: no errors.

- [ ] **Step 8: Commit**

```powershell
git add pyproject.toml uv.lock backend/use_cases/data_contract/odcs.py tests/fixtures tests/unit/use_cases/data_contract/test_odcs_emit.py
$env:PATH = "$PWD\.venv\Scripts;$env:PATH"; git commit -m "feat(data-contract): add ODCS v3.2.0 mapper"
```

---

### Task 3: Parse ODCS with `from_odcs`

**Files:**
- Modify: `backend/use_cases/data_contract/odcs.py`
- Test: `tests/unit/use_cases/data_contract/test_odcs_parse.py`

**Interfaces:**
- Consumes: `to_odcs`, `_rule_sentence`, `_sla_text` and the `sample_contract.py` helpers from Task 2.
- Produces: `from_odcs(doc: dict[str, Any]) -> ParsedContract`, which raises only `OdcsParseError` on bad input, and the key constants plans 3 to 5 extend: `_DOCUMENT_KEYS`, `_TEAM_KEYS`, `_SCHEMA_KEYS`, `_PROPERTY_KEYS`, `_RULE_KEYS`, `_RULE_CUSTOM_KEYS`, `_SLA_ENTRY_KEYS`, `_DB_STATUSES`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/use_cases/data_contract/test_odcs_parse.py`:

```python
import itertools

import pytest

from backend.domain.entities.data_contract import DataContract
from backend.use_cases.data_contract.odcs import (
    OdcsParseError,
    ParsedContract,
    from_odcs,
    to_odcs,
)
from tests.fixtures.odcs.sample_contract import (
    emit,
    make_contract,
    make_field,
    make_rule,
    sample_contract,
)


def _assert_round_trip(c: DataContract) -> None:
    assert from_odcs(emit(c)) == ParsedContract(
        id=c.id, title=c.title, version=c.version, owner=c.owner, domain_name=c.domain,
        tier=c.tier, status=c.status, models=c.models, servicelevels=c.servicelevels,
    )


def _doc(**overrides) -> dict:
    return {**to_odcs(sample_contract()), **overrides}


def test_round_trip_representative_contract():
    _assert_round_trip(sample_contract())


@pytest.mark.parametrize(
    ("status", "tier"),
    itertools.product(["draft", "in_review", "active", "deprecated"], [1, 2, 3, 4]),
)
def test_round_trip_status_and_tier(status, tier):
    _assert_round_trip(make_contract(status=status, tier=tier))


@pytest.mark.parametrize(
    ("field_type", "nullable", "primary_key"),
    itertools.product(
        ["string", "integer", "float", "boolean", "date", "timestamp"],
        [True, False],
        [True, False],
    ),
)
def test_round_trip_field(field_type, nullable, primary_key):
    field = make_field("a", field_type, "text", nullable, primary_key)
    _assert_round_trip(make_contract(models={"fields": [field], "quality": []}))


@pytest.mark.parametrize(
    ("dimension", "column", "operator", "description"),
    itertools.product(
        ["completeness", "freshness", "uniqueness", "validity", "integrity"],
        ["", "a", "ghost"],
        [">=", "<=", "="],
        ["", "free text"],
    ),
)
def test_round_trip_rule(dimension, column, operator, description):
    rule = make_rule(dimension, column, operator, "0.99", description)
    models = {"fields": [make_field("a")], "quality": [rule]}
    _assert_round_trip(make_contract(models=models))


@pytest.mark.parametrize("order", itertools.permutations(["z", "a", "", "ghost"]))
def test_round_trip_keeps_rule_order(order):
    models = {"fields": [make_field("z"), make_field("a")],
              "quality": [make_rule(column=column) for column in order]}
    _assert_round_trip(make_contract(models=models))


@pytest.mark.parametrize(
    "raw",
    ["24h", "99.9%", "365d", "1h", "30m", "24", "100.0%", "hourly", "24 h", "1.50h",
     "007", "5percent", "30min", "24h\n", "99.90%", "99%uptime", "1e5", "٣h"],
)
def test_round_trip_sla_value(raw):
    levels = {"freshness": raw, "availability": "", "retention": "", "latency": ""}
    _assert_round_trip(make_contract(servicelevels=levels))


def test_sla_unit_aliases_are_read():
    doc = _doc(slaProperties=[{"property": "availability", "value": 99, "unit": "percent"},
                              {"property": "latency", "value": 30, "unit": "m"}])
    levels = from_odcs(doc).servicelevels
    assert (levels["availability"], levels["latency"]) == ("99%", "30m")


def test_description_differing_from_the_sentence_is_kept():
    doc = to_odcs(make_contract(models={"fields": [], "quality": [make_rule()]}))
    doc["schema"][0]["quality"][0]["description"] = "Edited by hand"
    assert from_odcs(doc).models["quality"][0]["description"] == "Edited by hand"


def test_sla_key_outside_the_four_is_kept():
    doc = _doc(slaProperties=[{"property": "endOfSupport", "value": "2030-01-01"}])
    assert from_odcs(doc).servicelevels == {
        "freshness": "", "availability": "", "retention": "", "latency": "",
        "endOfSupport": "2030-01-01",
    }


def test_missing_tier_means_4():
    doc = _doc()
    del doc["customProperties"]
    assert from_odcs(doc).tier == 4


def test_missing_domain_is_empty_for_the_sync_to_report():
    doc = _doc()
    del doc["domain"]
    assert from_odcs(doc).domain_name == ""


def test_version_read_as_a_number_is_kept_as_text():
    assert from_odcs(_doc(version=1.0)).version == "1.0"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"apiVersion": "v2.2.2"}, "apiVersion 'v2.2.2'"),
        ({"kind": "DataProduct"}, "kind 'DataProduct'"),
        ({"schema": [{"name": "a"}, {"name": "b"}]}, "2 schema objects"),
        ({"status": "retired"}, "status 'retired'"),
        ({"id": "not-a-uuid"}, "not a UUID"),
        ({"team": [{"username": "a"}]}, "deprecated array"),
        ({"servers": []}, "unsupported keys: servers"),
        ({"team": {"name": "a", "members": []}}, "team has unsupported keys: members"),
        ({"customProperties": [{"property": "cost", "value": 1}]},
         "customProperties has unsupported keys: cost"),
        ({"customProperties": [{"property": "tier", "value": 9}]}, "tier must be"),
        ({"customProperties": [{"property": "tier", "value": "2"}]}, "tier must be"),
        ({"slaProperties": [{"property": "a", "value": 1, "driver": "x"}]}, "driver"),
        ({"slaProperties": [{"property": "a", "value": None}]}, "no storable value"),
        ({"slaProperties": [{"property": "a", "value": True}]}, "no storable value"),
        ({"slaProperties": [{"value": 1}]}, "malformed"),
    ],
)
def test_parse_errors(overrides, message):
    with pytest.raises(OdcsParseError, match=message):
        from_odcs(_doc(**overrides))


@pytest.mark.parametrize(
    "logical", ["time", "object", "array", "map", "vector", None]
)
def test_logical_type_the_model_cannot_hold(logical):
    prop = {"name": "b", "logicalType": logical}
    with pytest.raises(OdcsParseError, match=f"logicalType {logical!r}"):
        from_odcs(_doc(schema=[{"name": "a", "properties": [prop]}]))


@pytest.mark.parametrize(
    "rule",
    [{"type": "library", "metric": "nullValues", "mustBe": 0},
     {"type": "text", "description": "Hand written"}],
    ids=["library", "text-without-dmplt"],
)
def test_rule_outside_the_stored_format_is_rejected(rule):
    with pytest.raises(OdcsParseError, match="quality rule on the schema"):
        from_odcs(_doc(schema=[{"name": "a", "quality": [rule]}]))
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/use_cases/data_contract/test_odcs_parse.py -q`
Expected: collection error, `ImportError: cannot import name 'from_odcs'`.

- [ ] **Step 3: Implement `from_odcs(doc: dict[str, Any]) -> ParsedContract` in `odcs.py`**

Add these constants. Plans 3 to 5 extend them when they add a mapping:

```python
_DB_STATUSES = frozenset({"draft", "in_review", "active", "deprecated"})
_DOCUMENT_KEYS = frozenset(
    {"apiVersion", "kind", "id", "name", "version", "status", "domain", "team",
     "schema", "slaProperties", "customProperties"}
)
_TEAM_KEYS = frozenset({"name"})
_SCHEMA_KEYS = frozenset(
    {"name", "logicalType", "physicalType", "properties", "quality"}
)
_PROPERTY_KEYS = frozenset(
    {"name", "description", "logicalType", "required", "primaryKey", "quality"}
)
_RULE_KEYS = frozenset({"type", "dimension", "description", "customProperties"})
_RULE_CUSTOM_KEYS = frozenset(
    {"dmpltDimension", "dmpltOperator", "dmpltThreshold", "dmpltColumn",
     "dmpltPosition"}
)
_SLA_ENTRY_KEYS = frozenset({"property", "value", "unit"})
```

`from_odcs` wraps a private `_parse(doc)` and turns `AttributeError`, `KeyError` and `TypeError` into `OdcsParseError(f"malformed ODCS document: {exc!r}")`. `_parse` first raises `unsupported apiVersion {value!r}: expected v3.x`, then `unsupported kind {value!r}: expected DataContract`, then checks the document keys. It delegates each field to a small helper to stay under the complexity limit. A shared `_reject_unknown(mapping, allowed, where)` raises `{where} has unsupported keys: {sorted, comma separated}`.

| `ParsedContract` field | Rule |
|---|---|
| `id` | `uuid.UUID(str(raw))`. On `ValueError`, raise `contract id {raw!r} is not a UUID` |
| `title` | `doc.get("name", "")` |
| `version` | `str(doc.get("version", "1.0.0"))`, because an unquoted `1.0` reads as a float |
| `owner` | `team.name`, or `""` with no team. A list raises `team must be an object, not the deprecated array` |
| `domain_name` | `doc.get("domain", "")`. Sync reports an empty one |
| `tier` | The `tier` custom property, default `4`. Any other custom property is unsupported, with `where` set to `contract customProperties`. Raise `tier must be an integer from 1 to 4, got {tier!r}` unless `type(tier) is int` and it is in range |
| `status` | `proposed` becomes `in_review`, default `draft`. Raise `status {raw!r} is not accepted; expected one of {names}` unless the result is in `_DB_STATUSES`, where `names` is `_DB_STATUSES` sorted and comma separated, with `in_review` shown as `proposed`. Building it from the constant means plan 5 adds `retired` in one place |
| `models` | Always both keys, `{"fields": [...], "quality": [...]}` |
| `servicelevels` | Start from `dict.fromkeys(("freshness", "availability", "retention", "latency"), "")`, then write each entry with `_sla_text(value, unit)`, including keys outside the four. `None` or a `bool` value raises `slaProperties entry {key} has no storable value`. Unknown entry keys use `where` set to `slaProperties entry {key}` |

For `models`:

- More than one schema object raises `contract has {n} schema objects; at most one is supported`.
- A property's `type` comes from a six-entry map, `number` to `float` and the other five identical. Anything else raises `property {name} has logicalType {value!r}, which cannot be stored`.
- A rule under a property takes that property's name as `column`. A rule on the schema object takes `dmpltColumn`, or `""`. Its `where` label for errors is `quality rule on {column}` or `quality rule on the schema`.
- Rule keys and rule custom properties both go through `_reject_unknown`. `dmpltDimension`, `dmpltOperator`, `dmpltThreshold` and `dmpltPosition` are required, and a missing one raises `{where} is missing {keys}`. Stored `dimension` comes from `dmpltDimension`, never from the ODCS `dimension`.
- `description` becomes `""` when it equals `_rule_sentence(...)` rebuilt from the rule's values.
- Collect rules as `(position, rule)` pairs across all properties and the schema object, then sort by position.

- [ ] **Step 4: Run the tests and lint**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/use_cases/data_contract/ -q`
Expected: `255 passed`, which includes the 10 existing sync tests.

Run: `.venv\Scripts\python.exe -m ruff check backend`, then `.venv\Scripts\python.exe -m ruff format backend/use_cases/data_contract/odcs.py`
Expected: no errors, including no `C901`.

- [ ] **Step 5: Commit**

```powershell
git add backend/use_cases/data_contract/odcs.py tests/unit/use_cases/data_contract/test_odcs_parse.py
$env:PATH = "$PWD\.venv\Scripts;$env:PATH"; git commit -m "feat(data-contract): parse ODCS documents back into contracts"
```

---

### Task 4: Read both formats in sync

**Files:**
- Create: `backend/use_cases/data_contract/legacy_dcs.py`
- Create: `backend/use_cases/data_contract/contract_document.py`
- Modify: `backend/use_cases/data_contract/sync_from_github.py:38-84`
- Test: `tests/unit/use_cases/data_contract/test_contract_document.py`
- Test: `tests/unit/use_cases/data_contract/test_sync_from_github.py`

**Interfaces:**
- Consumes: `ParsedContract`, `OdcsParseError`, `from_odcs`, `to_odcs` from `odcs.py`.
- Produces: `from_legacy_dcs(doc: dict[str, Any]) -> ParsedContract` and `parse_contract_document(doc: dict[str, Any]) -> ParsedContract`, which plan 2 reduces to the mapping check plus a call to `from_odcs`.

- [ ] **Step 1: Write the failing dispatch and legacy tests**

Create `tests/unit/use_cases/data_contract/test_contract_document.py`:

```python
import uuid

import pytest
import yaml

from backend.use_cases.data_contract.contract_document import parse_contract_document
from backend.use_cases.data_contract.legacy_dcs import from_legacy_dcs
from backend.use_cases.data_contract.odcs import OdcsParseError, to_odcs
from tests.fixtures.odcs.sample_contract import sample_contract

# contracts/commerce/sales.yaml in GuhBrando/dmplt_data_contract
LEGACY_FILE = """\
dataContractSpecification: 0.9.3
id: 87e003b4-88c3-43b3-9819-d06d592dbb58
info:
  title: Sales
  version: 1.0.0
  owner: alice
  domain: commerce
  status: draft
models:
  fields: []
servicelevels:
  freshness: 24h
  availability: 99%
  retention: 365d
  latency: 1h
x-tier: 2
"""


def test_legacy_file_is_read_with_its_stored_shape():
    parsed = from_legacy_dcs(yaml.safe_load(LEGACY_FILE))
    assert parsed.id == uuid.UUID("87e003b4-88c3-43b3-9819-d06d592dbb58")
    assert (parsed.title, parsed.version, parsed.owner) == ("Sales", "1.0.0", "alice")
    assert (parsed.domain_name, parsed.tier, parsed.status) == ("commerce", 2, "draft")
    assert parsed.models == {"fields": []}
    assert parsed.servicelevels == {"freshness": "24h", "availability": "99%",
                                    "retention": "365d", "latency": "1h"}


def test_legacy_defaults_match_the_previous_sync():
    parsed = from_legacy_dcs({"id": str(uuid.uuid4()), "servicelevels": None})
    assert (parsed.title, parsed.version, parsed.owner) == ("", "1.0.0", "")
    assert (parsed.domain_name, parsed.tier, parsed.status) == ("", 4, "draft")
    assert parsed.models == {}
    assert parsed.servicelevels == {}


def test_legacy_quality_is_merged_into_models():
    doc = yaml.safe_load(LEGACY_FILE)
    doc["quality"] = [{"dimension": "freshness"}]
    assert from_legacy_dcs(doc).models == {
        "fields": [], "quality": [{"dimension": "freshness"}],
    }


def test_marker_routes_to_the_legacy_reader():
    assert parse_contract_document(yaml.safe_load(LEGACY_FILE)).title == "Sales"


def test_no_marker_routes_to_the_odcs_reader():
    parsed = parse_contract_document(to_odcs(sample_contract()))
    assert parsed.title == "Customer Orders"


def test_document_with_neither_format_is_an_odcs_error():
    with pytest.raises(OdcsParseError, match="apiVersion"):
        parse_contract_document({"id": str(uuid.uuid4()), "info": {}})


@pytest.mark.parametrize("doc", [None, [], "text"])
def test_non_mapping_document_is_rejected(doc):
    with pytest.raises(OdcsParseError, match="not a YAML mapping"):
        parse_contract_document(doc)
```

- [ ] **Step 2: Mark the existing sync fixtures as legacy**

Dispatch keys on `dataContractSpecification`, which every real central file has but the test helpers do not. Without this step, 8 of the 10 existing sync tests fail once sync switches. In `test_sync_from_github.py`:

- Add `"dataContractSpecification": "0.9.3",` as the first key of `data` in `_yaml()`.
- Add the same key to the dict dumped in `test_missing_domain_name_adds_error`.
- Add these imports:

```python
from backend.use_cases.data_contract.odcs import to_odcs
from tests.fixtures.odcs.sample_contract import sample_contract
```

Leave `test_exception_during_processing_adds_error` as it is. Its document has no marker and no `apiVersion`, so it still ends in `errors`.

- [ ] **Step 3: Write the failing sync tests**

Append to `tests/unit/use_cases/data_contract/test_sync_from_github.py`:

```python


def _odcs_yaml(**overrides) -> str:
    return yaml.dump({**to_odcs(sample_contract()), **overrides})


async def test_odcs_file_is_upserted_with_the_contract_values(use_case, github, repo):
    contract = sample_contract()
    github.list_all_yaml_contents.return_value = [("c/o.yaml", _odcs_yaml())]
    result = await use_case.execute()
    assert result == {"created": 1, "updated": 0, "errors": []}
    assert repo.upsert.call_args.kwargs == {
        "contract_id": contract.id,
        "title": contract.title,
        "version": contract.version,
        "owner": contract.owner,
        "domain_id": DOMAIN_ID,
        "tier": contract.tier,
        "status": contract.status,
        "models": contract.models,
        "servicelevels": contract.servicelevels,
    }


async def test_odcs_file_without_domain_keeps_the_error_message(use_case, github):
    doc = to_odcs(sample_contract())
    del doc["domain"]
    github.list_all_yaml_contents.return_value = [("x.yaml", yaml.dump(doc))]
    result = await use_case.execute()
    assert result["errors"] == [
        {"path": "x.yaml", "error": "YAML has no domain name; skipped"}
    ]


async def test_unsupported_odcs_key_is_reported_and_nothing_is_written(
    use_case, github, repo
):
    github.list_all_yaml_contents.return_value = [
        ("c/o.yaml", _odcs_yaml(servers=[{"server": "prod", "type": "postgres"}]))
    ]
    result = await use_case.execute()
    assert "unsupported keys: servers" in result["errors"][0]["error"]
    repo.upsert.assert_not_called()


@pytest.mark.parametrize("content", ["", "- a\n- b\n", "just text"])
async def test_non_mapping_file_is_reported_and_the_next_file_still_syncs(
    use_case, github, repo, content
):
    github.list_all_yaml_contents.return_value = [
        ("c/empty.yaml", content),
        ("c/o.yaml", _odcs_yaml()),
    ]
    result = await use_case.execute()
    assert result["created"] == 1
    assert result["errors"] == [
        {"path": "c/empty.yaml", "error": "contract file is not a YAML mapping"}
    ]
```

- [ ] **Step 4: Run them to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/use_cases/data_contract/test_contract_document.py tests/unit/use_cases/data_contract/test_sync_from_github.py -q`
Expected: `test_contract_document.py` fails at collection with `ModuleNotFoundError` for `contract_document`.

- [ ] **Step 5: Create `legacy_dcs.py` and `contract_document.py`**

`from_legacy_dcs(doc)` moves the current reads from `sync_from_github.py:41-48` and the `info.get(...)` calls of its `upsert` unchanged, including `str(doc["id"])`, `int(doc.get("x-tier", 4))`, the `if quality:` merge, and the defaults `""`, `"1.0.0"` and `"draft"`. Do not normalise anything: this reader exists to keep behaviour identical until plan 2 deletes it.

`parse_contract_document(doc)` raises `OdcsParseError("contract file is not a YAML mapping")` unless `isinstance(doc, dict)`, returns `from_legacy_dcs(doc)` when `"dataContractSpecification" in doc`, and otherwise returns `from_odcs(doc)`.

- [ ] **Step 6: Switch `SyncFromGitHubUseCase.execute`**

Replace lines 40-48 with `parsed = parse_contract_document(yaml.safe_load(content))`, importing it from `backend.use_cases.data_contract.contract_document`. In the rest of the `try` block, `yaml_domain` becomes `parsed.domain_name`, `contract_id` becomes `parsed.id`, and the `upsert` keyword arguments take `parsed.title`, `parsed.version`, `parsed.owner`, `parsed.tier`, `parsed.status`, `parsed.models` and `parsed.servicelevels`. The two error messages and the `except Exception` stay exactly as they are.

- [ ] **Step 7: Run the tests and lint**

Run: `.venv\Scripts\python.exe -m pytest tests/ -q`
Expected: `478 passed`.

Run: `.venv\Scripts\python.exe -m ruff check backend`, then `.venv\Scripts\python.exe -m ruff format backend/use_cases/data_contract`
Expected: no errors.

- [ ] **Step 8: Commit**

```powershell
git add backend/use_cases/data_contract/legacy_dcs.py backend/use_cases/data_contract/contract_document.py backend/use_cases/data_contract/sync_from_github.py tests/unit/use_cases/data_contract/test_contract_document.py tests/unit/use_cases/data_contract/test_sync_from_github.py
$env:PATH = "$PWD\.venv\Scripts;$env:PATH"; git commit -m "feat(data-contract): sync reads ODCS and legacy contract files"
```

---

### Task 5: Publish ODCS and lint it in CI

**Files:**
- Modify: `backend/use_cases/data_contract/yaml_builder.py`
- Modify: `tests/fixtures/odcs/sample_contract.py`
- Test: `tests/unit/use_cases/data_contract/test_odcs_emit.py`
- Modify: `.github/workflows/ci.yml`
- Modify: `README.md:375`

**Interfaces:**
- Consumes: `to_odcs`, `sample_contract()` and `EXPECTED_YAML` from Task 2.
- Produces: `assemble_yaml(contract: DataContract) -> str`, unchanged in signature. `python -m tests.fixtures.odcs.sample_contract <output-path>` writes the sample contract. The CI job `odcs-lint` lints every `odcs-lint/*.yaml` it generates, so plan 3 adds a contract by adding one generate line.

- [ ] **Step 1: Write the failing test**

Add `from backend.use_cases.data_contract.yaml_builder import assemble_yaml` to the imports of `test_odcs_emit.py`. Then append to `tests/unit/use_cases/data_contract/test_odcs_emit.py`:

```python


def test_assemble_yaml_emits_the_expected_text():
    assert assemble_yaml(sample_contract()) == EXPECTED_YAML
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/use_cases/data_contract/test_odcs_emit.py::test_assemble_yaml_emits_the_expected_text -q`
Expected: FAIL, the output still starts with `dataContractSpecification: 0.9.3`.

- [ ] **Step 3: Make `assemble_yaml` a thin call**

Its body becomes `yaml.dump(to_odcs(contract), default_flow_style=False, allow_unicode=True, sort_keys=False)`. Remove the unused `Any` import. `backend/interface/routers/data_contract.py` and `domains.py` do not change.

- [ ] **Step 4: Run the full suite**

Run: `.venv\Scripts\python.exe -m pytest tests/ -q`
Expected: `479 passed`. `test_get_data_contract_yaml` and `test_yaml_with_quality_data` in `test_routers.py` pass unchanged.

- [ ] **Step 5: Make the sample writable from the command line**

Add `import sys`, `from pathlib import Path` and `from backend.use_cases.data_contract.yaml_builder import assemble_yaml` to `tests/fixtures/odcs/sample_contract.py`, and append:

```python
if __name__ == "__main__":
    Path(sys.argv[1]).write_text(
        assemble_yaml(sample_contract()), encoding="utf-8", newline="\n"
    )
```

- [ ] **Step 6: Lint a generated contract locally**

Run in Git Bash. `PYTHONUTF8=1` is needed only on Windows, where the CLI otherwise crashes with exit 1 printing its result emoji. The exit code is not the verdict (spec decision 2): lint exits 0 with `result: warning` for a missing `apiVersion` or a wrong `kind`, so read the JSON report:

```bash
.venv/Scripts/python.exe -m tests.fixtures.odcs.sample_contract "$TEMP/sample-contract.yaml"
PYTHONUTF8=1 uvx --from datacontract-cli==1.2.9 datacontract lint "$TEMP/sample-contract.yaml" \
  --output "$TEMP/sample-lint.json" --output-format json
.venv/Scripts/python.exe -c "import json, sys; print(json.load(open(sys.argv[1]))['result'])" "$TEMP/sample-lint.json"
```

Expected: the last command prints `passed`.

- [ ] **Step 7: Add the CI job**

Add to `.github/workflows/ci.yml`, after the `lint` job. `uv sync` has no `--extra dev` on purpose: the job needs only runtime dependencies. The lint step judges the JSON report's `result`, never the exit code (spec decision 2), and lints every file in `odcs-lint/`.

```yaml
  odcs-lint:
    name: ODCS contract lint
    runs-on: ubuntu-latest
    needs: lint

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          enable-cache: true

      - name: Install dependencies
        run: uv sync

      - name: Generate contracts with the real serializer
        run: |
          mkdir -p odcs-lint
          uv run python -m tests.fixtures.odcs.sample_contract odcs-lint/sample.yaml

      - name: Lint the contracts
        run: |
          status=0
          for file in odcs-lint/*.yaml; do
            report="${file%.yaml}.lint.json"
            uvx --from datacontract-cli==1.2.9 datacontract lint "$file" \
              --output "$report" --output-format json || true
            result="$(jq -r '.result // "missing"' "$report" 2>/dev/null || echo missing)"
            echo "$file: datacontract lint result is '$result'"
            if [ "$result" != "passed" ]; then
              echo "::error file=$file::datacontract lint result is '$result', expected 'passed'"
              status=1
            fi
          done
          exit "$status"
```

Run: `uvx --from actionlint-py actionlint .github/workflows/ci.yml`
Expected: no output, exit 0.

- [ ] **Step 8: Correct the ODCS reference**

Replace `README.md:375` with:

```markdown
- **Open Data Contract Standard (ODCS)** — [bitol-io.github.io/open-data-contract-standard](https://bitol-io.github.io/open-data-contract-standard/)
```

This is the first commit to stage `README.md` since `.pre-commit-config.yaml` gained `trailing-whitespace` (commit `d72296b`, 2026-05-01; README.md was last committed on 2026-04-27). 22 README lines end in two spaces, the Markdown hard line break after each bold heading. The hook strips those spaces and fails the commit, and the headings would then run into the following paragraph. On each line `grep -n '  $' README.md` lists, replace the two trailing spaces with a single `\`, which GitHub renders as the same line break and the hook leaves alone.

Run, in Git Bash: `grep -c '  $' README.md`, then `grep -c '[\]$' README.md`
Expected: `0`, then `22`.

- [ ] **Step 9: Run every check CI runs**

Run: `.venv\Scripts\python.exe -m pytest tests/ -q`
Expected: `479 passed`.

Run: `.venv\Scripts\python.exe -m ruff check . --no-fix`, then `.venv\Scripts\python.exe -m ruff format --check .`
Expected: `All checks passed!` and every file already formatted.

Run: `uv lock --check`
Expected: exit 0.

- [ ] **Step 10: Commit**

```powershell
git add backend/use_cases/data_contract/yaml_builder.py tests/fixtures/odcs/sample_contract.py tests/unit/use_cases/data_contract/test_odcs_emit.py .github/workflows/ci.yml README.md
$env:PATH = "$PWD\.venv\Scripts;$env:PATH"; git commit -m "feat(data-contract): emit ODCS from assemble_yaml and lint it in CI"
```
