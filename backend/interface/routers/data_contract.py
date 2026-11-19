import logging
import uuid
from typing import Any, List

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from backend.domain.contract_evolution import ContractEvolutionError
from backend.domain.entities.contract_stakeholder import ContractStakeholder
from backend.domain.entities.data_contract import DataContract
from backend.domain.entities.user import User
from backend.domain.value_objects.user_role import UserRole
from backend.infra.github_client import GitHubClient
from backend.infra.postgres import get_db_connection
from backend.interface.dependencies import (
    get_assign_stakeholder_use_case,
    get_create_data_contract_use_case,
    get_data_contract_repository,
    get_delete_data_contract_use_case,
    get_domain_repository,
    get_get_contract_version_yaml_use_case,
    get_get_data_contract_use_case,
    get_github_client,
    get_list_contract_versions_use_case,
    get_list_data_contracts_use_case,
    get_remove_stakeholder_use_case,
    get_stakeholder_repository,
    get_update_data_contract_use_case,
)
from backend.interface.permissions import is_domain_member, require_roles
from backend.interface.schemas.data_contract import (
    ContractVersionResponseModel,
    DataContractCreateModel,
    DataContractResponseModel,
    DataContractUpdateModel,
)
from backend.interface.schemas.stakeholder import (
    StakeholderAssignModel,
    StakeholderResponseModel,
)
from backend.interface.security import get_current_user
from backend.use_cases.data_contract.create import CreateDataContractUseCase
from backend.use_cases.data_contract.delete import DeleteDataContractUseCase
from backend.use_cases.data_contract.get import GetDataContractUseCase
from backend.use_cases.data_contract.get_version_yaml import (
    GetContractVersionYamlUseCase,
)
from backend.use_cases.data_contract.list import ListDataContractsUseCase
from backend.use_cases.data_contract.list_versions import ListContractVersionsUseCase
from backend.use_cases.data_contract.sync_from_github import SyncFromGitHubUseCase
from backend.use_cases.data_contract.update import UpdateDataContractUseCase
from backend.use_cases.data_contract.yaml_builder import assemble_yaml
from backend.use_cases.stakeholder.assign import AssignStakeholderUseCase
from backend.use_cases.stakeholder.remove import RemoveStakeholderUseCase

logger = logging.getLogger(__name__)

router = APIRouter()

_steward_or_admin = require_roles(UserRole.PLATFORM_ADMIN, UserRole.DATA_STEWARD)
_owner_or_admin = require_roles(UserRole.PLATFORM_ADMIN, UserRole.DATA_OWNER)
_admin_only = require_roles(UserRole.PLATFORM_ADMIN)
_create_contract = require_roles(
    UserRole.PLATFORM_ADMIN, UserRole.DATA_STEWARD, UserRole.DATA_OWNER
)
_DOMAIN_RESTRICTED_ROLES = {UserRole.DATA_STEWARD, UserRole.DATA_OWNER}


async def _push_to_github(
    github: GitHubClient | None, contract: DataContract, action: str
) -> None:
    if github is None:
        return
    try:
        path = github.contract_path(contract.domain, contract.title)
        await github.push(path, assemble_yaml(contract), f"{action}: {contract.title}")
    except Exception as exc:
        logger.warning(
            "GitHub push failed for contract %s: %s", contract.id, exc, exc_info=True
        )


async def _require_contract_read_access(
    contract_id: uuid.UUID,
    current_user: User,
    stakeholder_repo,
) -> None:
    """Authorize reading a single contract, in any representation.

    A DATA_CONSUMER may only read a contract they are a registered stakeholder
    of. Every endpoint returning contract detail must call this — the JSON and
    YAML representations expose the same information and must not diverge.
    """
    if current_user.role != UserRole.DATA_CONSUMER:
        return
    if not await stakeholder_repo.is_stakeholder(contract_id, current_user.id):
        raise HTTPException(status_code=403, detail="Insufficient permissions")


def _plain(value: Any) -> Any:
    """A request value as the use cases take it: models and rows become dicts."""
    if isinstance(value, BaseModel):
        return value.model_dump()
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return value


def _content(body: BaseModel) -> dict[str, Any]:
    """The contract values a request sends. None is "not sent": the stored value
    stays, while an empty list clears that section."""
    return {name: _plain(value) for name, value in body if value is not None}


# Who works on a contract and where its data lives: shown in the list only to
# the readers _require_contract_read_access lets see the contract itself.
_RESTRICTED_SECTIONS = ("team_members", "support", "servers")


async def _readable_ids(current_user: User, stakeholder_repo) -> set[uuid.UUID] | None:
    """The contracts the user may read in full; None means all of them."""
    if current_user.role != UserRole.DATA_CONSUMER:
        return None
    return await stakeholder_repo.contract_ids_of(current_user.id)


def _to_response(contract: DataContract) -> DataContractResponseModel:
    return DataContractResponseModel(
        id=contract.id,
        title=contract.title,
        version=contract.version,
        owner=contract.owner,
        domain=contract.domain,
        tier=contract.tier,
        status=contract.status,
        models=contract.models,
        servicelevels=contract.servicelevels,
        description=contract.description,
        team_members=contract.team_members,
        support=contract.support,
        servers=contract.servers,
        domain_id=contract.domain_id,
        created_at=contract.created_at,
        updated_at=contract.updated_at,
    )


def _stakeholder_to_response(s: ContractStakeholder) -> StakeholderResponseModel:
    return StakeholderResponseModel(
        contract_id=s.contract_id,
        user_id=s.user_id,
        assigned_by=s.assigned_by,
        assigned_at=s.assigned_at,
    )


@router.post(
    "/data-contracts", response_model=DataContractResponseModel, status_code=201
)
async def create_data_contract(
    body: DataContractCreateModel,
    use_case: CreateDataContractUseCase = Depends(get_create_data_contract_use_case),
    current_user: User = Depends(_create_contract),
    github: GitHubClient | None = Depends(get_github_client),
    db=Depends(get_db_connection),
):
    if current_user.role in _DOMAIN_RESTRICTED_ROLES and not await is_domain_member(
        current_user.id, body.domain_id, db
    ):
        raise HTTPException(
            status_code=403,
            detail="You are not a member of the specified domain",
        )
    try:
        contract = await use_case.execute(**_content(body), created_by=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await _push_to_github(github, contract, "Add contract")
    return _to_response(contract)


@router.get("/data-contracts", response_model=List[DataContractResponseModel])
async def list_data_contracts(
    use_case: ListDataContractsUseCase = Depends(get_list_data_contracts_use_case),
    stakeholder_repo=Depends(get_stakeholder_repository),
    current_user: User = Depends(get_current_user),
):
    contracts = await use_case.execute()
    readable = await _readable_ids(current_user, stakeholder_repo)
    responses = [_to_response(c) for c in contracts]
    if readable is None:
        return responses
    hidden = {section: [] for section in _RESTRICTED_SECTIONS}
    return [r if r.id in readable else r.model_copy(update=hidden) for r in responses]


@router.get("/data-contracts/{contract_id}/yaml", response_class=PlainTextResponse)
async def get_data_contract_yaml(
    contract_id: uuid.UUID,
    use_case: GetDataContractUseCase = Depends(get_get_data_contract_use_case),
    stakeholder_repo=Depends(get_stakeholder_repository),
    current_user: User = Depends(get_current_user),
):
    await _require_contract_read_access(contract_id, current_user, stakeholder_repo)
    contract = await use_case.execute(contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Data contract not found")
    return PlainTextResponse(assemble_yaml(contract), media_type="text/plain")


@router.get(
    "/data-contracts/{contract_id}/versions",
    response_model=list[ContractVersionResponseModel],
)
async def list_data_contract_versions(
    contract_id: uuid.UUID,
    use_case: ListContractVersionsUseCase = Depends(
        get_list_contract_versions_use_case
    ),
    stakeholder_repo=Depends(get_stakeholder_repository),
    current_user: User = Depends(get_current_user),
):
    await _require_contract_read_access(contract_id, current_user, stakeholder_repo)
    versions = await use_case.execute(contract_id)
    if versions is None:
        raise HTTPException(status_code=404, detail="Data contract not found")
    return [
        ContractVersionResponseModel(
            version=v.version, created_by=v.created_by, created_at=v.created_at
        )
        for v in versions
    ]


@router.get(
    "/data-contracts/{contract_id}/versions/{version}/yaml",
    response_class=PlainTextResponse,
)
async def get_data_contract_version_yaml(
    contract_id: uuid.UUID,
    version: str,
    use_case: GetContractVersionYamlUseCase = Depends(
        get_get_contract_version_yaml_use_case
    ),
    stakeholder_repo=Depends(get_stakeholder_repository),
    current_user: User = Depends(get_current_user),
):
    await _require_contract_read_access(contract_id, current_user, stakeholder_repo)
    content = await use_case.execute(contract_id, version)
    if content is None:
        raise HTTPException(status_code=404, detail="Contract version not found")
    # The stored snapshot, untouched: history must not depend on today's mapper.
    return PlainTextResponse(content, media_type="text/plain")


@router.get("/data-contracts/{contract_id}", response_model=DataContractResponseModel)
async def get_data_contract(
    contract_id: uuid.UUID,
    use_case: GetDataContractUseCase = Depends(get_get_data_contract_use_case),
    stakeholder_repo=Depends(get_stakeholder_repository),
    current_user: User = Depends(get_current_user),
):
    await _require_contract_read_access(contract_id, current_user, stakeholder_repo)
    contract = await use_case.execute(contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Data contract not found")
    return _to_response(contract)


@router.put("/data-contracts/{contract_id}", response_model=DataContractResponseModel)
async def update_data_contract(
    contract_id: uuid.UUID,
    body: DataContractUpdateModel,
    use_case: UpdateDataContractUseCase = Depends(get_update_data_contract_use_case),
    get_use_case: GetDataContractUseCase = Depends(get_get_data_contract_use_case),
    current_user: User = Depends(_steward_or_admin),
    github: GitHubClient | None = Depends(get_github_client),
    db=Depends(get_db_connection),
):
    if current_user.role == UserRole.DATA_STEWARD:
        existing = await get_use_case.execute(contract_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Data contract not found")
        if not await is_domain_member(current_user.id, existing.domain_id, db):
            raise HTTPException(status_code=403, detail="Not a member of this domain")
    try:
        # Only the sent values: the use case merges them into the row it locks,
        # so a concurrent update is never overwritten with stale values.
        result = await use_case.execute(
            contract_id=contract_id,
            changes=_content(body),
            created_by=current_user.id,
        )
    except ContractEvolutionError as e:
        # A rejected change never reaches GitHub: the push below is skipped.
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if result is None:
        raise HTTPException(status_code=404, detail="Data contract not found")
    previous, contract = result
    await _push_to_github(github, contract, "Update contract")
    if github:
        old_path = github.contract_path(previous.domain, previous.title)
        new_path = github.contract_path(contract.domain, contract.title)
        if old_path != new_path:
            try:
                await github.delete(
                    old_path,
                    f"Remove stale contract file: {previous.title}",
                )
            except Exception as exc:
                logger.warning(
                    "GitHub delete of old path failed for contract %s: %s",
                    contract_id,
                    exc,
                    exc_info=True,
                )
    return _to_response(contract)


@router.delete("/data-contracts/{contract_id}", status_code=204)
async def delete_data_contract(
    contract_id: uuid.UUID,
    use_case: DeleteDataContractUseCase = Depends(get_delete_data_contract_use_case),
    get_use_case: GetDataContractUseCase = Depends(get_get_data_contract_use_case),
    current_user: User = Depends(_owner_or_admin),
    github: GitHubClient | None = Depends(get_github_client),
    db=Depends(get_db_connection),
):
    contract = await get_use_case.execute(contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Data contract not found")
    if current_user.role == UserRole.DATA_OWNER and not await is_domain_member(
        current_user.id, contract.domain_id, db
    ):
        raise HTTPException(status_code=403, detail="Not a member of this domain")
    try:
        deleted = await use_case.execute(contract_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=404, detail="Data contract not found")
    if github:
        try:
            path = github.contract_path(contract.domain, contract.title)
            await github.delete(path, f"Remove contract: {contract.title}")
        except Exception as exc:
            logger.warning("GitHub delete failed for contract %s: %s", contract_id, exc)


@router.post("/data-contracts/sync")
async def sync_data_contracts_from_github(
    github: GitHubClient | None = Depends(get_github_client),
    repo=Depends(get_data_contract_repository),
    domain_repo=Depends(get_domain_repository),
    current_user: User = Depends(_admin_only),
):
    if github is None:
        raise HTTPException(
            status_code=503,
            detail="GitHub integration not configured (GITHUB_TOKEN missing)",
        )
    use_case = SyncFromGitHubUseCase(
        repository=repo, github=github, domain_repo=domain_repo
    )
    try:
        return await use_case.execute(created_by=current_user.id)
    except (RuntimeError, httpx.HTTPError) as exc:
        # A dead token or a renamed repository must not look like an empty sync.
        raise HTTPException(
            status_code=502,
            detail=f"Could not read the contracts repository: {exc}",
        ) from exc


@router.post(
    "/data-contracts/{contract_id}/stakeholders",
    response_model=StakeholderResponseModel,
    status_code=201,
)
async def assign_stakeholder(
    contract_id: uuid.UUID,
    body: StakeholderAssignModel,
    use_case: AssignStakeholderUseCase = Depends(get_assign_stakeholder_use_case),
    get_use_case: GetDataContractUseCase = Depends(get_get_data_contract_use_case),
    current_user: User = Depends(_steward_or_admin),
    db=Depends(get_db_connection),
):
    if current_user.role == UserRole.DATA_STEWARD:
        contract = await get_use_case.execute(contract_id)
        if not contract:
            raise HTTPException(status_code=404, detail="Data contract not found")
        if not await is_domain_member(current_user.id, contract.domain_id, db):
            raise HTTPException(status_code=403, detail="Not a member of this domain")
    stakeholder = await use_case.execute(
        contract_id=contract_id, user_id=body.user_id, assigned_by=current_user.id
    )
    return _stakeholder_to_response(stakeholder)


@router.delete("/data-contracts/{contract_id}/stakeholders/{user_id}", status_code=204)
async def remove_stakeholder(
    contract_id: uuid.UUID,
    user_id: uuid.UUID,
    use_case: RemoveStakeholderUseCase = Depends(get_remove_stakeholder_use_case),
    get_use_case: GetDataContractUseCase = Depends(get_get_data_contract_use_case),
    current_user: User = Depends(_steward_or_admin),
    db=Depends(get_db_connection),
):
    if current_user.role == UserRole.DATA_STEWARD:
        contract = await get_use_case.execute(contract_id)
        if not contract:
            raise HTTPException(status_code=404, detail="Data contract not found")
        if not await is_domain_member(current_user.id, contract.domain_id, db):
            raise HTTPException(status_code=403, detail="Not a member of this domain")
    await use_case.execute(contract_id=contract_id, user_id=user_id)
