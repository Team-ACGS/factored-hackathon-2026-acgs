output "certificate_arn" {
  description = "Certificate covering the base domain and every name one label under it"
  value       = module.certificate.certificate_arn
}

output "api_url" {
  description = "API on its custom domain"
  value       = module.api.url
}

output "customers_pool_id" {
  description = "Cognito pool of customers"
  value       = module.customers_pool.id
}

output "staff_pool_id" {
  description = "Cognito pool of agents, officers and analysts"
  value       = module.staff_pool.id
}

output "client_ids" {
  description = "Cognito app client id per web"
  value       = merge(module.customers_pool.client_ids, module.staff_pool.client_ids)
}

output "realtime_http_url" {
  description = "AppSync Events endpoint chat-notifier and chatbot publish to"
  value       = module.realtime.http_url
}

output "realtime_url" {
  description = "AppSync Events WebSocket endpoint the webs subscribe to"
  value       = module.realtime.realtime_url
}

output "realtime_namespace" {
  description = "Channel namespace, the first segment of every room channel"
  value       = module.realtime.namespace
}

output "tables" {
  description = "DynamoDB table name per logical table"
  value       = { for name, table in module.table : name => table.name }
}

output "access_role_arns" {
  description = "Role a request lambda assumes per caller kind"
  value       = { for name, role in aws_iam_role.access : name => role.arn }
}

output "artifacts_bucket" {
  description = "Bucket the deploy workflow uploads Lambda bundles to"
  value       = module.artifacts_bucket.id
}

output "events_bucket" {
  description = "Bucket Firehose writes turn events to"
  value       = module.events_bucket.id
}

output "deploy_lambdas_role_arn" {
  description = "Role the Lambda deploy workflow assumes"
  value       = aws_iam_role.deploy_lambdas.arn
}

output "terraform_plan_role_arn" {
  description = "Role the Terraform plan workflow assumes"
  value       = aws_iam_role.terraform_plan.arn
}

output "frontend_env" {
  description = "Build-time variables per web, all public: they end up in a browser bundle"
  value = {
    for web, pool in { customer = module.customers_pool, support = module.staff_pool, backoffice = module.staff_pool } : web => {
      VITE_API_URL              = module.api.url
      VITE_USER_POOL_ID         = pool.id
      VITE_USER_POOL_CLIENT_ID  = pool.client_ids[web]
      VITE_REALTIME_URL         = module.realtime.realtime_url
      VITE_REALTIME_HTTP_URL    = module.realtime.http_url
      VITE_REALTIME_NAMESPACE   = module.realtime.namespace
    }
  }
}

output "policies_bucket" {
  description = "Bucket of the policy sources, the rendered documents and the build manifest"
  value       = module.policies_bucket.id
}

output "policy_documents_bucket" {
  description = "Bucket of the policy PDFs, served at the documents domain"
  value       = module.policy_documents_bucket.id
}

output "policy_documents_url" {
  description = "Public URL of the policy PDFs"
  value       = module.policy_documents_cdn.url
}

output "policy_index_arn" {
  description = "S3 Vectors index of the policy chunks"
  value       = aws_s3vectors_index.policies.index_arn
}

output "policies_builder_role_arn" {
  description = "Role the local policy build assumes"
  value       = aws_iam_role.policies_builder.arn
}
