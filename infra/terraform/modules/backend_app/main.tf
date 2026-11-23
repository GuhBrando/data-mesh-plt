data "azurerm_container_registry" "acr" {
  name                = var.acr_name
  resource_group_name = var.resource_group_name
}

data "azurerm_client_config" "current" {}

data "azurerm_resource_group" "main" {
  name = var.resource_group_name
}

locals {
  # The GitHub App private key is imported into the vault once by an operator
  # (`az keyvault key import --ops sign`) and is not managed here, so it never
  # reaches Terraform state. See docs/superpowers/specs/2026-11-22-github-app-auth-design.md.
  github_app_key_name = "github-app"
}

# The backend's identity for Key Vault (signing the GitHub App JWT) without any
# stored secret. The app must name it in AZURE_CLIENT_ID (set by cd.yml) so the
# Azure SDK picks it.
resource "azurerm_user_assigned_identity" "backend" {
  name                = "dmplt-ca-backend-id"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_container_app" "backend" {
  name                         = "dmplt-ca-backend"
  resource_group_name          = var.resource_group_name
  container_app_environment_id = var.container_app_environment_id
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"
  tags                         = var.tags

  # User-assigned, not system-assigned: dmplt-cae is an Express environment
  # (environmentMode "Express", visible from API 2026-07-01), which rejects
  # system-assigned identities. The provider's older API still accepted one, but
  # every later `az containerapp update` in cd.yml then failed with
  # ExpressSystemAssignedIdentityNotSupported. A user-assigned identity passed
  # create, update and a Key Vault sign from inside a container (2026-11-23).
  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.backend.id]
  }

  registry {
    server               = var.acr_login_server
    username             = data.azurerm_container_registry.acr.admin_username
    password_secret_name = "acr-password"
  }

  secret {
    name  = "acr-password"
    value = data.azurerm_container_registry.acr.admin_password
  }

  ingress {
    external_enabled = true
    target_port      = 8000
    transport        = "http"
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = 0
    max_replicas = 2

    http_scale_rule {
      name                = "http-scaler"
      concurrent_requests = "10"
    }

    container {
      name   = "backend"
      image  = "${var.acr_login_server}/backend:latest"
      cpu    = 0.25
      memory = "0.5Gi"
    }
  }

  lifecycle {
    ignore_changes = [
      # cd.yml owns the release: it rolls out the image, sets the app's secrets
      # and environment variables, and configures CORS from the CORS_ORIGINS
      # secret. Without ignoring them, an apply would strip what cd.yml set.
      template[0].container[0].image,
      template[0].container[0].env,
      secret,
      ingress[0].cors,
      # Single revision mode: Azure keeps no traffic split to compare against.
      ingress[0].traffic_weight,
      # Unset in Azure, so KEDA's defaults (300 s / 30 s) apply; the provider
      # would otherwise write its own defaults and roll a new revision.
      template[0].cooldown_period_in_seconds,
      template[0].polling_interval_in_seconds,
    ]
  }
}

# Holds the GitHub App private key. RBAC only: no access policies.
resource "azurerm_key_vault" "main" {
  name                       = "dmplt-kv"
  location                   = var.location
  resource_group_name        = var.resource_group_name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  rbac_authorization_enabled = true
  purge_protection_enabled   = true
  soft_delete_retention_days = 7
  tags                       = var.tags
}

# Least-privilege custom roles for the vault's keys. The built-in alternatives
# grant far more: Key Vault Crypto User also allows encrypt, decrypt, wrap,
# unwrap, verify, update and backup; Crypto Officer manages every key. Custom
# roles cannot list a single resource as assignable scope, so they are defined
# on the resource group and assigned on the vault only.
resource "azurerm_role_definition" "key_signer" {
  name        = "dmplt Key Vault Signer"
  scope       = data.azurerm_resource_group.main.id
  description = "Read Key Vault keys and sign with them. Nothing else."

  permissions {
    data_actions = [
      "Microsoft.KeyVault/vaults/keys/read",
      "Microsoft.KeyVault/vaults/keys/sign/action",
    ]
  }

  assignable_scopes = [data.azurerm_resource_group.main.id]
}

# Granted temporarily by grant-ci-permissions.sh (step 6) to the operator who
# imports the GitHub App key, and removed when the import ends.
resource "azurerm_role_definition" "key_importer" {
  name        = "dmplt Key Vault Key Importer"
  scope       = data.azurerm_resource_group.main.id
  description = "Read Key Vault keys and import new ones or new versions. Nothing else."

  permissions {
    data_actions = [
      "Microsoft.KeyVault/vaults/keys/read",
      "Microsoft.KeyVault/vaults/keys/import/action",
    ]
  }

  assignable_scopes = [data.azurerm_resource_group.main.id]
}

# Lets the backend sign with the vault's keys. The key itself is also restricted
# to the sign operation at import time.
resource "azurerm_role_assignment" "backend_key_signer" {
  scope              = azurerm_key_vault.main.id
  role_definition_id = azurerm_role_definition.key_signer.role_definition_resource_id
  principal_id       = azurerm_user_assigned_identity.backend.principal_id
}
