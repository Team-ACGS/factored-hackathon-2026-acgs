locals {
  project        = "clara"
  env            = "core"
  aws_region     = "us-east-1"
  aws_account_id = "975050033628"

  name_prefix = "${local.project}-${local.env}"

  tags = {
    Project     = local.project
    Environment = local.env
    ManagedBy   = "terraform"
  }
}
