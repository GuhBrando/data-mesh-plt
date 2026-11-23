variable "subscription_id" {
  type        = string
  description = "Azure subscription ID."
}

variable "tenant_id" {
  type        = string
  description = "Azure AD tenant ID."
}

variable "location" {
  type        = string
  default     = "westus2"
  description = "Azure region for all resources."
}

variable "github_repo" {
  type        = string
  default     = "data-mesh-platform-org/data-mesh-plt"
  description = "owner/repo used as the OIDC subject for the devops SP. Must be the repository's current name: GitHub puts it in the token's subject."
}

variable "tags" {
  type    = map(string)
  default = { project = "data_mesh_plt", managed_by = "terraform" }
}
