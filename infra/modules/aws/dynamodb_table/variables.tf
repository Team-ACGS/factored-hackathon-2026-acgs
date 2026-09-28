variable "name" {
  description = "Table name"
  type        = string
}

variable "hash_key" {
  description = "Partition key attribute name"
  type        = string
}

variable "range_key" {
  description = "Sort key attribute name. Null makes a table keyed by the partition key alone."
  type        = string
  default     = null
}

variable "attributes" {
  description = "Definitions of every key attribute of the table and its indexes, keyed by name, with the DynamoDB type (S, N or B)"
  type        = map(string)
}

variable "global_secondary_indexes" {
  description = "Global secondary indexes, keyed by index name"
  type = map(object({
    hash_key        = string
    range_key       = optional(string)
    projection_type = optional(string, "ALL")
  }))
  default = {}
}

variable "stream_view_type" {
  description = "What the table's stream carries (NEW_IMAGE, OLD_IMAGE, NEW_AND_OLD_IMAGES or KEYS_ONLY). Null leaves the table without a stream."
  type        = string
  default     = null
}

variable "tags" {
  description = "Tags added to the provider default tags"
  type        = map(string)
  default     = {}
}
