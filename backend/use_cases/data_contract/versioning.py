"""Applies the evolution policy to contracts and writes their version history.

The decision lives in backend.domain.contract_evolution; this module only turns
entities into ODCS documents for it and records snapshots through the port.
"""

import uuid
from typing import Any

from backend.domain.contract_evolution import (
    ContractEvolutionError,
    evolution_violation,
    is_semver,
)
from backend.domain.entities.contract_version import ContractBaseline
from backend.domain.entities.data_contract import DataContract
from backend.domain.interfaces.data_contract_repository import IDataContractRepository
from backend.use_cases.data_contract.odcs import to_odcs
from backend.use_cases.data_contract.yaml_builder import dump_odcs


def baseline(
    contract: DataContract, document: dict[str, Any] | None = None
) -> ContractBaseline:
    """The snapshot of the version `contract` has now, dated by its last change,
    so it sorts before any version written after it."""
    doc = document if document is not None else to_odcs(contract)
    return ContractBaseline(
        contract.id, contract.version, dump_odcs(doc), contract.updated_at
    )


def validate_new_version(version: str, previous: DataContract | None) -> None:
    """Any new version must be semver; an unchanged legacy value such as 1.0 passes."""
    if previous is not None and version == previous.version:
        return
    if not is_semver(version):
        raise ValueError(f"Version '{version}' must match MAJOR.MINOR.PATCH")


async def apply_evolution(
    repository: IDataContractRepository,
    previous: DataContract | None,
    current: DataContract,
    created_by: uuid.UUID | None,
) -> None:
    """Refuse a change the policy forbids, then snapshot `current` when it is new
    or its version changed.

    Call it after the write, inside the use case's transaction, so a refusal
    rolls the write back. Each contract is turned into ODCS once.
    """
    current_doc = to_odcs(current)
    if previous is not None:
        previous_doc = to_odcs(previous)
        violation = evolution_violation(previous_doc, current_doc)
        if violation:
            raise ContractEvolutionError(violation)
        if previous.version == current.version:
            return
        # A contract older than the history has no row for the version it had.
        # The baseline is a no-op when the row exists. updated_at keeps it
        # ordered before the new row, which gets now().
        await repository.add_baseline_versions([baseline(previous, previous_doc)])
    await repository.add_version(
        current.id, current.version, dump_odcs(current_doc), created_by
    )
