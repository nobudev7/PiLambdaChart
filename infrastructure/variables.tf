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

variable "chart_bucket_name" {
  description = "Name of the S3 bucket where the Lambda uploads chart PNG images and file-list.json."
  type        = string
  default     = "pilambdachart-charts"
}

# ── CloudFront & Access Control Variables ─────────────────────────────────────
variable "enable_cloudfront" {
  description = "Provision a CloudFront CDN distribution in front of the S3 chart bucket."
  type        = bool
  default     = false
}

variable "enable_cloudfront_basic_auth" {
  description = "Enable HTTP Basic Authentication on CloudFront via edge function. Defaults to true when CloudFront is enabled."
  type        = bool
  default     = true
}

variable "basic_auth_username" {
  description = "Username for CloudFront HTTP Basic Auth."
  type        = string
  default     = "admin"
}

variable "basic_auth_password" {
  description = "Password for CloudFront HTTP Basic Auth."
  type        = string
  default     = "pilambdachart2026!"
  sensitive   = true
}

variable "custom_domain_name" {
  description = "Optional custom domain name (e.g. dashboard.example.com). Leave empty to use the default *.cloudfront.net domain."
  type        = string
  default     = ""
}

variable "acm_certificate_arn" {
  description = "ACM Certificate ARN in us-east-1 (required if custom_domain_name is specified)."
  type        = string
  default     = ""
}

variable "web_acl_id" {
  description = "WAF Web ACL ARN attached to CloudFront distribution (required for CloudFront security / flat-rate subscription plans)."
  type        = string
  default     = ""
}

# ── Lambda & Schedule Variables ───────────────────────────────────────────────
variable "enable_lambda" {
  description = "Provision the Chart Generator AWS Lambda function and EventBridge trigger."
  type        = bool
  default     = false
}

variable "lambda_schedule_cron" {
  description = "EventBridge schedule for automatic chart generation (default: rate(5 minutes))."
  type        = string
  default     = "rate(5 minutes)"
}

variable "lambda_memory_size" {
  description = "Memory size (in MB) allocated to the Chart Generator AWS Lambda function."
  type        = number
  default     = 512
}

variable "lambda_trigger_devices" {
  description = "List of device IDs to generate charts for on each schedule trigger."
  type        = list(number)
  default     = [1]
}

variable "lambda_trigger_metrics" {
  description = "List of metric IDs per device to generate charts for on each schedule trigger."
  type        = list(number)
  default     = [1, 2, 3, 4, 5]
}

variable "lambda_trigger_timezone" {
  description = "Timezone context for target day calculations (e.g. America/New_York)."
  type        = string
  default     = "America/New_York"
}



