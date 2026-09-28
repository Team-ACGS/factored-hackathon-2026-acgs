module "realtime" {
  source = "../../modules/aws/appsync_events"

  name      = local.name_prefix
  namespace = "rooms"

  code_handlers = templatefile("${path.module}/handlers/rooms.js", {
    staff_issuer = "https://cognito-idp.${var.aws_region}.amazonaws.com/${module.staff_pool.id}"
  })

  cognito_user_pool_ids = {
    customers = module.customers_pool.id
    staff     = module.staff_pool.id
  }

  log_retention_days = var.log_retention_days
}
