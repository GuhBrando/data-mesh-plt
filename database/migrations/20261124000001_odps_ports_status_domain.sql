-- =============================================================================
-- ODPS plan 1: a data product gets its own domain, an ODPS status, and input
-- and output ports that reference contract versions. The single contract link
-- becomes nullable; the backfill command (scripts/backfill_output_ports.py, run
-- by entrypoint.sh) turns it into an output port, and plan 2 drops it.
-- Atlas manages the transaction; do NOT add explicit BEGIN/COMMIT here.
-- New catalog tables reach admin and app_user through ALTER DEFAULT PRIVILEGES
-- (20260428000001_add_rbac.sql, 20260401000001_fix_admin_schema_grants.sql).
-- =============================================================================

-- 1. The product's own domain, taken from its current contract.
ALTER TABLE catalog.data_products
    ADD COLUMN domain_id UUID REFERENCES catalog.domains(id) ON DELETE RESTRICT;
UPDATE catalog.data_products p
SET domain_id = dc.domain_id
FROM catalog.data_contracts dc
WHERE dc.id = p.data_contracts_id;
ALTER TABLE catalog.data_products ALTER COLUMN domain_id SET NOT NULL;
CREATE INDEX idx_data_products_domain ON catalog.data_products(domain_id);

-- 2. ODPS status: existing products are live, new ones start as drafts.
ALTER TABLE catalog.data_products
    ADD COLUMN status TEXT NOT NULL DEFAULT 'active'
    CONSTRAINT chk_dp_status
    CHECK (status IN ('proposed', 'draft', 'active', 'deprecated', 'retired'));
ALTER TABLE catalog.data_products ALTER COLUMN status SET DEFAULT 'draft';

-- 3. The single contract link is emptied by the backfill; plan 2 drops it.
ALTER TABLE catalog.data_products ALTER COLUMN data_contracts_id DROP NOT NULL;

-- 4. Input and output ports, owned by their product.
CREATE TABLE catalog.data_product_ports (
    id              UUID        NOT NULL DEFAULT gen_random_uuid(),
    data_product_id UUID        NOT NULL
                    REFERENCES catalog.data_products(id) ON DELETE CASCADE,
    role            TEXT        NOT NULL,
    name            TEXT        NOT NULL,
    version         TEXT,
    contract_id     UUID,
    type            TEXT,
    description     TEXT,
    deprecated      BOOLEAN     NOT NULL DEFAULT false,
    authoritative_definitions JSONB NOT NULL DEFAULT '[]',
    input_contracts JSONB       NOT NULL DEFAULT '[]',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT data_product_ports_pkey PRIMARY KEY (id),
    CONSTRAINT chk_dpp_role CHECK (role IN ('input', 'output')),
    -- With a contract, the version is the contract version.
    CONSTRAINT chk_dpp_contract_version
        CHECK (contract_id IS NULL OR version IS NOT NULL),
    CONSTRAINT chk_dpp_output_only CHECK (
        role = 'output'
        OR (type IS NULL AND description IS NULL AND input_contracts = '[]'::jsonb)
    ),
    -- ODPS keys a port by name and version. The btree, led by data_product_id,
    -- also serves lookups by product, so no separate index is needed.
    CONSTRAINT uq_dpp_key
        UNIQUE NULLS NOT DISTINCT (data_product_id, role, name, version),
    -- MATCH SIMPLE skips the check when contract_id is NULL, so a port without
    -- a contract keeps a free version. A contract a port uses cannot be deleted:
    -- the cascade to its versions stops here.
    CONSTRAINT fk_dpp_contract_version FOREIGN KEY (contract_id, version)
        REFERENCES catalog.contract_versions(contract_id, version)
        ON DELETE RESTRICT
);
CREATE INDEX idx_dpp_contract ON catalog.data_product_ports(contract_id, version);

-- 5. The platform data-port model was never used: no code reads it. Stop rather
--    than lose rows if that is not true.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM platform.product_port_binding)
       OR EXISTS (SELECT 1 FROM platform.data_ports)
       OR EXISTS (SELECT 1 FROM platform.data_ports_type) THEN
        RAISE EXCEPTION 'platform data-port tables hold rows; move them to catalog.data_product_ports before this migration';
    END IF;
END $$;
DROP TABLE platform.product_port_binding, platform.data_ports, platform.data_ports_type;
DROP TYPE platform.port_role_type, platform.binding_status;

-- =============================================================================
-- ROLLBACK (run manually if needed; the platform tables come back empty from
-- 20260326000001_create_ddl.sql):
-- DROP TABLE catalog.data_product_ports;
-- UPDATE catalog.data_products p SET data_contracts_id = ... ; -- from the ports
-- ALTER TABLE catalog.data_products ALTER COLUMN data_contracts_id SET NOT NULL;
-- ALTER TABLE catalog.data_products DROP COLUMN status;
-- ALTER TABLE catalog.data_products DROP COLUMN domain_id;
-- =============================================================================
