import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.domain.entities.data_contract import DataContract
from backend.domain.entities.data_product import OutputPort
from backend.domain.interfaces.data_product_repository import LegacyProduct
from backend.use_cases.data_contract.versioning import baseline
from backend.use_cases.data_product.backfill import BackfillOutputPortsUseCase

NOW = datetime.now(tz=timezone.utc)
DOMAIN = uuid.uuid4()


def _contract(title: str) -> DataContract:
    return DataContract(
        id=uuid.uuid4(), title=title, version="1.0", owner="o", domain="Risco",
        domain_id=DOMAIN, tier=3, status="active", models={"fields": []},
        servicelevels={"properties": []}, created_at=NOW, updated_at=NOW,
    )


def _legacy(contract: DataContract, status="active") -> LegacyProduct:
    return LegacyProduct(uuid.uuid4(), "Legacy", "desc", DOMAIN, status, contract.id)


@pytest.fixture
def repos():
    products, contracts = AsyncMock(), AsyncMock()
    products.transaction = MagicMock()
    return products, contracts


async def _run(repos, *pairs) -> int:
    products, contracts = repos
    products.list_legacy_products.return_value = [legacy for legacy, _ in pairs]
    by_id = {contract.id: contract for _, contract in pairs}
    contracts.get_by_id.side_effect = lambda cid: by_id[cid]
    return await BackfillOutputPortsUseCase(products, contracts).execute()


@pytest.mark.parametrize(
    "title, port_name",
    [("Exposição de Crédito", "exposicao-de-credito"), ("???", "output")],
)
async def test_backfill_names_the_port_from_the_contract_title(repos, title, port_name):
    contract = _contract(title)
    await _run(repos, (_legacy(contract), contract))
    product = repos[0].replace.await_args.args[0]
    assert product.output_ports == (
        OutputPort(port_name, contract.id, "1.0", type="tables"),
    )


async def test_backfill_writes_the_baseline_then_replaces_the_product(repos):
    contract = _contract("Orders")
    legacy = _legacy(contract, status="deprecated")
    products, contracts = repos
    order = []
    contracts.add_baseline_versions.side_effect = lambda *_: order.append("baseline")
    products.replace.side_effect = lambda *_: order.append("replace")
    assert await _run(repos, (legacy, contract)) == 1
    assert order == ["baseline", "replace"]
    contracts.add_baseline_versions.assert_awaited_once_with([baseline(contract)])
    product = products.replace.await_args.args[0]
    assert (product.id, product.name, product.description) == (legacy.id, "Legacy", "desc")
    assert (product.domain_id, product.status, product.input_ports) == (
        DOMAIN, "deprecated", ()
    )


async def test_backfill_is_a_no_op_when_nothing_is_linked(repos):
    assert await _run(repos) == 0
    repos[0].replace.assert_not_awaited()
    repos[0].transaction.assert_not_called()


async def test_backfill_uses_one_transaction_per_product(repos):
    first, second = _contract("A"), _contract("B")
    assert await _run(repos, (_legacy(first), first), (_legacy(second), second)) == 2
    assert repos[0].transaction.call_count == 2
    assert repos[0].replace.await_count == 2
