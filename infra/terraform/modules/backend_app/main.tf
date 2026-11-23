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
  workload_profile_name        = "Consumption"
  tags                         = var.tags

  # No managed identity: dmplt-cae is an Express environment (environmentMode
  # "Express", visible from API 2026-07-01), which rejects system-assigned
  # identities. Older API versions, like the provider's, still accept the field,
  # but every later `az containerapp update` in cd.yml then fails with
  # ExpressSystemAssignedIdentityNotSupported.

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
