import logging
import uuid
from typing import Any

import yaml

from backend.domain.interfaces.data_contract_repository import IDataContractRepository
from backend.domain.interfaces.domain_repository import IDomainRepository
from backend.infra.github_client import GitHubClient
from backend.use_cases.data_contract.contract_document import parse_contract_document

logger = logging.getLogger(__name__)


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
                parsed = parse_contract_document(yaml.safe_load(content))
                contract_id = parsed.id
                yaml_domain = parsed.domain_name
                if not yaml_domain:
                    errors.append(
                        {"path": path, "error": "YAML has no domain name; skipped"}
                    )
                    continue

                existing = await self.repository.get_by_id(contract_id)
                if existing is not None and existing.domain != yaml_domain:
                    errors.append(
                        {
                            "path": path,
                            "error": (
                                f"domain mismatch: YAML declares"
                                f" domain '{yaml_domain}'"
                                f" but contract {contract_id}"
                                f" belongs to '{existing.domain}'"
                            ),
                        }
                    )
                    continue

                domain_id = await self._resolve_domain_id(yaml_domain)

                was_created = await self.repository.upsert(
                    contract_id=contract_id,
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
                logger.warning("Failed to sync %s: %s", path, exc)
                errors.append({"path": path, "error": str(exc)})

        return {"created": created, "updated": updated, "errors": errors}
