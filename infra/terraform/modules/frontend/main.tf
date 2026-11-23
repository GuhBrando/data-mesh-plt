# Static Web Apps Free tier is only available in select regions; westus2 maps to "West US 2".
resource "azurerm_static_web_app" "frontend" {
  name                = "dmplt-stapp-frontend"
  resource_group_name = var.resource_group_name
  location            = var.location
  sku_tier            = "Free"
  sku_size            = "Free"
  tags                = var.tags

  lifecycle {
    # Recorded by the Static Web Apps deploy action in cd.yml on every release
    # (the branch is the release tag).
    ignore_changes = [repository_url, repository_branch]
  }
}
