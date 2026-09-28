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

variable "code_email" {
  description = "Subject and body of every email carrying a code: sign-up verification and password reset. The body must contain {####}."
  type = object({
    subject = string
    message = string
  })
}

variable "invite_email" {
  description = "Subject and body of the email a user created by an administrator receives. The body must contain {username} and {####}. Null keeps Cognito's default."
  type = object({
    subject = string
    message = string
  })
  default = null
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
  description = "Function ARN per Cognito trigger, keyed post_confirmation or pre_token_generation. pre_token_generation is required. A trigger's failure fails the operation that fired it, so every bootstrap bundle returns the event unchanged."
  type        = map(string)

  validation {
    condition     = contains(keys(var.triggers), "pre_token_generation") && alltrue([for k in keys(var.triggers) : contains(["post_confirmation", "pre_token_generation"], k)])
    error_message = "triggers takes pre_token_generation and optionally post_confirmation."
  }
}

variable "tags" {
  description = "Tags added to the provider default tags"
  type        = map(string)
  default     = {}
}
