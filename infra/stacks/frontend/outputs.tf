output "urls" {
  description = "Public URL per web"
  value       = { for web, cdn in module.cdn : web => cdn.url }
}

output "deploy_role_arns" {
  description = "Role each web's deploy workflow assumes"
  value       = { for web, role in aws_iam_role.deploy : web => role.arn }
}
