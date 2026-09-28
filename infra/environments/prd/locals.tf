locals {
  ### General ##################################################################
  project        = "clara"
  env            = "prd"
  aws_region     = "us-east-1"
  aws_account_id = "975050033628"

  tags = {
    Project     = local.project
    Environment = local.env
    ManagedBy   = "terraform"
  }

  ### DNS ######################################################################
  zone_id      = "Z07789852332B51WUS33Z"
  base_domain  = "factoredai.sdfles.com"
  email_domain = "notifications.factoredai.sdfles.com"

  ### Assistant ################################################################
  bedrock_inference_profile_id = "us.anthropic.claude-sonnet-5"

  ### GitHub ###################################################################
  github_owner               = "Team-ACGS"
  github_repository          = "factored-hackathon-2026-acgs"
  github_app_id              = "5099830"
  github_app_installation_id = "165552839"
  git_branch                 = "main"

  ### State ####################################################################
  state_bucket = "clara-terraform-state-975050033628"
}
