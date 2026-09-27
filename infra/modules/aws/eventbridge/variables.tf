variable "name" {
  description = "Event bus name"
  type        = string
}

variable "firehose_rules" {
  description = "Rules on the bus that deliver to a Firehose stream, keyed by a short rule name, each with its event pattern"
  type = map(object({
    pattern    = any
    stream_arn = string
  }))
}

variable "tags" {
  description = "Tags added to the provider default tags"
  type        = map(string)
  default     = {}
}
