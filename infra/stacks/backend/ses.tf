module "ses" {
  source = "../../modules/aws/ses"

  name    = local.name_prefix
  domain  = var.email_domain
  zone_id = var.zone_id
}
