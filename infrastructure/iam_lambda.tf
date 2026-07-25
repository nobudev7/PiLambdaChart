# ─────────────────────────────────────────────────────────────────────────────
# IAM Resources for the Chart Generator Lambda Function
# ─────────────────────────────────────────────────────────────────────────────
#
# The Lambda execution role needs:
#
#   DynamoDB (read-only):
#     dynamodb:GetItem   — IoT_Metadata  (device/metric name, unit, chart type)
#     dynamodb:Query     — IoT_Telemetry (time-bounded telemetry readings)
#
#   S3 (read + write on the chart bucket only):
#     s3:GetObject       — download existing file-list.json to merge updates
#     s3:PutObject       — upload generated chart PNG images
#     s3:PutObject       — overwrite file-list.json with updated index
#
#   CloudWatch Logs (standard Lambda logging):
#     logs:CreateLogGroup / logs:CreateLogStream / logs:PutLogEvents
#
# ─────────────────────────────────────────────────────────────────────────────

# ── Trust policy: allow Lambda service to assume this role ───────────────────
data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "lambda_exec_role" {
  name               = "${var.project_name}-lambda-exec-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json

  tags = merge(local.common_tags, {
    Component = "lambda-chart-generator"
  })
}

# ── DynamoDB read policy ─────────────────────────────────────────────────────
data "aws_iam_policy_document" "lambda_dynamodb" {
  statement {
    sid    = "ReadTelemetry"
    effect = "Allow"
    actions = [
      "dynamodb:Query"
    ]
    resources = [
      aws_dynamodb_table.iot_telemetry.arn
    ]
  }

  statement {
    sid    = "ReadMetadata"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem"
    ]
    resources = [
      aws_dynamodb_table.iot_metadata.arn
    ]
  }
}

resource "aws_iam_role_policy" "lambda_dynamodb" {
  name   = "${var.project_name}-lambda-dynamodb-read"
  role   = aws_iam_role.lambda_exec_role.id
  policy = data.aws_iam_policy_document.lambda_dynamodb.json
}

# ── S3 read + write policy (scoped to chart bucket only) ─────────────────────
data "aws_iam_policy_document" "lambda_s3" {
  statement {
    sid    = "ReadWriteChartBucket"
    effect = "Allow"
    actions = [
      "s3:GetObject",   # Download existing file-list.json before merging
      "s3:PutObject"    # Upload chart PNGs and updated file-list.json
    ]
    resources = [
      "${aws_s3_bucket.charts.arn}/*"
    ]
  }
}

resource "aws_iam_role_policy" "lambda_s3" {
  name   = "${var.project_name}-lambda-s3-readwrite"
  role   = aws_iam_role.lambda_exec_role.id
  policy = data.aws_iam_policy_document.lambda_s3.json
}

# ── CloudWatch Logs policy (basic Lambda logging) ────────────────────────────
resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_exec_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}
