variable "name" {
  description = "Name of the distribution and its origin access control"
  type        = string
}

variable "domain" {
  description = "Public domain the distribution answers on"
  type        = string
}

variable "zone_id" {
  description = "Route 53 zone the alias records are written into"
  type        = string
}

variable "certificate_arn" {
  description = "ACM certificate covering the domain, issued in us-east-1"
  type        = string
}

variable "origin_domain_name" {
  description = "Regional domain name of the S3 origin. Built from the bucket name by the caller, because the bucket policy needs this distribution's ARN."
  type        = string
}

variable "tags" {
  description = "Tags added to the provider default tags"
  type        = map(string)
  default     = {}
}
