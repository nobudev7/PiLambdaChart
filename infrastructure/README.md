# PiLambdaChart — Infrastructure as Code

This directory contains all Terraform configuration files to provision AWS resources for PiLambdaChart. Storage, database, compute, static hosting, CDN, and IAM roles are defined here.

---

## DynamoDB Tables

### `IoT_Telemetry` Table
Stores raw numeric telemetry data uploaded by edge devices.

| Key | Attribute Name | Type | Format / Example |
| :--- | :--- | :--- | :--- |
| Partition Key (PK) | `Device_Metric_UTCYear` | String | `{DeviceID}#{MetricID}#{UTCYear}` → `1#1#2026` |
| Sort Key (SK) | `Timestamp` | String | UTC ISO-8601 → `2026-07-12T14:30:00Z` |
| Attribute | `Value` | Number | `12.3` |
| Attribute | `DeviceID` | Number | `1` |
| Attribute | `MetricID` | Number | `1` |

**Partition design**: One partition per device × metric × calendar year. At 1-minute upload frequency, a single partition grows ~50 MB/year — well below DynamoDB's 10 GB partition limit.

### `IoT_Metadata` Table
Stores device and metric metadata. Read dynamically by the Lambda generator, CLI tool, and frontend dashboard.

| Key | Attribute Name | Type | Description | Example Values |
| :--- | :--- | :--- | :--- | :--- |
| Partition Key (PK) | `EntityType` | String | Entity type | `"DEVICE"` or `"METRIC"` |
| Sort Key (SK) | `ID` | Number | Unique identifier | `1`, `2`, `3`… |
| Attribute | `Name` | String | Display name | `"Temperature"`, `"Water Level Pi"` |
| Attribute | `Unit` | String | Telemetry measurement unit | `"°C"`, `"%"`, `"Lux"`, `"cm"` |
| Attribute | `ChartType` | String | Rendering style | `"XYLineChart"`, `"BarChart"` |
| Attribute | `MinYRange` | Number (Optional) | Minimum Y-axis range span | `7.0` |
| Attribute | `Icon` | String (Optional) | Display emoji icon | `"🌡️"`, `"💧"`, `"☀️"`, `"🔍"`, `"📏"` |

---

## Metadata Seeding & State Control

Seed data is defined in [`seeding.tf`](seeding.tf) and populates default device and metric records during initial setup.

### Controlling Seed State via `enable_metadata_seeding`

You can control whether Terraform manages seed items using the `enable_metadata_seeding` toggle in `terraform.tfvars`:

```hcl
# Set to false if metadata is managed dynamically out-of-band in DynamoDB
enable_metadata_seeding = false
```

- **`enable_metadata_seeding = true` (Default)**: Terraform provisions default seed items for initial environment creation.
- **`enable_metadata_seeding = false`**: Disables Terraform management of `IoT_Metadata` seed items (`count = 0`). This prevents `terraform plan` / `terraform apply` from overwriting or deleting custom attributes (such as `MinYRange` or `Icon`) modified directly in DynamoDB.

#### Alternative: Manual Bulk Seeding
To manually seed or edit metadata using JSON configurations rather than Terraform:
```bash
cp metrics-config.json.template metrics-config.json
# Edit metrics-config.json with custom values
aws dynamodb batch-write-item --request-items file://metrics-config.json
```

---

## AWS Lambda & Scheduled Generation

The Java Chart Generator Lambda function and its automated trigger schedule are provisioned in [`lambda.tf`](lambda.tf) and [`iam_lambda.tf`](iam_lambda.tf).

### Key Features:
- **Automatic Deployment & Updates**: Deploys `backend/lambda/target/chart-generator-lambda-1.0-SNAPSHOT.jar`. SHA-256 code hashing triggers code updates in AWS whenever you compile a new JAR.
- **Environment & IAM Binding**: Automatically binds DynamoDB table names and S3 bucket names to Lambda environment variables.
- **Metadata Export Permissions**: IAM role policy ([`iam_lambda.tf`](iam_lambda.tf)) includes `dynamodb:GetItem` and `dynamodb:Scan` permissions to allow exporting `output/metadata.json` to S3.
- **Scheduled Triggers**: Provisions EventBridge schedule targets for device and metric combinations.

### Lambda Configuration Options (`terraform.tfvars`)

```hcl
# 1. Enable AWS Lambda Provisioning
enable_lambda = true

# 2. Automated EventBridge Schedule (default: rate(5 minutes))
lambda_schedule_cron = "rate(5 minutes)"

# 3. Devices & Metrics to render on each schedule trigger
lambda_trigger_devices  = [1, 2]
lambda_trigger_metrics  = [1, 2, 3, 4, 5]
lambda_trigger_timezone = "America/New_York"
```

---

## CloudFront CDN & Access Protection

CloudFront CDN is optionally provisioned in front of the private S3 chart bucket via [`cloudfront.tf`](cloudfront.tf).

### Key Features:
- **Origin Access Control (OAC)**: S3 bucket remains private. Only CloudFront is granted read access via S3 bucket policy.
- **HTTP Basic Authentication**: Edge-deployed CloudFront Function prompts users for basic authentication.
- **Custom Domains**: Supports default `*.cloudfront.net` SSL or custom subdomains with ACM certificates in `us-east-1`.

```hcl
# Enable CloudFront CDN with Basic Auth
enable_cloudfront            = true
enable_cloudfront_basic_auth = true
basic_auth_username          = "admin"
basic_auth_password          = "your-secure-password-here!"
```

---

## Deployment Workflow

### Prerequisites
- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.5
- AWS CLI configured with administrator or appropriate provisioning permissions

### Execution Steps
```bash
cd infrastructure/

# 1. Copy example configuration
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your specific settings

# 2. Initialize Terraform
terraform init

# 3. Plan deployment
terraform plan

# 4. Apply configuration
terraform apply
```

### Outputs

| Output Name | Description |
| :--- | :--- |
| `telemetry_table_name` | Name of the telemetry table (`IoT_Telemetry`) |
| `telemetry_table_arn` | ARN — used to scope Lambda & edge agent IAM policies |
| `metadata_table_name` | Name of the metadata table (`IoT_Metadata`) |
| `metadata_table_arn` | ARN — used to scope Lambda IAM read policies |
| `client_access_key_id` | Access Key ID for the Raspberry Pi edge client IAM user |
| `client_secret_access_key` | Secret Access Key for the Raspberry Pi edge client IAM user |
| `chart_bucket_name` | S3 bucket name storing generated charts and metadata |
| `lambda_exec_role_arn` | Execution role ARN for the Chart Generator Lambda |
| `cloudfront_distribution_id` | CloudFront Distribution ID |
| `cloudfront_dashboard_url` | Full HTTPS URL to access the dashboard |

> **Edge Client Credentials Setup**: To configure the `client_access_key_id` and `client_secret_access_key` on a Raspberry Pi device, see the [AWS IAM Credentials Setup for Edge Client](../edge/README.md#aws-iam-credentials-setup-for-edge-client) guide in `edge/README.md`.
