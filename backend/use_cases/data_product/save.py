"""Creates and edits data products with their ports.

The aggregate checks the product's own rules. This module adds what needs the
contracts' state: a port's default version (rule: pinned at the contract's
current version), rule 4 (no new input on a retired contract), the version
history rows the ports' foreign key needs, and the warnings. Only ports that are
new or changed by the request are checked, so an edit never fails on a port that
was valid when it was written.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, NamedTuple

from backend.domain.contract_evolution import RETIRED_STATUS
from backend.domain.entities.data_product import DataProduct, DataProductRuleError
from backend.use_cases.data_contract.versioning import baseline

if TYPE_CHECKING:
    import uuid
    from collections.abc import Iterable

    from backend.domain.entities.data_contract import DataContract
    from backend.domain.entities.data_product import InputPort, OutputPort, PortUsage
    from backend.domain.interfaces.data_contract_repository import (
        IDataContractRepository,
    )
    from backend.domain.interfaces.data_product_repository import (
        IDataProductRepository,
    )

    Port = InputPort | OutputPort

_DEPRECATED_CONTRACT = "deprecated"


class SavedProduct(NamedTuple):
    product: DataProduct
    warnings: list[str]


def _contract_ids(
    ports: Iterable[Port], known: dict[uuid.UUID, DataContract] | None = None
) -> list[uuid.UUID]:
    """Each contract id once, in port order; only known ones when `known` is given."""
    ids = dict.fromkeys(p.contract_id for p in ports if p.contract_id is not None)
    return [i for i in ids if known is None or i in known]


def _pinned(port: Port, contracts: dict[uuid.UUID, DataContract]) -> Port:
    """A port that names a known contract and no version takes its current one."""
    contract = contracts.get(port.contract_id)
    if contract is None or port.version is not None:
        return port
    return dataclasses.replace(port, version=contract.version)


def _fresh(ports: Iterable[Port], before: Iterable[Port]) -> list[Port]:
    """The ports this request adds or points at another contract version."""
    kept = {(p.name, p.version, p.contract_id) for p in before}
    return [p for p in ports if (p.name, p.version, p.contract_id) not in kept]


def _retired_inputs(
    inputs: list[InputPort], contracts: dict[uuid.UUID, DataContract]
) -> list[str]:
    return [
        f"Input {p.name} cannot use contract {c.title}: it is retired"
        for p in inputs
        if (c := contracts.get(p.contract_id)) and c.status == RETIRED_STATUS
    ]


def _output_warnings(
    product: DataProduct,
    contract: DataContract,
    usage: list[PortUsage],
) -> Iterable[str]:
    publishers = sorted(
        {
            u.product_name
            for u in usage
            if u.role == "output"
            and u.contract_id == contract.id
            and u.product_id != product.id
        }
    )
    if publishers:
        yield (
            f"Contract {contract.title} is already published by {', '.join(publishers)}"
        )
    if contract.domain_id != product.domain_id:
        yield (
            f"Contract {contract.title} belongs to domain {contract.domain},"
            " not to this product's domain"
        )


def _warnings(
    product: DataProduct,
    fresh_inputs: list[InputPort],
    fresh_outputs: list[OutputPort],
    contracts: dict[uuid.UUID, DataContract],
    usage: list[PortUsage],
) -> list[str]:
    warnings = [
        f"Input {p.name} uses contract {c.title}, which is deprecated"
        for p in fresh_inputs
        if (c := contracts.get(p.contract_id)) and c.status == _DEPRECATED_CONTRACT
    ]
    for port in fresh_outputs:
        contract = contracts.get(port.contract_id)
        if contract is not None:
            warnings.extend(_output_warnings(product, contract, usage))
    return list(dict.fromkeys(warnings))


class _ProductWriter:
    def __init__(
        self, products: IDataProductRepository, contracts: IDataContractRepository
    ):
        self.products = products
        self.contracts = contracts

    async def _prepare(
        self, fields: dict[str, Any], previous: DataProduct | None
    ) -> tuple[DataProduct, list[str]]:
        """The product to store and its warnings; DataProductRuleError lists every
        broken rule. A fixed number of queries, whatever the number of ports."""
        ports = [*fields["input_ports"], *fields["output_ports"]]
        known = await self.contracts.list_by_ids(_contract_ids(ports))
        contracts = {c.id: c for c in known}
        inputs = [_pinned(p, contracts) for p in fields["input_ports"]]
        outputs = [_pinned(p, contracts) for p in fields["output_ports"]]
        fresh_inputs = _fresh(inputs, previous.input_ports if previous else ())
        fresh_outputs = _fresh(outputs, previous.output_ports if previous else ())

        product, problems = None, _retired_inputs(fresh_inputs, contracts)
        values = {**fields, "input_ports": inputs, "output_ports": outputs}
        try:
            product = previous.revised(**values) if previous else DataProduct(**values)
        except DataProductRuleError as e:
            problems = e.messages + problems
        if product is None or problems:
            raise DataProductRuleError(problems)

        # Contracts older than the version history get their current version
        # recorded, so the ports' foreign key finds it.
        fresh = [*fresh_inputs, *fresh_outputs]
        await self.contracts.add_baseline_versions(
            [baseline(contracts[i]) for i in _contract_ids(fresh, contracts)]
        )
        usage = await self.products.list_port_usage(
            _contract_ids(fresh_outputs, contracts)
        )
        warnings = _warnings(product, fresh_inputs, fresh_outputs, contracts, usage)
        return product, warnings


class CreateDataProductUseCase(_ProductWriter):
    async def execute(
        self,
        *,
        name: str,
        description: str,
        domain_id: uuid.UUID,
        status: str,
        input_ports: list[InputPort],
        output_ports: list[OutputPort],
    ) -> SavedProduct:
        fields = {
            "name": name,
            "description": description,
            "domain_id": domain_id,
            "status": status,
            "input_ports": input_ports,
            "output_ports": output_ports,
        }
        async with self.products.transaction():
            product, warnings = await self._prepare(fields, None)
            saved = await self.products.add(product)
        return SavedProduct(saved, warnings)


class UpdateDataProductUseCase(_ProductWriter):
    async def execute(
        self,
        product_id: uuid.UUID,
        *,
        name: str,
        description: str,
        domain_id: uuid.UUID,
        status: str,
        input_ports: list[InputPort],
        output_ports: list[OutputPort],
    ) -> SavedProduct | None:
        """A full replace of the product and its ports. None when it does not exist."""
        fields = {
            "name": name,
            "description": description,
            "domain_id": domain_id,
            "status": status,
            "input_ports": input_ports,
            "output_ports": output_ports,
        }
        async with self.products.transaction():
            previous = await self.products.get_by_id(product_id)
            if previous is None:
                return None
            product, warnings = await self._prepare(fields, previous)
            saved = await self.products.replace(product)
        return SavedProduct(saved, warnings) if saved is not None else None
