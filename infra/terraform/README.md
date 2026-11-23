# Data Mesh Platform — Terraform Infrastructure

All Azure infrastructure is managed here. Region: `westus2`.

## Layout

The config is split into independent **stacks** (separate state files) so that no
provider configuration ever depends on a value that is unknown at plan time. This
removes the chicken-and-egg the old monolithic root suffered (the
`databricks.workspace` provider was configured from a workspace created in the same
apply, which broke `import` and any non-`-target` `plan`).

```
infra/terraform/
  bootstrap/    one-time: creates the remote state storage (local state)
  modules/      shared modules (core, backend_app, frontend, storage,
                identities, databricks_workspace, unity_catalog)
  platform/     Azure layer: identities, core, apps, storage, Databricks WORKSPACE
                  state key: platform.tfstate · providers: azurerm, azuread
  data_plane/   Databricks layer: metastore, catalogs, grants (Unity Catalog)
                  state key: data_plane.tfstate · providers: databricks
                  reads platform outputs via terraform_remote_state
```

`data_plane` configures its `databricks.workspace` provider from the **platform**
stack's remote state. Those values are committed to state, hence known at plan time
— so each stack runs with a plain `terraform apply` (no `-target` gymnastics).

> **Shell note.** All `terraform`, `az`, `cd` and `terraform output` commands are
> identical on every OS. Only two things differ between shells: setting an
> environment variable, and which import helper you call. Both variants are shown
> below — PowerShell (Windows) and bash (Linux/macOS/Git Bash).

## 0. One-time bootstrap (remote state backend)

```bash
cd bootstrap
az login
terraform init
terraform apply -var="subscription_id=<SUB_ID>"   # creates dmplttfstate storage
cd ..
```

## 1. Platform stack

PowerShell:

```powershell
cd platform
Copy-Item terraform.tfvars.example terraform.tfvars   # fill in real values (gitignored)
terraform init
```

bash:

```bash
cd platform
cp terraform.tfvars.example terraform.tfvars          # fill in real values (gitignored)
terraform init
```

### Import pre-existing resources (first run only)

If the resource group `dmplt-rg` and friends already exist (created previously by
`scripts/azure-setup.sh`), import them so Terraform does not try to recreate them.

PowerShell:

```powershell
$env:SUBSCRIPTION_ID = "<SUB_ID>"
./import.ps1
terraform plan    # MUST show zero destroy/replace on imported resources
```

bash:

```bash
export SUBSCRIPTION_ID=<SUB_ID>
bash import.sh
terraform plan    # MUST show zero destroy/replace on imported resources
```

Imported: `dmplt-rg`, `dmpltacr`, `dmplt-cae`, `dmplt-ca-backend`,
`dmplt-stapp-frontend`. **New** (not imported, created by apply): the data storage
account `dmpltsta`, the Databricks workspace, the access connector, and the storage
role assignment.

> **Log Analytics note.** `dmplt-cae` may have been created with an auto-generated
> Log Analytics workspace (names like `workspace-dmpltrg…`). This config declares an
> explicit `dmplt-law`. Before `apply`, either import the existing LAW as
> `module.core.azurerm_log_analytics_workspace.main`, or verify `terraform plan`
> shows **no destroy/replace on `dmplt-cae`**.

### Apply

Creating Azure role assignments (`azurerm_role_assignment.uc_storage`, devops
Contributor) requires **Owner** or **User Access Administrator** — plain
`Contributor` cannot. Run with a privileged identity or grant the CI principal
`User Access Administrator`.

```bash
terraform apply
```

### Drift

Each setting has one owner. Terraform owns the shape of the resources; `cd.yml`
owns what changes per release on `dmplt-ca-backend` (image, env, secrets, CORS)
and the Static Web Apps deploy action records the repository and branch. Those are
listed in `lifecycle.ignore_changes`. Change everything else here, not in the portal
or with `az`, or the next apply reverts it.

`infra.yml` also runs every Monday on `main` with `terraform plan
-detailed-exitcode`: the run fails, and GitHub emails you, when live Azure no longer
matches the code. Reconcile by codifying the live value or by reverting the manual
change, until `plan` reports no changes.

The OIDC subject of the CI federated credentials contains the repository
(`github_repo`). The organization uses GitHub's immutable subject claims, so it
carries names and numeric IDs: `repo:<owner>@<owner_id>/<repo>@<repo_id>:...`. After
renaming or transferring the repository, update it and apply, or CI can no longer
log in to Azure. The exact subject GitHub sent is in the `azure/login` error
(`AADSTS700213 ... presented assertion subject '...'`).

## 2. Grant the admin SP account-admin (one-time)

The `dmplt-admin` service principal must be a Databricks **account admin** so the
data_plane stack can create the Unity Catalog metastore. This grant must be done
once by an existing account admin (an Azure AD Global Administrator is one).

> Terraform cannot do this grant — the provider's `access_control_rule_set` has no
> `account_admin` role. Use the SCIM API instead (the script below) or the console.

**Automated (recommended, idempotent):** first apply the `databricks_bootstrap`
stack to register the SP, then run the grant script:

```bash
cd databricks_bootstrap
terraform init && terraform apply          # registers dmplt-admin in the account
ACCOUNT_ID=<databricks-account-id> bash grant-account-admin.sh
```

The script (`grant-account-admin.sh`) gets an Azure CLI token, finds the SP and adds
the `account_admin` role via the Databricks CLI — additively (it never manages a
list of admins) and idempotently. Requires `az` (logged in as Global Admin), the
[Databricks CLI](https://docs.databricks.com/dev-tools/cli/install.html) and `jq`.

**Manual alternative:** in the Account Console (https://accounts.azuredatabricks.net)
→ User management → Service principals → `dmplt-admin` → toggle **Account admin**.

The **Databricks Account ID** comes from the same console → it goes into
`data_plane/terraform.tfvars`.

## 3. Data plane stack (Unity Catalog)

PowerShell:

```powershell
cd ../data_plane
Copy-Item terraform.tfvars.example terraform.tfvars   # set databricks_account_id
terraform init
terraform apply
```

bash:

```bash
cd ../data_plane
cp terraform.tfvars.example terraform.tfvars          # set databricks_account_id
terraform init
terraform apply
```

`terraform_remote_state` pulls the workspace URL/id, storage, connector and SP ids
from the platform stack automatically — no manual wiring.

## 4. Grant read access to all users (optional)

The catalogs are owned by the `dmplt-admin` service principal, so by default human
users do not see them (Unity Catalog only shows catalogs you have a privilege on).
To give **every account user** read access (`USE_CATALOG` + `USE_SCHEMA` + `SELECT`,
inherited by all schemas/tables) on every catalog, run the routine from
`data_plane/`:

```bash
cd data_plane
bash grant-read-all-users.sh
```

It authenticates as `dmplt-admin` (the catalog owner, using its credentials from the
platform stack), discovers the catalogs from `terraform output`, and grants read to
the built-in `account users` group. Additive and idempotent — re-running is safe and
never removes other grants. Requires `az` (logged in), the Databricks CLI and `jq`.

## Steady state

After bootstrap + the one-time grant: `terraform apply` in `platform/`, then in
`data_plane/`. The grant and import steps are never repeated.

## Outputs

- platform: `admin_client_id`, `devops_client_id`, `workspace_url`,
  `admin_client_secret` (sensitive), plus the wiring outputs the data_plane reads.
- data_plane: `catalog_names`, `metastore_id`.

Retrieve sensitive outputs: `terraform output -raw admin_client_secret` (in
`platform/`).

## Costs

Only fixed cost is ACR Basic (~$5/mo). Databricks Premium has no idle cost (DBU
pay-per-use); no clusters/SQL warehouses are provisioned here. Storage is Standard
LRS; Container App scales to zero; Static Web App is Free.
