# PiLambdaChart Backend Compute Tier

This folder contains the backend resources for PiLambdaChart, including the Java Lambda code.

## Folder Structure
*   `lambda/`: The Maven Java project implementing the chart-generating AWS Lambda handler.
*   `lambda/pom.xml`: Compilation descriptor for packaging the Lambda JAR.
*   `lambda/src/main/java/com/nobudev7/`:
    *   `TelemetryData.java`: Data model for generic timestamped numeric telemetry.
    *   `ChartGenerator.java`: JFreeChart compilation logic using a custom premium slate-dark style dashboard design.
    *   `ChartGeneratorHandler.java`: AWS Lambda handler managing input event parsing, metadata lookups, UTC timezone bounds calculations, S3 uploads, and `file-list.json` tree catalog updates.
    *   `ChartGeneratorCLI.java`: Command-line tool to fetch real DynamoDB telemetry and render chart PNGs locally (no S3 required).

## Compilation and Packaging

Build the fat/shaded JAR containing all dependencies using Maven:
```bash
cd lambda/
mvn clean package
```
This generates the packaged artifact:
*   `target/chart-generator-lambda-1.0-SNAPSHOT.jar`

Upload this shaded JAR as the deployment package for your AWS Lambda function.

## Lambda Configuration

### Environment Variables
Configure the following environment variables on the AWS Lambda function:
*   `TELEMETRY_TABLE_NAME`: Name of the DynamoDB telemetry storage table (defaults to `IoT_Telemetry`).
*   `METADATA_TABLE_NAME`: Name of the DynamoDB metadata registry table (defaults to `IoT_Metadata`).
*   `S3_BUCKET_NAME`: Name of the S3 bucket where generated charts and `file-list.json` are stored.

### Handler Configuration
*   **Runtime**: Java 21
*   **Handler**: `com.nobudev7.ChartGeneratorHandler::handleRequest`
*   **Timeout**: 30 seconds (recommended)
*   **Memory**: 512 MB (recommended)

### Input Event Payload
The Lambda function parses the following input event keys:
```json
{
  "device_id": 1,
  "metric_id": 5,
  "timezone": "America/New_York",
  "date": "2026-07-19"
}
```
*   `device_id` / `device` (Integer, default `1`): The numeric device ID partition key.
*   `metric_id` / `metric` (Integer, default `1`): The numeric metric ID partition key.
*   `timezone` / `tz` (String, default `America/New_York`): The timezone context used for converting start/end daily boundaries to UTC and adjusting points.
*   `date` (String, optional): Specific date in `YYYY-MM-DD` format. Alternatively, set `"target": "yesterday"` to fetch yesterday's readings relative to the target timezone's today. Defaults to today's date if omitted.

---

## Chart Generator CLI

[`ChartGeneratorCLI.java`](lambda/src/main/java/com/nobudev7/ChartGeneratorCLI.java) is a local developer tool that queries real DynamoDB telemetry and renders chart PNGs directly to the local filesystem — no S3 bucket or Lambda invocation required.

Useful for:
*   Verifying that telemetry data was correctly uploaded by the edge agent.
*   Inspecting chart output before deploying the Lambda.
*   Generating charts for arbitrary historical dates and device/metric combinations.

### Running the CLI

```bash
cd lambda/
mvn compile exec:java -Dexec.args="<options>"
```

Credentials and region are resolved automatically by the AWS SDK (env vars → `~/.aws/credentials` → `~/.aws/config`).

### Options

| Flag | Default | Description |
|:---|:---|:---|
| `-d`, `--device` | **required** | Device ID(s). Comma-separated or repeated (`-d 1,2` or `-d 1 -d 2`) |
| `-m`, `--metric` | **required** | Metric ID(s). Comma-separated or repeated |
| `--date` | yesterday | Single target date in `YYYY-MM-DD` format |
| `--dates` | — | Multiple dates, comma-separated |
| `--tz` | `America/New_York` | Timezone for local-day boundary calculation |
| `-o`, `--output` | `../../frontend/public/output` | Output directory (relative to `backend/lambda/` where `mvn` runs) |
| `--table` | `IoT_Telemetry` | DynamoDB table name (or set `TELEMETRY_TABLE_NAME` env var) |
| `--chart-type` | auto by metric | Force `XYLineChart` or `XYAreaChart` for all charts |
| `-h`, `--help` | — | Print help and exit |

### Known Metric IDs

| ID | Name | Default Chart Type |
|:---|:---|:---|
| 1 | Temperature | `XYLineChart` |
| 2 | Humidity | `XYLineChart` |
| 3 | Ambient Light | `XYAreaChart` |
| 4 | Motion Count | `XYAreaChart` |
| 5 | Water Level | `XYLineChart` |

### Examples

```bash
# Yesterday's temperature chart for device 1 (default output: frontend/public/output/)
mvn compile exec:java -Dexec.args="-d 1 -m 1"

# All five metrics for two devices on a specific date
mvn compile exec:java -Dexec.args="-d 1,2 -m 1,2,3,4,5 --date 2026-07-25"

# Multiple dates with a custom output directory
mvn compile exec:java -Dexec.args="-d 1 -m 1,3 --dates 2026-07-24,2026-07-25 -o ~/charts"

# Different timezone
mvn compile exec:java -Dexec.args="-d 1 -m 1 --tz America/Los_Angeles"
```

### Output Layout

By default, charts are written into the frontend's public asset directory so the static website can serve them directly:

```
frontend/public/output/
  file-list.json                          ← index consumed by the frontend
  {deviceId}/{metricId}/{year}/{month}/
    {metricId}-YYYYMMDD.png
```

Example for Device 1, Metric 1, date 2026-07-25:
```
frontend/public/output/1/1/2026/07/1-20260725.png
frontend/public/output/file-list.json
```

The key format is identical to the S3 keys written by the Lambda, so the same `file-list.json` structure and frontend code work with both sources.

---

## AWS Access Requirements

### Lambda Execution Role (Production)

The chart generator Lambda reads from two DynamoDB tables and reads/writes to one S3 bucket. The required IAM permissions are summarised below.

| Service | Action | Resource | Purpose |
|:---|:---|:---|:---|
| DynamoDB | `dynamodb:Query` | `IoT_Telemetry` table | Fetch time-bounded telemetry readings |
| DynamoDB | `dynamodb:GetItem` | `IoT_Metadata` table | Look up device/metric name, unit, chart type |
| S3 | `s3:GetObject` | `chart-bucket/*` | Download existing `file-list.json` before merging |
| S3 | `s3:PutObject` | `chart-bucket/*` | Upload chart PNG images and updated `file-list.json` |
| CloudWatch Logs | `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents` | Lambda log group | Standard Lambda execution logging |

These permissions are codified in the Terraform files under `infrastructure/`:

*   [`iam_lambda.tf`](../infrastructure/iam_lambda.tf): Creates the `{project}-lambda-exec-role` IAM role with least-privilege inline policies for DynamoDB and S3, plus the `AWSLambdaBasicExecutionRole` managed policy attachment for CloudWatch Logs.
*   [`s3.tf`](../infrastructure/s3.tf): Provisions the chart output S3 bucket with public-access block, versioning, and CORS.

After running `terraform apply`, retrieve the role ARN from the Terraform outputs:
```bash
cd infrastructure/
terraform output lambda_exec_role_arn
terraform output chart_bucket_name
```
Assign `lambda_exec_role_arn` as the **Execution role** on your Lambda function, and set the `chart_bucket_name` value as the `S3_BUCKET_NAME` environment variable.

### Local Integration Test (`LocalTest.java`)

[`LocalTest.java`](lambda/src/test/java/com/nobudev7/LocalTest.java) invokes the handler directly on your machine using real AWS credentials. It requires the same permissions as the Lambda execution role above, scoped to the same resources.

The test automatically skips (no failure) if no credentials are found:
```java
if (System.getenv("AWS_ACCESS_KEY_ID") == null && System.getProperty("aws.accessKeyId") == null) {
    System.out.println("Skipping local AWS integration test - no credentials found.");
    return;
}
```

**Recommended approach — use a named profile:**

1.  Create a developer IAM user or role in your AWS account with the permissions listed in the table above.
2.  Configure a named profile in `~/.aws/credentials`:
    ```ini
    [pilambdachart-dev]
    aws_access_key_id     = AKIA...
    aws_secret_access_key = ...
    region                = us-east-1
    ```
3.  Run the local tests with that profile active:
    ```bash
    cd lambda/
    AWS_PROFILE=pilambdachart-dev mvn test -Dtest=LocalTest
    ```

**Environment variable alternative:**
```bash
AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_REGION=us-east-1 mvn test -Dtest=LocalTest
```

> **Note:** `LocalTest.java` is skipped automatically during a standard `mvn test` (CI build) when no credentials are present, so it does not block standard unit tests in [`ChartGeneratorTest.java`](lambda/src/test/java/com/nobudev7/ChartGeneratorTest.java).
