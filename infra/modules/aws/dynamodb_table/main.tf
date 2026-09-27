resource "aws_dynamodb_table" "this" {
  name                        = var.name
  billing_mode                = "PAY_PER_REQUEST"
  hash_key                    = var.hash_key
  range_key                   = var.range_key
  deletion_protection_enabled = false

  dynamic "attribute" {
    for_each = var.attributes

    content {
      name = attribute.key
      type = attribute.value
    }
  }

  dynamic "global_secondary_index" {
    for_each = var.global_secondary_indexes

    content {
      name            = global_secondary_index.key
      projection_type = global_secondary_index.value.projection_type

      key_schema {
        attribute_name = global_secondary_index.value.hash_key
        key_type       = "HASH"
      }

      dynamic "key_schema" {
        for_each = global_secondary_index.value.range_key == null ? [] : [global_secondary_index.value.range_key]

        content {
          attribute_name = key_schema.value
          key_type       = "RANGE"
        }
      }
    }
  }

  point_in_time_recovery {
    enabled = false
  }

  server_side_encryption {
    enabled = true
  }

  tags = merge(var.tags, { Name = var.name })
}
