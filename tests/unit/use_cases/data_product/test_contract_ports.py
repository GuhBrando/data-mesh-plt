import uuid
from unittest.mock import AsyncMock

from backend.domain.entities.data_product import PortUsage
from backend.use_cases.data_product.contract_ports import ListContractPortsUseCase

CID = uuid.uuid4()
USAGE = [PortUsage(uuid.uuid4(), "Risk", "Risco", "active", "output", "o", CID, "1.0.0")]


async def test_lists_the_ports_using_the_contract():
    products, contracts = AsyncMock(), AsyncMock()
    products.list_port_usage.return_value = USAGE
    assert await ListContractPortsUseCase(products, contracts).execute(CID) == USAGE
    products.list_port_usage.assert_awaited_once_with([CID])
    contracts.get_by_id.assert_not_awaited()


async def test_an_unused_contract_has_no_usage():
    products, contracts = AsyncMock(), AsyncMock()
    products.list_port_usage.return_value = []
    contracts.get_by_id.return_value = object()
    assert await ListContractPortsUseCase(products, contracts).execute(CID) == []
    contracts.get_by_id.assert_awaited_once_with(CID)


async def test_a_missing_contract_is_none():
    products, contracts = AsyncMock(), AsyncMock()
    products.list_port_usage.return_value = []
    contracts.get_by_id.return_value = None
    assert await ListContractPortsUseCase(products, contracts).execute(CID) is None
