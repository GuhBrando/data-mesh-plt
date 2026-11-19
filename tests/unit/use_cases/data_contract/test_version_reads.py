import uuid
from unittest.mock import MagicMock

import pytest

from backend.use_cases.data_contract.get_version_yaml import GetContractVersionYamlUseCase
from backend.use_cases.data_contract.list_versions import ListContractVersionsUseCase

ROWS = [MagicMock()]


@pytest.mark.parametrize("history, contract, expected", [
    pytest.param(ROWS, None, ROWS, id="history-needs-no-existence-check"),
    pytest.param([], MagicMock(), [], id="contract-without-history"),
    pytest.param([], None, None, id="unknown-contract"),
])
async def test_list_versions(contract_repo, history, contract, expected):
    contract_repo.list_versions.return_value = history
    contract_repo.get_by_id.return_value = contract
    assert await ListContractVersionsUseCase(contract_repo).execute(uuid.uuid4()) == expected
    assert contract_repo.get_by_id.called is (not history)


async def test_get_version_yaml_passes_the_version_through(contract_repo):
    contract_repo.get_version_yaml.return_value = "apiVersion: v3.2.0\n"
    cid = uuid.uuid4()
    result = await GetContractVersionYamlUseCase(contract_repo).execute(cid, "1.0.0")
    assert result == "apiVersion: v3.2.0\n"
    contract_repo.get_version_yaml.assert_called_once_with(cid, "1.0.0")
