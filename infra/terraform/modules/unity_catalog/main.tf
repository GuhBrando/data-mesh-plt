# --- Metastore: auto-provisioned and assigned by Azure Databricks per region.
# We ADOPT it by reference (the workspace's current metastore) instead of creating
# one. Azure Databricks auto-creates a metastore per region and assigns it to the
# workspace, so a `databricks_metastore` resource here would collide with
# "reached the limit for metastores in region <region>". Referencing the existing
# one makes this stack deterministic — a single apply, no imports, no conflicts.
data "databricks_current_metastore" "this" {
  provider = databricks.workspace
}

# --- Storage credential via Access Connector (workspace-level) ---
resource "databricks_storage_credential" "this" {
  provider = databricks.workspace
  name     = "dmplt-uc-credential"
  azure_managed_identity {
    access_connector_id = var.access_connector_id
  }
  # The metastore is already assigned to the workspace by Azure; reading it ensures
  # the workspace is UC-enabled before we create the credential.
  depends_on = [data.databricks_current_metastore.this]
}

# --- One external location + catalog per environment ---
resource "databricks_external_location" "this" {
  provider        = databricks.workspace
  for_each        = var.container_names
  name            = "dmplt-loc-${each.key}"
  url             = "abfss://${each.value}@${var.storage_account_name}.dfs.core.windows.net/"
  credential_name = databricks_storage_credential.this.name
}

resource "databricks_catalog" "this" {
  provider = databricks.workspace
  for_each = var.container_names
  # Unity Catalog stores catalog names lowercase. Force it so the planned name
  # always matches what the provider returns (avoids "inconsistent final plan").
  name         = lower(each.key)
  storage_root = databricks_external_location.this[each.key].url
  owner        = var.catalog_owner
  comment      = "Managed by Terraform — ${upper(each.key)} environment"
}

resource "databricks_service_principal" "devops" {
  provider       = databricks.account
  application_id = var.devops_principal
  display_name   = "dmplt-devops"
}

# devops automation privileges on each catalog.
resource "databricks_grants" "devops" {
  provider   = databricks.workspace
  for_each   = var.container_names
  catalog    = databricks_catalog.this[each.key].name
  depends_on = [databricks_service_principal.devops]
  grant {
    principal  = var.devops_principal
    privileges = ["USE_CATALOG", "USE_SCHEMA", "CREATE_SCHEMA"]
  }
}
