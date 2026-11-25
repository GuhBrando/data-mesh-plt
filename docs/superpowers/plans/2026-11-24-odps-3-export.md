# ODPS Plan 3 — Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Export a data product as an ODPS v1.1.0 document that validates against the official JSON Schema, serve it at `GET /data-products/{id}/odps`, validate it in the tests and in CI, and let people view, copy and download it from the product page.

**Architecture:** `to_odps(product)` is pure. It builds the document from the aggregate in snake_case and passes it through one function, `_odps`, that maps every key to camelCase and drops empty values (one mapping for every section, never one function per section). The router dumps it as YAML with the platform's dumper. The official schema is vendored in the test fixtures; a sample product built by the real code is validated in unit tests and in the CI job that already lints ODCS.

**Tech Stack:** Python 3.12, FastAPI, PyYAML, jsonschema (Draft 2019-09), React 18, TanStack Query, Vitest.

**Spec:** `docs/superpowers/specs/2026-11-24-odps-adoption-design.md` (Plan 3, Standard Notes, Anti-goals, Engineering Principles "One mapping drives the export").

**Starting point:** branch `feat/odps-3-export`, stacked on `feat/odps-2-product-metadata` (PR #59), in the worktree `D:\Projetos\GitHub\data_mesh_plt-odps3`. No migration.

## Global Constraints

- `ODPS_API_VERSION = "v1.1.0"`, `kind: DataProduct`. `id`, `contractId` and `inputContracts[].id` are UUID strings.
- Empty values are left out (`None`, `""`, `[]`, `{}`, `false`), as `to_odcs` does, except a custom property's `value`, which is user data and kept as is (its inner keys are not renamed either).
- `deprecated` on the product is derived from status and appears only when true; ports and management ports carry their own flag.
- `productCreatedTs` is `created_at` in UTC, ISO 8601 with `Z`.
- Never exported: `repo_url`, port `contract`, `produced_by`, `consumed_by`, warnings (anti-goal: no platform-only fields).
- Schema vendored verbatim at `tests/fixtures/odps/odps-json-schema-v1.1.0.json` from tag `v1.1.0`, SHA-256 `b7eae1af15b3c6b18e5dffaa2119212acb38ec73286933c76d16c8712e0d90d1`.
- Prose rules checked beside the schema: at least one output port; status one of the five ODPS values.
- Same CI gates and repository rules as plans 1 and 2. CI job names stay unchanged (they may be required checks).

## Review Focus

1. A custom property whose value is an object with snake_case keys (`{"cost_center": 1}`) keeps those keys; only ODPS keys are renamed. Test: `test_custom_property_values_are_left_alone` (Task 1).
2. A custom property whose value is `0`, `false` or `""` is still exported. Test: `test_falsy_custom_property_values_are_kept` (Task 1).
3. A product with only the short-path fields (no sections, no inputs) still validates. Test: `test_minimal_product_validates` (Task 1).
4. A name or text with non-ASCII characters (`Exposição`) is written as is in the YAML, not escaped. Test: `test_yaml_keeps_accents` (Task 2).
5. A `${VAR}` value survives the export verbatim. Test: `test_variables_are_exported_verbatim` (Task 1).

---

### Task 1: `to_odps` and the vendored schema

**Files:** Create `backend/use_cases/data_product/odps.py`, `tests/fixtures/odps/__init__.py`, `tests/fixtures/odps/odps-json-schema-v1.1.0.json`, `tests/fixtures/odps/validator.py` (`VALIDATOR`, plus a `__main__` that validates YAML files and exits 1 on any error), `tests/fixtures/odps/sample_product.py` (`make_product()`, `FULL_PRODUCT`, `__main__` writing a product's YAML), `tests/unit/use_cases/data_product/test_odps.py`.

**Interfaces — Produces:** `ODPS_API_VERSION: str`; `to_odps(product: DataProduct) -> dict[str, Any]`; `odps_yaml(product: DataProduct) -> str` (`dump_odcs` from `yaml_builder`, the platform's YAML dumper).

- [ ] Failing tests: `test_minimal_product_validates` (exact dict for a one-output product), `test_full_product_validates`, `test_keys_are_odps_camel_case` (`dateIn`, `invitationUrl`, `verifiedStatements`, `inputContracts[0].id`, `contractId`, `productCreatedTs`), `test_custom_property_values_are_left_alone`, `test_falsy_custom_property_values_are_kept`, `test_variables_are_exported_verbatim`, `test_platform_only_fields_are_not_exported`, `test_deprecated_follows_status`, `test_empty_sections_are_left_out`, `test_prose_rules_hold` (≥ 1 output, status in the five), `test_vendored_schema_is_the_v1_1_0_tag` (SHA-256).
- [ ] Implement; PASS; ruff; commit `feat(products): export a data product as ODPS v1.1.0`.

### Task 2: API and CI

**Files:** Modify `backend/interface/routers/data_product.py` (+ test), `.github/workflows/ci.yml` (the ODCS lint job also generates `sample_product` and validates it).

- [ ] Failing router tests: `test_odps_export_is_yaml_of_to_odps`, `test_odps_export_404_for_unknown_product`, `test_yaml_keeps_accents`.
- [ ] Implement `GET /data-products/{product_id}/odps` (`PlainTextResponse`, `text/plain`, 404 `Data product not found`); add to the CI job: `uv sync --extra dev` (jsonschema is a dev dependency), `python -m tests.fixtures.odps.sample_product odcs-lint/product.odps.yaml full` and `python -m tests.fixtures.odps.validator odcs-lint/product.odps.yaml`; the datacontract lint loop skips `*.odps.yaml`.
- [ ] PASS; run the two CI commands locally; commit `feat(api): ODPS export endpoint, validated in CI`.

### Task 3: "Export ODPS" on the product page

**Files:** Create `frontend/src/components/ui/YamlModal.tsx` (+ test) from the contract page's local `YamlModal`, with optional `fileName` adding **Copy** and **Download**; modify `DataContractDetail.tsx` to use it (unchanged behaviour), `hooks/useDataProducts.ts` (`useDataProductOdps(id, enabled)`, key `['data-products', id, 'odps']`), `DataProductDetail.tsx` (+ test).

- [ ] Failing tests: modal shows YAML, Copy writes it to the clipboard and says "Copied", Download saves `<product-slug>.odps.yaml`; product page "Export ODPS" opens it and fetches only when opened; contract page tests unchanged.
- [ ] Implement; full frontend gate; commit `feat(frontend): view, copy and download a product's ODPS document`.

### Task 4: Verify and open the PR

- [ ] Isolated stack (own network): export the products created in the plan 2 run and validate each with the vendored schema.
- [ ] Backend and frontend gates; push; PR against `feat/odps-2-product-metadata`'s target, noting it goes after #59.
