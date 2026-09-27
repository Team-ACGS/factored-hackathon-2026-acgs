locals {
  table_defaults = {
    range_key                = null
    global_secondary_indexes = {}
  }

  table_specs = {
    customers = {
      hash_key   = "customer_id"
      attributes = { customer_id = "S" }
    }

    products = {
      hash_key   = "customer_id"
      range_key  = "product_id"
      attributes = { customer_id = "S", product_id = "S" }
    }

    transactions = {
      hash_key   = "customer_id"
      range_key  = "transaction_key"
      attributes = { customer_id = "S", transaction_key = "S" }
    }

    complaints = {
      hash_key   = "customer_id"
      range_key  = "complaint_id"
      attributes = { customer_id = "S", complaint_id = "S", area = "S", priority_score = "N" }

      global_secondary_indexes = {
        (local.complaints_queue_index) = {
          hash_key  = "area"
          range_key = "priority_score"
        }
      }
    }

    staff = {
      hash_key   = "staff_id"
      attributes = { staff_id = "S" }
    }

    rooms = {
      hash_key   = "customer_id"
      range_key  = "room_id"
      attributes = { customer_id = "S", room_id = "S" }
    }

    messages = {
      hash_key   = "customer_id"
      range_key  = "message_key"
      attributes = { customer_id = "S", message_key = "S" }
    }
  }

  tables = {
    for name, spec in local.table_specs : name => merge(local.table_defaults, spec)
  }

  complaints_queue_index = "by-area-priority"

  table_env = {
    for name, table in module.table : "TABLE_${upper(name)}" => table.name
  }
}

module "table" {
  source   = "../../modules/aws/dynamodb_table"
  for_each = local.tables

  name                     = "${local.name_prefix}-${each.key}"
  hash_key                 = each.value.hash_key
  range_key                = each.value.range_key
  attributes               = each.value.attributes
  global_secondary_indexes = each.value.global_secondary_indexes
}
