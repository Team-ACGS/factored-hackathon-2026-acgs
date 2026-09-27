variable "github_app_pem" {
  description = "Private key of the GitHub App Terraform authenticates as"
  type        = string
  sensitive   = true
}
