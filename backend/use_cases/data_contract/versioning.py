"""Applies the evolution policy to contracts and writes their version history.

The decision lives in backend.domain.contract_evolution; this module only turns
entities into ODCS documents for it and records snapshots through the port.
"""

import uuid

from backend.domain.contract_evolution import (
    ContractEvolutionError,
    evolution_violation,
    is_semver,
)
from backend.domain.entities.data_contract import DataContract
from backend.domain.interfaces.data_contract_repository import IDataContractRepository
from backend.use_cases.data_contract.odcs import to_odcs
from backend.use_cases.data_contract.yaml_builder import assemble_yaml


def validate_new_version(version: str, previous: DataContract | None) -> None:
    """Any new version must be semver; an unchanged legacy value such as 1.0 passes."""
    if previous is not None and version == previous.version:
        return
    if not is_semver(version):
        raise ValueError(f"Version '{version}' must match MAJOR.MINOR.PATCH")


def enforce_evolution(previous: DataContract, current: DataContract) -> None:
    violation = evolution_violation(to_odcs(previous), to_odcs(current))
    if violation:
        raise ContractEvolutionError(violation)


async def record_version(
    repository: IDataContractRepository,
    previous: DataContract | None,
    current: DataContract,
    created_by: uuid.UUID | None,
) -> None:
    """Snapshot `current` when it is new or its version changed."""
    if previous is not None:
        if previous.version == current.version:
            return
        # A contract older than the history has no row for the version it had.
        # The baseline is a no-op when the row exists. updated_at keeps it
        # ordered before the new row, which gets now().
        await repository.add_baseline_version(
            previous.id, previous.version, assemble_yaml(previous), previous.updated_at
        )
    await repository.add_version(
        current.id, current.version, assemble_yaml(current), created_by
    )
