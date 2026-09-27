variable "name" {
  description = "API name"
  type        = string
}

variable "namespace" {
  description = "Channel namespace, the first segment of every channel path"
  type        = string
}

variable "cognito_user_pool_ids" {
  description = "Pools whose users may connect and subscribe with their id token. Publishing is IAM only, so only a backend role publishes."
  type        = map(string)
}

variable "log_retention_days" {
  description = "Retention of the API's log group"
  type        = number
  default     = 14
}

variable "tags" {
  description = "Tags added to the provider default tags"
  type        = map(string)
  default     = {}
}
