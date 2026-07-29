# ─────────────────────────────────────────────────────────────────────────────
# Default Metadata Seed Items for DynamoDB IoT_Metadata
# ─────────────────────────────────────────────────────────────────────────────
# Automatically inserts default device and metric configurations into the
# metadata registry table when enable_metadata_seeding = true.
# Set enable_metadata_seeding = false if metadata is managed dynamically.
# ─────────────────────────────────────────────────────────────────────────────

# Devices
resource "aws_dynamodb_table_item" "device_1" {
  count      = var.enable_metadata_seeding ? 1 : 0
  table_name = aws_dynamodb_table.iot_metadata.name
  hash_key   = aws_dynamodb_table.iot_metadata.hash_key
  range_key  = aws_dynamodb_table.iot_metadata.range_key

  item = jsonencode({
    EntityType = { S = "DEVICE" }
    ID         = { N = "1" }
    Name       = { S = "Water Level Pi" }
    Location   = { S = "Basement" }
  })
}

resource "aws_dynamodb_table_item" "device_2" {
  count      = var.enable_metadata_seeding ? 1 : 0
  table_name = aws_dynamodb_table.iot_metadata.name
  hash_key   = aws_dynamodb_table.iot_metadata.hash_key
  range_key  = aws_dynamodb_table.iot_metadata.range_key

  item = jsonencode({
    EntityType = { S = "DEVICE" }
    ID         = { N = "2" }
    Name       = { S = "Ambient Monitor" }
    Location   = { S = "Bedroom" }
  })
}

# Metrics (Matching IDs 1-5 from config.yaml.example)
resource "aws_dynamodb_table_item" "metric_1" {
  count      = var.enable_metadata_seeding ? 1 : 0
  table_name = aws_dynamodb_table.iot_metadata.name
  hash_key   = aws_dynamodb_table.iot_metadata.hash_key
  range_key  = aws_dynamodb_table.iot_metadata.range_key

  item = jsonencode({
    EntityType = { S = "METRIC" }
    ID         = { N = "1" }
    Name       = { S = "Temperature" }
    Unit       = { S = "°C" }
    ChartType  = { S = "XYLineChart" }
    MinYRange  = { N = "6" }
    Icon       = { S = "🌡️" }
  })
}

resource "aws_dynamodb_table_item" "metric_2" {
  count      = var.enable_metadata_seeding ? 1 : 0
  table_name = aws_dynamodb_table.iot_metadata.name
  hash_key   = aws_dynamodb_table.iot_metadata.hash_key
  range_key  = aws_dynamodb_table.iot_metadata.range_key

  item = jsonencode({
    EntityType = { S = "METRIC" }
    ID         = { N = "2" }
    Name       = { S = "Humidity" }
    Unit       = { S = "%" }
    ChartType  = { S = "XYLineChart" }
    Icon       = { S = "💧" }
  })
}

resource "aws_dynamodb_table_item" "metric_3" {
  count      = var.enable_metadata_seeding ? 1 : 0
  table_name = aws_dynamodb_table.iot_metadata.name
  hash_key   = aws_dynamodb_table.iot_metadata.hash_key
  range_key  = aws_dynamodb_table.iot_metadata.range_key

  item = jsonencode({
    EntityType = { S = "METRIC" }
    ID         = { N = "3" }
    Name       = { S = "Ambient Light" }
    Unit       = { S = "Lux" }
    ChartType  = { S = "XYLineChart" }
    Icon       = { S = "☀️" }
  })
}

resource "aws_dynamodb_table_item" "metric_4" {
  count      = var.enable_metadata_seeding ? 1 : 0
  table_name = aws_dynamodb_table.iot_metadata.name
  hash_key   = aws_dynamodb_table.iot_metadata.hash_key
  range_key  = aws_dynamodb_table.iot_metadata.range_key

  item = jsonencode({
    EntityType = { S = "METRIC" }
    ID         = { N = "4" }
    Name       = { S = "Motion Count" }
    Unit       = { S = "triggers/min" }
    ChartType  = { S = "BarChart" }
    Icon       = { S = "🔍" }
  })
}

resource "aws_dynamodb_table_item" "metric_5" {
  count      = var.enable_metadata_seeding ? 1 : 0
  table_name = aws_dynamodb_table.iot_metadata.name
  hash_key   = aws_dynamodb_table.iot_metadata.hash_key
  range_key  = aws_dynamodb_table.iot_metadata.range_key

  item = jsonencode({
    EntityType = { S = "METRIC" }
    ID         = { N = "5" }
    Name       = { S = "Water Level" }
    Unit       = { S = "cm" }
    ChartType  = { S = "XYLineChart" }
    Icon       = { S = "📏" }
  })
}
