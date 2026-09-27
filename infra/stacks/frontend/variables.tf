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
  description = "Domain of the customer web; the staff webs live one label under it"
  type        = string
}

variable "zone_id" {
  description = "Route 53 zone that answers for base_domain"
  type        = string
}

variable "certificate_arn" {
  description = "Certificate covering base_domain and *.base_domain, issued in us-east-1"
  type        = string
}

variable "web_env" {
  description = "Build-time variables per web, written to its Actions environment"
  type        = map(map(string))
}

variable "github_owner" {
  description = "Organization that owns the repository"
  type        = string
}

variable "github_repository" {
  description = "Repository whose workflows deploy the webs"
  type        = string
}

variable "git_branch" {
  description = "The only branch allowed to deploy the webs"
  type        = string
}

variable "github_oidc_provider_arn" {
  description = "ARN of the account's GitHub OIDC provider"
  type        = string
}
