module "artifacts_bucket" {
  source = "../../modules/aws/s3"

  name          = "${local.name_prefix}-artifacts${local.bucket_suffix}"
  force_destroy = true

  lifecycle_rules = {
    expire-old-bundles = {
      prefix = "functions/"
      days   = 30
    }
  }
}

locals {
  bootstrap_bundles = {
    api = {
      "handler.py" = <<-PY
        import json


        def handler(event, context):
            return {
                "statusCode": 503,
                "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"message": "not deployed yet"}),
            }
      PY
    }

    cognito = {
      "post_confirmation.py"    = "def handler(event, context):\n    return event\n"
      "pre_token_generation.py" = "def handler(event, context):\n    return event\n"
      "custom_message.py"       = "def handler(event, context):\n    raise RuntimeError(\"custom_message is not deployed yet\")\n"
    }
  }
}

# Cognito fails the operation whenever a trigger does not return the event, so
# the trigger bundles pass it through; custom_message fails on purpose, so no
# email goes out until its real handler is deployed.
data "archive_file" "bootstrap" {
  for_each = local.bootstrap_bundles

  type        = "zip"
  output_path = "${path.module}/.bootstrap/${each.key}.zip"

  dynamic "source" {
    for_each = each.value

    content {
      filename = source.key
      content  = source.value
    }
  }
}

resource "aws_s3_object" "bootstrap" {
  for_each = local.bootstrap_bundles

  bucket = module.artifacts_bucket.id
  key    = "bootstrap/${each.key}.zip"
  source = data.archive_file.bootstrap[each.key].output_path
  etag   = data.archive_file.bootstrap[each.key].output_md5
}
