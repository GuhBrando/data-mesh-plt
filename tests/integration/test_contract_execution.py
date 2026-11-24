"""Every library rule the platform emits runs under datacontract-cli 1.2.9.

The contract comes from to_odcs, server included: nothing is added to the
document by hand. Verdicts come from the JSON report, never the exit code.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from backend.domain.contract_metadata import empty_server, server_problems
from backend.domain.quality_rules import (
    PERCENT_METRICS,
    QUALITY_METRICS,
    QUALITY_UNITS,
    find_quality_rule_problems,
)
from backend.use_cases.data_contract.odcs import to_odcs
from tests.quality_rule_builders import library_rule, orders_contract


# uvx resolves the tool's dependencies on every run, so freeze them to the date
# UV_EXCLUDE_NEWER sets in ci.yml: sqlglot 30.34.0 breaks the duplicate check.
CLI = ["uvx", "--exclude-newer", "2026-11-01T00:00:00Z",
       "--from", "datacontract-cli[csv]==1.2.9", "datacontract"]
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

# Two CLI runs in all: each one starts the tool. CI's odcs-lint job lints the
# emitted contracts, so lint is not run here again.

def test_every_metric_and_unit_the_api_accepts_runs_and_passes_on_good_data(tmp_path):
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
    assert server_problems(contract.servers[0]) == []
    proc = _cli(tmp_path, "test", to_odcs(contract))
    overall, checks = _quality_checks(tmp_path)
    assert (proc.returncode, overall) == (0, "passed"), proc.stdout
    assert len(checks) == len(rules)
    assert all(c["result"] == "passed" for c in checks.values())

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
