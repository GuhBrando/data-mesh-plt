"""Give every data product created before ODPS its output port.

Run by entrypoint.sh after the migrations and before the app serves:

  uv run python -m scripts.backfill_output_ports

Idempotent. Uses the application's database settings (DB_* and ADMIN_PASSWORD).
ODPS plan 2 deletes this script with `data_products.data_contracts_id`.
"""

import asyncio

from backend.infra.postgres import connect
from backend.infra.repositories.data_contract_repository import (
    PostgresDataContractRepository,
)
from backend.infra.repositories.data_product_repository import (
    PostgresDataProductRepository,
)
from backend.use_cases.data_product.backfill import BackfillOutputPortsUseCase


async def main() -> None:
    conn = await connect()
    try:
        count = await BackfillOutputPortsUseCase(
            PostgresDataProductRepository(conn), PostgresDataContractRepository(conn)
        ).execute()
    finally:
        await conn.close()
    print(f"Backfilled output ports for {count} data products")


if __name__ == "__main__":
    asyncio.run(main())
