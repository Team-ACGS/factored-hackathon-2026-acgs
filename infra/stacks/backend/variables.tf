################################################################################
# General
################################################################################

variable "project" {
  description = "Project slug, the first segment of every resource name"
  type        = string
}

variable "env" {
  description = "Environment slug, the second segment of every resource name"
  type        = string
}

variable "aws_region" {
  description = "Region every resource lives in"
  type        = string
}

variable "base_domain" {
  description = "Root domain of the environment; every hostname derives from it"
  type        = string
}

variable "email_domain" {
  description = "Dedicated SES sending domain, never the apex"
  type        = string
}

variable "zone_id" {
  description = "Route 53 zone that answers for base_domain. It exists outside Terraform and survives a destroy."
  type        = string
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention of every log group"
  type        = number
  default     = 14
}

################################################################################
# Identity
################################################################################

variable "cognito_allow_password_auth" {
  description = "Enables USER_PASSWORD and ADMIN_USER_PASSWORD on every app client, for scripts and tests"
  type        = bool
  default     = false
}

################################################################################
# Assistant
################################################################################

variable "bedrock_inference_profile_id" {
  description = "Cross-region inference profile chatbot invokes. Sonnet 5 is only served through a profile, never on demand."
  type        = string
}

################################################################################
# GitHub
################################################################################

variable "github_owner" {
  description = "Organization that owns the repository"
  type        = string
}

variable "github_repository" {
  description = "Repository whose workflows deploy this environment"
  type        = string
}

variable "git_branch" {
  description = "The only branch allowed to deploy this environment"
  type        = string
}

variable "github_oidc_provider_arn" {
  description = "ARN of the account's GitHub OIDC provider"
  type        = string
}

variable "state_bucket" {
  description = "Bucket holding the Terraform state, read by the plan role"
  type        = string
}

variable "state_key" {
  description = "Key of this environment's state inside state_bucket"
  type        = string
}

variable "github_app_pem" {
  description = "Private key of the GitHub App Terraform authenticates as, stored as an Actions secret so CI can plan"
  type        = string
  sensitive   = true
}
