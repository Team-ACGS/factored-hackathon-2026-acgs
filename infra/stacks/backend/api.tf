module "api" {
  source = "../../modules/aws/rest_api"

  name = "${local.name_prefix}-api"

  domain          = local.api_domain
  certificate_arn = module.certificate.certificate_arn
  zone_id         = var.zone_id

  cognito_user_pool_arns = [module.customers_pool.arn, module.staff_pool.arn]
  log_retention_days     = var.log_retention_days

  routes = merge([
    for prefix, fn in { crud = "crud", messages = "messages" } : {
      "${prefix}" = {
        path          = prefix
        method        = "ANY"
        invoke_arn    = module.function[fn].invoke_arn
        function_name = module.function[fn].name
      }
      "${prefix}_proxy" = {
        path          = "${prefix}/{proxy+}"
        method        = "ANY"
        invoke_arn    = module.function[fn].invoke_arn
        function_name = module.function[fn].name
      }
    }
  ]...)
}
