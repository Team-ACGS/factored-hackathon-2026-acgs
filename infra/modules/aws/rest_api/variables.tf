variable "name" {
  description = "API name, also the name of its companions"
  type        = string
}

variable "stage_name" {
  description = "Stage name. It never appears in a URL because every caller goes through the custom domain."
  type        = string
  default     = "v1"
}

variable "routes" {
  description = "The API surface, keyed by an id used only inside Terraform. `path` has no leading slash; `authorized` puts the route behind the Cognito authorizer. Every path gets the CORS preflight."
  type = map(object({
    path          = string
    method        = string
    invoke_arn    = string
    function_name = string
    authorized    = optional(bool, true)
  }))
}

variable "cognito_user_pool_arns" {
  description = "Pools whose id tokens the authorizer accepts"
  type        = list(string)
}

variable "cors_allow_origin" {
  description = "Access-Control-Allow-Origin on the preflight and on API Gateway's own error responses. Auth travels in a header, never a cookie, so a wildcard does not expose credentials."
  type        = string
  default     = "*"
}

variable "domain" {
  description = "Custom domain the API answers on"
  type        = string
}

variable "certificate_arn" {
  description = "ACM certificate covering the domain, issued in this region"
  type        = string
}

variable "zone_id" {
  description = "Route 53 zone the alias records are written into"
  type        = string
}

variable "log_retention_days" {
  description = "Retention of the access and execution log groups"
  type        = number
  default     = 14
}

variable "tags" {
  description = "Tags added to the provider default tags"
  type        = map(string)
  default     = {}
}
