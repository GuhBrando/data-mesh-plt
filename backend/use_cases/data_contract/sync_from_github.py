import copy
import logging
import uuid
from typing import Any

from backend.domain.contract_evolution import (
    RETIRED_STATUS,
    RetiredContractError,
    is_unchanged,
)
from backend.domain.entities.data_contract import CONTRACT_VALUE_FIELDS, DataContract
from backend.domain.interfaces.data_contract_repository import IDataContractRepository
from backend.domain.interfaces.domain_repository import IDomainRepository
from backend.infra.github_client import GitHubClient
from backend.use_cases.data_contract.contract_document import (
    load_contract_yaml,
    parse_contract_document,
)
from backend.use_cases.data_contract.odcs import to_odcs
from backend.use_cases.data_contract.parsed_contract import ParsedContract
from backend.use_cases.data_contract.versioning import (
    apply_evolution,
    validate_new_version,
)

logger = logging.getLogger(__name__)

# Errors quote values from the file; keep the response and the log bounded.
_MAX_ERROR_CHARS = 500


def _error_text(exc: Exception) -> str:
    text = str(exc)
    return text if len(text) <= _MAX_ERROR_CHARS else text[:_MAX_ERROR_CHARS] + "…"


def _file_matches(current: DataContract, parsed: ParsedContract) -> bool:
    """Whether storing the file would leave the contract as it is.

    Compares what the platform would store, not the raw file, so a file that
    differs only in spelling (an older v3 apiVersion, an uppercase id, a legacy
    DCS layout) still matches.
    """
    candidate = copy.copy(current)
    for name in CONTRACT_VALUE_FIELDS:
        setattr(candidate, name, getattr(parsed, name))
    return is_unchanged(to_odcs(current), to_odcs(candidate))


class SyncFromGitHubUseCase:
    def __init__(
        self,
        repository: IDataContractRepository,
        github: GitHubClient,
        domain_repo: IDomainRepository,
    ):
        self.repository = repository
        self.github = github
        self.domain_repo = domain_repo

    async def _resolve_domain_id(self, name: str) -> uuid.UUID:
        existing = await self.domain_repo.find_by_name(name)
        if existing:
            return existing.id
        created = await self.domain_repo.create(
            name=name, description="", owner_id=None
        )
        return created.id

    async def _sync_file(
        self, content: str, created_by: uuid.UUID | None
    ) -> bool | None:
        """Sync one file. True when created, False when updated, None when skipped.

        Raises to report the file; the transaction rolls this file back only.
        """
        data = load_contract_yaml(content)
        parsed = parse_contract_document(data)
        if not parsed.domain_name:
            raise ValueError("YAML has no domain name; skipped")

        async with self.repository.transaction():
            current = await self.repository.get_by_id_for_update(parsed.id)
            if current is None and parsed.status == RETIRED_STATUS:
                # Same rule as the API: a contract is not born retired.
                raise ValueError(f"Contract {parsed.id} cannot be created as retired")
            if current is not None and current.domain != parsed.domain_name:
                raise ValueError(
                    f"domain mismatch: YAML declares domain '{parsed.domain_name}'"
                    f" but contract {parsed.id} belongs to '{current.domain}'"
                )
            if current is not None and current.status == RETIRED_STATUS:
                # A retired contract's file stays in the repository; every sync
                # re-reads it, so an unchanged file is silently skipped.
                if _file_matches(current, parsed):
                    return None
                raise RetiredContractError(
                    f"Contract {parsed.id} is retired; its file changed and was ignored"
                )
            validate_new_version(parsed.version, current)
            # Inside the transaction, so a rejected file leaves no new domain.
            domain_id = await self._resolve_domain_id(parsed.domain_name)
            stored = await self.repository.upsert(
                contract_id=parsed.id,
                domain_id=domain_id,
                **{name: getattr(parsed, name) for name in CONTRACT_VALUE_FIELDS},
            )
            await apply_evolution(self.repository, current, stored, created_by)
            return current is None

    async def execute(self, created_by: uuid.UUID | None = None) -> dict[str, Any]:
        yamls = await self.github.list_all_yaml_contents()
        created, updated, errors = 0, 0, []

        for path, content in yamls:
            try:
                was_created = await self._sync_file(content, created_by)
            except Exception as exc:
                message = _error_text(exc)
                # %r escapes control characters, so a file cannot forge log lines.
                logger.warning("Failed to sync %r: %r", path, message)
                errors.append({"path": path, "error": message})
                continue
            if was_created is True:
                created += 1
            elif was_created is False:
                updated += 1

        return {"created": created, "updated": updated, "errors": errors}
