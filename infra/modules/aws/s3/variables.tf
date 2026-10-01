variable "name" {
  description = "Bucket name, globally unique, so callers append the account id"
  type        = string
}

variable "force_destroy" {
  description = "Allow Terraform to delete the bucket while it still holds objects"
  type        = bool
  default     = false
}

variable "versioned" {
  description = "Keep every version of every object"
  type        = bool
  default     = false
}

variable "lifecycle_rules" {
  description = "Expiration rules, keyed by rule id, each with a prefix and a number of days"
  type = map(object({
    prefix = string
    days   = number
  }))
  default = {}
}

variable "cloudfront_read" {
  description = "Whether the bucket policy lets one CloudFront distribution read every object. Separate from cloudfront_distribution_arn because the ARN is unknown until apply and the policy shape must be known at plan time."
  type        = bool
  default     = false
}

variable "cloudfront_distribution_arn" {
  description = "Distribution allowed to read the bucket through its origin access control. Only read when cloudfront_read is true."
  type        = string
  default     = null
}

variable "tags" {
  description = "Tags added to the provider default tags"
  type        = map(string)
  default     = {}
}
