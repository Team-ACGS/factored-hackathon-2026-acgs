variable "name" {
  description = "Queue name, without the .fifo suffix"
  type        = string
}

variable "fifo" {
  description = "Whether the queue is FIFO. Producers then send a MessageGroupId and a MessageDeduplicationId, since content based deduplication is off."
  type        = bool
  default     = false
}

variable "visibility_timeout_seconds" {
  description = "How long a received message stays invisible. Must be at least the consumer's timeout."
  type        = number
  default     = 30
}

variable "message_retention_seconds" {
  description = "How long an unconsumed message survives"
  type        = number
  default     = 345600
}

variable "dead_letter_arn" {
  description = "Queue a message is moved to after max_receive_count failed receives. Null leaves the queue without a dead letter target."
  type        = string
  default     = null
}

variable "max_receive_count" {
  description = "Receives a message survives before it is moved to the dead letter queue"
  type        = number
  default     = 3
}

variable "tags" {
  description = "Tags added to the provider default tags"
  type        = map(string)
  default     = {}
}
