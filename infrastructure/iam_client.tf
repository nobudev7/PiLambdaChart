resource "aws_iam_user" "edge_client_user" {
  name = "${var.project_name}-edge-client-user"

  tags = merge(local.common_tags, {
    Component = "edge-client"
  })
}

resource "aws_iam_access_key" "client_key" {
  user = aws_iam_user.edge_client_user.name
}

# Explicit policy granting access ONLY to our specific storage layer
resource "aws_iam_user_policy" "client_policy" {
  name = "${var.project_name}-edge-client-dynamodb-access"
  user = aws_iam_user.edge_client_user.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:BatchWriteItem"
        ]
        Resource = aws_dynamodb_table.iot_telemetry.arn
      }
    ]
  })
}
