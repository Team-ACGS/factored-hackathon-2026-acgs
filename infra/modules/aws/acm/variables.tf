variable "domain_name" {
  description = "Primary domain name on the certificate"
  type        = string
}

variable "subject_alternative_names" {
  description = "Extra names on the certificate. A wildcard only covers one label."
  type        = list(string)
  default     = []
}

variable "zone_id" {
  description = "Route 53 zone that answers for these names"
  type        = string
}

variable "tags" {
  description = "Tags added to the provider default tags"
  type        = map(string)
  default     = {}
}
