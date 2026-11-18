import json
import subprocess
import uuid
from dataclasses import replace
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import yaml

import scripts.migrate_contracts_to_odcs as migration
from backend.infra.github_client import ContractFile, GitHubClient
from backend.use_cases.data_contract.odcs import from_odcs


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
def test_real_files_convert_to_the_path_the_app_would_push_to(path, text):
    source = yaml.safe_load(text)
    result = _convert(path, text)
    assert result.action == "convert"
    parsed = from_odcs(yaml.safe_load(result.converted))
    info = source["info"]
    assert (str(parsed.id), parsed.title, parsed.domain_name, parsed.owner) == (
        source["id"], info["title"], info["domain"], info["owner"])
    client = GitHubClient(token="t", repo="a/b")
    assert client.contract_path(parsed.domain_name, parsed.title) == path


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
    ("text", "error"),
    [("", "ValueError"), ("id: [unclosed\n", "ParserError"), ("id: 1\n", "ValueError")],
)
def test_a_file_of_unknown_format_is_refused_naming_the_error(text, error):
    result = _convert("p.yaml", text)
    assert result.action == "refused"
    assert result.reason.startswith(f"{error}: ")


def test_lint_failure_refuses_the_file():
    result = migration.convert_file(
        _file(*REAL_FILES[0]), lambda text: "lint result is 'failed'"
    )
    assert result.action == "refused"
    assert "failed" in result.reason


def test_odcs_file_failing_lint_is_refused_not_left_alone():
    converted = _convert(*REAL_FILES[0]).converted
    result = migration.convert_file(_file("p.yaml", converted), lambda text: "failed")
    assert (result.action, result.reason) == ("refused", "failed")


@pytest.mark.parametrize(("change", "reason"), [
    ({"x-tier": 2.7}, "x-tier must be an integer"),
    ({"x-tier": True}, "x-tier must be an integer"),
    ({"x-tier": 9}, "x-tier must be an integer"),
    ({"info": ["title"]}, "info must be an object"),
    ({"models": {"fields": [], "quality": [{"dimension": "freshness"}]},
      "quality": [{"dimension": "uniqueness"}]}, "both hold rules"),
])
def test_values_the_legacy_reader_would_coerce_or_drop_are_refused(change, reason):
    doc = {**yaml.safe_load(SALES), **change}
    result = _convert("p.yaml", yaml.safe_dump(doc))
    assert result.action == "refused"
    assert reason in result.reason


def test_a_bug_in_the_conversion_is_not_reported_as_a_bad_file(monkeypatch):
    def broken(contract):
        raise AttributeError("a bug, not a bad file")
    monkeypatch.setattr(migration, "assemble_yaml", broken)
    with pytest.raises(AttributeError):
        _convert(*REAL_FILES[0])


def _lint_with(monkeypatch, result, returncode, *, checks=(), stderr=b""):
    seen: dict = {}

    def run(cmd, **kwargs):
        seen.update(kwargs)
        kwargs["stderr"].write(stderr)
        if result is not None:
            report = Path(cmd[cmd.index("--output") + 1])
            body = {"result": result, "checks": list(checks)}
            report.write_text(json.dumps(body), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, returncode)
    monkeypatch.setattr(migration.subprocess, "run", run)
    monkeypatch.setattr(migration.shutil, "which", lambda name: "/bin/uvx")
    return migration.lint_yaml("x"), seen


def test_lint_yaml_trusts_the_report_over_the_exit_code(monkeypatch):
    # rich crashes printing the result in a cp1252 console, after writing the report.
    assert _lint_with(monkeypatch, "passed", 1)[0] is None


def test_lint_yaml_treats_warning_as_failure(monkeypatch):
    assert "warning" in _lint_with(monkeypatch, "warning", 0)[0]


def test_lint_yaml_refuses_when_there_is_no_report(monkeypatch):
    reason, _ = _lint_with(monkeypatch, None, 1, stderr=b"resolution failed\n")
    assert "resolution failed" in reason


def test_lint_reason_names_the_failed_checks(monkeypatch):
    checks = [{"name": "ODCS schema", "result": "failed", "reason": "kind is wrong"},
              {"name": "other", "result": "passed", "reason": ""}]
    reason, _ = _lint_with(monkeypatch, "failed", 1, checks=checks)
    assert reason == "lint result is 'failed': ODCS schema: kind is wrong"


def test_lint_runs_without_the_secrets_of_this_process(monkeypatch):
    for key in ("GITHUB_TOKEN", "ADMIN_PASSWORD", "JWT_SECRET_KEY"):
        monkeypatch.setenv(key, "secret-value")
    _, seen = _lint_with(monkeypatch, "passed", 0)
    env = seen["env"]
    assert "secret-value" not in env.values()
    assert "PATH" in {key.upper() for key in env}
    assert (env["PYTHONUTF8"], env["UV_EXCLUDE_NEWER"]) == (
        "1", migration.DEPENDENCIES_BEFORE)


def test_lint_yaml_refuses_when_uvx_is_not_on_path(monkeypatch):
    monkeypatch.setattr(migration.shutil, "which", lambda name: None)
    assert "uvx is not on PATH" in migration.lint_yaml("x")


def test_lint_yaml_refuses_when_uvx_is_missing(monkeypatch):
    def missing(cmd, **kwargs):
        raise FileNotFoundError("uvx")
    monkeypatch.setattr(migration.subprocess, "run", missing)
    monkeypatch.setattr(migration.shutil, "which", lambda name: "/bin/uvx")
    assert "uvx" in migration.lint_yaml("x")


@pytest.fixture
def repo():
    client = AsyncMock(spec=GitHubClient)
    client.repo = "acme/contracts"
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
    # The shared id warns without blocking.
    assert (
        "WARNING duplicate id 87e003b4-88c3-43b3-9819-d06d592dbb58: "
        "contracts/commerce/sales.yaml, contracts/commerce/updated.yaml"
    ) in out


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
    err = capsys.readouterr().err
    assert "no contract files found in acme/contracts" in err.lower()


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


def test_lint_report_that_is_not_an_object_is_refused(monkeypatch):
    def run(cmd, **kwargs):
        Path(cmd[cmd.index("--output") + 1]).write_text("[]", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0)
    monkeypatch.setattr(migration.subprocess, "run", run)
    monkeypatch.setattr(migration.shutil, "which", lambda name: "/bin/uvx")
    assert migration.lint_yaml("x") == "datacontract lint left an unexpected report"
