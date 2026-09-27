# API Gateway writes stage logs through one CloudWatch role per account and
# region. It lives here, not in prd, so destroying prd never leaves the account
# pointing at a deleted role.
resource "aws_iam_role" "api_gateway_logs" {
  name = "${local.name_prefix}-apigateway-logs"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "apigateway.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = { Name = "${local.name_prefix}-apigateway-logs" }
}

resource "aws_iam_role_policy_attachment" "api_gateway_logs" {
  role       = aws_iam_role.api_gateway_logs.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs"
}

resource "aws_api_gateway_account" "this" {
  cloudwatch_role_arn = aws_iam_role.api_gateway_logs.arn

  depends_on = [aws_iam_role_policy_attachment.api_gateway_logs]
}
