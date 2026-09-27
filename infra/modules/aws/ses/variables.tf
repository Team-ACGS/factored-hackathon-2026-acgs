variable "name" {
  description = "Name of the configuration set"
  type        = string
}

variable "domain" {
  description = "Domain to authenticate as a sender"
  type        = string
}

variable "mail_from_subdomain" {
  description = "Label prepended to the domain for the MAIL FROM domain, so bounces come back to SES and SPF aligns"
  type        = string
  default     = "bounce"
}

variable "zone_id" {
  description = "Route 53 zone the DKIM, MAIL FROM and DMARC records are written into"
  type        = string
}

variable "tags" {
  description = "Tags added to the provider default tags"
  type        = map(string)
  default     = {}
}
