module "realtime" {
  source = "../../modules/aws/appsync_events"

  name      = local.name_prefix
  namespace = "rooms"

  cognito_user_pool_ids = {
    customers = module.customers_pool.id
    staff     = module.staff_pool.id
  }

  log_retention_days = var.log_retention_days
}
