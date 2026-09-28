################################################################################
# Triggers
################################################################################

# The pools read these functions' ARNs, so nothing here may read a pool: an
# environment variable or a statement naming one closes a cycle.
locals {
  auth_triggers = {
    post-confirmation = {
      environment = {
        TABLE_CUSTOMERS   = module.table["customers"].name
        ROLE_CUSTOMER_ARN = local.access_role_arns.customer
      }

      policy_statements = {
        assume_customer_role = {
          actions   = ["sts:AssumeRole", "sts:TagSession"]
          resources = [local.access_role_arns.customer]
        }
      }
    }

    pre-token-generation = {
      environment       = {}
      policy_statements = {}
    }
  }

  code_email = {
    subject = "Clara: your code · tu código · seu código"
    message = file("${path.module}/emails/code.html")
  }
}

module "auth_function" {
  source   = "../../modules/aws/lambda_function"
  for_each = local.auth_triggers

  name    = "${local.name_prefix}-auth-${each.key}"
  handler = "${replace(each.key, "-", "_")}.handler"
  timeout = 5

  artifacts_bucket = module.artifacts_bucket.id
  initial_s3_key   = aws_s3_object.bootstrap["cognito"].key

  environment = merge(each.value.environment, {
    POWERTOOLS_SERVICE_NAME      = "auth"
    POWERTOOLS_METRICS_NAMESPACE = "Clara/Backend"
  })

  policy_statements = each.value.policy_statements

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
  code_email          = local.code_email

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
  code_email          = local.code_email

  invite_email = {
    subject = "Clara: your staff account · tu cuenta de staff · sua conta de equipe"
    message = file("${path.module}/emails/invite.html")
  }

  triggers = {
    pre_token_generation = module.auth_function["pre-token-generation"].arn
  }
}
