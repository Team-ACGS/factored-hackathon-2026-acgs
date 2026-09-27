################################################################################
# Triggers
################################################################################

# The pools read these functions' ARNs, so nothing here may read a pool: an
# environment variable or a statement naming one closes a cycle.
module "auth_function" {
  source   = "../../modules/aws/lambda_function"
  for_each = toset(["post-confirmation", "pre-token-generation"])

  name    = "${local.name_prefix}-auth-${each.key}"
  handler = "${replace(each.key, "-", "_")}.handler"
  timeout = 5

  artifacts_bucket = module.artifacts_bucket.id
  initial_s3_key   = aws_s3_object.bootstrap["cognito"].key

  environment = {
    POWERTOOLS_SERVICE_NAME      = "auth"
    POWERTOOLS_METRICS_NAMESPACE = "Clara/Backend"
  }

  log_retention_days = var.log_retention_days
}

################################################################################
# Pools
################################################################################

module "customers_pool" {
  source = "../../modules/aws/cognito_user_pool"

  name                = "${local.name_prefix}-customers"
  self_sign_up        = true
  clients             = ["customer"]
  allow_password_auth = var.cognito_allow_password_auth
  from_email_address  = local.cognito_from_email_address
  ses_identity_arn    = module.ses.identity_arn

  triggers = {
    post_confirmation    = module.auth_function["post-confirmation"].arn
    pre_token_generation = module.auth_function["pre-token-generation"].arn
  }
}

module "staff_pool" {
  source = "../../modules/aws/cognito_user_pool"

  name                = "${local.name_prefix}-staff"
  self_sign_up        = false
  clients             = ["support", "backoffice"]
  groups              = ["agents", "officers", "analysts"]
  allow_password_auth = var.cognito_allow_password_auth
  from_email_address  = local.cognito_from_email_address
  ses_identity_arn    = module.ses.identity_arn

  triggers = {
    pre_token_generation = module.auth_function["pre-token-generation"].arn
  }
}
