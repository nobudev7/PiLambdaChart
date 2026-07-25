output "telemetry_table_name" {
  description = "Name of the DynamoDB telemetry table."
  value       = aws_dynamodb_table.iot_telemetry.name
}

output "telemetry_table_arn" {
  description = "ARN of the DynamoDB telemetry table. Use this to scope IAM policies for the Lambda execution role and edge client IAM user."
  value       = aws_dynamodb_table.iot_telemetry.arn
}

output "metadata_table_name" {
  description = "Name of the DynamoDB metadata registry table."
  value       = aws_dynamodb_table.iot_metadata.name
}

output "metadata_table_arn" {
  description = "ARN of the DynamoDB metadata registry table."
  value       = aws_dynamodb_table.iot_metadata.arn
}

output "client_access_key_id" {
  value     = aws_iam_access_key.client_key.id
  sensitive = false
}

output "client_secret_access_key" {
  value     = aws_iam_access_key.client_key.secret
  sensitive = true # Keeps the secret concealed from accidental stdout prints
}

output "chart_bucket_name" {
  description = "Name of the S3 bucket used for chart PNG output and file-list.json."
  value       = aws_s3_bucket.charts.bucket
}

output "chart_bucket_arn" {
  description = "ARN of the S3 chart bucket. Use in Lambda execution role policies."
  value       = aws_s3_bucket.charts.arn
}

output "lambda_exec_role_arn" {
  description = "ARN of the Lambda execution IAM role. Assign this as the Lambda function's execution role."
  value       = aws_iam_role.lambda_exec_role.arn
}