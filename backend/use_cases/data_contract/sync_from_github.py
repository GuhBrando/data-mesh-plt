import logging
import uuid
from typing import Any

from backend.domain.interfaces.data_contract_repository import IDataContractRepository
from backend.domain.interfaces.domain_repository import IDomainRepository
from backend.infra.github_client import GitHubClient
from backend.use_cases.data_contract.contract_document import (
    load_contract_yaml,
    parse_contract_document,
)

logger = logging.getLogger(__name__)

# Errors quote values from the file; keep the response and the log bounded.
_MAX_ERROR_CHARS = 500


def _error_text(exc: Exception) -> str:
    text = str(exc)
    return text if len(text) <= _MAX_ERROR_CHARS else text[:_MAX_ERROR_CHARS] + "…"


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

    async def execute(self) -> dict[str, Any]:
        yamls = await self.github.list_all_yaml_contents()
        created, updated, errors = 0, 0, []

        for path, content in yamls:
            try:
                parsed = parse_contract_document(load_contract_yaml(content))
                yaml_domain = parsed.domain_name
                if not yaml_domain:
                    errors.append(
                        {"path": path, "error": "YAML has no domain name; skipped"}
                    )
                    continue

                existing = await self.repository.get_by_id(parsed.id)
                if existing is not None and existing.domain != yaml_domain:
                    errors.append(
                        {
                            "path": path,
                            "error": (
                                f"domain mismatch: YAML declares"
                                f" domain '{yaml_domain}'"
                                f" but contract {parsed.id}"
                                f" belongs to '{existing.domain}'"
                            ),
                        }
                    )
                    continue

                domain_id = await self._resolve_domain_id(yaml_domain)

                was_created = await self.repository.upsert(
                    contract_id=parsed.id,
                    title=parsed.title,
                    version=parsed.version,
                    owner=parsed.owner,
                    domain_id=domain_id,
                    tier=parsed.tier,
                    status=parsed.status,
                    models=parsed.models,
                    servicelevels=parsed.servicelevels,
                )
                if was_created:
                    created += 1
                else:
                    updated += 1
            except Exception as exc:
                message = _error_text(exc)
                # %r escapes control characters, so a file cannot forge log lines.
                logger.warning("Failed to sync %r: %r", path, message)
                errors.append({"path": path, "error": message})

        return {"created": created, "updated": updated, "errors": errors}
