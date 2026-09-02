import logging
import re
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from backend.domain.entities.data_product import DataProduct
from backend.domain.entities.user import User
from backend.domain.interfaces.data_contract_repository import IDataContractRepository
from backend.domain.interfaces.data_product_repository import IDataProductRepository
from backend.infra.github_client import GitHubClient, RepoNameUnavailable
from backend.interface.dependencies import (
    get_create_data_product_use_case,
    get_data_contract_repository,
    get_data_product_repository,
    get_delete_data_product_use_case,
    get_get_data_product_use_case,
    get_github_client,
    get_list_data_products_use_case,
    get_update_data_product_use_case,
)
from backend.interface.schemas.data_product import (
    DataProductCreateModel,
    DataProductResponseModel,
    DataProductUpdateModel,
)
from backend.interface.security import get_current_user
from backend.use_cases.data_product.create import CreateDataProductUseCase
from backend.use_cases.data_product.delete import DeleteDataProductUseCase
from backend.use_cases.data_product.get import GetDataProductUseCase
from backend.use_cases.data_product.list import ListDataProductsUseCase
from backend.use_cases.data_product.update import UpdateDataProductUseCase

logger = logging.getLogger(__name__)

router = APIRouter()


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _build_scaffold(product: DataProduct, domain_name: str) -> dict[str, str]:
    readme = (
        f"# {product.name}\n\n"
        f"{product.description}\n\n"
        f"**Domain:** {domain_name}\n\n"
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


async def _resolve_domain_name(
    contract_repo: IDataContractRepository, product: DataProduct
) -> str | None:
    contract = await contract_repo.get_by_id(product.data_contracts_id)
    return contract.domain if contract else None


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
    contract_repo: IDataContractRepository,
) -> None:
    if github is None or product.repo_url:
        return
    try:
        domain_name = await _resolve_domain_name(contract_repo, product)
        if not domain_name:
            return
        name = f"dp-{_slugify(domain_name)}-{_slugify(product.name)}"
        created = await _create_repo_with_fallback(github, product, name)
        # Persist the link before scaffolding: a scaffold failure must not
        # leave a repo on GitHub that no product points at.
        await product_repo.update_repo_url(product.id, created["html_url"])
        product.repo_url = created["html_url"]
        await github.push_scaffold(
            created["full_name"], _build_scaffold(product, domain_name)
        )
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


def _to_response(product: DataProduct) -> DataProductResponseModel:
    return DataProductResponseModel(
        id=product.id,
        name=product.name,
        description=product.description,
        data_contracts_id=product.data_contracts_id,
        repo_url=product.repo_url,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


@router.post("/data-products", response_model=DataProductResponseModel, status_code=201)
async def create_data_product(
    body: DataProductCreateModel,
    use_case: CreateDataProductUseCase = Depends(get_create_data_product_use_case),
    product_repo: IDataProductRepository = Depends(get_data_product_repository),
    contract_repo: IDataContractRepository = Depends(get_data_contract_repository),
    github: GitHubClient | None = Depends(get_github_client),
    _: User = Depends(get_current_user),
):
    product = await use_case.execute(
        name=body.name,
        description=body.description,
        data_contracts_id=body.data_contracts_id,
    )
    await _ensure_product_repo(github, product, product_repo, contract_repo)
    return _to_response(product)


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
    contract_repo: IDataContractRepository = Depends(get_data_contract_repository),
    github: GitHubClient | None = Depends(get_github_client),
    _: User = Depends(get_current_user),
):
    product = await use_case.execute(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Data product not found")
    await _ensure_product_repo(github, product, product_repo, contract_repo)
    return _to_response(product)


@router.put("/data-products/{product_id}", response_model=DataProductResponseModel)
async def update_data_product(
    product_id: uuid.UUID,
    body: DataProductUpdateModel,
    use_case: UpdateDataProductUseCase = Depends(get_update_data_product_use_case),
    product_repo: IDataProductRepository = Depends(get_data_product_repository),
    contract_repo: IDataContractRepository = Depends(get_data_contract_repository),
    github: GitHubClient | None = Depends(get_github_client),
    _: User = Depends(get_current_user),
):
    product = await use_case.execute(
        product_id=product_id,
        name=body.name,
        description=body.description,
        data_contracts_id=body.data_contracts_id,
    )
    if not product:
        raise HTTPException(status_code=404, detail="Data product not found")
    await _ensure_product_repo(github, product, product_repo, contract_repo)
    return _to_response(product)


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
