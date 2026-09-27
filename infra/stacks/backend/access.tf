locals {
  table_arns = { for name, table in module.table : name => table.arn }

  customer_owned_tables = ["customers", "products", "transactions", "complaints", "rooms", "messages"]

  item_read_actions  = ["dynamodb:GetItem", "dynamodb:BatchGetItem", "dynamodb:Query", "dynamodb:ConditionCheckItem"]
  item_write_actions = ["dynamodb:PutItem", "dynamodb:UpdateItem"]

  access_role_defaults = {
    session_tag = null
    write       = []
    scan        = false
  }

  access_role_specs = {
    customer = {
      assumed_by  = ["crud", "chatbot"]
      session_tag = "customer_id"
      read        = local.customer_owned_tables
      write       = ["products", "complaints", "rooms"]
    }

    agent = {
      assumed_by = ["crud"]
      read       = keys(local.tables)
      write      = ["complaints", "rooms"]
    }

    officer = {
      assumed_by = ["crud"]
      read       = keys(local.tables)
      write      = ["complaints", "staff"]
    }

    analyst = {
      assumed_by = ["crud"]
      read       = keys(local.tables)
      scan       = true
    }
  }

  access_roles = {
    for name, spec in local.access_role_specs : name => merge(local.access_role_defaults, spec)
  }

  access_role_arns = {
    for name in keys(local.access_role_specs) :
    name => "arn:aws:iam::${local.account_id}:role/${local.name_prefix}-role-${name}"
  }
}

data "aws_iam_policy_document" "access_role_trust" {
  for_each = local.access_roles

  statement {
    actions = each.value.session_tag == null ? ["sts:AssumeRole"] : ["sts:AssumeRole", "sts:TagSession"]

    principals {
      type        = "AWS"
      identifiers = [for fn in each.value.assumed_by : module.function[fn].role_arn]
    }

    dynamic "condition" {
      for_each = each.value.session_tag == null ? [] : [each.value.session_tag]

      content {
        test     = "StringLike"
        variable = "aws:RequestTag/${condition.value}"
        values   = ["?*"]
      }
    }

    dynamic "condition" {
      for_each = each.value.session_tag == null ? [] : [each.value.session_tag]

      content {
        test     = "ForAllValues:StringEquals"
        variable = "aws:TagKeys"
        values   = [condition.value]
      }
    }
  }
}

data "aws_iam_policy_document" "access_role" {
  for_each = local.access_roles

  statement {
    sid       = "Read"
    actions   = each.value.scan ? concat(local.item_read_actions, ["dynamodb:Scan"]) : local.item_read_actions
    resources = flatten([for t in each.value.read : [local.table_arns[t], "${local.table_arns[t]}/index/*"]])

    dynamic "condition" {
      for_each = each.value.session_tag == null ? [] : [each.value.session_tag]

      content {
        test     = "ForAllValues:StringEquals"
        variable = "dynamodb:LeadingKeys"
        values   = ["$${aws:PrincipalTag/${condition.value}}"]
      }
    }
  }

  dynamic "statement" {
    for_each = length(each.value.write) > 0 ? [1] : []

    content {
      sid       = "Write"
      actions   = local.item_write_actions
      resources = [for t in each.value.write : local.table_arns[t]]

      dynamic "condition" {
        for_each = each.value.session_tag == null ? [] : [each.value.session_tag]

        content {
          test     = "ForAllValues:StringEquals"
          variable = "dynamodb:LeadingKeys"
          values   = ["$${aws:PrincipalTag/${condition.value}}"]
        }
      }
    }
  }
}

resource "aws_iam_role" "access" {
  for_each = local.access_roles

  name               = "${local.name_prefix}-role-${each.key}"
  assume_role_policy = data.aws_iam_policy_document.access_role_trust[each.key].json

  tags = { Name = "${local.name_prefix}-role-${each.key}" }
}

resource "aws_iam_role_policy" "access" {
  for_each = local.access_roles

  name   = "tables"
  role   = aws_iam_role.access[each.key].id
  policy = data.aws_iam_policy_document.access_role[each.key].json
}
