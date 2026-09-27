provider "aws" {
  region              = local.aws_region
  allowed_account_ids = [local.aws_account_id]

  default_tags {
    tags = local.tags
  }
}

provider "github" {
  owner = local.github_owner

  app_auth {
    id              = local.github_app_id
    installation_id = local.github_app_installation_id
    pem_file        = var.github_app_pem
  }
}
