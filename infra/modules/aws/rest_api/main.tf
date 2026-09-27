locals {
  cors_headers = "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,X-Requested-With"

  paths = distinct([for r in var.routes : r.path])

  routes_by_path = {
    for p in local.paths : p => [for r in var.routes : r if r.path == p]
  }

  path_parameters = {
    for p in local.paths : p => [
      for match in regexall("\\{([^}]+)\\}", p) : {
        name     = trimsuffix(match[0], "+")
        in       = "path"
        required = true
        schema   = { type = "string" }
      }
    ]
  }

  methods_by_path = {
    for p, routes in local.routes_by_path : p => merge([
      for r in routes : {
        (upper(r.method) == "ANY" ? "x-amazon-apigateway-any-method" : lower(r.method)) = merge(
          {
            responses = {
              "200" = { description = "Handled by the function" }
            }
            "x-amazon-apigateway-integration" = {
              type                = "aws_proxy"
              httpMethod          = "POST"
              uri                 = r.invoke_arn
              passthroughBehavior = "when_no_match"
            }
          },
          length(local.path_parameters[p]) > 0 ? { parameters = local.path_parameters[p] } : {},
          r.authorized ? { security = [{ cognito = [] }] } : {}
        )
      }
    ]...)
  }

  preflight = {
    options = {
      responses = {
        "200" = {
          description = "CORS preflight"
          headers = {
            "Access-Control-Allow-Origin"  = { schema = { type = "string" } }
            "Access-Control-Allow-Methods" = { schema = { type = "string" } }
            "Access-Control-Allow-Headers" = { schema = { type = "string" } }
          }
        }
      }
      "x-amazon-apigateway-integration" = {
        type             = "mock"
        requestTemplates = { "application/json" = "{\"statusCode\": 200}" }
        responses = {
          default = {
            statusCode = "200"
            responseParameters = {
              "method.response.header.Access-Control-Allow-Origin"  = "'${var.cors_allow_origin}'"
              "method.response.header.Access-Control-Allow-Headers" = "'${local.cors_headers}'"
              "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,GET,POST,PUT,PATCH,DELETE'"
            }
          }
        }
      }
    }
  }

  gateway_response = {
    responseParameters = {
      "gatewayresponse.header.Access-Control-Allow-Origin"  = "'${var.cors_allow_origin}'"
      "gatewayresponse.header.Access-Control-Allow-Headers" = "'${local.cors_headers}'"
    }
  }

  openapi = {
    openapi = "3.0.1"
    info = {
      title   = var.name
      version = "1.0"
    }
    paths = {
      for p in local.paths : "/${p}" => merge(local.methods_by_path[p], local.preflight)
    }
    components = {
      securitySchemes = {
        cognito = {
          type                           = "apiKey"
          name                           = "Authorization"
          in                             = "header"
          "x-amazon-apigateway-authtype" = "cognito_user_pools"
          "x-amazon-apigateway-authorizer" = {
            type         = "cognito_user_pools"
            providerARNs = var.cognito_user_pool_arns
          }
        }
      }
    }
    "x-amazon-apigateway-gateway-responses" = {
      DEFAULT_4XX = local.gateway_response
      DEFAULT_5XX = local.gateway_response
    }
  }
}

resource "aws_api_gateway_rest_api" "this" {
  name = var.name
  body = jsonencode(local.openapi)

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = merge(var.tags, { Name = var.name })
}

resource "aws_lambda_permission" "routes" {
  for_each = toset([for r in var.routes : r.function_name])

  statement_id  = "AllowInvokeFrom-${var.name}"
  action        = "lambda:InvokeFunction"
  function_name = each.value
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.this.execution_arn}/*/*"
}

resource "aws_api_gateway_deployment" "this" {
  rest_api_id = aws_api_gateway_rest_api.this.id

  triggers = {
    redeployment = sha1(jsonencode(local.openapi))
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_cloudwatch_log_group" "access" {
  name              = "/aws/apigateway/${var.name}"
  retention_in_days = var.log_retention_days

  tags = merge(var.tags, { Name = "${var.name}-access" })
}

resource "aws_cloudwatch_log_group" "execution" {
  name              = "API-Gateway-Execution-Logs_${aws_api_gateway_rest_api.this.id}/${var.stage_name}"
  retention_in_days = var.log_retention_days

  tags = merge(var.tags, { Name = "${var.name}-execution" })
}

resource "aws_api_gateway_stage" "this" {
  rest_api_id          = aws_api_gateway_rest_api.this.id
  deployment_id        = aws_api_gateway_deployment.this.id
  stage_name           = var.stage_name
  xray_tracing_enabled = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.access.arn
    format = jsonencode({
      requestId          = "$context.requestId"
      extendedRequestId  = "$context.extendedRequestId"
      xrayTraceId        = "$context.xrayTraceId"
      ip                 = "$context.identity.sourceIp"
      requestTime        = "$context.requestTime"
      httpMethod         = "$context.httpMethod"
      resourcePath       = "$context.resourcePath"
      path               = "$context.path"
      status             = "$context.status"
      responseLength     = "$context.responseLength"
      responseLatency    = "$context.responseLatency"
      integrationStatus  = "$context.integration.status"
      integrationLatency = "$context.integration.latency"
      integrationError   = "$context.integration.error"
      authorizerError    = "$context.authorizer.error"
      userSub            = "$context.authorizer.claims.sub"
      errorMessage       = "$context.error.message"
    })
  }

  tags = merge(var.tags, { Name = var.name })

  depends_on = [aws_cloudwatch_log_group.execution]
}

resource "aws_api_gateway_method_settings" "all" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  stage_name  = aws_api_gateway_stage.this.stage_name
  method_path = "*/*"

  settings {
    logging_level      = "ERROR"
    data_trace_enabled = false
    metrics_enabled    = false
  }
}

resource "aws_api_gateway_domain_name" "this" {
  domain_name              = var.domain
  regional_certificate_arn = var.certificate_arn
  security_policy          = "TLS_1_2"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = merge(var.tags, { Name = var.domain })
}

resource "aws_api_gateway_base_path_mapping" "this" {
  api_id      = aws_api_gateway_rest_api.this.id
  stage_name  = aws_api_gateway_stage.this.stage_name
  domain_name = aws_api_gateway_domain_name.this.domain_name
}

resource "aws_route53_record" "alias" {
  for_each = toset(["A", "AAAA"])

  zone_id = var.zone_id
  name    = var.domain
  type    = each.value

  alias {
    name                   = aws_api_gateway_domain_name.this.regional_domain_name
    zone_id                = aws_api_gateway_domain_name.this.regional_zone_id
    evaluate_target_health = false
  }
}
