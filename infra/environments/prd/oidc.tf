# The account has one GitHub OIDC provider and it belongs to the my-napkin
# Terraform (environments/core there). Clara reads it and never manages it.
data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}
