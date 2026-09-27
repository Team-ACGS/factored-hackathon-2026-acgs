data "aws_caller_identity" "current" {}

locals {
  name_prefix = "${var.project}-${var.env}"

  webs = {
    customer   = var.base_domain
    support    = "support.${var.base_domain}"
    backoffice = "backoffice.${var.base_domain}"
  }

  bucket_names = {
    for web in keys(local.webs) : web => "${local.name_prefix}-web-${web}-${data.aws_caller_identity.current.account_id}"
  }

  placeholder = <<-HTML
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Clara</title>
      </head>
      <body style="margin:0;min-height:100vh;display:grid;place-items:center;font-family:system-ui,sans-serif;color:#1f2937;background:#f9fafb">
        <main style="text-align:center">
          <h1 style="margin:0 0 8px;font-size:32px">Clara</h1>
          <p style="margin:0;color:#6b7280">Coming soon.</p>
        </main>
      </body>
    </html>
  HTML
}

################################################################################
# Hosting
################################################################################

module "bucket" {
  source   = "../../modules/aws/s3"
  for_each = local.webs

  name                        = local.bucket_names[each.key]
  force_destroy               = true
  cloudfront_read             = true
  cloudfront_distribution_arn = module.cdn[each.key].distribution_arn
}

module "cdn" {
  source   = "../../modules/aws/cloudfront"
  for_each = local.webs

  name               = "${local.name_prefix}-web-${each.key}"
  domain             = each.value
  zone_id            = var.zone_id
  certificate_arn    = var.certificate_arn
  origin_domain_name = "${local.bucket_names[each.key]}.s3.${var.aws_region}.amazonaws.com"
}

# Only the first apply writes this page. The deploy workflow replaces it with
# the real build and Terraform never looks at its content again.
resource "aws_s3_object" "placeholder" {
  for_each = local.webs

  bucket        = module.bucket[each.key].id
  key           = "index.html"
  content       = local.placeholder
  content_type  = "text/html; charset=utf-8"
  cache_control = "no-cache"

  lifecycle {
    ignore_changes = [content, content_type, cache_control, etag, metadata, tags, tags_all]
  }
}

################################################################################
# Deploys
################################################################################

data "aws_iam_policy_document" "assume_github" {
  for_each = local.webs

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
        "repo:${var.github_owner}/${var.github_repository}:environment:${each.key}-${var.env}",
        "repo:${var.github_owner}@*/${var.github_repository}@*:environment:${each.key}-${var.env}",
      ]
    }
  }
}

resource "aws_iam_role" "deploy" {
  for_each = local.webs

  name               = "${local.name_prefix}-deploy-web-${each.key}"
  assume_role_policy = data.aws_iam_policy_document.assume_github[each.key].json

  tags = { Name = "${local.name_prefix}-deploy-web-${each.key}" }
}

resource "aws_iam_role_policy" "deploy" {
  for_each = local.webs

  name = "deploy"
  role = aws_iam_role.deploy[each.key].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ListSite"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = module.bucket[each.key].arn
      },
      {
        Sid      = "SyncSite"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = "${module.bucket[each.key].arn}/*"
      },
      {
        Sid      = "Invalidate"
        Effect   = "Allow"
        Action   = ["cloudfront:CreateInvalidation", "cloudfront:GetInvalidation"]
        Resource = module.cdn[each.key].distribution_arn
      },
    ]
  })
}

module "actions_environment" {
  source   = "../../modules/github/actions_environment"
  for_each = local.webs

  repository        = var.github_repository
  environment       = "${each.key}-${var.env}"
  deployment_branch = var.git_branch

  env_vars = merge(var.web_env[each.key], {
    AWS_REGION      = var.aws_region
    AWS_ROLE_ARN    = aws_iam_role.deploy[each.key].arn
    SITE_BUCKET     = module.bucket[each.key].id
    DISTRIBUTION_ID = module.cdn[each.key].distribution_id
    SITE_URL        = module.cdn[each.key].url
  })
}
