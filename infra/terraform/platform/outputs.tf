# Consumed by the data_plane stack via terraform_remote_state.

output "workspace_url" { value = module.databricks_workspace.workspace_url }
output "workspace_id" { value = module.databricks_workspace.workspace_id }
output "workspace_numeric_id" { value = module.databricks_workspace.workspace_numeric_id }
output "access_connector_id" { value = module.databricks_workspace.access_connector_id }
output "storage_account_name" { value = module.storage.storage_account_name }
output "container_names" { value = module.storage.container_names }
output "admin_client_id" { value = module.identities.admin_client_id }
output "devops_client_id" { value = module.identities.devops_client_id }
output "location" { value = var.location }

output "admin_client_secret" {
  value     = module.identities.admin_client_secret
  sensitive = true
}

# Backend configuration for GitHub App authentication: GITHUB_APP_KEY_VAULT_KEY_ID
# and AZURE_CLIENT_ID (repository variables GH_APP_KEY_VAULT_KEY_ID and
# BACKEND_IDENTITY_CLIENT_ID, read by cd.yml).
output "github_app_key_id" { value = module.backend_app.github_app_key_id }
output "backend_identity_client_id" { value = module.backend_app.identity_client_id }
