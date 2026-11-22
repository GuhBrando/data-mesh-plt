data "azurerm_container_registry" "acr" {
  name                = var.acr_name
  resource_group_name = var.resource_group_name
}

data "azurerm_client_config" "current" {}

locals {
  # The GitHub App private key is imported into the vault once by an operator
  # (`az keyvault key import --ops sign`) and is not managed here, so it never
  # reaches Terraform state. See docs/superpowers/specs/2026-11-22-github-app-auth-design.md.
  github_app_key_name = "github-app"
}

resource "azurerm_container_app" "backend" {
  name                         = "dmplt-ca-backend"
  resource_group_name          = var.resource_group_name
  container_app_environment_id = var.container_app_environment_id
  revision_mode                = "Single"
  tags                         = var.tags

  # Authenticates the backend to Key Vault (signing the GitHub App JWT) without
  # any stored secret.
  identity {
    type = "SystemAssigned"
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
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = 0
    max_replicas = 2

    container {
      name   = "backend"
      image  = "${var.acr_login_server}/backend:latest"
      cpu    = 0.25
      memory = "0.5Gi"
    }
  }

  lifecycle {
    # cd.yml owns the release: it rolls out the image and sets the app's
    # secrets and environment variables (az containerapp secret set / update).
    # Without ignoring them, an apply would strip what cd.yml configured.
    ignore_changes = [
      template[0].container[0].image,
      template[0].container[0].env,
      secret,
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
  enable_rbac_authorization  = true
  purge_protection_enabled   = true
  soft_delete_retention_days = 7
  tags                       = var.tags
}

# Lets the backend sign with the vault's keys. The key itself is restricted to
# the sign operation at import time.
resource "azurerm_role_assignment" "backend_key_signer" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Crypto User"
  principal_id         = azurerm_container_app.backend.identity[0].principal_id
}
