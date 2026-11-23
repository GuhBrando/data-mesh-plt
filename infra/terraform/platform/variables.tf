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
  default     = "data-mesh-platform-org@359737315/data-mesh-plt@1087487046"
  description = "Repository part of the OIDC subject for the devops SP, exactly as GitHub sends it. The organization uses immutable subject claims: owner@<owner_id>/repo@<repo_id> (gh api repos/<owner>/<repo> --jq '[.owner.id, .id]')."
}

variable "tags" {
  type    = map(string)
  default = { project = "data_mesh_plt", managed_by = "terraform" }
}
