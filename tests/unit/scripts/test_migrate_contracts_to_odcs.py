import json
import subprocess
import uuid
from dataclasses import replace
from pathlib import Path

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
