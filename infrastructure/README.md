# PiLambdaChart — Infrastructure as Code

This directory contains all Terraform configuration files to provision the AWS resources for PiLambdaChart. All cloud infrastructure — storage, compute, hosting, and CDN — is defined here.

---

## Phase 1: DynamoDB Tables (current)

### `IoT_Telemetry` Table
Stores raw numeric telemetry data uploaded by edge devices.

| Key | Attribute Name | Type | Format / Example |
| :--- | :--- | :--- | :--- |
| Partition Key (PK) | `Device_Metric_UTCYear` | String | `{DeviceID}#{MetricID}#{UTCYear}` → `1#1#2026` |
| Sort Key (SK) | `Timestamp` | String | UTC ISO-8601 → `2026-07-12T14:30:00Z` |
| Attribute | `Value` | Number | `12.3` |
| Attribute | `DeviceID` | Number | `1` |
| Attribute | `MetricID` | Number | `1` |

**Partition design**: One partition per device × metric × calendar year. At 1-minute upload frequency, a single partition grows ~50 MB/year — well below DynamoDB's 10 GB limit.

### `IoT_Metadata` Table
Stores human-readable metadata for devices and metrics. Written once at registration; read by the Lambda and frontend at chart generation time.

| Key | Attribute Name | Type | Example Values |
| :--- | :--- | :--- | :--- |
| Partition Key (PK) | `EntityType` | String | `"DEVICE"` or `"METRIC"` |
| Sort Key (SK) | `ID` | Number | `1`, `2`, `3`… |

---

## Metadata Registry Config File

`metrics-config.json.template` is a file-based alternative to the DynamoDB Metadata table. Either approach can be used by the Lambda and frontend:
- **File-based** (`metrics-config.json`): simpler, deployed alongside the Lambda JAR and frontend JS.
- **DynamoDB-based** (`IoT_Metadata`): more dynamic, allows adding new devices/metrics without redeployment.

To use the file-based approach:
```bash
cp metrics-config.json.template metrics-config.json
# Edit metrics-config.json with your actual device and metric names
```

---

## Deploying

### Prerequisites
- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.5
- AWS credentials configured (`aws configure` or environment variables)

### Steps
```bash
cd infrastructure/

# 1. Initialise Terraform (downloads the AWS provider)
terraform init

# 2. Preview the resources that will be created
terraform plan

# 3. Apply — creates both DynamoDB tables
terraform apply
```

### Variables
Override any default in a `terraform.tfvars` file:
```hcl
aws_region           = "us-east-1"
project_name         = "pilambdachart"
telemetry_table_name = "IoT_Telemetry"
metadata_table_name  = "IoT_Metadata"
enable_point_in_time_recovery = false
```

### Outputs
After `terraform apply`, the following values are printed and can be referenced in IAM policies for later phases:

| Output | Description |
| :--- | :--- |
| `telemetry_table_name` | Name of the telemetry table |
| `telemetry_table_arn` | ARN — used to scope Lambda and edge client IAM policies |
| `metadata_table_name` | Name of the metadata table |
| `metadata_table_arn` | ARN — used to scope Lambda IAM read policy |


### Seeding Metadata

The database metadata registry (`IoT_Metadata` table) is automatically populated with default device identities and metric definitions (mapping metric IDs 1 to 5 to temperature, humidity, light, motion, and water level) during the Terraform provisioning process. This is managed by:
*   [seeding.tf](file:///Users/nobu/Projects/PiLambdaChart/infrastructure/seeding.tf): Uses `aws_dynamodb_table_item` resources to insert seed records directly upon running `terraform apply`.

#### Alternative: Manual Bulk Import
If you want to manually seed or edit metadata using JSON configurations rather than Terraform state, you can copy the template:
```bash
cp metrics-config.json.template metrics-config.json
# Edit metrics-config.json with custom values
```
And load them into DynamoDB using the AWS CLI:
```bash
aws dynamodb batch-write-item --request-items file://metrics-config.json
```

