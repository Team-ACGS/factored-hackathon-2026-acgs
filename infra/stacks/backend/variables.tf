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

variable "policy_embedding_model_id" {
  description = "Bedrock model that embeds policy chunks and queries; the index dimension follows it"
  type        = string
}

variable "policy_min_similarity" {
  description = "Cosine similarity a policy chunk must reach to be returned, per document language (es, pt, en); below it search_policies answers no_match"
  type        = map(number)

  validation {
    condition     = length(var.policy_min_similarity) == 3 && alltrue([for language in ["es", "pt", "en"] : contains(keys(var.policy_min_similarity), language)])
    error_message = "policy_min_similarity must hold exactly one cut for each of es, pt and en."
  }

  validation {
    condition     = alltrue([for cut in values(var.policy_min_similarity) : cut > 0 && cut <= 1])
    error_message = "Each policy_min_similarity cut must be in (0, 1]."
  }
}

variable "bedrock_inference_profile_id" {
  description = "Cross-region inference profile chatbot invokes for Claude; the role may invoke the profile and the models it routes to."
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
  description = "Bucket holding the state of every root, read and locked by the plan role"
  type        = string
}

variable "github_app_pem" {
  description = "Private key of the GitHub App Terraform authenticates as, stored as an Actions secret so CI can plan"
  type        = string
  sensitive   = true
}
