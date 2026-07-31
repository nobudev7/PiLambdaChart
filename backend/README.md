# PiLambdaChart Backend Compute Tier

This folder contains the backend compute resources for PiLambdaChart, implementing Java-based chart generation, JSON metadata exports, and AWS Lambda event handlers.

## Folder Structure
*   `lambda/`: The Maven Java project implementing the chart-generating AWS Lambda handler and developer CLI tool.
*   `lambda/pom.xml`: Compilation descriptor for packaging the Lambda fat/shaded JAR.
*   `lambda/src/main/java/com/nobudev7/`:
    *   `TelemetryData.java`: Data model for generic timestamped numeric telemetry.
    *   `ChartGenerator.java`: JFreeChart compilation logic supporting dynamic plot bounds, minimum Y-axis range scaling (`MinYRange`), PNG image byte rendering, and `.json` sidecar generation.
    *   `ChartGeneratorHandler.java`: AWS Lambda handler managing event payload parsing (`date`, `device`, `metrics`, `timezone`), DynamoDB metadata lookups, UTC timezone bounds, chart rendering, S3 uploads, `file-list.json` catalog updates, and `output/metadata.json` exports.
    *   `ChartGeneratorCLI.java`: Command-line tool to query real DynamoDB telemetry and render chart PNGs, `.json` sidecars, `file-list.json`, and `output/metadata.json` locally.
*   `lambda/src/test/java/com/nobudev7/`:
    *   `ChartGeneratorTest.java`: JUnit 5 unit tests for chart generation, sub-pixel alignments, `MinYRange` scaling, and metadata sidecar exports.
    *   `LocalChartRenderTest.java`: JUnit 5 unit tests for local chart rendering validation.

---

## Compilation and Packaging

Build the fat/shaded JAR containing all dependencies using Maven:
```bash
cd lambda/
mvn clean package
```
This generates the packaged artifact:
*   `target/chart-generator-lambda-1.0-SNAPSHOT.jar`

---

## Automated Deployment via Terraform

The Lambda function and its EventBridge automated trigger schedule are managed declaratively in [`infrastructure/lambda.tf`](../infrastructure/lambda.tf).

### Deploy / Update Function Code

1. Build the JAR:
   ```bash
   cd lambda/
   mvn clean package
   ```

2. Enable and deploy via Terraform:
   ```bash
   cd ../infrastructure/
   # Ensure `enable_lambda = true` is set in terraform.tfvars
   terraform apply
   ```

Terraform automatically binds the DynamoDB and S3 bucket names to the environment variables, assigns the IAM execution role, provisions an automated EventBridge trigger schedule, and detects JAR checksum changes to update function code on re-build.

---

## Lambda Configuration

### Environment Variables
Configure the following environment variables on the AWS Lambda function:
*   `TELEMETRY_TABLE_NAME`: Name of the DynamoDB telemetry storage table (defaults to `IoT_Telemetry`).
*   `METADATA_TABLE_NAME`: Name of the DynamoDB metadata registry table (defaults to `IoT_Metadata`).
*   `S3_BUCKET_NAME`: Name of the S3 bucket where generated charts, `.json` sidecars, `file-list.json`, and `output/metadata.json` are stored.

### Handler Configuration
*   **Runtime**: Java 21
*   **Handler**: `com.nobudev7.ChartGeneratorHandler::handleRequest`
*   **Timeout**: 30 seconds (recommended)
*   **Memory**: 512 MB (recommended)

### Input Event Payload
The Lambda function parses the following input event keys:
```json
{
  "device": 1,
  "metrics": [1, 2, 3, 4, 5],
  "date": "yesterday",
  "timezone": "America/New_York"
}
```
*   `device` / `device_id` (Integer, default `1`): The numeric device ID partition key.
*   `metrics` / `metric` / `metric_id` (List<Integer> or Integer, default `[1, 2, 3, 4, 5]`): Metric IDs to process.
*   `timezone` / `tz` (String, default `America/New_York`): The timezone context used for daily UTC boundary calculations.
*   `date` / `target` (String, optional): Specific date (`YYYY-MM-DD`), `"yesterday"`, or `"today"`. Defaults to today's date if omitted.

---

## Dynamic Metadata & Minimum Y-Axis Range (`MinYRange`)

Chart metadata (Metric Names, Units, Chart Types, Emoji Icons, and Minimum Y-Axis Ranges) is retrieved dynamically from the DynamoDB `IoT_Metadata` registry table.

- **`MinYRange`**: Optional number attribute (e.g. `7.0` for Temperature). Ensures the chart Y-axis spans at least the specified range even when data fluctuations are small.
- **`Icon`**: Optional emoji icon (e.g. `"🌡️"`, `"💧"`, `"☀️"`, `"🔍"`, `"📏"`) stored in DynamoDB metadata and consumed by the frontend dashboard.
- **Metadata Export (`output/metadata.json`)**: Exported to S3 / local output folder whenever charts are generated, providing the frontend with dynamic metric metadata.

---

## Chart Generator CLI

[`ChartGeneratorCLI.java`](lambda/src/main/java/com/nobudev7/ChartGeneratorCLI.java) is a local developer tool that queries real DynamoDB telemetry and renders chart PNGs, JSON sidecars, `file-list.json`, and `metadata.json` directly to disk — no S3 bucket or Lambda invocation required.

### Running the CLI

```bash
cd lambda/
mvn compile exec:java -Dexec.args="<options>"
```

### Options

| Flag | Default | Description |
|:---|:---|:---|
| `-d`, `--device` | **required** | Device ID(s). Comma-separated or repeated (`-d 1,2` or `-d 1 -d 2`) |
| `-m`, `--metric` | **required** | Metric ID(s). Comma-separated or repeated |
| `--date` | `today` | Single target date (`today`, `yesterday`, or `YYYY-MM-DD`) |
| `--dates` | — | Multiple dates, comma-separated |
| `--tz` | `America/New_York` | Timezone for daily boundary calculation |
| `-o`, `--output` | `frontend/public/output` | Output directory (relative to `backend/lambda/`) |
| `--table` | `IoT_Telemetry` | DynamoDB table name (or set `TELEMETRY_TABLE_NAME` env var) |
| `--chart-type` | auto from metadata | Override chart type (`XYLineChart` or `XYAreaChart`) for all charts |
| `-h`, `--help` | — | Print help and exit |

### Examples

```bash
# Today's chart for device 1, metric 1
mvn compile exec:java -Dexec.args="-d 1 -m 1"

# All sensor metrics for two devices on a specific date
mvn compile exec:java -Dexec.args="-d 1,2 -m 1,2,3,4,5 --date 2026-07-25"

# Multiple dates with a custom output directory
mvn compile exec:java -Dexec.args="-d 1 -m 1,3 --dates 2026-07-24,2026-07-25 -o ~/charts"

# Override timezone
mvn compile exec:java -Dexec.args="-d 1 -m 1 --tz America/Los_Angeles"
```

### Output Layout

Charts and metadata are saved to disk under the frontend's output directory:

```
frontend/public/output/
  file-list.json                          ← index catalog consumed by frontend
  metadata.json                           ← metadata registry exported from DynamoDB
  {deviceId}/{metricId}/{year}/{month}/
    {metricId}-YYYYMMDD.png               ← Chart image
    {metricId}-YYYYMMDD.json              ← Sidecar data points & plot boundaries
```

---

## AWS Access Requirements

### Lambda Execution Role (Production)

| Service | Action | Resource | Purpose |
|:---|:---|:---|:---|
| DynamoDB | `dynamodb:Query` | `IoT_Telemetry` table | Fetch time-bounded telemetry readings |
| DynamoDB | `dynamodb:GetItem`, `dynamodb:Scan` | `IoT_Metadata` table | Look up device/metric metadata and export `metadata.json` |
| S3 | `s3:GetObject` | `chart-bucket/*` | Download existing `file-list.json` before merging |
| S3 | `s3:PutObject` | `chart-bucket/*` | Upload PNG charts, JSON sidecars, `file-list.json`, and `metadata.json` |
| CloudWatch Logs | `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents` | Lambda log group | Standard Lambda execution logging |

Permissions are configured declaratively in [`infrastructure/iam_lambda.tf`](../infrastructure/iam_lambda.tf).
