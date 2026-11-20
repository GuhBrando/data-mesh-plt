-- =============================================================================
-- ODCS contract metadata: description, team members, support channels, servers.
-- Additive: NOT NULL with constant defaults, so existing rows are filled by
-- ADD COLUMN. app_user holds table-level DML on catalog.data_contracts
-- (20260428000001_add_rbac.sql), which covers new columns; no GRANT needed.
-- Atlas manages the transaction; do NOT add explicit BEGIN/COMMIT here.
-- =============================================================================

ALTER TABLE catalog.data_contracts
    ADD COLUMN description  JSONB NOT NULL DEFAULT '{"purpose":"","usage":"","limitations":""}',
    ADD COLUMN team_members JSONB NOT NULL DEFAULT '[]',
    ADD COLUMN support      JSONB NOT NULL DEFAULT '[]',
    ADD COLUMN servers      JSONB NOT NULL DEFAULT '[]';

-- =============================================================================
-- ROLLBACK (run manually if needed):
-- ALTER TABLE catalog.data_contracts
--     DROP COLUMN description,
--     DROP COLUMN team_members,
--     DROP COLUMN support,
--     DROP COLUMN servers;
-- =============================================================================
