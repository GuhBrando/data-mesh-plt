"""Who may read a data contract, change it, and move its status.

Three layers (spec: docs/superpowers/specs/2026-11-26-contract-access-layers-design.md):
readers (everyone reads a published contract), approval (the domain's steward
proposes) and owner (the domain's owner approves, deprecates and retires).
The router gathers the facts about the caller; every rule lives here.
"""

from dataclasses import dataclass

from backend.domain.value_objects.user_role import UserRole

PUBLISHED_STATUSES = frozenset({"active", "deprecated", "retired"})

_EDITABLE_STATUSES = frozenset({"draft", "active", "deprecated"})

# (from, to) -> who may make the move besides a Platform Admin. Listed in the
# order the page offers them. Nothing leads from a published status back to
# draft or in_review: a reader never loses a contract they already read.
_TRANSITIONS: dict[tuple[str, str], frozenset[str]] = {
    ("draft", "in_review"): frozenset({"steward"}),
    ("in_review", "draft"): frozenset({"steward", "owner"}),
    ("in_review", "active"): frozenset({"owner"}),
    ("active", "deprecated"): frozenset({"owner"}),
    ("active", "retired"): frozenset({"owner"}),
    ("deprecated", "active"): frozenset({"owner"}),
    ("deprecated", "retired"): frozenset({"owner"}),
}


@dataclass(frozen=True)
class ContractActor:
    """The caller, as the rules see them for one contract."""

    role: UserRole
    is_member: bool  # of the contract's domain
    is_stakeholder: bool = False


class TransitionRefused(Exception):
    """A status move the caller may not make.

    `forbidden` is True when the move exists but this caller may not make it,
    False when no one may (the pair is not in the table).
    """

    def __init__(self, message: str, *, forbidden: bool):
        super().__init__(message)
        self.forbidden = forbidden


def _is_admin(actor: ContractActor) -> bool:
    return actor.role == UserRole.PLATFORM_ADMIN


def _domain_role(actor: ContractActor) -> str | None:
    """The caller's part in the contract's domain: steward, owner or None."""
    if not actor.is_member:
        return None
    return {UserRole.DATA_STEWARD: "steward", UserRole.DATA_OWNER: "owner"}.get(
        actor.role
    )


def _may(actor: ContractActor, who: frozenset[str]) -> bool:
    return _is_admin(actor) or _domain_role(actor) in who


def can_read(status: str, actor: ContractActor) -> bool:
    if status in PUBLISHED_STATUSES:
        return True
    return _is_admin(actor) or _domain_role(actor) is not None or actor.is_stakeholder


def can_edit(status: str, actor: ContractActor) -> bool:
    return status in _EDITABLE_STATUSES and _may(actor, frozenset({"steward"}))


def can_delete(actor: ContractActor) -> bool:
    return _may(actor, frozenset({"owner"}))


def can_manage_stakeholders(status: str, actor: ContractActor) -> bool:
    return status not in PUBLISHED_STATUSES and _may(actor, frozenset({"steward"}))


def allowed_transitions(status: str, actor: ContractActor) -> list[str]:
    return [
        target
        for (current, target), who in _TRANSITIONS.items()
        if current == status and _may(actor, who)
    ]


def check_transition(current: str, target: str, actor: ContractActor) -> None:
    who = _TRANSITIONS.get((current, target))
    if who is None:
        raise TransitionRefused(
            f"A {current} contract cannot move to {target}.", forbidden=False
        )
    if not _may(actor, who):
        raise TransitionRefused(
            f"You cannot move this contract from {current} to {target}.",
            forbidden=True,
        )
