"""What a change to a data contract is worth under the evolution policy.

Pure, standard library only. Works on two ODCS documents, as to_odcs emits them,
so the history does not depend on the internal model.

Policy (README, "Política de Evolução"):
- MAJOR: a property removed or renamed, its logicalType changed, required turned on.
- MINOR: a property added, or a constraint relaxed (required, unique, primaryKey off).
- PATCH: any other content change.

Rules apply only to active and deprecated contracts. Drafts change freely.
"""

import json
import re
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

RETIRED_STATUS = "retired"
GOVERNED_STATUSES = frozenset({"active", "deprecated"})

# Keys that are not content. The first three cannot differ between two versions
# of one contract; version and status changing alone are not content changes.
_NON_CONTENT_KEYS = frozenset({"apiVersion", "kind", "id", "version", "status"})
# schema[0].name is the slug of the title, which the top-level name covers.
_SCHEMA_SKIP_KEYS = frozenset({"name", "properties"})
_PROPERTY_SKIP_KEYS = frozenset(
    {"name", "logicalType", "required", "unique", "primaryKey"}
)
# SemVer 2.0 core: no leading zeros, so one version has one spelling.
_SEMVER = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", re.ASCII)


class ChangeKind(IntEnum):
    NONE = 0
    PATCH = 1
    MINOR = 2
    MAJOR = 3


@dataclass(frozen=True)
class ContractChange:
    kind: ChangeKind
    description: str


class ContractEvolutionError(Exception):
    """A change the evolution policy refuses. Not a ValueError: surfaces as 409."""


class RetiredContractError(ContractEvolutionError):
    pass


class ContractVersionConflictError(ContractEvolutionError):
    pass


def is_semver(version: Any) -> bool:
    return isinstance(version, str) and _SEMVER.fullmatch(version) is not None


def _semver(version: str) -> tuple[int, int, int]:
    major, minor, patch = _SEMVER.fullmatch(version).groups()  # type: ignore[union-attr]
    return int(major), int(minor), int(patch)


def _is_empty(value: Any) -> bool:
    # `value is False` keeps 0, which is a value.
    return value is None or value is False or value in ("", [], {})


def _normalize(value: Any) -> Any:
    """Absent, None, False and empty are equal; lists compare without order."""
    if isinstance(value, dict):
        normalized = {key: _normalize(item) for key, item in value.items()}
        return {key: item for key, item in normalized.items() if not _is_empty(item)}
    if isinstance(value, list):
        items = [_normalize(item) for item in value]
        return sorted(
            items, key=lambda item: json.dumps(item, sort_keys=True, default=str)
        )
    return value


def _schema(doc: dict[str, Any]) -> dict[str, Any]:
    # A contract has at most one schema object; pair by position, never by name,
    # or a title change would look like a removed table.
    schemas = doc.get("schema") or []
    return schemas[0] if schemas else {}


def _flag_change(name: str, flag: str, old: dict, new: dict) -> ContractChange | None:
    was_on, is_on = bool(old.get(flag)), bool(new.get(flag))
    if was_on == is_on:
        return None
    if is_on:
        kind = ChangeKind.MAJOR if flag == "required" else ChangeKind.PATCH
        return ContractChange(kind, f"property '{name}' {flag} turned on")
    return ContractChange(ChangeKind.MINOR, f"property '{name}' {flag} turned off")


def _property_changes(name: str, old: dict, new: dict) -> list[ContractChange]:
    changes = []
    if old.get("logicalType") != new.get("logicalType"):
        changes.append(
            ContractChange(
                ChangeKind.MAJOR,
                f"property '{name}' logicalType changed from"
                f" {old.get('logicalType')} to {new.get('logicalType')}",
            )
        )
    for flag in ("required", "unique", "primaryKey"):
        change = _flag_change(name, flag, old, new)
        if change:
            changes.append(change)
    for key in sorted((old.keys() | new.keys()) - _PROPERTY_SKIP_KEYS):
        if old.get(key) != new.get(key):
            changes.append(
                ContractChange(ChangeKind.PATCH, f"property '{name}' {key} changed")
            )
    return changes


def _schema_changes(old: dict, new: dict) -> list[ContractChange]:
    old_props = {p.get("name"): p for p in old.get("properties") or []}
    new_props = {p.get("name"): p for p in new.get("properties") or []}
    changes = [
        ContractChange(ChangeKind.MAJOR, f"property '{name}' removed")
        for name in sorted(old_props.keys() - new_props.keys(), key=str)
    ]
    changes += [
        ContractChange(ChangeKind.MINOR, f"property '{name}' added")
        for name in sorted(new_props.keys() - old_props.keys(), key=str)
    ]
    for name in sorted(old_props.keys() & new_props.keys(), key=str):
        changes += _property_changes(name, old_props[name], new_props[name])
    for key in sorted((old.keys() | new.keys()) - _SCHEMA_SKIP_KEYS):
        if old.get(key) != new.get(key):
            changes.append(ContractChange(ChangeKind.PATCH, f"schema {key} changed"))
    return changes


def describe_changes(old: dict, new: dict) -> list[ContractChange]:
    old, new = _normalize(old), _normalize(new)
    changes = _schema_changes(_schema(old), _schema(new))
    # Deny-list: a key a later plan emits counts as PATCH instead of being ignored.
    skip = _NON_CONTENT_KEYS | {"schema"}
    for key in sorted((old.keys() | new.keys()) - skip):
        if old.get(key) != new.get(key):
            changes.append(ContractChange(ChangeKind.PATCH, f"{key} changed"))
    return changes


def required_bump(changes: list[ContractChange]) -> ChangeKind:
    """The smallest version bump that covers every change."""
    return max((change.kind for change in changes), default=ChangeKind.NONE)


def version_bump(old: str, new: str) -> ChangeKind | None:
    """What moving from old to new is worth; None when new is lower.

    A non-semver value on either side counts as MAJOR.
    """
    if old == new:
        return ChangeKind.NONE
    if not (is_semver(old) and is_semver(new)):
        return ChangeKind.MAJOR
    before, after = _semver(old), _semver(new)
    if after < before:
        return None
    if after[0] > before[0]:
        return ChangeKind.MAJOR
    if after[1] > before[1]:
        return ChangeKind.MINOR
    return ChangeKind.PATCH


def is_unchanged(old: dict, new: dict) -> bool:
    """Same content, version and status."""
    return _normalize(old) == _normalize(new)


def evolution_violation(old: dict, new: dict) -> str | None:
    """Why the policy refuses moving from old to new, or None when it allows it."""
    if old.get("status") not in GOVERNED_STATUSES:
        return None
    old_version, new_version = str(old.get("version")), str(new.get("version"))
    bump = version_bump(old_version, new_version)
    if bump is None:
        return f"Version {new_version} is lower than the current version {old_version}"
    changes = describe_changes(old, new)
    required = required_bump(changes)
    if bump >= required:
        return None
    reasons = "; ".join(c.description for c in changes if c.kind == required)
    return (
        f"Contract changes require a {required.name} version bump"
        f" (current {old_version}, requested {new_version}): {reasons}"
    )
