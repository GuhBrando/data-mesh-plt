from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import asyncpg

from backend.domain.entities.data_product import (
    STATUS_RULE,
    ContractRef,
    ContractSummary,
    DataProduct,
    DataProductRuleError,
    InputPort,
    OutputPort,
    PortUsage,
    ProductRef,
)
from backend.domain.interfaces.data_product_repository import (
    IDataProductRepository,
    LegacyProduct,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterator
    from contextlib import AbstractAsyncContextManager

# One query reads a product with its ports, each port with the contract it
# references and, through the same contract version, the products on the other
# side: producers for an input, consumers for an output.
_SELECT = """
    SELECT p.id, p.name, p.description, p.domain_id, d.name AS domain, p.status,
           p.repo_url, p.created_at, p.updated_at,
           COALESCE(ports.items, '[]') AS ports
    FROM catalog.data_products p
    JOIN catalog.domains d ON d.id = p.domain_id
    LEFT JOIN LATERAL (
        SELECT json_agg(json_build_object(
            'id', pt.id, 'role', pt.role, 'name', pt.name, 'version', pt.version,
            'contract_id', pt.contract_id, 'type', pt.type,
            'description', pt.description, 'deprecated', pt.deprecated,
            'authoritative_definitions', pt.authoritative_definitions,
            'input_contracts', pt.input_contracts,
            'contract', CASE WHEN dc.id IS NOT NULL THEN json_build_object(
                'title', dc.title, 'status', dc.status, 'version', dc.version,
                'domain', cd.name) END,
            'counterparts', COALESCE(other.items, '[]')
        ) ORDER BY pt.role, pt.name, pt.created_at DESC) AS items
        FROM catalog.data_product_ports pt
        LEFT JOIN catalog.data_contracts dc ON dc.id = pt.contract_id
        LEFT JOIN catalog.domains cd ON cd.id = dc.domain_id
        LEFT JOIN LATERAL (
            SELECT json_agg(DISTINCT jsonb_build_object(
                'id', op.id, 'name', op.name, 'status', op.status)) AS items
            FROM catalog.data_product_ports o
            JOIN catalog.data_products op ON op.id = o.data_product_id
            WHERE o.contract_id = pt.contract_id AND o.version = pt.version
              AND o.role <> pt.role AND o.data_product_id <> pt.data_product_id
        ) other ON true
        WHERE pt.data_product_id = p.id
    ) ports ON true
"""

# Ports are written in one statement: the ones left out are deleted and the rest
# upserted by their key, so a port keeps its id across edits.
_WRITE_PORTS = """
    WITH incoming AS (
        SELECT * FROM unnest($2::text[], $3::text[], $4::text[], $5::uuid[],
                             $6::text[], $7::text[], $8::bool[], $9::text[],
                             $10::text[])
            AS u(role, name, version, contract_id, type, description, deprecated,
                 authoritative_definitions, input_contracts)
    ), removed AS (
        DELETE FROM catalog.data_product_ports p
        WHERE p.data_product_id = $1 AND NOT EXISTS (
            SELECT 1 FROM incoming i
            WHERE i.role = p.role AND i.name = p.name
              AND i.version IS NOT DISTINCT FROM p.version)
    )
    INSERT INTO catalog.data_product_ports
        (data_product_id, role, name, version, contract_id, type, description,
         deprecated, authoritative_definitions, input_contracts)
    SELECT $1, role, name, version, contract_id, type, description, deprecated,
           authoritative_definitions::jsonb, input_contracts::jsonb
    FROM incoming
    ON CONFLICT ON CONSTRAINT uq_dpp_key DO UPDATE SET
        contract_id = EXCLUDED.contract_id, type = EXCLUDED.type,
        description = EXCLUDED.description, deprecated = EXCLUDED.deprecated,
        authoritative_definitions = EXCLUDED.authoritative_definitions,
        input_contracts = EXCLUDED.input_contracts, updated_at = now();
"""

_MISSING_REFERENCES = """
    SELECT r.contract_id, r.version, dc.title
    FROM unnest($1::uuid[], $2::text[]) AS r(contract_id, version)
    LEFT JOIN catalog.data_contracts dc ON dc.id = r.contract_id
    WHERE NOT EXISTS (
        SELECT 1 FROM catalog.contract_versions v
        WHERE v.contract_id = r.contract_id AND v.version = r.version)
"""

_REFERENCE_CONSTRAINTS = frozenset(
    {"fk_dpp_contract_version", "chk_dpp_contract_version"}
)

_MESSAGES: dict[str, Callable[[DataProduct], str]] = {
    "chk_dpp_output_only": lambda _: (
        "Only outputs can have a type, a description or input contracts"
    ),
    "chk_dp_status": lambda _: STATUS_RULE,
    "data_products_domain_id_fkey": lambda p: f"Domain {p.domain_id} does not exist",
}


def _ports(product: DataProduct) -> Iterator[tuple[str, InputPort | OutputPort]]:
    yield from (("input", p) for p in product.input_ports)
    yield from (("output", p) for p in product.output_ports)


def _port_columns(product: DataProduct) -> list[list[Any]]:
    """The ports as one array per column, for unnest."""
    rows = [
        (
            role,
            port.name,
            port.version,
            port.contract_id,
            getattr(port, "type", None),
            getattr(port, "description", None),
            port.deprecated,
            json.dumps(list(port.authoritative_definitions)),
            json.dumps(
                [
                    {"contract_id": str(ref.contract_id), "version": ref.version}
                    for ref in getattr(port, "input_contracts", ())
                ]
            ),
        )
        for role, port in _ports(product)
    ]
    return [list(column) for column in zip(*rows, strict=True)]


def _duplicate_message(product: DataProduct) -> str:
    seen: set[tuple[str, str, str | None]] = set()
    for role, port in _ports(product):
        key = (role, port.name, port.version)
        if key in seen:
            return (
                f"Two {role}s share the name {port.name} and version"
                f" {port.version or '(none)'}; each port needs its own"
            )
        seen.add(key)
    return "Two ports share a name and version; each port needs its own"


def _missing_message(row: Any) -> str:
    if row["title"] is None:
        return f"Contract {row['contract_id']} does not exist"
    if row["version"] is None:
        return f"Contract {row['title']} needs a version"
    return f"Version {row['version']} of contract {row['title']} does not exist"


def _uuid(value: str | None) -> uuid.UUID | None:
    return uuid.UUID(value) if value is not None else None


def _summary(value: dict[str, str] | None) -> ContractSummary | None:
    return ContractSummary(**value) if value is not None else None


def _refs(values: list[dict[str, str]]) -> tuple[ProductRef, ...]:
    refs = (ProductRef(uuid.UUID(v["id"]), v["name"], v["status"]) for v in values)
    return tuple(sorted(refs, key=lambda r: r.name))


def _input(port: dict[str, Any]) -> InputPort:
    return InputPort(
        name=port["name"],
        contract_id=_uuid(port["contract_id"]),
        version=port["version"],
        deprecated=port["deprecated"],
        authoritative_definitions=tuple(port["authoritative_definitions"]),
        id=uuid.UUID(port["id"]),
        contract=_summary(port["contract"]),
        produced_by=_refs(port["counterparts"]),
    )


def _output(port: dict[str, Any]) -> OutputPort:
    return OutputPort(
        name=port["name"],
        contract_id=_uuid(port["contract_id"]),
        version=port["version"],
        type=port["type"],
        description=port["description"],
        deprecated=port["deprecated"],
        authoritative_definitions=tuple(port["authoritative_definitions"]),
        input_contracts=tuple(
            ContractRef(uuid.UUID(ref["contract_id"]), ref["version"])
            for ref in port["input_contracts"]
        ),
        id=uuid.UUID(port["id"]),
        contract=_summary(port["contract"]),
        consumed_by=_refs(port["counterparts"]),
    )


def _row_to_entity(row: Any) -> DataProduct:
    ports = json.loads(row["ports"])
    return DataProduct(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        domain_id=row["domain_id"],
        domain=row["domain"],
        status=row["status"],
        input_ports=[_input(p) for p in ports if p["role"] == "input"],
        output_ports=[_output(p) for p in ports if p["role"] == "output"],
        repo_url=row["repo_url"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class PostgresDataProductRepository(IDataProductRepository):
    def __init__(self, db):
        self.db = db

    def transaction(self) -> AbstractAsyncContextManager[Any]:
        return self.db.transaction()

    async def add(self, product: DataProduct) -> DataProduct:
        async with self._writing(product):
            product_id = await self.db.fetchval(
                """
                INSERT INTO catalog.data_products (name, description, domain_id, status)
                VALUES ($1, $2, $3, $4)
                RETURNING id;
                """,
                product.name,
                product.description,
                product.domain_id,
                product.status,
            )
            await self.db.execute(_WRITE_PORTS, product_id, *_port_columns(product))
        return await self.get_by_id(product_id)

    async def replace(self, product: DataProduct) -> DataProduct | None:
        async with self._writing(product):
            # data_contracts_id is gone from the API: every write empties it.
            found = await self.db.fetchval(
                """
                UPDATE catalog.data_products
                SET name = $1, description = $2, domain_id = $3, status = $4,
                    data_contracts_id = NULL, updated_at = now()
                WHERE id = $5
                RETURNING id;
                """,
                product.name,
                product.description,
                product.domain_id,
                product.status,
                product.id,
            )
            if found is None:
                return None
            await self.db.execute(_WRITE_PORTS, product.id, *_port_columns(product))
        return await self.get_by_id(product.id)

    async def get_by_id(self, product_id: uuid.UUID) -> DataProduct | None:
        row = await self.db.fetchrow(f"{_SELECT} WHERE p.id = $1;", product_id)
        return _row_to_entity(row) if row else None

    async def list(self) -> list[DataProduct]:
        rows = await self.db.fetch(f"{_SELECT} ORDER BY p.updated_at DESC;")
        return [_row_to_entity(r) for r in rows]

    async def delete(self, product_id: uuid.UUID) -> bool:
        async with self.db.transaction():
            result = await self.db.execute(
                "DELETE FROM catalog.data_products WHERE id = $1;",
                product_id,
            )
            return result == "DELETE 1"

    async def update_repo_url(self, product_id: uuid.UUID, repo_url: str) -> None:
        async with self.db.transaction():
            result = await self.db.execute(
                "UPDATE catalog.data_products SET repo_url = $1 WHERE id = $2;",
                repo_url,
                product_id,
            )
            if result != "UPDATE 1":
                raise ValueError(f"No data product with id {product_id}")

    async def list_port_usage(self, contract_ids: list[uuid.UUID]) -> list[PortUsage]:
        if not contract_ids:
            return []
        rows = await self.db.fetch(
            """
            SELECT p.id AS product_id, p.name AS product_name, d.name AS domain,
                   p.status, pt.role, pt.name AS port_name, pt.contract_id,
                   pt.version
            FROM catalog.data_product_ports pt
            JOIN catalog.data_products p ON p.id = pt.data_product_id
            JOIN catalog.domains d ON d.id = p.domain_id
            WHERE pt.contract_id = ANY($1::uuid[])
            ORDER BY pt.role DESC, p.name, pt.version;
            """,
            list(contract_ids),
        )
        return [PortUsage(**dict(r)) for r in rows]

    async def list_legacy_products(self) -> list[LegacyProduct]:
        rows = await self.db.fetch(
            """
            SELECT id, name, description, domain_id, status,
                   data_contracts_id AS contract_id
            FROM catalog.data_products
            WHERE data_contracts_id IS NOT NULL
            ORDER BY created_at;
            """
        )
        return [LegacyProduct(**dict(r)) for r in rows]

    @asynccontextmanager
    async def _writing(self, product: DataProduct) -> AsyncIterator[None]:
        """A savepoint whose constraint violations become DataProductRuleError.
        The savepoint is rolled back first, so the caller's transaction can still
        run the lookup that names a missing contract version."""
        try:
            async with self.db.transaction():
                yield
        except asyncpg.CardinalityViolationError:
            # Two incoming ports with one key: the upsert would touch a row twice.
            raise DataProductRuleError([_duplicate_message(product)]) from None
        except asyncpg.IntegrityConstraintViolationError as exc:
            raise await self._rule_error(exc, product) from None

    async def _rule_error(
        self, exc: asyncpg.IntegrityConstraintViolationError, product: DataProduct
    ) -> Exception:
        name = exc.constraint_name
        if name in _REFERENCE_CONSTRAINTS:
            return DataProductRuleError(await self._missing_references(product))
        message = _MESSAGES.get(name)
        return DataProductRuleError([message(product)]) if message else exc

    async def _missing_references(self, product: DataProduct) -> list[str]:
        refs = [(p.contract_id, p.version) for _, p in _ports(product) if p.contract_id]
        rows = await self.db.fetch(
            _MISSING_REFERENCES, [r[0] for r in refs], [r[1] for r in refs]
        )
        return [_missing_message(r) for r in rows] or [
            "A port references a contract version that does not exist"
        ]
