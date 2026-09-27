module "certificate" {
  source = "../../modules/aws/acm"

  domain_name               = var.base_domain
  subject_alternative_names = ["*.${var.base_domain}"]
  zone_id                   = var.zone_id
}
