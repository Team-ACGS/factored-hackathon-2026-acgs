################################################################################
# Trust
################################################################################

# A job that names an Actions environment gets that environment as its OIDC
# subject, so each role trusts exactly one environment of this repository.
# GitHub emits the second shape once a repository is renamed or transferred.
data "aws_iam_policy_document" "assume_github" {
  for_each = toset(["lambdas", "terraform"])

  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [var.github_oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "repo:${var.github_owner}/${var.github_repository}:environment:${local.actions_environments[each.key]}",
        "repo:${var.github_owner}@*/${var.github_repository}@*:environment:${local.actions_environments[each.key]}",
      ]
    }
  }
}

locals {
  actions_environments = {
    lambdas   = var.env
    terraform = "terraform"
  }
}

################################################################################
# Lambda deploys
################################################################################

resource "aws_iam_role" "deploy_lambdas" {
  name               = "${local.name_prefix}-deploy-lambdas"
  assume_role_policy = data.aws_iam_policy_document.assume_github["lambdas"].json

  tags = { Name = "${local.name_prefix}-deploy-lambdas" }
}

resource "aws_iam_role_policy" "deploy_lambdas" {
  name = "deploy"
  role = aws_iam_role.deploy_lambdas.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "UploadBundles"
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:GetObject"]
        Resource = "${module.artifacts_bucket.arn}/functions/*"
      },
      {
        Sid    = "UpdateFunctions"
        Effect = "Allow"
        Action = [
          "lambda:UpdateFunctionCode",
          "lambda:GetFunction",
          "lambda:GetFunctionConfiguration",
        ]
        Resource = concat(
          [for fn in module.function : fn.arn],
          [for fn in module.auth_function : fn.arn],
        )
      },
    ]
  })
}

module "lambdas_actions_environment" {
  source = "../../modules/github/actions_environment"

  repository        = var.github_repository
  environment       = local.actions_environments.lambdas
  deployment_branch = var.git_branch

  env_vars = {
    AWS_REGION       = var.aws_region
    AWS_ROLE_ARN     = aws_iam_role.deploy_lambdas.arn
    ARTIFACTS_BUCKET = module.artifacts_bucket.id
    FUNCTION_PREFIX  = local.name_prefix
    API_URL          = module.api.url
  }
}

################################################################################
# Terraform plan on pull requests
################################################################################

resource "aws_iam_role" "terraform_plan" {
  name               = "${local.name_prefix}-terraform-plan"
  assume_role_policy = data.aws_iam_policy_document.assume_github["terraform"].json

  tags = { Name = "${local.name_prefix}-terraform-plan" }
}

resource "aws_iam_role_policy_attachment" "terraform_plan_read" {
  role       = aws_iam_role.terraform_plan.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

resource "aws_iam_role_policy" "terraform_plan" {
  name = "plan"
  role = aws_iam_role.terraform_plan.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "StateLock"
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:DeleteObject"]
        Resource = "arn:aws:s3:::${var.state_bucket}/${var.state_key}.tflock"
      },
      {
        Sid    = "DenyCustomerData"
        Effect = "Deny"
        Action = [
          "dynamodb:BatchGetItem",
          "dynamodb:GetItem",
          "dynamodb:GetRecords",
          "dynamodb:Query",
          "dynamodb:Scan",
          "cognito-idp:AdminGetUser",
          "cognito-idp:ListUsers",
          "cognito-idp:ListUsersInGroup",
          "logs:FilterLogEvents",
          "logs:GetLogEvents",
          "logs:StartQuery",
          "sqs:ReceiveMessage",
        ]
        Resource = "*"
      },
      {
        Sid      = "DenyTurnEvents"
        Effect   = "Deny"
        Action   = ["s3:GetObject"]
        Resource = "${module.events_bucket.arn}/*"
      },
    ]
  })
}

module "terraform_actions_environment" {
  source = "../../modules/github/actions_environment"

  repository  = var.github_repository
  environment = local.actions_environments.terraform

  env_vars = {
    AWS_REGION   = var.aws_region
    AWS_ROLE_ARN = aws_iam_role.terraform_plan.arn
  }

  env_secrets = {
    TF_GITHUB_APP_PEM = var.github_app_pem
  }
}
