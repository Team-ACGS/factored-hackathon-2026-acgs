variable "name" {
  description = "Delivery stream name"
  type        = string
}

variable "bucket_arn" {
  description = "Bucket the stream writes to"
  type        = string
}

variable "prefix" {
  description = "Key prefix of delivered objects, followed by the delivery date"
  type        = string
}

variable "buffering_interval_seconds" {
  description = "Longest a record waits before its batch is written"
  type        = number
  default     = 60
}

variable "log_retention_days" {
  description = "Retention of the delivery error log group"
  type        = number
  default     = 14
}

variable "tags" {
  description = "Tags added to the provider default tags"
  type        = map(string)
  default     = {}
}
