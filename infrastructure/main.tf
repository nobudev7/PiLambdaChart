terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ─────────────────────────────────────────────
# IoT Telemetry Table
# ─────────────────────────────────────────────
# Schema:
#   PK  Device_Metric_UTCYear  String  "{DeviceID}#{MetricID}#{UTCYear}"  e.g. "1#1#2026"
#   SK  Timestamp              String  UTC ISO-8601                        e.g. "2026-07-12T14:30:00Z"
#
# Non-key attributes (written by edge client, not declared here):
#   Value     Number  — The numeric telemetry reading
#   DeviceID  Number  — Redundant copy for filtering / GSI use
#   MetricID  Number  — Redundant copy for filtering / GSI use
#
# Partition strategy: one partition per device × metric × calendar year.
# At 1-min upload intervals, a single partition grows ~50 MB/year —
# well below DynamoDB's 10 GB partition limit.
# ─────────────────────────────────────────────
resource "aws_dynamodb_table" "iot_telemetry" {
  name         = var.telemetry_table_name
  billing_mode = "PAY_PER_REQUEST" # On-demand: cost scales with IoT traffic, no capacity planning needed.
  hash_key     = "Device_Metric_UTCYear"
  range_key    = "Timestamp"

  attribute {
    name = "Device_Metric_UTCYear"
    type = "S"
  }

  attribute {
    name = "Timestamp"
    type = "S"
  }

  point_in_time_recovery {
    enabled = var.enable_point_in_time_recovery
  }

  tags = merge(local.common_tags, {
    Component = "telemetry-storage"
  })
}

# ─────────────────────────────────────────────
# IoT Metadata Table
# ─────────────────────────────────────────────
# Stores human-readable metadata for devices and metrics.
# Written once at registration time; read by the Lambda and frontend.
#
# Schema:
#   PK  EntityType  String  "DEVICE" or "METRIC"
#   SK  ID          Number  Numeric device or metric ID (e.g. 1, 2, 3...)
#
# Example items:
#   { EntityType: "DEVICE", ID: 1, Name: "Sump Pump Pi", Location: "Basement" }
#   { EntityType: "METRIC", ID: 1, Name: "Water Level",  Unit: "cm", ChartType: "XYLineChart" }
#   { EntityType: "METRIC", ID: 2, Name: "Motion Count", Unit: "triggers/min", ChartType: "BarChart" }
# ─────────────────────────────────────────────
resource "aws_dynamodb_table" "iot_metadata" {
  name         = var.metadata_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "EntityType"
  range_key    = "ID"

  attribute {
    name = "EntityType"
    type = "S"
  }

  attribute {
    name = "ID"
    type = "N"
  }

  tags = merge(local.common_tags, {
    Component = "metadata-registry"
  })
}
