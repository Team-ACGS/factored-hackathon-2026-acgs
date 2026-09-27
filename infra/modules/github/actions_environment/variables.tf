variable "repository" {
  description = "Repository the environment belongs to, the name alone, not owner/name"
  type        = string
}

variable "environment" {
  description = "Name of the Actions environment. A job reaches its variables and secrets, and the OIDC role trusting it, by naming it in `environment:`."
  type        = string
}

variable "deployment_branch" {
  description = "The only branch whose jobs may use the environment, so the role trusting it is reachable from that branch alone. Null lets any branch use it."
  type        = string
  default     = null
}

variable "env_vars" {
  description = "Plain variables, exposed to the workflow as vars.*"
  type        = map(string)
  default     = {}
}

variable "env_secrets" {
  description = "Secrets, exposed to the workflow as secrets.*"
  type        = map(string)
  default     = {}
  sensitive   = true
}
