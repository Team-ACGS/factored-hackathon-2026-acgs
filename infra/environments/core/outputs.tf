output "console_url" {
  description = "Sign-in URL of the account for the admin users"
  value       = "https://${local.aws_account_id}.signin.aws.amazon.com/console"
}

output "admins" {
  description = "IAM users in the admins group"
  value       = [for user in aws_iam_user.admin : user.name]
}
