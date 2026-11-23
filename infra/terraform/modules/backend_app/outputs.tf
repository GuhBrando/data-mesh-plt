output "fqdn" { value = azurerm_container_app.backend.ingress[0].fqdn }
output "key_vault_name" { value = azurerm_key_vault.main.name }

# Versionless, so a key rotated by importing a new version is used without a
# config change. Goes into GITHUB_APP_KEY_VAULT_KEY_ID.
output "github_app_key_id" {
  value = "${azurerm_key_vault.main.vault_uri}keys/${local.github_app_key_name}"
}

# Goes into the backend's AZURE_CLIENT_ID, so the Azure SDK uses this identity.
output "identity_client_id" { value = azurerm_user_assigned_identity.backend.client_id }
