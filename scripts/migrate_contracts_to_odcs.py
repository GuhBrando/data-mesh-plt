#!/usr/bin/env python3
"""Convert the contract files in the central repository to ODCS v3.2.0.

One-shot migration from the legacy Data Contract Specification 0.9.3. A file is
converted only when reading the result back gives the same contract and
`datacontract lint` passes. A file that is already ODCS is never rewritten.

Usage:
  python scripts/migrate_contracts_to_odcs.py            dry run, prints the result
  python scripts/migrate_contracts_to_odcs.py --apply    writes to the repository

Environment (or a .env file in the project root):
  GITHUB_TOKEN  - token with write access to the contracts repository
  GITHUB_REPO   - contracts repository, as owner/name

Needs `uvx` on PATH for the lint.
"""

import argparse
import asyncio
import dataclasses
import json
import os
import subprocess  # nosec B404
import sys
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import httpx
import yaml

from backend.domain.entities.data_contract import DataContract
from backend.infra.config import GITHUB_REPO, GITHUB_TOKEN
from backend.infra.github_client import ContractFile, GitHubClient
from backend.use_cases.data_contract.legacy_dcs import from_legacy_dcs
from backend.use_cases.data_contract.odcs import ParsedContract, from_odcs
from backend.use_cases.data_contract.yaml_builder import assemble_yaml

LINT_COMMAND = ["uvx", "--from", "datacontract-cli==1.2.9", "datacontract", "lint"]
LEGACY_TOP_KEYS = frozenset(
    {
        "dataContractSpecification",
        "id",
        "info",
        "models",
        "servicelevels",
        "quality",
        "x-tier",
    }
)
LEGACY_INFO_KEYS = frozenset({"title", "version", "owner", "domain", "status"})

LintFn = Callable[[str], str | None]


@dataclass(frozen=True)
class FileResult:
    path: str
    action: Literal["convert", "already-odcs", "refused"]
    sha: str
    contract_id: str | None = None
    title: str | None = None
    converted: str | None = None
    reason: str = ""


def lint_yaml(text: str) -> str | None:
    """Lint one contract. None means passed; a string says why it did not.

    Only the JSON report decides: the CLI exits 0 with result "warning" for a file
    that is not ODCS, and exits 1 on a pass in a cp1252 Windows console.
    """
    with tempfile.TemporaryDirectory() as tmp:
        contract = Path(tmp) / "contract.yaml"
        report = Path(tmp) / "report.json"
        contract.write_text(text, encoding="utf-8", newline="\n")
        command = [
            *LINT_COMMAND,
            str(contract),
            "--output",
            str(report),
            "--output-format",
            "json",
        ]
        try:
            subprocess.run(  # nosec B603
                command,
                capture_output=True,
                check=False,
                timeout=300,
                env={**os.environ, "PYTHONUTF8": "1"},
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return f"could not run datacontract lint: {exc}"
        try:
            result = json.loads(report.read_text(encoding="utf-8")).get("result")
        except (OSError, ValueError, AttributeError) as exc:
            return f"datacontract lint left no readable report: {exc}"
    if result != "passed":
        return f"lint result is {result!r}, expected 'passed'"
    return None


def _to_entity(parsed: ParsedContract) -> DataContract:
    now = datetime.now(tz=UTC)
    return DataContract(
        id=parsed.id,
        title=parsed.title,
        version=parsed.version,
        owner=parsed.owner,
        domain=parsed.domain_name,
        tier=parsed.tier,
        status=parsed.status,
        models=parsed.models,
        servicelevels=parsed.servicelevels,
        created_at=now,
        updated_at=now,
    )


def _without_empty(section: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in section.items() if v not in ("", [], {}, None)}


def _comparable(parsed: ParsedContract) -> dict[str, Any]:
    """The contract's values, ignoring the empty ones ODCS omits by design."""
    values = dataclasses.asdict(parsed)
    values["models"] = _without_empty(values["models"])
    values["servicelevels"] = _without_empty(values["servicelevels"])
    return values


def _convert_legacy(
    file: ContractFile, doc: dict[str, Any], lint: LintFn
) -> FileResult:
    info = doc.get("info") or {}
    dropped = sorted(set(doc) - LEGACY_TOP_KEYS) + sorted(
        f"info.{key}" for key in set(info) - LEGACY_INFO_KEYS
    )
    if dropped:
        reason = f"keys the conversion would drop: {', '.join(dropped)}"
        return FileResult(file.path, "refused", file.sha, reason=reason)

    parsed = from_legacy_dcs(doc)
    converted = assemble_yaml(_to_entity(parsed))
    before = _comparable(parsed)
    after = _comparable(from_odcs(yaml.safe_load(converted)))
    lost = [field for field in before if before[field] != after[field]]
    if lost:
        reason = f"conversion would change: {', '.join(lost)}"
        return FileResult(file.path, "refused", file.sha, reason=reason)

    failure = lint(converted)
    if failure:
        return FileResult(file.path, "refused", file.sha, reason=failure)
    return FileResult(
        file.path, "convert", file.sha, str(parsed.id), parsed.title, converted
    )


def _check_odcs(file: ContractFile, doc: dict[str, Any], lint: LintFn) -> FileResult:
    parsed = from_odcs(doc)
    failure = lint(file.content)
    if failure:
        return FileResult(file.path, "refused", file.sha, reason=failure)
    return FileResult(file.path, "already-odcs", file.sha, str(parsed.id), parsed.title)


def convert_file(file: ContractFile, lint: LintFn) -> FileResult:
    try:
        doc = yaml.safe_load(file.content)
        if not isinstance(doc, dict):
            raise ValueError("not a YAML mapping")
        legacy = "dataContractSpecification" in doc
        odcs = "apiVersion" in doc
        if legacy == odcs:
            raise ValueError(
                "cannot tell the format: expected exactly one of "
                "dataContractSpecification and apiVersion"
            )
        if odcs:
            return _check_odcs(file, doc, lint)
        return _convert_legacy(file, doc, lint)
    except Exception as exc:
        return FileResult(file.path, "refused", file.sha, reason=str(exc))


def find_duplicate_ids(results: Iterable[FileResult]) -> dict[str, list[str]]:
    paths_by_id: dict[str, list[str]] = {}
    for result in results:
        if result.action != "refused" and result.contract_id:
            paths_by_id.setdefault(result.contract_id, []).append(result.path)
    return {cid: paths for cid, paths in paths_by_id.items() if len(paths) > 1}


def _report(results: list[FileResult]) -> None:
    for result in results:
        detail = f" ({result.reason})" if result.reason else ""
        print(f"{result.action:<12} {result.path}{detail}")
    for result in results:
        if result.action == "convert":
            print()
            print(f"--- {result.path}")
            print(result.converted, end="")
    print()
    for contract_id, paths in find_duplicate_ids(results).items():
        print(f"WARNING duplicate id {contract_id}: {', '.join(paths)}")
    counts = {
        action: sum(1 for result in results if result.action == action)
        for action in ("convert", "already-odcs", "refused")
    }
    print(
        f"Summary: {counts['convert']} to convert, "
        f"{counts['already-odcs']} already ODCS, {counts['refused']} refused"
    )


async def migrate(
    client: GitHubClient, *, apply: bool, lint: LintFn = lint_yaml
) -> int:
    try:
        files = await client.read_contract_files()
    except (RuntimeError, httpx.HTTPError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if not files:
        print(
            f"Error: no contract files found in {GITHUB_REPO}; nothing was migrated",
            file=sys.stderr,
        )
        return 1

    results = [convert_file(file, lint) for file in files]
    _report(results)
    if any(result.action == "refused" for result in results):
        print("Nothing written: fix the refused files first.")
        return 1
    if not apply:
        print("Dry run: nothing written. Re-run with --apply to write.")
        return 0

    failed = False
    for result in results:
        if result.action != "convert":
            continue
        try:
            await client.push(
                result.path,
                result.converted,
                f"Migrate contract to ODCS v3.2.0: {result.title}",
                expected_sha=result.sha,
            )
            print(f"written {result.path}")
        except (RuntimeError, httpx.HTTPError) as exc:
            print(f"failed {result.path}: {exc}", file=sys.stderr)
            failed = True
    return 1 if failed else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write the converted files; without it nothing is written",
    )
    args = parser.parse_args()
    if not GITHUB_TOKEN:
        sys.exit("Error: GITHUB_TOKEN is required")
    client = GitHubClient(token=GITHUB_TOKEN, repo=GITHUB_REPO)
    sys.exit(asyncio.run(migrate(client, apply=args.apply)))


if __name__ == "__main__":
    main()
