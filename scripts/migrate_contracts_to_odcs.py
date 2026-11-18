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
import shutil
import subprocess  # nosec B404
import sys
import tempfile
from collections import Counter, defaultdict
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
from backend.use_cases.data_contract.contract_document import (
    is_legacy_document,
    load_contract_yaml,
)
from backend.use_cases.data_contract.legacy_dcs import from_legacy_dcs
from backend.use_cases.data_contract.odcs import (
    ODCS_API_VERSION,
    ParsedContract,
    from_odcs,
)
from backend.use_cases.data_contract.yaml_builder import assemble_yaml

# Keep in step with the odcs-lint job in .github/workflows/ci.yml.
DATACONTRACT_CLI = "datacontract-cli==1.2.9"
# Freezes the CLI's transitive dependencies, as CI's UV_EXCLUDE_NEWER does.
DEPENDENCIES_BEFORE = "2026-11-01T00:00:00Z"
LINT_TIMEOUT_SECONDS = 300
LINT_CONCURRENCY = 4
# The lint subprocess sees only what uv and Python need: never GITHUB_TOKEN or
# the database and JWT secrets that load_dotenv put in this process.
LINT_ENV_KEYS = frozenset(
    {
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "SYSTEMDRIVE",
        "COMSPEC",
        "WINDIR",
        "TEMP",
        "TMP",
        "TMPDIR",
        "HOME",
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
        "XDG_CACHE_HOME",
        "XDG_DATA_HOME",
        "SSL_CERT_FILE",
        "REQUESTS_CA_BUNDLE",
    }
)
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
# to_odcs ignores timestamps; a fixed value keeps the conversion deterministic.
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
# What a malformed file raises while it is read or converted. Anything else is a
# bug in this script and propagates.
_FILE_ERRORS = (yaml.YAMLError, ValueError, KeyError, TypeError)

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


def _lint_env() -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if key.upper() in LINT_ENV_KEYS or key.upper().startswith("UV_")
    }
    return {**env, "PYTHONUTF8": "1", "UV_EXCLUDE_NEWER": DEPENDENCIES_BEFORE}


def _failed_checks(report: dict[str, Any]) -> str:
    failed = [
        f"{check.get('name')}: {check.get('reason')}"
        for check in report.get("checks") or []
        if check.get("result") != "passed"
    ]
    return "; ".join(failed[:5])


def _tail(path: Path) -> str:
    # The file always exists: lint_yaml opens it before running the CLI.
    lines = path.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    return " | ".join(lines[-3:])


def lint_yaml(text: str) -> str | None:
    """Lint one contract. None means passed; a string says why it did not.

    Only the JSON report decides: the CLI exits 0 with result "warning" for a file
    that is not ODCS, and exits 1 on a pass in a cp1252 Windows console.
    """
    uvx = shutil.which("uvx")
    if uvx is None:
        return "could not run datacontract lint: uvx is not on PATH"
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        folder = Path(tmp)
        (folder / "contract.yaml").write_text(text, encoding="utf-8", newline="\n")
        report, stderr = folder / "report.json", folder / "stderr.txt"
        command = [
            uvx,
            "--from",
            DATACONTRACT_CLI,
            "datacontract",
            "lint",
            str(folder / "contract.yaml"),
            "--output",
            str(report),
            "--output-format",
            "json",
        ]
        try:
            # Files, not pipes: a grandchild holding a pipe open would keep a
            # timed-out run waiting on Windows.
            with (folder / "stdout.txt").open("wb") as out, stderr.open("wb") as err:
                subprocess.run(  # nosec B603
                    command,
                    stdout=out,
                    stderr=err,
                    check=False,
                    timeout=LINT_TIMEOUT_SECONDS,
                    env=_lint_env(),
                )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return f"could not run datacontract lint: {exc}"
        try:
            result = json.loads(report.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return f"datacontract lint left no readable report: {exc}; {_tail(stderr)}"
    if not isinstance(result, dict):
        return "datacontract lint left an unexpected report"
    if result.get("result") != "passed":
        return f"lint result is {result.get('result')!r}: {_failed_checks(result)}"
    return None


def _to_entity(parsed: ParsedContract) -> DataContract:
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
        created_at=_EPOCH,
        updated_at=_EPOCH,
    )


def _without_empty(section: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in section.items() if v not in ("", [], {}, None)}


def _comparable(parsed: ParsedContract) -> dict[str, Any]:
    """The contract's values, ignoring the empty ones ODCS omits by design."""
    values = dataclasses.asdict(parsed)
    values["models"] = _without_empty(values["models"])
    values["servicelevels"] = _without_empty(values["servicelevels"])
    return values


def _legacy_problem(doc: dict[str, Any]) -> str | None:
    """What from_legacy_dcs would coerce or drop silently, read from the file."""
    info = doc.get("info", {})
    if not isinstance(info, dict):
        return "info must be an object"
    dropped = sorted(set(doc) - LEGACY_TOP_KEYS) + sorted(
        f"info.{key}" for key in set(info) - LEGACY_INFO_KEYS
    )
    if dropped:
        return f"keys the conversion would drop: {', '.join(dropped)}"
    tier = doc.get("x-tier", 4)
    if type(tier) is not int or not 1 <= tier <= 4:
        return f"x-tier must be an integer from 1 to 4, got {tier!r}"
    models = doc.get("models") or {}
    if isinstance(models, dict) and "quality" in models and doc.get("quality"):
        return "models.quality and quality both hold rules; merge them into one"
    return None


def _convert_legacy(
    file: ContractFile, doc: dict[str, Any], lint: LintFn
) -> FileResult:
    problem = _legacy_problem(doc)
    if problem:
        return FileResult(file.path, "refused", file.sha, reason=problem)

    parsed = from_legacy_dcs(doc)
    converted = assemble_yaml(_to_entity(parsed))
    before = _comparable(parsed)
    after = _comparable(from_odcs(load_contract_yaml(converted)))
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
        doc = load_contract_yaml(file.content)
        if not isinstance(doc, dict):
            raise ValueError("not a YAML mapping")
        if is_legacy_document(doc):
            return _convert_legacy(file, doc, lint)
        if "apiVersion" in doc:
            return _check_odcs(file, doc, lint)
        raise ValueError(
            "cannot tell the format: neither dataContractSpecification, info nor"
            " apiVersion"
        )
    except _FILE_ERRORS as exc:
        reason = f"{type(exc).__name__}: {exc}"
        return FileResult(file.path, "refused", file.sha, reason=reason)


def find_duplicate_ids(results: Iterable[FileResult]) -> dict[str, list[str]]:
    paths_by_id: defaultdict[str, list[str]] = defaultdict(list)
    for result in results:
        if result.action != "refused" and result.contract_id:
            paths_by_id[result.contract_id].append(result.path)
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
    counts = Counter(result.action for result in results)
    print(
        f"Summary: {counts['convert']} to convert, "
        f"{counts['already-odcs']} already ODCS, {counts['refused']} refused"
    )


async def _convert_all(files: list[ContractFile], lint: LintFn) -> list[FileResult]:
    """Convert every file. Each lint is a cold uvx start, so a few run at once."""
    limit = asyncio.Semaphore(LINT_CONCURRENCY)

    async def one(file: ContractFile) -> FileResult:
        async with limit:
            return await asyncio.to_thread(convert_file, file, lint)

    return list(await asyncio.gather(*(one(file) for file in files)))


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
            f"Error: no contract files found in {client.repo}; nothing was migrated",
            file=sys.stderr,
        )
        return 1

    results = await _convert_all(files, lint)
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
                f"Migrate contract to ODCS {ODCS_API_VERSION}: {result.title}",
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
