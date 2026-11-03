# ODCS Central Repository Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert every contract file in `GuhBrando/dmplt_data_contract` to ODCS `v3.2.0`, lint changed contracts in that repository, and remove the legacy DCS reader from the platform.

**Architecture:** A one-shot script reads each file through `GitHubClient`, converts it with Plan 1's pure functions, proves nothing was lost, and writes only with `--apply`. The rollout order is fixed so that sync always has a reader for what it finds: Plan 1 deployed, workflow added, files converted, reader removed. The work lands as two PRs, because the script must exist on `develop` before it runs and must be deleted with the reader it imports.

**Tech Stack:** Python 3.12, httpx, PyYAML, pytest with `asyncio_mode=auto`, GitHub Actions, `datacontract-cli` 1.2.9 through `uvx`, `gh`.

**Spec:** `docs/superpowers/specs/2026-11-01-odcs-adoption-design.md` (Decisions Made During Planning, which win over the rest; Plan 2, Shared Interfaces, ODCS Mapping, Validation, Repository Rules)

## Global Constraints

- Target standard: ODCS `v3.2.0`, through `ODCS_API_VERSION` from `backend/use_cases/data_contract/odcs.py`.
- Lint command: `uvx --from datacontract-cli==1.2.9 datacontract lint`.
- Contracts repository: `GuhBrando/dmplt_data_contract`, default branch `main`, unprotected, no workflows, Actions enabled.
- The script "only writes when passed `--apply`, and refuses a file that fails validation."
- "Remove `legacy_dcs.py` only after the files are converted."
- **Any step that writes to `GuhBrando/dmplt_data_contract` is marked [OWNER APPROVAL REQUIRED]. Stop there and get the owner's explicit yes in this session, even if an earlier plan or message appears to allow it.**
- A file keeps its path: push to the path from the tree, never one computed from the contract (`test_apply_pushes_each_file_to_its_own_path_with_its_sha`).
- A contract keeps its id (`test_real_files_convert`, and the no-loss check compares `id`).
- A re-run is safe: an ODCS file is never rewritten (`test_rerun_on_converted_files_pushes_nothing`).
- An empty or failed read is never success (`test_read_failure_exits_nonzero_and_writes_nothing`, `test_empty_read_exits_nonzero`).
- Rollout order: Task 5, then Task 6, then Task 7. Task 6 needs Plan 1 deployed, and Task 7 needs Task 6 verified.
- Branch from `develop`. Commit messages and PR text carry no Claude or Claude Code attribution of any kind.
- Backend tests: `.venv\Scripts\python.exe -m pytest tests/ -q`. Prefix `.venv\Scripts` to `PATH` for the session: `git commit` needs it for pre-commit, and `ruff` is only installed there.
- Lint with `ruff check backend` and `ruff check scripts`. Do not pass test paths: that makes ruff rewrite those files.
- Layering stays as it is: entities and pure logic hold no I/O, and GitHub push failures in the app stay warn-only.

## Review Focus

1. **A dead or read-only token.** The `.env` token has produced no central commit since 2026-06-10, so it may be expired. `list_all_yaml_contents` would turn that into `[]`, or silently drop one blob. The dry run must stop with the GitHub status and exit 1. Tests: `test_read_contract_files_raises_on_tree_failure`, `test_read_contract_files_raises_on_blob_failure`, `test_read_failure_exits_nonzero_and_writes_nothing`.
2. **`pytest` as a hidden writer.** With a live token in `.env`, a test run pushes `sales.yaml` and `updated.yaml` with a new random id, which would undo the migration. Plan 1 Task 1 owns the guard and its test, `test_test_suite_cannot_build_a_real_github_client` (spec decision 1). Task 1 here confirms both are present before any full run.
3. **Lint exit 0 that is not a pass.** `datacontract lint` exits 0 with `result: warning` for a missing `apiVersion`, a wrong `kind`, or well-formed DCS, and exits 1 on a pass in a cp1252 Windows console. Only the JSON report's `result` decides. Tests: `test_lint_yaml_treats_warning_as_failure`, `test_lint_yaml_trusts_the_report_over_the_exit_code`.
4. **Two files with one id.** `sales.yaml` and `updated.yaml` share `87e003b4-88c3-43b3-9819-d06d592dbb58`. Preserving ids keeps that, so the owner must see it before approving. Test: `test_duplicate_ids_warn_but_do_not_block`.
5. **The app writing the same path mid-run.** `push` looks the sha up just before writing, so a stale conversion would silently replace a newer app push. The script sends the sha it read, and GitHub answers 409. Tests: `test_push_with_stale_expected_sha_raises`, `test_apply_continues_after_a_failed_push`.

## Central Repository Facts

Read on 2026-11-01 at commit `6c08a9ab848cc9102e7a2e89dcbc98f8fd671d67`.

| File | id | Title | Domain | Tier | Fields | Service levels |
|---|---|---|---|---|---|---|
| `contracts/commerce/sales.yaml` | `87e003b4-…dbb58` | Sales | commerce | 2 | none | 24h, 99%, 365d, 1h |
| `contracts/commerce/updated.yaml` | `87e003b4-…dbb58` | Updated | commerce | 2 | none | 24h, 99%, 365d, 1h |
| `contracts/riscos/test.yaml` | `91875ffe-…5719` | test | Riscos | 4 | none | all four `''` |

- No file has quality rules or keys outside the legacy set. All three hand-converted copies pass lint as ODCS v3.2.0, and each `contract_path` equals its current path.
- `sales.yaml` and `updated.yaml` are unit test output, not contracts. They match `_contract()` in `tests/unit/interface/test_routers.py`, and the history holds 19 `Add contract: Sales` and 19 `Update contract: Updated` commits.
- `test.yaml` was created by the app. Its `Riscos` domain must keep its capital in the content while the path stays lowercase.

## Rollout Behaviour

CD runs only on `v*.*.*` tags, so merging is not deploying. The latest deployed tag at the time of writing is `v0.2.8a`, which emits and reads legacy DCS.

| Event | Old app (before Plan 1) | Plan 1 app | After Task 7 is deployed |
|---|---|---|---|
| Sync meets an ODCS file | Reports `YAML has no domain name; skipped`, writes nothing (verified: 0 upserts) | Reads it | Reads it |
| Sync meets a legacy file | Reads it | Reads it | Reports the parse error, skips the file, writes nothing |
| Contract saved through the app | Overwrites the path with legacy DCS, with no conflict | Writes ODCS to the path | Writes ODCS to the path |

So an old app during the migration loses no data, but it fails every sync with one error per file and can silently revert a converted file on any save. The lint workflow turns red on that commit, and a re-run of the script converts the file again. Task 6's first gate exists to rule this case out.

---

## File Structure

**PR 1, Tasks 2 to 4 (Task 1 changes no file):**
- Modify `backend/infra/github_client.py`: strict read, conditional push.
- Modify `tests/unit/infra/test_github_client.py`.
- Create `scripts/migrate_contracts_to_odcs.py`: the migration.
- Create `tests/unit/scripts/__init__.py` and `tests/unit/scripts/test_migrate_contracts_to_odcs.py`.

**`GuhBrando/dmplt_data_contract`, Tasks 5 and 6:**
- Create `.github/workflows/lint-contracts.yml`.
- Convert the files under `contracts/`.

**PR 2, Task 7:**
- Modify `backend/use_cases/data_contract/contract_document.py`.
- Modify `tests/unit/use_cases/data_contract/test_contract_document.py` and `test_sync_from_github.py`: legacy inputs become ODCS or go.
- Delete `backend/use_cases/data_contract/legacy_dcs.py`, the script, `tests/unit/scripts/`, and everything Task 2 added.

---

## Task 1: Confirm Plan 1 and its test-suite guard

Spec decision 1: Plan 1 Task 1 blanks `GITHUB_TOKEN` in `tests/conftest.py`, and this plan only checks that the guard is present. Until it is confirmed, a full `pytest` run with a live token is an unapproved write to the contracts repository. This task changes no file and has no commit.

**Files:** none.

**Interfaces:**
- Consumes: Plan 1 modules `odcs.py`, `legacy_dcs.py`, `contract_document.py`, and Plan 1's guard with its test `tests/unit/infra/test_suite_isolation.py::test_test_suite_cannot_build_a_real_github_client`.
- Produces: confirmation that every later `pytest` run in this plan stays away from GitHub.

- [ ] **Step 1: Confirm Plan 1 is present**

Run: `Test-Path backend\use_cases\data_contract\odcs.py, backend\use_cases\data_contract\legacy_dcs.py, backend\use_cases\data_contract\contract_document.py`
Expected: `True` three times. If not, stop: this plan assumes Plan 1 has shipped.

- [ ] **Step 2: Confirm the guard is present and passes**

Run: `Select-String -Path tests\conftest.py -SimpleMatch -Pattern 'os.environ["GITHUB_TOKEN"] = ""'`, then `.venv\Scripts\python.exe -m pytest tests/unit/infra/test_suite_isolation.py -q`
Expected: one match, then `1 passed`. If either fails, stop and report it: Plan 1 Task 1 has not shipped, and a full run could write to the contracts repository. Do not add the guard here.

- [ ] **Step 3: Run the full suite and confirm the central repository did not move**

Run: `gh api repos/GuhBrando/dmplt_data_contract/commits/main --jq .sha`, then `.venv\Scripts\python.exe -m pytest tests/ -q`, then the `gh api` command again.
Expected: the full suite passes, and both `gh api` outputs are identical.

---

## Task 2: Strict read and conditional push on GitHubClient

`list_all_yaml_contents` stays as it is. Sync depends on its current behaviour, and changing that is out of scope.

**Files:**
- Modify: `backend/infra/github_client.py`
- Test: `tests/unit/infra/test_github_client.py`

**Interfaces:**
- Produces:
  - `class ContractFile(NamedTuple)` with `path: str`, `content: str`, `sha: str`
  - `async def read_contract_files(self) -> list[ContractFile]`, raising `RuntimeError` on any non-success tree or blob response
  - `async def push(self, path: str, content: str, message: str, expected_sha: str | None = None) -> None`, which skips the sha lookup when `expected_sha` is given

- [ ] **Step 1: Write the failing tests**

Add `import base64` and import `ContractFile`. The file already has `_resp`, `_async_client_ctx` and the `client` fixture.

```python
@pytest.fixture
def http():
    mock_http = AsyncMock()
    with patch(
        "backend.infra.github_client.httpx.AsyncClient",
        return_value=_async_client_ctx(mock_http),
    ):
        yield mock_http


def _tree(*items: tuple[str, str]) -> MagicMock:
    return _resp(200, {"tree": [
        {"path": p, "type": "blob", "sha": s, "url": f"https://api.test/blobs/{s}"}
        for p, s in items
    ]})


def _blob(text: str) -> MagicMock:
    return _resp(200, {"content": base64.b64encode(text.encode()).decode()})


async def test_read_contract_files_returns_path_content_and_sha(client, http):
    http.get.side_effect = [
        _tree(("contracts/a/x.yaml", "sha-x"), ("README.md", "sha-r")),
        _blob("id: 1\n"),
    ]
    assert await client.read_contract_files() == [
        ContractFile("contracts/a/x.yaml", "id: 1\n", "sha-x")
    ]


async def test_read_contract_files_raises_on_tree_failure(client, http):
    http.get.return_value = _resp(401, {"message": "Bad credentials"})
    with pytest.raises(RuntimeError, match="401"):
        await client.read_contract_files()


async def test_read_contract_files_raises_on_blob_failure(client, http):
    http.get.side_effect = [
        _tree(("contracts/a/x.yaml", "s")), _resp(403, {"message": "rate limit"}),
    ]
    with pytest.raises(RuntimeError, match="403"):
        await client.read_contract_files()


async def test_list_all_yaml_contents_still_returns_empty_on_failure(client, http):
    http.get.return_value = _resp(401)
    assert await client.list_all_yaml_contents() == []


async def test_push_with_expected_sha_sends_it_without_a_lookup(client, http):
    http.put.return_value = _resp(200, {})
    await client.push("contracts/a/x.yaml", "body", "msg", expected_sha="abc")
    http.get.assert_not_awaited()
    assert http.put.await_args.kwargs["json"]["sha"] == "abc"


async def test_push_with_stale_expected_sha_raises(client, http):
    http.put.return_value = _resp(409, {"message": "does not match"})
    with pytest.raises(RuntimeError, match="409"):
        await client.push("contracts/a/x.yaml", "body", "msg", expected_sha="old")


async def test_push_without_expected_sha_looks_the_sha_up(client, http):
    http.get.return_value = _resp(200, {"sha": "current"})
    http.put.return_value = _resp(200, {})
    await client.push("contracts/a/x.yaml", "body", "msg")
    assert http.put.await_args.kwargs["json"]["sha"] == "current"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/infra/test_github_client.py -q`
Expected: collection error on `ContractFile`.

- [ ] **Step 3: Implement `ContractFile`, `read_contract_files` and `expected_sha` in `backend/infra/github_client.py`**

`read_contract_files` uses the same tree URL, the same `contracts/` and `.yaml` filter, and the same blob decoding as `list_all_yaml_contents`, with `self._raise_for_status(r)` on both responses. The sha is the tree item's `sha`. In `push`, use `expected_sha or await self._get_sha(client, path)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/infra/test_github_client.py -q`
Expected: PASS

- [ ] **Step 5: Lint and commit**

Run: `ruff check backend`
Expected: `All checks passed!`

```bash
git add backend/infra/github_client.py tests/unit/infra/test_github_client.py
git commit -m "feat: add strict contract read and conditional push to GitHubClient"
```

---

## Task 3: Convert one file and prove nothing was lost

**Files:**
- Create: `scripts/migrate_contracts_to_odcs.py`
- Create: `tests/unit/scripts/__init__.py`
- Test: `tests/unit/scripts/test_migrate_contracts_to_odcs.py`

**Interfaces:**
- Consumes: `ContractFile` (Task 2); `from_odcs`, `ParsedContract` (`odcs.py`); `from_legacy_dcs` (`legacy_dcs.py`); `assemble_yaml` (`yaml_builder.py`). Import them by name into the script so tests can patch `migration.from_odcs`.
- Produces, in `scripts/migrate_contracts_to_odcs.py`:
  - `LintFn = Callable[[str], str | None]`: `None` means passed, a string is the reason it did not
  - `def lint_yaml(text: str) -> str | None`
  - `@dataclass(frozen=True) class FileResult` with `path: str`, `action: Literal["convert", "already-odcs", "refused"]`, `sha: str`, `contract_id: str | None = None`, `title: str | None = None`, `converted: str | None = None`, `reason: str = ""`
  - `def convert_file(file: ContractFile, lint: LintFn) -> FileResult`
  - `def find_duplicate_ids(results: Iterable[FileResult]) -> dict[str, list[str]]`

- [ ] **Step 1: Write the failing tests**

The constants are the real files, verbatim. Tests import the script with `import scripts.migrate_contracts_to_odcs as migration`.

```python
SALES = """\
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
UPDATED = SALES.replace("title: Sales", "title: Updated")
RISCOS = """\
dataContractSpecification: 0.9.3
id: 91875ffe-bfcd-48d3-abe7-5fc8319b5719
info:
  title: test
  version: 1.0.0
  owner: teste
  domain: Riscos
  status: draft
models:
  fields: []
servicelevels:
  latency: ''
  freshness: ''
  retention: ''
  availability: ''
x-tier: 4
"""
REAL_FILES = [
    ("contracts/commerce/sales.yaml", SALES),
    ("contracts/commerce/updated.yaml", UPDATED),
    ("contracts/riscos/test.yaml", RISCOS),
]


def _file(path: str, text: str, sha: str = "sha-1") -> ContractFile:
    return ContractFile(path, text, sha)


def _lint_ok(text: str) -> None:
    return None


def _convert(path: str, text: str) -> migration.FileResult:
    return migration.convert_file(_file(path, text), _lint_ok)


@pytest.mark.parametrize(("path", "text"), REAL_FILES)
def test_real_files_convert(path, text):
    source = yaml.safe_load(text)
    result = _convert(path, text)
    assert result.action == "convert"
    doc = yaml.safe_load(result.converted)
    assert doc["apiVersion"] == "v3.2.0"
    assert doc["kind"] == "DataContract"
    assert doc["id"] == source["id"]
    assert doc["name"] == source["info"]["title"]
    assert doc["domain"] == source["info"]["domain"]
    assert doc["team"]["name"] == source["info"]["owner"]
    assert "dataContractSpecification" not in doc


@pytest.mark.parametrize(("path", "text"), REAL_FILES)
def test_app_would_push_to_the_same_path(path, text):
    parsed = from_odcs(yaml.safe_load(_convert(path, text).converted))
    client = GitHubClient(token="t", repo="a/b")
    assert client.contract_path(parsed.domain_name, parsed.title) == path


def test_empty_service_levels_are_omitted_and_not_a_lost_value():
    result = _convert(*REAL_FILES[2])
    assert result.action == "convert"
    assert "slaProperties" not in yaml.safe_load(result.converted)


def test_parsing_restores_all_four_empty_service_levels():
    # Sync stores this dict, and the contract form needs all four keys.
    parsed = from_odcs(yaml.safe_load(_convert(*REAL_FILES[2]).converted))
    assert parsed.tier == 4
    assert parsed.servicelevels == {
        "freshness": "", "availability": "", "retention": "", "latency": "",
    }


@pytest.mark.parametrize(
    ("field", "change"),
    [
        ("owner", {"owner": "someone-else"}),
        ("id", {"id": uuid.uuid4()}),
        ("servicelevels", {"servicelevels": {}}),
    ],
)
def test_a_value_lost_in_conversion_is_refused(monkeypatch, field, change):
    real = migration.from_odcs
    monkeypatch.setattr(migration, "from_odcs", lambda d: replace(real(d), **change))
    result = _convert(*REAL_FILES[0])
    assert result.action == "refused"
    assert field in result.reason


@pytest.mark.parametrize(
    ("text", "key"),
    [
        (SALES + "terms:\n  usage: internal\n", "terms"),
        (SALES.replace("  status: draft", "  status: draft\n  contact: a@b.c"), "contact"),
    ],
)
def test_a_key_the_conversion_would_drop_is_refused(text, key):
    result = _convert("contracts/a/b.yaml", text)
    assert result.action == "refused"
    assert key in result.reason


def test_already_odcs_is_left_alone():
    converted = _convert(*REAL_FILES[0]).converted
    result = _convert("contracts/commerce/sales.yaml", converted)
    assert result.action == "already-odcs"
    assert result.converted is None
    assert result.contract_id == "87e003b4-88c3-43b3-9819-d06d592dbb58"


def test_odcs_file_the_platform_cannot_read_is_refused():
    converted = _convert(*REAL_FILES[0]).converted
    assert _convert("p.yaml", converted.replace("v3.2.0", "v2.0.0")).action == "refused"


@pytest.mark.parametrize(
    "text",
    [
        "",
        "- a\n",
        "id: [unclosed\n",
        "id: 1\n",
        "dataContractSpecification: 0.9.3\napiVersion: v3.2.0\n",
    ],
)
def test_a_file_of_unknown_format_is_refused(text):
    assert _convert("p.yaml", text).action == "refused"


def test_lint_failure_refuses_the_file():
    result = migration.convert_file(
        _file(*REAL_FILES[0]), lambda text: "lint result is 'failed'"
    )
    assert result.action == "refused"
    assert "failed" in result.reason


def _lint_with(monkeypatch, result, returncode):
    def run(cmd, **kwargs):
        if result is not None:
            report = Path(cmd[cmd.index("--output") + 1])
            report.write_text(json.dumps({"result": result}), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, returncode)
    monkeypatch.setattr(migration.subprocess, "run", run)
    return migration.lint_yaml("x")


def test_lint_yaml_trusts_the_report_over_the_exit_code(monkeypatch):
    # rich crashes printing the result in a cp1252 console, after writing the report.
    assert _lint_with(monkeypatch, "passed", 1) is None


def test_lint_yaml_treats_warning_as_failure(monkeypatch):
    assert "warning" in _lint_with(monkeypatch, "warning", 0)


def test_lint_yaml_refuses_when_there_is_no_report(monkeypatch):
    assert _lint_with(monkeypatch, None, 1) is not None


def test_lint_yaml_refuses_when_uvx_is_missing(monkeypatch):
    def missing(cmd, **kwargs):
        raise FileNotFoundError("uvx")
    monkeypatch.setattr(migration.subprocess, "run", missing)
    assert "uvx" in migration.lint_yaml("x")


def test_find_duplicate_ids_reports_the_shared_id():
    results = [_convert(path, text) for path, text in REAL_FILES]
    assert migration.find_duplicate_ids(results) == {
        "87e003b4-88c3-43b3-9819-d06d592dbb58": [
            "contracts/commerce/sales.yaml",
            "contracts/commerce/updated.yaml",
        ]
    }
```

If `test_parsing_restores_all_four_empty_service_levels` fails because `from_odcs` returns `{}`, fix `from_odcs` to fill the four keys with `""`. Do not relax the test.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/scripts/test_migrate_contracts_to_odcs.py -q`
Expected: collection error, no module `scripts.migrate_contracts_to_odcs`.

- [ ] **Step 3: Implement `lint_yaml` in `scripts/migrate_contracts_to_odcs.py`**

Follow `scripts/seed_admin.py`: shebang, then a docstring stating usage and environment (`GITHUB_TOKEN`, `GITHUB_REPO`). The script runs directly because `backend` is an editable install.

In a `tempfile.TemporaryDirectory`, write the text as UTF-8 and run the Global Constraints lint command plus `<file> --output <report> --output-format json` with `subprocess.run(..., capture_output=True, check=False, timeout=300)`. Ignore the exit code. Return `None` only when the report's `result` is `"passed"`. Return a reason for any other result, a missing or unparseable report, `OSError`, or `subprocess.TimeoutExpired`.

- [ ] **Step 4: Implement `convert_file` and `find_duplicate_ids`**

```text
parse the YAML; a YAML error or a non-mapping is refused
legacy = "dataContractSpecification" in doc; odcs = "apiVersion" in doc
both or neither: refused, the format cannot be told
odcs: from_odcs(doc), then lint(text), then already-odcs (never rewrite)
legacy:
  keys outside LEGACY_TOP_KEYS or LEGACY_INFO_KEYS: refused, naming them
  parsed = from_legacy_dcs(doc)
  converted = assemble_yaml(_to_entity(parsed))
  reparsed = from_odcs(yaml.safe_load(converted))
  any field where _comparable(parsed) != _comparable(reparsed): refused, naming it
  lint(converted), then convert
any exception on the way: refused, with its message
```

- `LEGACY_TOP_KEYS = {"dataContractSpecification", "id", "info", "models", "servicelevels", "quality", "x-tier"}` and `LEGACY_INFO_KEYS = {"title", "version", "owner", "domain", "status"}`. `from_legacy_dcs` cannot report what it ignores, so this check is what stops a silent drop.
- `_to_entity(parsed: ParsedContract) -> DataContract` maps `domain_name` to `domain`, and uses `datetime.now(tz=timezone.utc)` for both timestamps, which `to_odcs` does not emit.
- `_comparable(parsed: ParsedContract) -> dict[str, Any]` is `dataclasses.asdict(parsed)` with values in `""`, `[]`, `{}`, `None` removed from `models` and `servicelevels`. `to_odcs` omits those by design, so strict equality would refuse `test.yaml`.
- Use `assemble_yaml`, which is `to_odcs` plus `yaml.dump`, so the file is byte-for-byte what the app would push.
- `find_duplicate_ids` covers `convert` and `already-odcs` results, keeps only ids seen on more than one path, and keeps the paths in input order.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/scripts/test_migrate_contracts_to_odcs.py -q`
Expected: PASS

- [ ] **Step 6: Lint and commit**

Run: `ruff check scripts`
Expected: `All checks passed!`

```bash
git add scripts/migrate_contracts_to_odcs.py tests/unit/scripts
git commit -m "feat: convert one contract file to ODCS with a no-loss check"
```

---

## Task 4: Dry run and `--apply`

**Files:**
- Modify: `scripts/migrate_contracts_to_odcs.py`
- Test: `tests/unit/scripts/test_migrate_contracts_to_odcs.py`

**Interfaces:**
- Consumes: `read_contract_files`, `push(..., expected_sha=...)` (Task 2); `convert_file`, `find_duplicate_ids`, `lint_yaml`, `LintFn` (Task 3).
- Produces: `async def migrate(client: GitHubClient, *, apply: bool, lint: LintFn = lint_yaml) -> int` returning the exit code, and `def main() -> None`.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.fixture
def repo():
    client = AsyncMock(spec=GitHubClient)
    client.read_contract_files.return_value = [
        _file(path, text, f"sha-{i}") for i, (path, text) in enumerate(REAL_FILES)
    ]
    return client


async def test_dry_run_pushes_nothing_and_prints_the_result(repo, capsys):
    assert await migration.migrate(repo, apply=False, lint=_lint_ok) == 0
    repo.push.assert_not_awaited()
    out = capsys.readouterr().out
    assert "apiVersion: v3.2.0" in out
    assert "Summary: 3 to convert, 0 already ODCS, 0 refused" in out
    assert "nothing written" in out.lower()


async def test_apply_pushes_each_file_to_its_own_path_with_its_sha(repo):
    assert await migration.migrate(repo, apply=True, lint=_lint_ok) == 0
    pushed = [
        (c.args[0], c.kwargs["expected_sha"]) for c in repo.push.await_args_list
    ]
    assert pushed == [
        ("contracts/commerce/sales.yaml", "sha-0"),
        ("contracts/commerce/updated.yaml", "sha-1"),
        ("contracts/riscos/test.yaml", "sha-2"),
    ]
    assert repo.push.await_args_list[0].args[2] == (
        "Migrate contract to ODCS v3.2.0: Sales"
    )


async def test_read_failure_exits_nonzero_and_writes_nothing(repo, capsys):
    repo.read_contract_files.side_effect = RuntimeError("GitHub API 401: Bad credentials")
    assert await migration.migrate(repo, apply=True, lint=_lint_ok) == 1
    repo.push.assert_not_awaited()
    assert "401" in capsys.readouterr().err


async def test_empty_read_exits_nonzero(repo, capsys):
    repo.read_contract_files.return_value = []
    assert await migration.migrate(repo, apply=True, lint=_lint_ok) == 1
    assert "no contract files" in capsys.readouterr().err.lower()


async def test_rerun_on_converted_files_pushes_nothing(repo, capsys):
    repo.read_contract_files.return_value = [
        _file(path, _convert(path, text).converted) for path, text in REAL_FILES
    ]
    assert await migration.migrate(repo, apply=True, lint=_lint_ok) == 0
    repo.push.assert_not_awaited()
    assert "Summary: 0 to convert, 3 already ODCS, 0 refused" in capsys.readouterr().out


async def test_a_refused_file_blocks_every_write(repo):
    repo.read_contract_files.return_value = [
        _file(*REAL_FILES[0]), _file("contracts/x/bad.yaml", "- not a contract\n"),
    ]
    assert await migration.migrate(repo, apply=True, lint=_lint_ok) == 1
    repo.push.assert_not_awaited()


async def test_apply_continues_after_a_failed_push(repo, capsys):
    repo.push.side_effect = [None, RuntimeError("GitHub API 409: stale"), None]
    assert await migration.migrate(repo, apply=True, lint=_lint_ok) == 1
    assert repo.push.await_count == 3
    assert "409" in capsys.readouterr().err


async def test_duplicate_ids_warn_but_do_not_block(repo, capsys):
    assert await migration.migrate(repo, apply=False, lint=_lint_ok) == 0
    assert (
        "WARNING duplicate id 87e003b4-88c3-43b3-9819-d06d592dbb58: "
        "contracts/commerce/sales.yaml, contracts/commerce/updated.yaml"
    ) in capsys.readouterr().out


@pytest.mark.parametrize(("argv", "apply"), [([], False), (["--apply"], True)])
def test_main_is_a_dry_run_unless_told_otherwise(monkeypatch, argv, apply):
    fake = AsyncMock(return_value=0)
    monkeypatch.setattr(migration, "migrate", fake)
    monkeypatch.setattr(migration, "GITHUB_TOKEN", "t")
    monkeypatch.setattr(migration.sys, "argv", ["migrate", *argv])
    with pytest.raises(SystemExit) as exit_info:
        migration.main()
    assert exit_info.value.code == 0
    assert fake.await_args.kwargs["apply"] is apply


def test_main_requires_a_token(monkeypatch):
    monkeypatch.setattr(migration, "GITHUB_TOKEN", "")
    monkeypatch.setattr(migration.sys, "argv", ["migrate"])
    with pytest.raises(SystemExit, match="GITHUB_TOKEN"):
        migration.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/scripts/test_migrate_contracts_to_odcs.py -q`
Expected: the new tests FAIL with `AttributeError` on `migrate`.

- [ ] **Step 3: Implement `migrate` and `main`**

`migrate`, in this order:

1. `read_contract_files()`. On `RuntimeError` or `httpx.HTTPError`, print `Error: <message>` to stderr and return 1.
2. No files: print `Error: no contract files found in <GITHUB_REPO>; nothing was migrated` to stderr and return 1.
3. Run `convert_file` over every file before writing anything.
4. Print one line per file, then the full YAML of each `convert` result. Print `WARNING duplicate id <id>: <path>, <path>` for each duplicate, then `Summary: N to convert, N already ODCS, N refused`.
5. Any refused file: print `Nothing written: fix the refused files first.` and return 1. All-or-nothing makes the outcome clear from the report alone.
6. Not `apply`: print `Dry run: nothing written. Re-run with --apply to write.` and return 0.
7. For each `convert` result, `await client.push(path, converted, f"Migrate contract to ODCS v3.2.0: {title}", expected_sha=sha)`. On `RuntimeError` or `httpx.HTTPError`, print `failed <path>: <message>` to stderr and continue. Return 1 if any failed, otherwise 0.

`main`: `argparse` with a `--apply` store-true flag. An empty `GITHUB_TOKEN` gives `sys.exit("Error: GITHUB_TOKEN is required")`. Otherwise `sys.exit(asyncio.run(migrate(GitHubClient(token=GITHUB_TOKEN, repo=GITHUB_REPO), apply=args.apply)))`. Import `GITHUB_TOKEN` and `GITHUB_REPO` from `backend.infra.config`, which loads `.env`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/scripts/test_migrate_contracts_to_odcs.py -q`
Expected: PASS

- [ ] **Step 5: Run the full suite and lint**

Run: `.venv\Scripts\python.exe -m pytest tests/ -q`, `ruff check backend`, `ruff check scripts`, `ruff format --check scripts backend`
Expected: all pass.

- [ ] **Step 6: Commit and open PR 1**

```bash
git add scripts/migrate_contracts_to_odcs.py tests/unit/scripts/test_migrate_contracts_to_odcs.py
git commit -m "feat: add ODCS migration script with dry run and --apply"
```

Open the PR against `develop`. Merging it writes nothing to the contracts repository. Tasks 5 and 6 run after it is merged.

---

## Task 5: Add the lint workflow to the central repository

The workflow goes in before the conversion, so the conversion commits are its first real input. Added afterwards, nothing would prove it works until someone next changed a contract.

It judges the JSON report's `result`, because lint exits 0 on non-ODCS files. It also skips deleted files, because the app deletes stale paths and those commits match the path filter.

**Files:**
- Create in `GuhBrando/dmplt_data_contract`: `.github/workflows/lint-contracts.yml`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: a check on every push and PR that changes `contracts/**/*.yaml`, which Task 6 relies on.

- [ ] **Step 1: Save this file outside the repository as `lint-contracts.yml`**

The body is fixed. It was run through `actionlint` and against ten git scenarios while writing this plan.

```yaml
name: Lint contracts

on:
  push:
    paths:
      - "contracts/**/*.yaml"
      - ".github/workflows/lint-contracts.yml"
  pull_request:
    paths:
      - "contracts/**/*.yaml"
      - ".github/workflows/lint-contracts.yml"

permissions:
  contents: read

jobs:
  lint:
    name: datacontract lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: astral-sh/setup-uv@v4

      - name: Lint changed contracts
        env:
          BASE_SHA: ${{ github.event.pull_request.base.sha || github.event.before }}
          HEAD_SHA: ${{ github.sha }}
        run: |
          set -euo pipefail

          # A branch's first push has an all-zero "before": compare with the empty tree.
          if [[ "$BASE_SHA" =~ ^0+$ ]]; then
            BASE_SHA="$(git hash-object -t tree /dev/null)"
          fi

          # A separate file, not process substitution: a failed git diff must fail
          # the step instead of looking like "nothing to lint".
          changed="$RUNNER_TEMP/changed-contracts"
          git diff -z --name-only --diff-filter=d "$BASE_SHA" "$HEAD_SHA" \
            -- ':(glob)contracts/**/*.yaml' > "$changed"
          mapfile -d '' files < "$changed"
          echo "Contracts to lint: ${#files[@]}"

          # The result field decides, not the exit code: lint exits 0 with result
          # "warning" for a file that is not ODCS, such as a missing apiVersion.
          status=0
          for file in "${files[@]}"; do
            report="$RUNNER_TEMP/lint-report.json"
            rm -f "$report"
            uvx --from datacontract-cli==1.2.9 datacontract lint "$file" \
              --output "$report" --output-format json || true
            result="$(jq -r '.result // "missing"' "$report" 2>/dev/null || echo missing)"
            if [[ "$result" != "passed" ]]; then
              echo "::error file=$file::datacontract lint result is '$result', expected 'passed'"
              status=1
            fi
          done
          exit "$status"
```

- [ ] **Step 2: Validate it locally**

Run: `uvx --from actionlint-py actionlint lint-contracts.yml`
Expected: no output, exit 0.

- [ ] **Step 3: [OWNER APPROVAL REQUIRED] Show the owner the file and the command in Step 4, and wait for an explicit yes**

This adds one commit to `main` of `GuhBrando/dmplt_data_contract`. Each later contract change uses a minute or two of Actions time on a private repository.

- [ ] **Step 4: [OWNER APPROVAL REQUIRED] Push it**

Run in Git Bash, in the directory holding the file. `gh` has the required `repo` and `workflow` scopes.

```bash
gh api --method PUT repos/GuhBrando/dmplt_data_contract/contents/.github/workflows/lint-contracts.yml \
  -f message="Add datacontract lint workflow" \
  -f branch=main \
  -f content="$(base64 -w0 lint-contracts.yml)"
```

- [ ] **Step 5: Verify the first run**

Run: `gh run list --repo GuhBrando/dmplt_data_contract --workflow lint-contracts.yml --limit 1 --json conclusion,headSha`
Expected: `conclusion` is `success`. Its log says `Contracts to lint: 0`, because the workflow's own path triggered it and no contract changed.

---

## Task 6: Convert the files

This task changes no code in this repository. Run it from `develop` after PR 1 is merged, in Git Bash, from the repository root.

**Files:**
- Modify in `GuhBrando/dmplt_data_contract`: the files under `contracts/`

**Interfaces:**
- Consumes: `scripts/migrate_contracts_to_odcs.py` (Task 4), the workflow (Task 5).
- Produces: a repository where every file is ODCS, which is Task 7's precondition.

- [ ] **Step 1: Gate: Plan 1 must be deployed, not only merged**

```bash
TAG=$(gh run list --repo GuhBrando/data_mesh_plt --workflow cd.yml --status success --limit 1 --json headBranch --jq '.[0].headBranch')
git fetch --tags origin
git merge-base --is-ancestor "$(git log -1 --format=%h -- backend/use_cases/data_contract/odcs.py)" "$TAG"; echo "plan 1 in $TAG: exit $?"
```

Expected: `exit 0`. On exit 1 the deployed app is older than Plan 1: stop and ask the owner to cut a release tag first. Do not continue past this gate, for the reasons under Rollout Behaviour.

- [ ] **Step 2: Gate: no local writer on old code**

Ask the owner to confirm that no local app instance on pre-Plan 1 code is running, and that no branch without Plan 1's test-suite guard (Plan 1 Task 1) will run its tests during this task. `worktree-feat+data-contract-picker` is one such branch. The simplest fix is to blank `GITHUB_TOKEN` in the local `.env`, which is the owner's decision.

- [ ] **Step 3: Record the starting point**

Run: `gh api repos/GuhBrando/dmplt_data_contract/commits/main --jq .sha`
Expected: a sha. Keep it as `PRE_SHA` for rollback. It differs from the sha in Central Repository Facts by the workflow commit from Task 5.

- [ ] **Step 4: Dry run**

Use the `gh` token, because the `.env` token may be dead. Do not print it.

```bash
GITHUB_TOKEN="$(gh auth token)" .venv/Scripts/python.exe scripts/migrate_contracts_to_odcs.py
```

Expected: exit 0, nothing written, and these lines:

```text
WARNING duplicate id 87e003b4-88c3-43b3-9819-d06d592dbb58: contracts/commerce/sales.yaml, contracts/commerce/updated.yaml
Summary: 3 to convert, 0 already ODCS, 0 refused
```

Any refused file or a GitHub error stops the task. Read the printed YAML: each `id` must match Central Repository Facts, and `test.yaml` must keep `domain: Riscos`.

- [ ] **Step 5: [OWNER APPROVAL REQUIRED] Show the owner the dry run and get an explicit yes and a decision on the two fixture files**

The spec leaves this choice to the owner (spec decision 12).

- **Option A:** convert all three. The shared id stays. Sync keeps upserting one row twice, so its title ends as `Updated` and `Sales` never appears. Any sync imports this fixture data into Postgres.
- **Option B:** delete `sales.yaml` and `updated.yaml` first, leaving one real contract. Recommended, because they are test output:

```bash
for F in contracts/commerce/sales.yaml contracts/commerce/updated.yaml; do
  SHA=$(gh api "repos/GuhBrando/dmplt_data_contract/contents/$F" --jq .sha)
  gh api --method DELETE "repos/GuhBrando/dmplt_data_contract/contents/$F" -f message="Remove unit test output: $F" -f sha="$SHA"
done
```

The expected results below are for Option A. Under Option B the counts are 1 instead of 3, Step 7 checks only `test.yaml`, and the delete commits show `Contracts to lint: 0`.

- [ ] **Step 6: [OWNER APPROVAL REQUIRED] Apply**

```bash
GITHUB_TOKEN="$(gh auth token)" .venv/Scripts/python.exe scripts/migrate_contracts_to_odcs.py --apply
```

Expected: exit 0, one `Migrate contract to ODCS v3.2.0: <title>` commit per file. On a failed push, fix the cause and re-run the same command. Files already converted are skipped, and a 409 means the app wrote the file first.

- [ ] **Step 7: Verify the result**

Run the Step 4 dry run again.
Expected: `Summary: 0 to convert, 3 already ODCS, 0 refused`, exit 0.

```bash
gh api "repos/GuhBrando/dmplt_data_contract/git/trees/main?recursive=1" --jq '.tree[] | select(.type=="blob") | .path'
for F in contracts/commerce/sales.yaml contracts/commerce/updated.yaml contracts/riscos/test.yaml; do
  gh api "repos/GuhBrando/dmplt_data_contract/contents/$F" --jq .content | base64 -d | grep -E '^(apiVersion|id):'
done
```

Expected: the same three contract paths plus the workflow file, with `apiVersion: v3.2.0` and the original ids.

- [ ] **Step 8: Verify the workflow judged the conversion**

Run: `gh run list --repo GuhBrando/dmplt_data_contract --workflow lint-contracts.yml --limit 3 --json conclusion,headSha`
Expected: one `success` per conversion commit, each with `Contracts to lint: 1` in its log.

- [ ] **Step 9: Ask the owner to run sync on the deployed app**

`POST /api/v1/data-contracts/sync` as a platform admin.
Expected: `errors` is `[]`, and `created` plus `updated` equals the number of files.

**Rollback [OWNER APPROVAL REQUIRED]:** while Plan 1 is deployed and Task 7 is not, sync reads both formats, so nothing is urgent. To restore a file, read it with `?ref=<PRE_SHA>` and push that content back with the current sha through the Contents API.

---

## Task 7: Remove the legacy reader

`legacy_dcs.py` and the script go together, because the script imports `from_legacy_dcs` and could never run again. `read_contract_files`, `ContractFile` and `expected_sha` go with it, because they have no other caller. The script stays in git history.

**Files:**
- Modify: `backend/use_cases/data_contract/contract_document.py`
- Modify: `backend/infra/github_client.py`
- Modify: `tests/unit/infra/test_github_client.py`
- Modify: `tests/unit/use_cases/data_contract/test_contract_document.py` (the legacy reader's tests go)
- Modify: `tests/unit/use_cases/data_contract/test_sync_from_github.py`
- Delete: `backend/use_cases/data_contract/legacy_dcs.py`
- Delete: `scripts/migrate_contracts_to_odcs.py`
- Delete: `tests/unit/scripts/`

**Interfaces:**
- Consumes: `from_odcs`, `OdcsParseError`, `to_odcs`.
- Produces: `parse_contract_document(doc: dict[str, Any]) -> ParsedContract`, whose body is Plan 1's mapping check, raising `OdcsParseError("contract file is not a YAML mapping")` unless `isinstance(doc, dict)`, followed by `return from_odcs(doc)`. The check stays because Plan 1's `test_non_mapping_document_is_rejected` and `test_non_mapping_file_is_reported_and_the_next_file_still_syncs` pin its message.
- Produces: `_yaml(...)` in `test_sync_from_github.py`, with the same keyword parameters minus `quality`, now returning ODCS. Plan 5 calls it as `_yaml(version=..., status=...)`.

- [ ] **Step 1: Gate: the repository holds no legacy file**

Run: `GITHUB_TOKEN="$(gh auth token)" .venv/Scripts/python.exe scripts/migrate_contracts_to_odcs.py`
Expected: `0 to convert` and `0 refused`, exit 0. Task 6 Step 9 must also have reported no errors. If not, stop: removing the reader now would make sync skip those files.

- [ ] **Step 2: Find every test that feeds legacy input**

Run: `git grep -nE "legacy_dcs|from_legacy_dcs|dataContractSpecification" -- tests`
Keep the list. Plan 1's dispatch tests and the legacy reader's tests are on it.

- [ ] **Step 3: Write the failing tests**

Add to `tests/unit/use_cases/data_contract/test_sync_from_github.py`, importing `parse_contract_document` and `OdcsParseError`.

```python
LEGACY_YAML = yaml.dump({
    "dataContractSpecification": "0.9.3",
    "id": str(CONTRACT_ID),
    "info": {"title": "X", "version": "1.0.0", "owner": "a",
             "domain": "commerce", "status": "draft"},
    "models": {"fields": []},
})


async def test_legacy_file_is_reported_and_skipped(use_case, github, repo):
    github.list_all_yaml_contents.return_value = [("c/x.yaml", LEGACY_YAML)]
    result = await use_case.execute()
    assert result["created"] == 0
    assert result["updated"] == 0
    assert result["errors"][0]["path"] == "c/x.yaml"
    repo.upsert.assert_not_awaited()


def test_parse_contract_document_rejects_legacy_dcs():
    with pytest.raises(OdcsParseError):
        parse_contract_document(yaml.safe_load(LEGACY_YAML))
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/use_cases/data_contract -q`
Expected: both new tests FAIL, because the legacy reader still accepts the file.

- [ ] **Step 5: Reduce `parse_contract_document` to the mapping check plus `return from_odcs(doc)`, then delete the rest**

Delete `legacy_dcs.py`, `scripts/migrate_contracts_to_odcs.py` and `tests/unit/scripts/`. Remove `ContractFile`, `read_contract_files`, the `expected_sha` parameter, and every test Task 2 added, along with the `_tree` and `_blob` helpers. Plan 1's guard in `tests/conftest.py` stays.

Then handle each test from Step 2's list:

- `test_contract_document.py`: delete `LEGACY_FILE`, the `from_legacy_dcs` import, `test_legacy_file_is_read_with_its_stored_shape`, `test_legacy_defaults_match_the_previous_sync`, `test_legacy_quality_is_merged_into_models` and `test_marker_routes_to_the_legacy_reader`. Keep `test_no_marker_routes_to_the_odcs_reader`, `test_document_with_neither_format_is_an_odcs_error` and `test_non_mapping_document_is_rejected`.
- `test_sync_from_github.py`: `_yaml()` drops its `quality` parameter and returns `yaml.dump(to_odcs(DataContract(id=contract_id or CONTRACT_ID, title=title, version=version, owner=owner, domain=domain, tier=tier, status=status, models=models or {}, servicelevels=servicelevels or {}, created_at=NOW, updated_at=NOW)))`. The tests that call it keep their assertions. Delete `test_quality_merged_into_models`, which tests a key only the legacy format has, and `test_missing_domain_name_adds_error`, which Plan 1's `test_odcs_file_without_domain_keeps_the_error_message` replaces.

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/use_cases/data_contract tests/unit/infra -q`
Expected: PASS

- [ ] **Step 7: Sweep for leftovers**

Run: `git grep -nE "legacy_dcs|from_legacy_dcs|dataContractSpecification|x-tier|read_contract_files|expected_sha|ContractFile" -- backend scripts`
Expected: no matches.

Run: `git grep -n "dataContractSpecification" -- tests`
Expected: only `LEGACY_YAML` and Plan 1's `test_schema_validator_rejects_a_legacy_document` in `test_odcs_emit.py`, which checks the JSON Schema, not the reader, and stays.

- [ ] **Step 8: Run the full suite and lint**

Run: `.venv\Scripts\python.exe -m pytest tests/ -q`, `ruff check backend`, `ruff check scripts`
Expected: all pass. `ruff check scripts` still covers `seed_admin.py`.

- [ ] **Step 9: Commit and open PR 2**

```bash
git add -A backend scripts tests
git commit -m "refactor: remove the legacy DCS reader after the contract migration"
```

Open the PR against `develop`. It is safe in any later release, because every file is ODCS and the deployed app only writes ODCS.
