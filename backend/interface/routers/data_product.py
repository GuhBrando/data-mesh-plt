import logging
import uuid
from collections.abc import Awaitable
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException

from backend.domain.entities.data_product import (
    ContractRef,
    DataProduct,
    DataProductRuleError,
    InputPort,
    OutputPort,
)
from backend.domain.entities.user import User
from backend.domain.interfaces.data_product_repository import IDataProductRepository
from backend.domain.naming import slugify
from backend.infra.github_client import GitHubClient, RepoNameUnavailable
from backend.interface.dependencies import (
    get_create_data_product_use_case,
    get_data_product_repository,
    get_delete_data_product_use_case,
    get_get_data_product_use_case,
    get_github_client,
    get_list_contract_ports_use_case,
    get_list_data_products_use_case,
    get_update_data_product_use_case,
)
from backend.interface.schemas.data_product import (
    DataProductResponseModel,
    DataProductWriteModel,
    InputPortModel,
    OutputPortModel,
    PortUsageResponseModel,
)
from backend.interface.security import get_current_user
from backend.use_cases.data_product.contract_ports import ListContractPortsUseCase
from backend.use_cases.data_product.delete import DeleteDataProductUseCase
from backend.use_cases.data_product.get import GetDataProductUseCase
from backend.use_cases.data_product.list import ListDataProductsUseCase
from backend.use_cases.data_product.save import (
    CreateDataProductUseCase,
    SavedProduct,
    UpdateDataProductUseCase,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _build_scaffold(product: DataProduct) -> dict[str, str]:
    readme = (
        f"# {product.name}\n\n"
        f"{product.description}\n\n"
        f"**Domain:** {product.domain}\n\n"
        "This repository holds the implementation code (pipeline, tests, "
        "infrastructure) for the data product. The public contract YAML lives "
        "in the central contracts repository.\n\n"
        "## Layout\n\n"
        "- `pipeline/` — transformation code\n"
        "- `tests/` — pipeline and contract-conformance tests\n"
        "- `infrastructure/` — IaC for resources owned by this product\n"
    )
    return {
        "README.md": readme,
        "pipeline/.gitkeep": "",
        "tests/.gitkeep": "",
        "infrastructure/.gitkeep": "",
    }


async def _create_repo_with_fallback(
    github: GitHubClient, product: DataProduct, name: str
) -> dict:
    """Create the product repo, falling back to a product-unique name when the
    preferred one is held by a repo we must not touch (archived or foreign)."""
    try:
        return await github.create_product_repo(name, product.description)
    except RepoNameUnavailable:
        logger.info(
            "Repo name %s unavailable for product %s; using suffixed name",
            name,
            product.id,
        )
        return await github.create_product_repo(
            f"{name}-{product.id.hex[:8]}", product.description
        )


async def _ensure_product_repo(
    github: GitHubClient | None,
    product: DataProduct,
    product_repo: IDataProductRepository,
) -> None:
    if github is None or product.repo_url:
        return
    try:
        name = f"dp-{slugify(product.domain)}-{slugify(product.name)}"
        created = await _create_repo_with_fallback(github, product, name)
        # Persist the link before scaffolding: a scaffold failure must not
        # leave a repo on GitHub that no product points at.
        await product_repo.update_repo_url(product.id, created["html_url"])
        product.repo_url = created["html_url"]
        await github.push_scaffold(created["full_name"], _build_scaffold(product))
    except Exception as exc:
        logger.warning(
            "GitHub repo provision failed for product %s: %s",
            product.id,
            exc,
            exc_info=True,
        )


async def _archive_product_repo(
    github: GitHubClient | None, product: DataProduct
) -> None:
    if github is None or not product.repo_url:
        return
    try:
        parts = product.repo_url.rstrip("/").split("/")
        repo_full_name = "/".join(parts[-2:])
        await github.archive_repo(repo_full_name)
    except Exception as exc:
        logger.warning(
            "GitHub archive failed for product %s: %s",
            product.id,
            exc,
            exc_info=True,
        )


def _definitions(port: InputPortModel) -> tuple[dict[str, str], ...]:
    return tuple(d.model_dump() for d in port.authoritative_definitions)


def _input_port(port: InputPortModel) -> InputPort:
    return InputPort(
        name=port.name,
        contract_id=port.contract_id,
        version=port.version,
        deprecated=port.deprecated,
        authoritative_definitions=_definitions(port),
    )


def _output_port(port: OutputPortModel) -> OutputPort:
    return OutputPort(
        name=port.name,
        contract_id=port.contract_id,
        version=port.version,
        type=port.type,
        description=port.description,
        deprecated=port.deprecated,
        authoritative_definitions=_definitions(port),
        input_contracts=tuple(
            ContractRef(r.contract_id, r.version) for r in port.input_contracts
        ),
    )


def _fields(body: DataProductWriteModel) -> dict[str, Any]:
    return {
        "name": body.name,
        "description": body.description,
        "domain_id": body.domain_id,
        "status": body.status,
        "input_ports": [_input_port(p) for p in body.input_ports],
        "output_ports": [_output_port(p) for p in body.output_ports],
    }


async def _saving(pending: Awaitable[SavedProduct | None]) -> SavedProduct | None:
    """Broken product rules are a 422 with one message per rule."""
    try:
        return await pending
    except DataProductRuleError as e:
        raise HTTPException(
            status_code=422, detail=[{"msg": m} for m in e.messages]
        ) from None


def _to_response(
    product: DataProduct, warnings: list[str] | None = None
) -> DataProductResponseModel:
    response = DataProductResponseModel.model_validate(product)
    return response.model_copy(update={"warnings": warnings or []})


@router.post("/data-products", response_model=DataProductResponseModel, status_code=201)
async def create_data_product(
    body: DataProductWriteModel,
    use_case: CreateDataProductUseCase = Depends(get_create_data_product_use_case),
    product_repo: IDataProductRepository = Depends(get_data_product_repository),
    github: GitHubClient | None = Depends(get_github_client),
    _: User = Depends(get_current_user),
):
    saved = await _saving(use_case.execute(**_fields(body)))
    await _ensure_product_repo(github, saved.product, product_repo)
    return _to_response(saved.product, saved.warnings)


@router.get("/data-products", response_model=List[DataProductResponseModel])
async def list_data_products(
    use_case: ListDataProductsUseCase = Depends(get_list_data_products_use_case),
    _: User = Depends(get_current_user),
):
    products = await use_case.execute()
    return [_to_response(p) for p in products]


@router.get("/data-products/{product_id}", response_model=DataProductResponseModel)
async def get_data_product(
    product_id: uuid.UUID,
    use_case: GetDataProductUseCase = Depends(get_get_data_product_use_case),
    product_repo: IDataProductRepository = Depends(get_data_product_repository),
    github: GitHubClient | None = Depends(get_github_client),
    _: User = Depends(get_current_user),
):
    product = await use_case.execute(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Data product not found")
    await _ensure_product_repo(github, product, product_repo)
    return _to_response(product)


@router.put("/data-products/{product_id}", response_model=DataProductResponseModel)
async def update_data_product(
    product_id: uuid.UUID,
    body: DataProductWriteModel,
    use_case: UpdateDataProductUseCase = Depends(get_update_data_product_use_case),
    product_repo: IDataProductRepository = Depends(get_data_product_repository),
    github: GitHubClient | None = Depends(get_github_client),
    _: User = Depends(get_current_user),
):
    saved = await _saving(use_case.execute(product_id, **_fields(body)))
    if saved is None:
        raise HTTPException(status_code=404, detail="Data product not found")
    await _ensure_product_repo(github, saved.product, product_repo)
    return _to_response(saved.product, saved.warnings)


@router.delete("/data-products/{product_id}", status_code=204)
async def delete_data_product(
    product_id: uuid.UUID,
    use_case: DeleteDataProductUseCase = Depends(get_delete_data_product_use_case),
    get_use_case: GetDataProductUseCase = Depends(get_get_data_product_use_case),
    github: GitHubClient | None = Depends(get_github_client),
    _: User = Depends(get_current_user),
):
    product = await get_use_case.execute(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Data product not found")
    deleted = await use_case.execute(product_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Data product not found")
    await _archive_product_repo(github, product)


@router.get(
    "/data-contracts/{contract_id}/ports",
    response_model=list[PortUsageResponseModel],
)
async def list_contract_ports(
    contract_id: uuid.UUID,
    use_case: ListContractPortsUseCase = Depends(get_list_contract_ports_use_case),
    _: User = Depends(get_current_user),
):
    """Who produces and who consumes this contract: every port that references it."""
    usage = await use_case.execute(contract_id)
    if usage is None:
        raise HTTPException(status_code=404, detail="Data contract not found")
    return [PortUsageResponseModel.model_validate(u) for u in usage]
