resource "azurerm_resource_group" "main" {
  name     = "dmplt-rg"
  location = var.location
  tags     = var.tags
}

resource "azurerm_container_registry" "main" {
  name                = "dmpltacr"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Basic"
  admin_enabled       = true
  tags                = var.tags
}

resource "azurerm_log_analytics_workspace" "main" {
  name                = "dmplt-law"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = var.tags
}

resource "azurerm_container_app_environment" "main" {
  name                       = "dmplt-cae"
  resource_group_name        = azurerm_resource_group.main.name
  location                   = azurerm_resource_group.main.location
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
  tags                       = var.tags

  # The environment was created with the workload-profiles plan; dmplt-ca-backend
  # runs on its Consumption profile.
  workload_profile {
    name                  = "Consumption"
    workload_profile_type = "Consumption"
  }
}
