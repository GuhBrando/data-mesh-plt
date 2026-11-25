import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.domain.entities.data_contract import DataContract
from backend.domain.entities.data_product import (
    ContractRef,
    DataProduct,
    DataProductRuleError,
    InputPort,
    OutputPort,
    PortUsage,
)
from backend.use_cases.data_contract.versioning import baseline
from backend.use_cases.data_product.save import (
    CreateDataProductUseCase,
    SavedProduct,
    UpdateDataProductUseCase,
)

NOW = datetime.now(tz=timezone.utc)
DOMAIN, OTHER_DOMAIN = uuid.uuid4(), uuid.uuid4()
PRODUCT_ID = uuid.uuid4()
C_ACTIVE, C_DEPRECATED, C_RETIRED, C_FOREIGN = (uuid.uuid4() for _ in range(4))


def _contract(cid, title, status="active", domain_id=DOMAIN, domain="Risco", version="1.1.0"):
    return DataContract(
        id=cid, title=title, version=version, owner="o", domain=domain,
        domain_id=domain_id, tier=3, status=status, models={"fields": []},
        servicelevels={"properties": []}, created_at=NOW, updated_at=NOW,
    )


CONTRACTS = {
    C_ACTIVE: _contract(C_ACTIVE, "Orders"),
    C_DEPRECATED: _contract(C_DEPRECATED, "Cadastro", status="deprecated"),
    C_RETIRED: _contract(C_RETIRED, "Legacy", status="retired"),
    C_FOREIGN: _contract(C_FOREIGN, "Payments", domain_id=OTHER_DOMAIN, domain="Pagamentos"),
}


@pytest.fixture
def contracts():
    repo = AsyncMock()
    repo.transaction = MagicMock()
    repo.list_by_ids.side_effect = lambda ids: [CONTRACTS[i] for i in ids if i in CONTRACTS]
    return repo


@pytest.fixture
def products():
    repo = AsyncMock()
    repo.transaction = MagicMock()
    repo.add.side_effect = lambda product: product
    repo.replace.side_effect = lambda product: product
    repo.list_port_usage.return_value = []
    return repo


def _fields(**kw):
    fields = {
        "name": "Risk",
        "description": "d",
        "domain_id": DOMAIN,
        "status": "draft",
        "input_ports": [],
        "output_ports": [OutputPort("out")],
    }
    return {**fields, **kw}


async def _create(products, contracts, **kw) -> SavedProduct:
    return await CreateDataProductUseCase(products, contracts).execute(**_fields(**kw))


def _stored(**kw) -> DataProduct:
    fields = {**_fields(status="active"), "id": PRODUCT_ID, **kw}
    return DataProduct(**fields)


async def _update(products, contracts, previous, **kw) -> SavedProduct | None:
    products.get_by_id.return_value = previous
    return await UpdateDataProductUseCase(products, contracts).execute(
        PRODUCT_ID, **_fields(**kw)
    )


async def test_create_fills_the_contracts_current_version(products, contracts):
    saved = await _create(
        products,
        contracts,
        input_ports=[InputPort("in", C_ACTIVE)],
        output_ports=[OutputPort("out", C_ACTIVE), OutputPort("free")],
    )
    assert saved.product.input_ports[0].version == "1.1.0"
    assert [p.version for p in saved.product.output_ports] == ["1.1.0", None]
    assert saved.warnings == []


async def test_create_keeps_a_pinned_version(products, contracts):
    saved = await _create(
        products, contracts, input_ports=[InputPort("in", C_ACTIVE, "1.0.0")]
    )
    assert saved.product.input_ports[0].version == "1.0.0"


async def test_create_stores_through_add(products, contracts):
    saved = await _create(products, contracts)
    products.add.assert_awaited_once_with(saved.product)
    products.replace.assert_not_awaited()


async def test_create_refuses_a_retired_input_contract(products, contracts):
    with pytest.raises(DataProductRuleError) as e:
        await _create(products, contracts, input_ports=[InputPort("cad", C_RETIRED)])
    assert e.value.messages == ["Input cad cannot use contract Legacy: it is retired"]
    products.add.assert_not_awaited()
    contracts.add_baseline_versions.assert_not_awaited()


async def test_a_retired_output_contract_is_allowed(products, contracts):
    saved = await _create(products, contracts, output_ports=[OutputPort("out", C_RETIRED)])
    assert saved.product.output_ports[0].contract_id == C_RETIRED


async def test_rule_errors_and_aggregate_errors_come_together(products, contracts):
    with pytest.raises(DataProductRuleError) as e:
        await _create(
            products, contracts, input_ports=[InputPort("cad", C_RETIRED)], output_ports=[]
        )
    assert e.value.messages == [
        "A data product needs at least one output",
        "Input cad cannot use contract Legacy: it is retired",
    ]


async def test_deprecated_input_is_a_warning(products, contracts):
    saved = await _create(products, contracts, input_ports=[InputPort("cad", C_DEPRECATED)])
    assert saved.warnings == ["Input cad uses contract Cadastro, which is deprecated"]


async def test_output_published_elsewhere_is_a_warning(products, contracts):
    other = uuid.uuid4()
    products.list_port_usage.return_value = [
        PortUsage(other, "Billing", "Risco", "active", "output", "o", C_ACTIVE, "1.1.0"),
        PortUsage(uuid.uuid4(), "Audit", "Risco", "active", "output", "o", C_ACTIVE, "1.0.0"),
        PortUsage(uuid.uuid4(), "Reader", "Risco", "active", "input", "i", C_ACTIVE, "1.1.0"),
    ]
    saved = await _create(products, contracts, output_ports=[OutputPort("out", C_ACTIVE)])
    products.list_port_usage.assert_awaited_once_with([C_ACTIVE])
    assert saved.warnings == ["Contract Orders is already published by Audit, Billing"]


async def test_own_output_usage_is_not_a_warning(products, contracts):
    products.list_port_usage.return_value = [
        PortUsage(PRODUCT_ID, "Risk", "Risco", "active", "output", "old", C_ACTIVE, "1.0.0"),
    ]
    previous = _stored(output_ports=[OutputPort("old", C_ACTIVE, "1.0.0")])
    saved = await _update(
        products,
        contracts,
        previous,
        output_ports=[OutputPort("old", C_ACTIVE, "1.0.0"), OutputPort("old", C_ACTIVE)],
    )
    assert saved.warnings == []


async def test_output_from_another_domain_is_a_warning(products, contracts):
    saved = await _create(products, contracts, output_ports=[OutputPort("pay", C_FOREIGN)])
    assert saved.warnings == [
        "Contract Payments belongs to domain Pagamentos, not to this product's domain"
    ]


async def test_an_input_from_another_domain_is_not_a_warning(products, contracts):
    saved = await _create(products, contracts, input_ports=[InputPort("pay", C_FOREIGN)])
    assert saved.warnings == []


async def test_the_same_warning_is_given_once(products, contracts):
    saved = await _create(
        products,
        contracts,
        output_ports=[OutputPort("a", C_FOREIGN), OutputPort("b", C_FOREIGN)],
    )
    assert len(saved.warnings) == 1


async def test_baselines_cover_contracts_of_fresh_ports_only(products, contracts):
    previous = _stored(input_ports=[InputPort("kept", C_DEPRECATED, "1.1.0")])
    await _update(
        products,
        contracts,
        previous,
        input_ports=[InputPort("kept", C_DEPRECATED, "1.1.0"), InputPort("new", C_ACTIVE)],
    )
    contracts.add_baseline_versions.assert_awaited_once_with([baseline(CONTRACTS[C_ACTIVE])])


async def test_unchanged_input_on_a_retired_contract_still_saves(products, contracts):
    previous = _stored(input_ports=[InputPort("cad", C_RETIRED, "1.0.0")])
    saved = await _update(
        products,
        contracts,
        previous,
        name="Renamed",
        input_ports=[InputPort("cad", C_RETIRED, "1.0.0")],
    )
    assert saved.product.name == "Renamed"
    assert saved.warnings == []


async def test_moving_an_input_to_a_retired_contract_is_refused(products, contracts):
    previous = _stored(input_ports=[InputPort("cad", C_ACTIVE, "1.1.0")])
    with pytest.raises(DataProductRuleError):
        await _update(
            products, contracts, previous, input_ports=[InputPort("cad", C_RETIRED, "1.1.0")]
        )


async def test_unchanged_deprecated_input_gives_no_warning(products, contracts):
    previous = _stored(input_ports=[InputPort("cad", C_DEPRECATED, "1.1.0")])
    saved = await _update(
        products, contracts, previous, input_ports=[InputPort("cad", C_DEPRECATED, "1.1.0")]
    )
    assert saved.warnings == []


async def test_update_keeps_identity_and_stores_through_replace(products, contracts):
    previous = _stored(repo_url="https://github.com/acme/dp")
    saved = await _update(products, contracts, previous, description="new")
    products.replace.assert_awaited_once_with(saved.product)
    assert (saved.product.id, saved.product.repo_url) == (PRODUCT_ID, previous.repo_url)
    assert saved.product.description == "new"


async def test_update_of_a_missing_product_returns_none(products, contracts):
    assert await _update(products, contracts, None) is None
    products.replace.assert_not_awaited()


async def test_update_returns_none_when_the_product_vanished(products, contracts):
    products.replace.side_effect = None
    products.replace.return_value = None
    assert await _update(products, contracts, _stored()) is None


async def test_update_cannot_reactivate_a_retired_product(products, contracts):
    with pytest.raises(DataProductRuleError) as e:
        await _update(products, contracts, _stored(status="retired"), status="active")
    assert e.value.messages == ["A retired data product cannot change status"]


async def test_unknown_contract_is_left_to_the_database(products, contracts):
    unknown = uuid.uuid4()
    saved = await _create(
        products, contracts, input_ports=[InputPort("x", unknown, "1.0.0")]
    )
    assert saved.product.input_ports[0] == InputPort("x", unknown, "1.0.0")
    contracts.add_baseline_versions.assert_awaited_once_with([])


async def test_input_contracts_may_cite_a_version_the_platform_filled(products, contracts):
    saved = await _create(
        products,
        contracts,
        input_ports=[InputPort("in", C_ACTIVE)],
        output_ports=[OutputPort("out", input_contracts=(ContractRef(C_ACTIVE, "1.1.0"),))],
    )
    assert saved.product.output_ports[0].input_contracts == (ContractRef(C_ACTIVE, "1.1.0"),)


@pytest.mark.n1
async def test_save_runs_in_one_transaction_with_a_fixed_number_of_queries(
    products, contracts
):
    ports = [InputPort(f"in{i}", C_ACTIVE, "1.1.0") for i in range(5)]
    await _create(products, contracts, input_ports=ports)
    products.transaction.assert_called_once()
    contracts.list_by_ids.assert_awaited_once()
    contracts.add_baseline_versions.assert_awaited_once()
    products.list_port_usage.assert_awaited_once()
    products.add.assert_awaited_once()
