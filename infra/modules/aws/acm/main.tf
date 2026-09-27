resource "aws_acm_certificate" "this" {
  domain_name               = var.domain_name
  subject_alternative_names = var.subject_alternative_names
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = merge(var.tags, { Name = var.domain_name })
}

locals {
  all_domains = concat([var.domain_name], var.subject_alternative_names)

  validated_domains = toset([
    for domain in local.all_domains : domain
    if !(startswith(domain, "*.") && contains(local.all_domains, trimprefix(domain, "*.")))
  ])

  validation_options = {
    for dvo in aws_acm_certificate.this.domain_validation_options :
    dvo.domain_name => dvo
  }
}

resource "aws_route53_record" "validation" {
  for_each = local.validated_domains

  zone_id = var.zone_id
  name    = local.validation_options[each.value].resource_record_name
  type    = local.validation_options[each.value].resource_record_type
  records = [local.validation_options[each.value].resource_record_value]
  ttl     = 60
}

resource "aws_acm_certificate_validation" "this" {
  certificate_arn         = aws_acm_certificate.this.arn
  validation_record_fqdns = [for r in aws_route53_record.validation : r.fqdn]
}
