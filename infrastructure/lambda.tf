# ─────────────────────────────────────────────
# AWS Lambda Function & Automated EventBridge Schedule
# ─────────────────────────────────────────────
#
# This file provisions:
#   1. AWS Lambda Function — deploys the compiled Maven shaded JAR from backend/lambda.
#   2. EventBridge Rule — triggers automated chart generation on schedule (default: rate(5 minutes)).
#   3. EventBridge Targets — links schedule rule to the Lambda function (one invocation per device).
#   4. Lambda Permission — allows EventBridge service to invoke the function.
#
# Controlled by variables:
#   - enable_lambda (default: false)
#   - lambda_schedule_cron (default: "rate(5 minutes)")
#   - lambda_trigger_devices (default: [1])
#   - lambda_trigger_metrics (default: [1, 2, 3, 4, 5])
#   - lambda_trigger_timezone (default: "America/New_York")
# ─────────────────────────────────────────────

# 1. Lambda Function Definition
resource "aws_lambda_function" "chart_generator" {
  count = var.enable_lambda ? 1 : 0

  function_name = "${var.project_name}-chart-generator"
  role          = aws_iam_role.lambda_exec_role.arn
  handler       = "com.nobudev7.ChartGeneratorHandler::handleRequest"
  runtime       = "java21"
  memory_size   = var.lambda_memory_size
  timeout       = 30

  filename         = "${path.module}/../backend/lambda/target/chart-generator-lambda-1.0-SNAPSHOT.jar"
  source_code_hash = fileexists("${path.module}/../backend/lambda/target/chart-generator-lambda-1.0-SNAPSHOT.jar") ? filebase64sha256("${path.module}/../backend/lambda/target/chart-generator-lambda-1.0-SNAPSHOT.jar") : null

  environment {
    variables = {
      TELEMETRY_TABLE_NAME = aws_dynamodb_table.iot_telemetry.name
      METADATA_TABLE_NAME  = aws_dynamodb_table.iot_metadata.name
      S3_BUCKET_NAME       = aws_s3_bucket.charts.bucket
    }
  }

  tags = merge(local.common_tags, {
    Component = "lambda-chart-generator"
  })
}

# 2. EventBridge Rule (Automated Schedule Trigger — Every 5 Minutes)
resource "aws_cloudwatch_event_rule" "daily_chart_schedule" {
  count               = var.enable_lambda ? 1 : 0
  name                = "${var.project_name}-chart-schedule"
  description         = "Trigger chart generation Lambda every 5 minutes"
  schedule_expression = var.lambda_schedule_cron
}

# 3. Targets linking EventBridge to the Lambda function (one target per device)
resource "aws_cloudwatch_event_target" "trigger_lambda_target" {
  for_each  = var.enable_lambda ? toset([for dev_id in var.lambda_trigger_devices : tostring(dev_id)]) : []
  rule      = aws_cloudwatch_event_rule.daily_chart_schedule[0].name
  target_id = "ChartGen-Dev${each.key}"
  arn       = aws_lambda_function.chart_generator[0].arn

  input = jsonencode({
    "device_id" : tonumber(each.key),
    "metrics"   : var.lambda_trigger_metrics,
    "target"    : "today",
    "timezone"  : var.lambda_trigger_timezone
  })
}

# 4. Permission for EventBridge to invoke the Lambda function
resource "aws_lambda_permission" "allow_eventbridge" {
  count         = var.enable_lambda ? 1 : 0
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.chart_generator[0].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_chart_schedule[0].arn
}
