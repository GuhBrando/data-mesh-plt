-- =============================================================================
-- ODPS plan 2: every other ODPS v1.1.0 field on the data product and its ports,
-- management ports, and the end of the single contract link.
-- Atlas manages the transaction; do NOT add explicit BEGIN/COMMIT here.
-- New catalog tables reach admin and app_user through ALTER DEFAULT PRIVILEGES.
--
-- Release gate (ODPS design, call 11): ship only after a release containing
-- plan 1 has run its backfill everywhere; the guard below is the safety net.
-- =============================================================================

-- 1. Nothing may still depend on what this migration drops.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM catalog.data_products WHERE data_contracts_id IS NOT NULL) THEN
        RAISE EXCEPTION 'data products still linked by data_contracts_id: run the ODPS plan 1 backfill (start the backend on plan 1 once) before this migration';
    END IF;
    IF EXISTS (SELECT 1 FROM platform.control_ports)
       OR EXISTS (SELECT 1 FROM platform.control_port_types) THEN
        RAISE EXCEPTION 'platform control-port tables hold rows; move them to catalog.data_product_management_ports before this migration';
    END IF;
END $$;

ALTER TABLE catalog.data_products DROP COLUMN data_contracts_id;
-- Replaced by catalog.data_product_management_ports; no code ever read them.
DROP TABLE platform.control_ports, platform.control_port_types;

-- 2. The product's ODPS sections. Keys inside JSONB are the API's snake_case
--    names; the ODPS export maps them to camelCase.
ALTER TABLE catalog.data_products
    ALTER COLUMN description TYPE JSONB USING jsonb_build_object(
        'purpose', description, 'usage', '', 'limitations', ''),
    ALTER COLUMN description SET DEFAULT '{"purpose": "", "usage": "", "limitations": ""}',
    ADD COLUMN version TEXT,
    ADD COLUMN type TEXT,
    ADD COLUMN tenant TEXT,
    ADD COLUMN tags JSONB NOT NULL DEFAULT '[]',
    ADD COLUMN synonyms JSONB NOT NULL DEFAULT '[]',
    ADD COLUMN context JSONB NOT NULL DEFAULT '{}',
    ADD COLUMN team JSONB NOT NULL DEFAULT '{}',
    ADD COLUMN support JSONB NOT NULL DEFAULT '[]',
    ADD COLUMN custom_properties JSONB NOT NULL DEFAULT '[]',
    ADD COLUMN authoritative_definitions JSONB NOT NULL DEFAULT '[]';

-- 3. Port fields. ODPS puts synonyms, context and SBOM on output ports only.
ALTER TABLE catalog.data_product_ports
    ADD COLUMN tags JSONB NOT NULL DEFAULT '[]',
    ADD COLUMN custom_properties JSONB NOT NULL DEFAULT '[]',
    ADD COLUMN synonyms JSONB NOT NULL DEFAULT '[]',
    ADD COLUMN context JSONB NOT NULL DEFAULT '{}',
    ADD COLUMN sbom JSONB NOT NULL DEFAULT '[]',
    DROP CONSTRAINT chk_dpp_output_only,
    ADD CONSTRAINT chk_dpp_output_only CHECK (
        role = 'output'
        OR (type IS NULL AND description IS NULL
            AND input_contracts = '[]'::jsonb AND synonyms = '[]'::jsonb
            AND context = '{}'::jsonb AND sbom = '[]'::jsonb)
    );

-- 4. Management ports, owned by their product and keyed by name.
CREATE TABLE catalog.data_product_management_ports (
    id              UUID        NOT NULL DEFAULT gen_random_uuid(),
    data_product_id UUID        NOT NULL
                    REFERENCES catalog.data_products(id) ON DELETE CASCADE,
    name            TEXT        NOT NULL,
    content         TEXT        NOT NULL,
    type            TEXT        NOT NULL DEFAULT 'rest',
    url             TEXT,
    channel         TEXT,
    description     TEXT,
    deprecated      BOOLEAN     NOT NULL DEFAULT false,
    tags            JSONB       NOT NULL DEFAULT '[]',
    custom_properties JSONB     NOT NULL DEFAULT '[]',
    authoritative_definitions JSONB NOT NULL DEFAULT '[]',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT data_product_management_ports_pkey PRIMARY KEY (id),
    CONSTRAINT chk_dmp_type CHECK (type IN ('rest', 'topic')),
    -- Its btree, led by data_product_id, also serves lookups by product.
    CONSTRAINT uq_dmp_name UNIQUE (data_product_id, name)
);

-- =============================================================================
-- ROLLBACK (run manually if needed; the control tables come back empty from
-- 20260326000001_create_ddl.sql, the contract link from the output ports):
-- DROP TABLE catalog.data_product_management_ports;
-- ALTER TABLE catalog.data_product_ports DROP COLUMN tags, DROP COLUMN custom_properties,
--     DROP COLUMN synonyms, DROP COLUMN context, DROP COLUMN sbom;  -- and restore chk_dpp_output_only
-- ALTER TABLE catalog.data_products DROP COLUMN version, ... ,
--     ALTER COLUMN description TYPE TEXT USING description->>'purpose';
-- ALTER TABLE catalog.data_products ADD COLUMN data_contracts_id UUID REFERENCES catalog.data_contracts(id);
-- =============================================================================
