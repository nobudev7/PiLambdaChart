variable "aws_region" {
  description = "AWS region to deploy all resources."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Short name used to prefix all AWS resource names."
  type        = string
  default     = "pilambdachart"
}

variable "telemetry_table_name" {
  description = "Name of the DynamoDB table that stores IoT telemetry data points."
  type        = string
  default     = "IoT_Telemetry"
}

variable "metadata_table_name" {
  description = "Name of the DynamoDB table that stores device and metric metadata."
  type        = string
  default     = "IoT_Metadata"
}

variable "enable_point_in_time_recovery" {
  description = "Enable point-in-time recovery (PITR) on the telemetry table for production environments."
  type        = bool
  default     = false
}

