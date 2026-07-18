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
