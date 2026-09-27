data "aws_region" "current" {}

locals {
  mail_from_domain = "${var.mail_from_subdomain}.${var.domain}"
}

resource "aws_sesv2_configuration_set" "this" {
  configuration_set_name = var.name

  delivery_options {
    tls_policy = "REQUIRE"
  }

  reputation_options {
    reputation_metrics_enabled = true
  }

  sending_options {
    sending_enabled = true
  }

  tags = merge(var.tags, { Name = var.name })
}

resource "aws_sesv2_email_identity" "this" {
  email_identity         = var.domain
  configuration_set_name = aws_sesv2_configuration_set.this.configuration_set_name

  dkim_signing_attributes {
    next_signing_key_length = "RSA_2048_BIT"
  }

  tags = merge(var.tags, { Name = var.domain })
}

resource "aws_route53_record" "dkim" {
  count = 3

  zone_id = var.zone_id
  name    = "${aws_sesv2_email_identity.this.dkim_signing_attributes[0].tokens[count.index]}._domainkey.${var.domain}"
  type    = "CNAME"
  records = ["${aws_sesv2_email_identity.this.dkim_signing_attributes[0].tokens[count.index]}.dkim.amazonses.com"]
  ttl     = 3600
}

resource "aws_sesv2_email_identity_mail_from_attributes" "this" {
  email_identity         = aws_sesv2_email_identity.this.email_identity
  mail_from_domain       = local.mail_from_domain
  behavior_on_mx_failure = "USE_DEFAULT_VALUE"
}

resource "aws_route53_record" "mail_from_mx" {
  zone_id = var.zone_id
  name    = local.mail_from_domain
  type    = "MX"
  records = ["10 feedback-smtp.${data.aws_region.current.region}.amazonses.com"]
  ttl     = 3600
}

resource "aws_route53_record" "mail_from_spf" {
  zone_id = var.zone_id
  name    = local.mail_from_domain
  type    = "TXT"
  records = ["v=spf1 include:amazonses.com ~all"]
  ttl     = 3600
}

resource "aws_route53_record" "dmarc" {
  zone_id = var.zone_id
  name    = "_dmarc.${var.domain}"
  type    = "TXT"
  records = ["v=DMARC1; p=reject"]
  ttl     = 3600
}

# Cognito refuses a pool whose SES identity is not verified yet, and SES
# verifies the domain asynchronously once it sees the DKIM records. Terraform
# has no waiter for a SESv2 identity, so this one polls.
resource "terraform_data" "verified" {
  triggers_replace = [aws_sesv2_email_identity.this.arn]

  provisioner "local-exec" {
    interpreter = ["/bin/sh", "-c"]
    command     = <<-EOT
      for attempt in $(seq 1 90); do
        status=$(aws sesv2 get-email-identity --region ${data.aws_region.current.region} --email-identity ${var.domain} --query VerifiedForSendingStatus --output text)
        [ "$status" = "True" ] && exit 0
        sleep 10
      done
      echo "SES identity ${var.domain} is still unverified after 15 minutes" >&2
      exit 1
    EOT
  }

  depends_on = [aws_route53_record.dkim]
}
