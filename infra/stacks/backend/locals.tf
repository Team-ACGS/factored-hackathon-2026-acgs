data "aws_caller_identity" "current" {}

locals {
  name_prefix = "${var.project}-${var.env}"
  account_id  = data.aws_caller_identity.current.account_id

  bucket_suffix = "-${local.account_id}"

  api_domain = "api.${var.base_domain}"

  cognito_from_email_address = "Clara <no-reply@${var.email_domain}>"
}
