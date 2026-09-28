resource "aws_cognito_user_pool" "this" {
  name = var.name

  user_pool_tier      = "ESSENTIALS"
  deletion_protection = "INACTIVE"

  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  username_configuration {
    case_sensitive = false
  }

  admin_create_user_config {
    allow_admin_create_user_only = !var.self_sign_up

    dynamic "invite_message_template" {
      for_each = var.invite_email == null ? [] : [var.invite_email]

      content {
        email_subject = invite_message_template.value.subject
        email_message = invite_message_template.value.message
        sms_message   = "Clara: {username} {####}"
      }
    }
  }

  verification_message_template {
    default_email_option = "CONFIRM_WITH_CODE"
    email_subject        = var.code_email.subject
    email_message        = var.code_email.message
  }

  email_configuration {
    email_sending_account = "DEVELOPER"
    from_email_address    = var.from_email_address
    source_arn            = var.ses_identity_arn
  }

  lambda_config {
    post_confirmation = lookup(var.triggers, "post_confirmation", null)

    pre_token_generation_config {
      lambda_arn     = var.triggers["pre_token_generation"]
      lambda_version = "V2_0"
    }
  }

  password_policy {
    minimum_length                   = 10
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = true
    require_uppercase                = true
    password_history_size            = 2
    temporary_password_validity_days = 3
  }

  schema {
    name                     = "email"
    attribute_data_type      = "String"
    required                 = true
    mutable                  = false
    developer_only_attribute = false

    string_attribute_constraints {
      min_length = 1
      max_length = 256
    }
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  tags = merge(var.tags, { Name = var.name })
}

resource "aws_cognito_user_pool_client" "this" {
  for_each = toset(var.clients)

  name         = "${var.name}-${each.value}"
  user_pool_id = aws_cognito_user_pool.this.id

  generate_secret               = false
  enable_token_revocation       = true
  prevent_user_existence_errors = "ENABLED"

  explicit_auth_flows = concat(
    ["ALLOW_USER_SRP_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"],
    var.allow_password_auth ? ["ALLOW_USER_PASSWORD_AUTH", "ALLOW_ADMIN_USER_PASSWORD_AUTH"] : []
  )

  access_token_validity  = 60
  id_token_validity      = 60
  refresh_token_validity = 30

  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
}

resource "aws_cognito_user_group" "this" {
  for_each = toset(var.groups)

  name         = each.value
  user_pool_id = aws_cognito_user_pool.this.id
}

resource "aws_lambda_permission" "triggers" {
  for_each = var.triggers

  statement_id  = "AllowCognito-${var.name}"
  action        = "lambda:InvokeFunction"
  function_name = each.value
  principal     = "cognito-idp.amazonaws.com"
  source_arn    = aws_cognito_user_pool.this.arn
}
