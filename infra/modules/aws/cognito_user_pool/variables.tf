variable "name" {
  description = "User pool name, also the prefix of its app client names"
  type        = string
}

variable "self_sign_up" {
  description = "Whether anyone can sign up. False means only an administrator creates users."
  type        = bool
}

variable "clients" {
  description = "One public app client per web that signs in against this pool"
  type        = list(string)
}

variable "client_write_attributes" {
  description = "Attributes every app client of the pool may write, at sign-up or later; Cognito requires the pool's required attributes (email) in the list. Anything else stays read-only to the user."
  type        = list(string)
}

variable "groups" {
  description = "Cognito groups of the pool, read from cognito:groups in the token"
  type        = list(string)
  default     = []
}

variable "allow_password_auth" {
  description = "Enables USER_PASSWORD and ADMIN_USER_PASSWORD on every client, for scripts and tests; the webs use SRP"
  type        = bool
  default     = false
}

variable "from_email_address" {
  description = "Friendly From of every message the pool sends, on the SES sending domain"
  type        = string
}

variable "ses_identity_arn" {
  description = "Verified SES identity the pool sends as"
  type        = string
}

variable "triggers" {
  description = "Function ARN per Cognito trigger, keyed custom_message, pre_token_generation (both required) or post_confirmation. A trigger's failure fails the operation that fired it."
  type        = map(string)

  validation {
    condition     = contains(keys(var.triggers), "custom_message") && contains(keys(var.triggers), "pre_token_generation") && alltrue([for k in keys(var.triggers) : contains(["custom_message", "post_confirmation", "pre_token_generation"], k)])
    error_message = "triggers takes custom_message and pre_token_generation, and optionally post_confirmation."
  }
}

variable "tags" {
  description = "Tags added to the provider default tags"
  type        = map(string)
  default     = {}
}
