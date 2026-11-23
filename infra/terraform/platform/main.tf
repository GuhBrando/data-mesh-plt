locals {
  catalogs = ["dev", "pre", "pro"]
}

# Azure AD service principals (dmplt-admin, dmplt-devops) + OIDC federated creds.
module "identities" {
  source          = "../modules/identities"
  github_repo     = var.github_repo
  subscription_id = var.subscription_id
}

# Resource group, ACR, Container App Environment (+ Log Analytics).
module "core" {
  source   = "../modules/core"
  location = var.location
  tags     = var.tags
}

module "backend_app" {
  source                       = "../modules/backend_app"
  resource_group_name          = module.core.resource_group_name
  location                     = var.location
  container_app_environment_id = module.core.container_app_environment_id
  acr_login_server             = module.core.acr_login_server
  acr_name                     = module.core.acr_name
  tags                         = var.tags
}

module "frontend" {
  source              = "../modules/frontend"
  resource_group_name = module.core.resource_group_name
  location            = var.location
  tags                = var.tags
}

module "storage" {
  source              = "../modules/storage"
  resource_group_name = module.core.resource_group_name
  location            = var.location
  tags                = var.tags
  containers          = local.catalogs
}

# Databricks workspace + Unity Catalog access connector (managed identity).
module "databricks_workspace" {
  source              = "../modules/databricks_workspace"
  resource_group_name = module.core.resource_group_name
  location            = var.location
  tags                = var.tags
}

# Access Connector managed identity → data plane access on the data storage account.
resource "azurerm_role_assignment" "uc_storage" {
  scope                = module.storage.storage_account_id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = module.databricks_workspace.access_connector_principal_id
}
