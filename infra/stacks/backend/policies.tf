################################################################################
# Policy corpus: sources, documents, vectors
################################################################################

locals {
  docs_domain = "docs.${var.base_domain}"

  policy_documents_bucket = "${local.name_prefix}-policy-documents${local.bucket_suffix}"

  policy_embedding_model_arn = "arn:aws:bedrock:${var.aws_region}::foundation-model/${var.policy_embedding_model_id}"

  policy_non_filterable_keys = [
    "text",
    "title",
    "section",
    "page_end",
    "url",
    "figures",
    "effective_date",
    "policy_facts_version",
    "content_hash",
  ]
}

module "policies_bucket" {
  source = "../../modules/aws/s3"

  name          = "${local.name_prefix}-policies${local.bucket_suffix}"
  force_destroy = true
  versioned     = true
}

module "policy_documents_bucket" {
  source = "../../modules/aws/s3"

  name                        = local.policy_documents_bucket
  force_destroy               = true
  cloudfront_read             = true
  cloudfront_distribution_arn = module.policy_documents_cdn.distribution_arn
}

module "policy_documents_cdn" {
  source = "../../modules/aws/cloudfront"

  name               = "${local.name_prefix}-policy-documents"
  domain             = local.docs_domain
  zone_id            = var.zone_id
  certificate_arn    = module.certificate.certificate_arn
  origin_domain_name = "${local.policy_documents_bucket}.s3.${var.aws_region}.amazonaws.com"
  single_page_app    = false
}

resource "aws_s3vectors_vector_bucket" "policies" {
  vector_bucket_name = "${local.name_prefix}-policy-vectors${local.bucket_suffix}"
  force_destroy      = true

  tags = { Name = "${local.name_prefix}-policy-vectors" }
}

resource "aws_s3vectors_index" "policies" {
  vector_bucket_name = aws_s3vectors_vector_bucket.policies.vector_bucket_name
  index_name         = "policies"
  data_type          = "float32"
  dimension          = 1024
  distance_metric    = "cosine"

  metadata_configuration {
    non_filterable_metadata_keys = local.policy_non_filterable_keys
  }

  tags = { Name = "${local.name_prefix}-policies" }
}

################################################################################
# The local build's role
################################################################################

data "aws_iam_policy_document" "policies_builder_trust" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${local.account_id}:root"]
    }
  }
}

data "aws_iam_policy_document" "policies_builder" {
  statement {
    sid       = "ListBuckets"
    actions   = ["s3:ListBucket"]
    resources = [module.policies_bucket.arn, module.policy_documents_bucket.arn]
  }

  statement {
    sid       = "ReadWriteObjects"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${module.policies_bucket.arn}/*", "${module.policy_documents_bucket.arn}/*"]
  }

  statement {
    sid = "WriteVectors"
    actions = [
      "s3vectors:PutVectors",
      "s3vectors:DeleteVectors",
      "s3vectors:ListVectors",
      "s3vectors:QueryVectors",
      "s3vectors:GetVectors",
    ]
    resources = [aws_s3vectors_index.policies.index_arn]
  }

  statement {
    sid       = "Embed"
    actions   = ["bedrock:InvokeModel"]
    resources = [local.policy_embedding_model_arn]
  }
}

resource "aws_iam_role" "policies_builder" {
  name                 = "${local.name_prefix}-policies-builder"
  assume_role_policy   = data.aws_iam_policy_document.policies_builder_trust.json
  max_session_duration = 4 * 3600

  tags = { Name = "${local.name_prefix}-policies-builder" }
}

resource "aws_iam_role_policy" "policies_builder" {
  name   = "policies"
  role   = aws_iam_role.policies_builder.id
  policy = data.aws_iam_policy_document.policies_builder.json
}
