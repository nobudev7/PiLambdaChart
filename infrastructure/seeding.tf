# ─────────────────────────────────────────────────────────────────────────────
# Dynamic Metadata Seed Items for DynamoDB IoT_Metadata
# ─────────────────────────────────────────────────────────────────────────────
# Automatically inserts custom device and metric configurations into the
# metadata registry table when enable_metadata_seeding = true.
# The list of devices and metrics is defined via variables and can be
# customized in terraform.tfvars.
# ─────────────────────────────────────────────────────────────────────────────

# Devices
resource "aws_dynamodb_table_item" "devices" {
  for_each   = var.enable_metadata_seeding ? var.seeded_devices : {}
  table_name = aws_dynamodb_table.iot_metadata.name
  hash_key   = aws_dynamodb_table.iot_metadata.hash_key
  range_key  = aws_dynamodb_table.iot_metadata.range_key

  item = jsonencode({
    EntityType = { S = "DEVICE" }
    ID         = { N = each.key }
    Name       = { S = each.value.name }
    Location   = { S = each.value.location }
  })
}

# Metrics
resource "aws_dynamodb_table_item" "metrics" {
  for_each   = var.enable_metadata_seeding ? var.seeded_metrics : {}
  table_name = aws_dynamodb_table.iot_metadata.name
  hash_key   = aws_dynamodb_table.iot_metadata.hash_key
  range_key  = aws_dynamodb_table.iot_metadata.range_key

  # Construct item conditionally based on optional parameters
  item = jsonencode(
    merge(
      {
        EntityType = { S = "METRIC" }
        ID         = { N = each.key }
        Name       = { S = each.value.name }
        Unit       = { S = each.value.unit }
        ChartType  = { S = each.value.chart_type }
        Icon       = { S = each.value.icon }
      },
      each.value.min_y_range != null ? {
        MinYRange = { N = tostring(each.value.min_y_range) }
      } : {}
    )
  )
}
