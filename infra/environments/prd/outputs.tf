output "web_urls" {
  description = "Public URL per web"
  value       = module.frontend.urls
}

output "api_url" {
  description = "API on its custom domain"
  value       = module.backend.api_url
}

output "customers_pool_id" {
  description = "Cognito pool of customers"
  value       = module.backend.customers_pool_id
}

output "staff_pool_id" {
  description = "Cognito pool of agents, officers and analysts"
  value       = module.backend.staff_pool_id
}

output "client_ids" {
  description = "Cognito app client id per web"
  value       = module.backend.client_ids
}

output "realtime_url" {
  description = "AppSync Events WebSocket endpoint"
  value       = module.backend.realtime_url
}

output "tables" {
  description = "DynamoDB table name per logical table"
  value       = module.backend.tables
}

output "access_role_arns" {
  description = "Role a request lambda assumes per caller kind"
  value       = module.backend.access_role_arns
}

output "events_bucket" {
  description = "Bucket Firehose writes turn events to"
  value       = module.backend.events_bucket
}

output "artifacts_bucket" {
  description = "Bucket the deploy workflow uploads Lambda bundles to"
  value       = module.backend.artifacts_bucket
}

output "policies_bucket" {
  description = "Bucket of the policy sources, the rendered documents and the build manifest"
  value       = module.backend.policies_bucket
}

output "policy_documents_bucket" {
  description = "Bucket of the policy PDFs"
  value       = module.backend.policy_documents_bucket
}

output "policy_documents_url" {
  description = "Public URL of the policy PDFs"
  value       = module.backend.policy_documents_url
}

output "policy_index_arn" {
  description = "S3 Vectors index of the policy chunks"
  value       = module.backend.policy_index_arn
}

output "policies_builder_role_arn" {
  description = "Role the local policy build assumes"
  value       = module.backend.policies_builder_role_arn
}
