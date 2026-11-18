import uuid
from unittest.mock import MagicMock

from backend.use_cases.data_contract.get_version_yaml import GetContractVersionYamlUseCase
from backend.use_cases.data_contract.list_versions import ListContractVersionsUseCase


async def test_list_versions_is_none_for_an_unknown_contract(contract_repo):
    contract_repo.get_by_id.return_value = None
    assert await ListContractVersionsUseCase(contract_repo).execute(uuid.uuid4()) is None
    contract_repo.list_versions.assert_not_called()


async def test_list_versions_returns_the_repository_rows(contract_repo):
    contract_repo.get_by_id.return_value = MagicMock()
    contract_repo.list_versions.return_value = []
    assert await ListContractVersionsUseCase(contract_repo).execute(uuid.uuid4()) == []


async def test_get_version_yaml_passes_the_version_through(contract_repo):
    contract_repo.get_version_yaml.return_value = "apiVersion: v3.2.0\n"
    cid = uuid.uuid4()
    result = await GetContractVersionYamlUseCase(contract_repo).execute(cid, "1.0.0")
    assert result == "apiVersion: v3.2.0\n"
    contract_repo.get_version_yaml.assert_called_once_with(cid, "1.0.0")
