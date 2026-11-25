"""The catalog as the migrations before ODPS plan 1 leave it, for tests that run
that plan's migration and the SQL written against it on a throwaway Postgres.

Only the tables and constraints the plan touches are built. Callers run inside a
transaction they roll back, as the other migration tests do.
"""

import os
from pathlib import Path

import pytest

DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
requires_database = pytest.mark.skipif(
    not DATABASE_URL, reason="TEST_DATABASE_URL is not set"
)

MIGRATIONS = Path(__file__).parents[2] / "database/migrations"
PLAN_1_SQL = MIGRATIONS / "20261124000001_odps_ports_status_domain.sql"
_HISTORY_SQL = MIGRATIONS / "20261101000005_contract_versions.sql"

BASE_DDL = """
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'admin') THEN
        CREATE ROLE admin;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_user') THEN
        CREATE ROLE app_user;
    END IF;
END $$;
CREATE SCHEMA catalog;
CREATE SCHEMA platform;
ALTER DEFAULT PRIVILEGES IN SCHEMA catalog GRANT ALL ON TABLES TO admin, app_user;

CREATE TABLE catalog.domains (
    id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE catalog.data_contracts (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title         TEXT  NOT NULL DEFAULT '',
    version       TEXT  NOT NULL DEFAULT '1.0.0',
    owner         TEXT  NOT NULL DEFAULT '',
    domain_id     UUID  NOT NULL REFERENCES catalog.domains(id) ON DELETE RESTRICT,
    tier          INT   NOT NULL DEFAULT 4,
    status        TEXT  NOT NULL DEFAULT 'draft'
                  CONSTRAINT chk_dc_status
                  CHECK (status IN ('draft', 'in_review', 'active', 'deprecated')),
    models        JSONB NOT NULL DEFAULT '{"fields":[]}',
    servicelevels JSONB NOT NULL DEFAULT '{"properties": []}',
    description   JSONB NOT NULL DEFAULT '{"purpose":"","usage":"","limitations":""}',
    team_members  JSONB NOT NULL DEFAULT '[]',
    support       JSONB NOT NULL DEFAULT '[]',
    servers       JSONB NOT NULL DEFAULT '[]',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE catalog.data_products (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name              TEXT NOT NULL,
    description       TEXT NOT NULL,
    data_contracts_id UUID NOT NULL,
    repo_url          TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (data_contracts_id)
        REFERENCES catalog.data_contracts(id) ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TYPE platform.port_role_type AS ENUM ('INPUT', 'OUTPUT', 'INTERNAL');
CREATE TYPE platform.binding_status AS ENUM ('ACTIVE', 'DISABLED');
CREATE TABLE platform.data_ports_type (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type TEXT NOT NULL,
    connection_ref TEXT NOT NULL,
    schema_ref TEXT NOT NULL
);
CREATE TABLE platform.data_ports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    port_role platform.port_role_type NOT NULL,
    data_ports_type_id UUID NOT NULL REFERENCES platform.data_ports_type(id)
);
CREATE TABLE platform.product_port_binding (
    data_products_id UUID NOT NULL REFERENCES catalog.data_products(id),
    data_ports_id UUID NOT NULL REFERENCES platform.data_ports(id),
    status platform.binding_status NOT NULL,
    PRIMARY KEY (data_products_id, data_ports_id)
);
"""


async def before_plan_1(conn) -> None:
    """The schema as it stands just before the plan 1 migration."""
    await conn.execute(BASE_DDL)
    await conn.execute(_HISTORY_SQL.read_text(encoding="utf-8"))


async def run_plan_1(conn) -> None:
    await conn.execute(PLAN_1_SQL.read_text(encoding="utf-8"))


async def migrated(conn) -> None:
    await before_plan_1(conn)
    await run_plan_1(conn)
