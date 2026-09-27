locals {
  admins = ["ariana.quispe", "carolina.mejia"]

  global_services = [
    "account:*",
    "aws-portal:*",
    "billing:*",
    "budgets:*",
    "ce:*",
    "cloudfront:*",
    "consolidatedbilling:*",
    "cur:*",
    "freetier:*",
    "health:*",
    "iam:*",
    "invoicing:*",
    "notifications:*",
    "organizations:*",
    "payments:*",
    "pricing:*",
    "route53:*",
    "route53domains:*",
    "s3:GetAccountPublicAccessBlock",
    "s3:ListAllMyBuckets",
    "sts:*",
    "support:*",
    "tax:*",
    "trustedadvisor:*",
  ]
}

resource "aws_iam_group" "admins" {
  name = "${local.name_prefix}-admins"
}

resource "aws_iam_group_policy_attachment" "admins" {
  group      = aws_iam_group.admins.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}

resource "aws_iam_group_policy" "admins_region" {
  name  = "only-${local.aws_region}"
  group = aws_iam_group.admins.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyOutsideRegion"
      Effect    = "Deny"
      NotAction = local.global_services
      Resource  = "*"
      Condition = {
        StringNotEquals = { "aws:RequestedRegion" = [local.aws_region] }
      }
    }]
  })
}

resource "aws_iam_user" "admin" {
  for_each = toset(local.admins)

  name          = each.value
  force_destroy = true

  tags = { Name = each.value }
}

resource "aws_iam_user_group_membership" "admin" {
  for_each = aws_iam_user.admin

  user   = each.value.name
  groups = [aws_iam_group.admins.name]
}
