-- =============================================================================
-- Immutable contract version history and the terminal `retired` status.
-- Atlas manages the transaction; do NOT add explicit BEGIN/COMMIT here.
-- =============================================================================

-- 1. `retired` joins the accepted statuses.
ALTER TABLE catalog.data_contracts DROP CONSTRAINT chk_dc_status;
ALTER TABLE catalog.data_contracts
    ADD CONSTRAINT chk_dc_status
    CHECK (status IN ('draft', 'in_review', 'active', 'deprecated', 'retired'));

-- 2. History table. The primary key is the unique rule on (contract_id, version).
--    created_by has no FK on purpose: ON DELETE SET NULL is an UPDATE, which the
--    trigger below rejects, so deleting a user would fail.
CREATE TABLE catalog.contract_versions (
    contract_id  UUID        NOT NULL
                 REFERENCES catalog.data_contracts(id) ON DELETE CASCADE,
    version      TEXT        NOT NULL,
    yaml_content TEXT        NOT NULL,
    created_by   UUID,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT contract_versions_pkey PRIMARY KEY (contract_id, version)
);

-- 3. Grants. ALTER DEFAULT PRIVILEGES hands every new catalog table to both roles
--    with UPDATE and DELETE, so they are taken back here. DELETE stays on admin:
--    where admin owns this table (azure), ON DELETE CASCADE runs as the owner and
--    fails without it. The triggers below cover direct deletes.
REVOKE UPDATE, TRUNCATE ON catalog.contract_versions FROM admin, app_user;
REVOKE DELETE ON catalog.contract_versions FROM app_user;

-- 4. Rows are immutable for every role, superusers included: no UPDATE, no
--    TRUNCATE, and no DELETE except the cascade from catalog.data_contracts,
--    recognised by the parent row being gone already. The table owner (admin on
--    azure) and superusers can still disable or drop the triggers; they stop
--    mistakes and the application, not the owner.
CREATE FUNCTION catalog.reject_contract_version_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF NOT EXISTS (
            SELECT 1 FROM catalog.data_contracts WHERE id = OLD.contract_id
        ) THEN
            RETURN OLD;
        END IF;
    END IF;
    RAISE EXCEPTION 'catalog.contract_versions rows are immutable (%)', TG_OP;
END $$;

CREATE TRIGGER trg_contract_versions_immutable
    BEFORE UPDATE OR DELETE ON catalog.contract_versions
    FOR EACH ROW EXECUTE FUNCTION catalog.reject_contract_version_change();

CREATE TRIGGER trg_contract_versions_no_truncate
    BEFORE TRUNCATE ON catalog.contract_versions
    FOR EACH STATEMENT EXECUTE FUNCTION catalog.reject_contract_version_change();

-- =============================================================================
-- ROLLBACK (run manually if needed):
-- DROP TABLE catalog.contract_versions;
-- DROP FUNCTION catalog.reject_contract_version_change();
-- UPDATE catalog.data_contracts SET status = 'deprecated' WHERE status = 'retired';
-- ALTER TABLE catalog.data_contracts DROP CONSTRAINT chk_dc_status;
-- ALTER TABLE catalog.data_contracts ADD CONSTRAINT chk_dc_status
--     CHECK (status IN ('draft', 'in_review', 'active', 'deprecated'));
-- =============================================================================
