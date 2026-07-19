# ─────────────────────────────────────────────────────────────────────────────
# Default Metadata Seed Items for DynamoDB IoT_Metadata
# ─────────────────────────────────────────────────────────────────────────────
# Automatically inserts the default devices and metric configurations matching
# edge/config.yaml.example into the metadata registry table.
# ─────────────────────────────────────────────────────────────────────────────

# Devices
resource "aws_dynamodb_table_item" "device_1" {
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
  table_name = aws_dynamodb_table.iot_metadata.name
  hash_key   = aws_dynamodb_table.iot_metadata.hash_key
  range_key  = aws_dynamodb_table.iot_metadata.range_key

  item = jsonencode({
    EntityType = { S = "METRIC" }
    ID         = { N = "1" }
    Name       = { S = "Temperature" }
    Unit       = { S = "°C" }
    ChartType  = { S = "XYLineChart" }
  })
}

resource "aws_dynamodb_table_item" "metric_2" {
  table_name = aws_dynamodb_table.iot_metadata.name
  hash_key   = aws_dynamodb_table.iot_metadata.hash_key
  range_key  = aws_dynamodb_table.iot_metadata.range_key

  item = jsonencode({
    EntityType = { S = "METRIC" }
    ID         = { N = "2" }
    Name       = { S = "Humidity" }
    Unit       = { S = "%" }
    ChartType  = { S = "XYLineChart" }
  })
}

resource "aws_dynamodb_table_item" "metric_3" {
  table_name = aws_dynamodb_table.iot_metadata.name
  hash_key   = aws_dynamodb_table.iot_metadata.hash_key
  range_key  = aws_dynamodb_table.iot_metadata.range_key

  item = jsonencode({
    EntityType = { S = "METRIC" }
    ID         = { N = "3" }
    Name       = { S = "Ambient Light" }
    Unit       = { S = "Lux" }
    ChartType  = { S = "XYLineChart" }
  })
}

resource "aws_dynamodb_table_item" "metric_4" {
  table_name = aws_dynamodb_table.iot_metadata.name
  hash_key   = aws_dynamodb_table.iot_metadata.hash_key
  range_key  = aws_dynamodb_table.iot_metadata.range_key

  item = jsonencode({
    EntityType = { S = "METRIC" }
    ID         = { N = "4" }
    Name       = { S = "Motion Count" }
    Unit       = { S = "triggers/min" }
    ChartType  = { S = "BarChart" }
  })
}

resource "aws_dynamodb_table_item" "metric_5" {
  table_name = aws_dynamodb_table.iot_metadata.name
  hash_key   = aws_dynamodb_table.iot_metadata.hash_key
  range_key  = aws_dynamodb_table.iot_metadata.range_key

  item = jsonencode({
    EntityType = { S = "METRIC" }
    ID         = { N = "5" }
    Name       = { S = "Water Level" }
    Unit       = { S = "cm" }
    ChartType  = { S = "XYLineChart" }
  })
}
