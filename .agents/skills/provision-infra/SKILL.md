---
name: provision-infra
description: Use when provisioning the Data Mesh Platform Azure infrastructure from scratch (or resuming a partial setup) — bootstrap remote state, platform stack, Databricks workspace, Unity Catalog. Triggers include "provisionar infra", "set up infra from zero", "terraform apply do zero", first-time environment setup, recreating the platform in a new subscription.
---

# Provision Data Mesh Platform Infrastructure

## Overview

Guided, end-to-end provisioning of the platform's Azure + Databricks infra via the
Terraform stacks under `infra/terraform/`. You (Codex) run the commands in order,
collect inputs, validate every `plan` before `apply`, and STOP at the manual gates.

**Source of truth:** `infra/terraform/README.md`. This skill is the runbook; read
that README for the long-form rationale behind any step.

**Scope:** infrastructure only. App deploy (backend/frontend containers) happens via
GitHub Actions (`.github/workflows/cd.yml`) — not here.

**Reentrant:** every phase is idempotent. If a phase is already done (state exists,
SP already admin, resource already imported), detect it and skip — never re-run
`bootstrap` or the one-time grants blindly.

## Execution order (STOP at each ⛔ gate)

| # | Directory | Does | Gate |
|---|-----------|------|------|
| 0 | — | prereqs, `az login`, collect IDs | — |
| 1 | `bootstrap/` | remote-state storage (local state) | — |
| 2 | `platform/` | identities, core, apps, storage, Databricks **workspace** | ⛔ Owner/UAA identity |
| 3 | `databricks_bootstrap/` | register `dmplt-admin` SP + grant account-admin | ⛔ caller is Databricks **account admin** |
| 4 | `data_plane/` | Unity Catalog metastore, catalogs, grants | — |
| 5 | `data_plane/` | (optional) read access for all users | — |

All commands run from each stack's directory under `infra/terraform/`. PowerShell is
primary (Windows). The three `grant-*.sh` scripts are **bash** — run them in Git Bash.

## Phase 0 — Prerequisites & inputs

1. Verify CLIs on PATH: `az`, `terraform`, `databricks`, `jq`, plus `bash` (Git Bash,
   for the grant scripts). If any is missing, tell the user how to install it — do
   NOT auto-install.
2. `az login`, then `az account set --subscription <SUB_ID>`.
3. Collect and confirm three values (these fill the tfvars):
   - `subscription_id` — `az account show --query id -o tsv`
   - `tenant_id` — `az account show --query tenantId -o tsv`
   - `databricks_account_id` — from the Account Console
     (https://accounts.azuredatabricks.net → top-right → Account ID). **Sensitive.**

## Phase 1 — Bootstrap remote state

```powershell
cd infra/terraform/bootstrap
terraform init
terraform apply -var="subscription_id=<SUB_ID>"
```
Creates `dmplt-tfstate-rg` / `dmplttfstate` / container `tfstate`. **Skip-if-done:**
if `dmplttfstate` already exists (`az storage account show -n dmplttfstate -g dmplt-tfstate-rg`),
the backend is ready — move on.

## Phase 2 — Platform stack ⛔

⛔ **Gate:** creating role assignments needs **Owner** or **User Access
Administrator**. Plain Contributor fails on `azurerm_role_assignment.*`. Confirm the
logged-in identity has it before `apply`.

The state backend authenticates via **Azure AD** (`use_azuread_auth`), so the
operator needs `Storage Blob Data Contributor` on `dmplttfstate` — Owner alone is
control-plane only and does NOT grant blob data access. **Run in Git Bash** (idempotent;
before dmplt-devops exists it grants only the operator and tells you to re-run later):
```bash
cd ../platform
bash grant-ci-permissions.sh
```

```powershell
cd ../platform
Copy-Item terraform.tfvars.example terraform.tfvars   # set subscription_id, tenant_id, github_repo, location
terraform init
```

**Import (first run only)** — if `dmplt-rg`, `dmpltacr`, `dmplt-cae`,
`dmplt-ca-backend`, `dmplt-stapp-frontend` already exist from the old
`scripts/azure-setup.sh`:
```powershell
$env:SUBSCRIPTION_ID = "<SUB_ID>"
./import.ps1
```
Then heed the script's **Log Analytics** warning: if a LAW already backs `dmplt-cae`,
import it as `module.core.azurerm_log_analytics_workspace.main` before applying, or a
duplicate `dmplt-law` is created. On a truly empty subscription, skip import entirely.

```powershell
terraform plan    # MUST show zero destroy/replace on any imported resource — if not, stop and reconcile
terraform apply
```
New resources (not imported): `dmpltsta`, the Databricks workspace, the access
connector, the UC storage role assignment.

**After apply — enable CI (one-time).** GitHub Actions (`infra.yml`) runs the platform
stack as the `dmplt-devops` SP via OIDC (no secret). Everything CI needs comes from
the same script: tfstate blob access, the Graph `Application.ReadWrite.OwnedBy` role,
ownership of the dmplt-admin/dmplt-devops apps (self-ownership is inexpressible in
HCL), and the repository variables the workflow reads (`AZURE_CLIENT_ID` /
`AZURE_TENANT_ID` / `AZURE_SUBSCRIPTION_ID`, set via `gh`). Locally nothing is
hardcoded: the script autodetects ids from the `az` session (override with
`AZURE_SUBSCRIPTION_ID=... AZURE_TENANT_ID=...`). The same run also imports the
**GitHub App private key** into Key Vault `dmplt-kv` (sign-only, never in Terraform
state). While the vault has no key, `GITHUB_APP_PEM` is **required** — ask the user
for the path of the `.pem` downloaded from the App (Credentials → Key pairs → New
key); never read, print or copy its content. **Re-run it in Git Bash** now that
`dmplt-devops` exists:
```bash
GITHUB_APP_PEM="<path-to>/<app>.<date>.private-key.pem" bash grant-ci-permissions.sh
```
Have the user compare the printed fingerprint with the one GitHub lists for the key,
then delete the `.pem`. Once the key is in the vault, re-runs need no `GITHUB_APP_PEM`.
See `docs/superpowers/specs/2026-11-22-github-app-auth-design.md` for the cutover.

## Phase 3 — Register admin SP + account admin ⛔

⛔ **Gate:** this is the ONE place a human **Databricks account admin** is required.
An Azure AD **Global Administrator** is one implicitly. The `databricks_bootstrap`
account provider auths as your `az` identity (`auth_type = azure-cli`), and
registering an account-level SP requires account admin. Ensure `az` is logged in as
such an identity.

```powershell
cd ../databricks_bootstrap
Copy-Item terraform.tfvars.example terraform.tfvars   # set databricks_account_id, tenant_id
terraform init
terraform apply                                        # registers dmplt-admin in the account
```

Then promote the SP to account admin (Terraform cannot — no `account_admin` role in
the provider). **Run in Git Bash** from this directory:
```bash
ACCOUNT_ID=<databricks_account_id> bash grant-account-admin.sh
```
Idempotent: a no-op if `dmplt-admin` is already an account admin. **Manual
alternative:** Account Console → User management → Service principals → `dmplt-admin`
→ toggle **Account admin**.

## Phase 4 — Data plane (Unity Catalog)

```powershell
cd ../data_plane
Copy-Item terraform.tfvars.example terraform.tfvars   # set databricks_account_id, tenant_id
terraform init
terraform apply
```
No gate: it authenticates purely as the `dmplt-admin` SP (id/secret pulled from the
platform stack's remote state). Outputs: `catalog_names`, `metastore_id`.

## Phase 5 — Grant read to all users (optional)

Catalogs are owned by `dmplt-admin`, so humans don't see them until granted. To give
every account user read (`USE_CATALOG`+`USE_SCHEMA`+`SELECT`), **run in Git Bash**:
```bash
cd ../data_plane
bash grant-read-all-users.sh
```
Additive and idempotent.

## Steady state (after first full run)

The bootstrap, import, and both grants are one-time. Ongoing changes are just
`terraform apply` in `platform/`, then in `data_plane/`.

## Retrieving outputs

- Workspace URL / client ids: `terraform output` in `platform/`.
- Secret: `terraform output -raw admin_client_secret` (in `platform/`).

## Common mistakes

| Symptom | Cause / fix |
|---------|-------------|
| `plan` wants to **destroy/replace** an imported resource | Import mismatch or missing LAW import. Stop, reconcile state before `apply`. |
| `init` fails with 403 on blob/state access | Identity lacks `Storage Blob Data Contributor` on `dmplttfstate` (backend uses Azure AD auth). Run `platform/grant-ci-permissions.sh`. |
| CI plan: `Authorization_RequestDenied` on `azuread_application.*` | `dmplt-devops` lacks Graph role/ownership — `grant-ci-permissions.sh` wasn't (re-)run after the platform apply. |
| `AuthorizationFailed` on `azurerm_role_assignment` | Identity lacks Owner/UAA (Phase 2 gate). Re-run with a privileged identity. |
| `grant-ci-permissions.sh`: "GitHub App key is not in dmplt-kv yet" | Pass `GITHUB_APP_PEM` with the path of the App's `.pem`. |
| `terraform apply`: `dmplt-kv` "already exists" | The vault was created by hand: `terraform import 'module.backend_app.azurerm_key_vault.main' <vault-id>`, then plan again. |
| `grant-account-admin.sh`: "SP is not registered in the account" | Phase 3 `terraform apply` (databricks_bootstrap) didn't run first. |
| data_plane provider auth fails | `dmplt-admin` isn't account admin yet (Phase 3 grant) — complete it first. |
| grant script returns HTML / CRLF errors | Run in Git Bash, not PowerShell; scripts already strip CRLF. |
| Databricks Account ID unknown | Account Console top-right → Account ID (also feeds `data_plane/terraform.tfvars`). |

## Costs

Only fixed cost is ACR Basic (~$5/mo). Databricks Premium has no idle cost; no
clusters/SQL warehouses are provisioned here. Storage Standard LRS; Container App
scales to zero; Static Web App Free.
