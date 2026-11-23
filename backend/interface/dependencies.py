from functools import cache

import httpx
from fastapi import Depends

from backend.infra.config import (
    GITHUB_APP_CLIENT_ID,
    GITHUB_APP_INSTALLATION_ID,
    GITHUB_APP_KEY_VAULT_KEY_ID,
    GITHUB_REPO,
    GITHUB_TOKEN,
)
from backend.infra.github_auth import build_github_auth
from backend.infra.github_client import GitHubClient
from backend.infra.postgres import get_db_connection
from backend.infra.repositories.data_contract_repository import (
    PostgresDataContractRepository,
)
from backend.infra.repositories.data_product_repository import (
    PostgresDataProductRepository,
)
from backend.infra.repositories.domain_repository import PostgresDomainRepository
from backend.infra.repositories.refresh_token_repository import (
    PostgresRefreshTokenRepository,
)
from backend.infra.repositories.stakeholder_repository import (
    PostgresStakeholderRepository,
)
from backend.infra.repositories.user_repository import PostgresUserRepository
from backend.use_cases.auth.login import LoginUseCase
from backend.use_cases.auth.logout import LogoutUseCase
from backend.use_cases.auth.refresh import RefreshUseCase
from backend.use_cases.data_contract.create import CreateDataContractUseCase
from backend.use_cases.data_contract.delete import DeleteDataContractUseCase
from backend.use_cases.data_contract.get import GetDataContractUseCase
from backend.use_cases.data_contract.get_version_yaml import (
    GetContractVersionYamlUseCase,
)
from backend.use_cases.data_contract.list import ListDataContractsUseCase
from backend.use_cases.data_contract.list_versions import ListContractVersionsUseCase
from backend.use_cases.data_contract.update import UpdateDataContractUseCase
from backend.use_cases.data_product.create import CreateDataProductUseCase
from backend.use_cases.data_product.delete import DeleteDataProductUseCase
from backend.use_cases.data_product.get import GetDataProductUseCase
from backend.use_cases.data_product.list import ListDataProductsUseCase
from backend.use_cases.data_product.update import UpdateDataProductUseCase
from backend.use_cases.domain.add_member import AddDomainMemberUseCase
from backend.use_cases.domain.create import CreateDomainUseCase
from backend.use_cases.domain.delete import DeleteDomainUseCase
from backend.use_cases.domain.list import ListDomainsUseCase
from backend.use_cases.domain.remove_member import RemoveDomainMemberUseCase
from backend.use_cases.domain.update import UpdateDomainUseCase
from backend.use_cases.domain.update_member import UpdateDomainMemberUseCase
from backend.use_cases.stakeholder.assign import AssignStakeholderUseCase
from backend.use_cases.stakeholder.remove import RemoveStakeholderUseCase
from backend.use_cases.user.assign_role import AssignRoleUseCase
from backend.use_cases.user.create import CreateUserUseCase
from backend.use_cases.user.delete import DeleteUserUseCase
from backend.use_cases.user.get import GetUserUseCase
from backend.use_cases.user.list import ListUsersUseCase
from backend.use_cases.user.update import UpdateUserUseCase

# --- GitHub client ---


@cache
def _github_auth() -> httpx.Auth | None:
    # One instance per process: the GitHub App installation token is cached on it.
    return build_github_auth(
        token=GITHUB_TOKEN,
        app_client_id=GITHUB_APP_CLIENT_ID,
        app_installation_id=GITHUB_APP_INSTALLATION_ID,
        app_key_vault_key_id=GITHUB_APP_KEY_VAULT_KEY_ID,
    )


def get_github_client() -> GitHubClient | None:
    auth = _github_auth()
    if auth is None:
        return None
    return GitHubClient(repo=GITHUB_REPO, auth=auth)


# --- Repositories ---


def get_user_repository(db=Depends(get_db_connection)) -> PostgresUserRepository:
    return PostgresUserRepository(db)


def get_data_contract_repository(
    db=Depends(get_db_connection),
) -> PostgresDataContractRepository:
    return PostgresDataContractRepository(db)


def get_data_product_repository(
    db=Depends(get_db_connection),
) -> PostgresDataProductRepository:
    return PostgresDataProductRepository(db)


# --- User use cases ---


def get_create_user_use_case(
    repo=Depends(get_user_repository),
) -> CreateUserUseCase:
    return CreateUserUseCase(repo)


def get_get_user_use_case(
    repo=Depends(get_user_repository),
) -> GetUserUseCase:
    return GetUserUseCase(repo)


def get_list_users_use_case(
    repo=Depends(get_user_repository),
) -> ListUsersUseCase:
    return ListUsersUseCase(repo)


def get_update_user_use_case(
    repo=Depends(get_user_repository),
) -> UpdateUserUseCase:
    return UpdateUserUseCase(repo)


def get_delete_user_use_case(
    repo=Depends(get_user_repository),
) -> DeleteUserUseCase:
    return DeleteUserUseCase(repo)


# --- Data Contract use cases ---


def get_create_data_contract_use_case(
    repo=Depends(get_data_contract_repository),
) -> CreateDataContractUseCase:
    return CreateDataContractUseCase(repo)


def get_get_data_contract_use_case(
    repo=Depends(get_data_contract_repository),
) -> GetDataContractUseCase:
    return GetDataContractUseCase(repo)


def get_list_data_contracts_use_case(
    repo=Depends(get_data_contract_repository),
) -> ListDataContractsUseCase:
    return ListDataContractsUseCase(repo)


def get_list_contract_versions_use_case(
    repo=Depends(get_data_contract_repository),
) -> ListContractVersionsUseCase:
    return ListContractVersionsUseCase(repo)


def get_get_contract_version_yaml_use_case(
    repo=Depends(get_data_contract_repository),
) -> GetContractVersionYamlUseCase:
    return GetContractVersionYamlUseCase(repo)


def get_update_data_contract_use_case(
    repo=Depends(get_data_contract_repository),
) -> UpdateDataContractUseCase:
    return UpdateDataContractUseCase(repo)


def get_delete_data_contract_use_case(
    repo=Depends(get_data_contract_repository),
) -> DeleteDataContractUseCase:
    return DeleteDataContractUseCase(repo)


# --- Data Product use cases ---


def get_create_data_product_use_case(
    repo=Depends(get_data_product_repository),
) -> CreateDataProductUseCase:
    return CreateDataProductUseCase(repo)


def get_get_data_product_use_case(
    repo=Depends(get_data_product_repository),
) -> GetDataProductUseCase:
    return GetDataProductUseCase(repo)


def get_list_data_products_use_case(
    repo=Depends(get_data_product_repository),
) -> ListDataProductsUseCase:
    return ListDataProductsUseCase(repo)


def get_update_data_product_use_case(
    repo=Depends(get_data_product_repository),
) -> UpdateDataProductUseCase:
    return UpdateDataProductUseCase(repo)


def get_delete_data_product_use_case(
    repo=Depends(get_data_product_repository),
) -> DeleteDataProductUseCase:
    return DeleteDataProductUseCase(repo)


# --- Auth ---


def get_refresh_token_repository(
    db=Depends(get_db_connection),
) -> PostgresRefreshTokenRepository:
    return PostgresRefreshTokenRepository(db)


def get_login_use_case(
    user_repo=Depends(get_user_repository),
    token_repo=Depends(get_refresh_token_repository),
) -> LoginUseCase:
    return LoginUseCase(user_repo=user_repo, token_repo=token_repo)


def get_refresh_use_case(
    token_repo=Depends(get_refresh_token_repository),
) -> RefreshUseCase:
    return RefreshUseCase(token_repo=token_repo)


def get_logout_use_case(
    token_repo=Depends(get_refresh_token_repository),
) -> LogoutUseCase:
    return LogoutUseCase(token_repo=token_repo)


# --- Domain repository ---


def get_domain_repository(db=Depends(get_db_connection)) -> PostgresDomainRepository:
    return PostgresDomainRepository(db)


# --- Stakeholder repository ---


def get_stakeholder_repository(
    db=Depends(get_db_connection),
) -> PostgresStakeholderRepository:
    return PostgresStakeholderRepository(db)


# --- Role assignment use case ---


def get_assign_role_use_case(
    repo=Depends(get_user_repository),
    token_repo=Depends(get_refresh_token_repository),
) -> AssignRoleUseCase:
    return AssignRoleUseCase(repo, token_repo)


# --- Domain use cases ---


def get_create_domain_use_case(
    repo=Depends(get_domain_repository),
) -> CreateDomainUseCase:
    return CreateDomainUseCase(repo)


def get_add_domain_member_use_case(
    repo=Depends(get_domain_repository),
) -> AddDomainMemberUseCase:
    return AddDomainMemberUseCase(repo)


def get_remove_domain_member_use_case(
    repo=Depends(get_domain_repository),
) -> RemoveDomainMemberUseCase:
    return RemoveDomainMemberUseCase(repo)


def get_list_domains_use_case(
    repo=Depends(get_domain_repository),
) -> ListDomainsUseCase:
    return ListDomainsUseCase(repo)


def get_update_domain_use_case(
    repo=Depends(get_domain_repository),
) -> UpdateDomainUseCase:
    return UpdateDomainUseCase(repo)


def get_delete_domain_use_case(
    repo=Depends(get_domain_repository),
) -> DeleteDomainUseCase:
    return DeleteDomainUseCase(repo)


def get_update_domain_member_use_case(
    repo=Depends(get_domain_repository),
) -> UpdateDomainMemberUseCase:
    return UpdateDomainMemberUseCase(repo)


# --- Stakeholder use cases ---


def get_assign_stakeholder_use_case(
    repo=Depends(get_stakeholder_repository),
) -> AssignStakeholderUseCase:
    return AssignStakeholderUseCase(repo)


def get_remove_stakeholder_use_case(
    repo=Depends(get_stakeholder_repository),
) -> RemoveStakeholderUseCase:
    return RemoveStakeholderUseCase(repo)
