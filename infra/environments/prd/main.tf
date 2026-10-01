module "backend" {
  source = "../../stacks/backend"

  project      = local.project
  env          = local.env
  aws_region   = local.aws_region
  base_domain  = local.base_domain
  email_domain = local.email_domain
  zone_id      = local.zone_id

  log_retention_days          = 14
  cognito_allow_password_auth = false

  bedrock_inference_profile_id = local.bedrock_inference_profile_id
  policy_embedding_model_id    = local.policy_embedding_model_id
  policy_min_similarity        = local.policy_min_similarity

  github_owner             = local.github_owner
  github_repository        = local.github_repository
  git_branch               = local.git_branch
  github_oidc_provider_arn = data.aws_iam_openid_connect_provider.github.arn
  github_app_pem           = var.github_app_pem

  state_bucket = local.state_bucket
}

module "frontend" {
  source = "../../stacks/frontend"

  project         = local.project
  env             = local.env
  aws_region      = local.aws_region
  base_domain     = local.base_domain
  zone_id         = local.zone_id
  certificate_arn = module.backend.certificate_arn
  web_env         = module.backend.frontend_env

  github_owner             = local.github_owner
  github_repository        = local.github_repository
  git_branch               = local.git_branch
  github_oidc_provider_arn = data.aws_iam_openid_connect_provider.github.arn
}
