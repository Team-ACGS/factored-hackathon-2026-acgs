variable "name" {
  description = "Function name, also the log group suffix and the IAM role name"
  type        = string
}

variable "handler" {
  description = "Handler path inside the bundle, module.function"
  type        = string
}

variable "runtime" {
  description = "Lambda runtime"
  type        = string
  default     = "python3.12"
}

variable "memory_size" {
  description = "Memory in MB"
  type        = number
  default     = 512
}

variable "timeout" {
  description = "Timeout in seconds"
  type        = number
  default     = 30
}

variable "artifacts_bucket" {
  description = "Bucket the deploy workflow uploads bundles to"
  type        = string
}

variable "initial_s3_key" {
  description = "Bootstrap object used only when the function is created. Every later deploy replaces the code out of band and Terraform ignores it."
  type        = string
}

variable "environment" {
  description = "Plain environment variables. Never a secret: the value is readable in the function configuration."
  type        = map(string)
  default     = {}
}

variable "policy_statements" {
  description = "Statements of this function's role beyond logs and tracing, keyed by capability name"
  type = map(object({
    actions   = list(string)
    resources = list(string)
  }))
  default = {}
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention"
  type        = number
  default     = 14
}

variable "tags" {
  description = "Tags added to the provider default tags"
  type        = map(string)
  default     = {}
}
