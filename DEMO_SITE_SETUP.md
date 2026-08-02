# Demo Site Setup Guide

This guide describes how to deploy a secondary, public-facing **Demo Website** for PiLambdaChart. 

To protect household privacy and physical security, the demo website serves chart data that is **always 7 days behind** real-time (e.g., displaying charts up to July 10th when today is July 17th). This prevents revealing real-time physical presence or occupancy patterns (such as prolonged motion inactivity).

> **Live Demo Example**: [https://chartdemo.nobudev7.com/](https://chartdemo.nobudev7.com/)

---

## Architectural Principles

The demo environment is deployed out-of-band to ensure complete isolation from production:

*   **Real-Time Data Source**: Reads directly from the production DynamoDB tables (`IoT_Telemetry` and `IoT_Metadata`) via read-only queries.
*   **Isolated Storage**: Uses a dedicated S3 bucket (`pilambdachart-demo-charts`) so public static assets and demo charts are physically separated from production storage.
*   **Isolated Compute**: Uses a separate AWS Lambda function (`pilambdachart-chart-generator-demo`) to prevent altering production Lambda configurations.
*   **Zero Terraform Impact**: Created manually/out-of-band so that `infrastructure/terraform.tfstate` and production IAM policies remain 100% untouched.

---

## Step-by-Step Setup Guide

### 1. Create the Demo S3 Bucket

Create a dedicated S3 bucket to host the demo site assets and 7-day lagged chart output:

```bash
aws s3 mb s3://<your-demo-bucket-name> --region <region>
```

---

### 2. Create the Demo IAM Role & Policy

Create an IAM execution role for the demo Lambda function (e.g., `pilambdachart-demo-lambda-exec-role`). Attach an inline policy granting:

1. **DynamoDB Read Access**: `dynamodb:Query`, `dynamodb:GetItem`, and `dynamodb:Scan` on `IoT_Metadata` and `IoT_Telemetry` tables.
2. **S3 Write Access**: `s3:PutObject`, `s3:GetObject`, `s3:ListBucket` on `s3://<your-demo-bucket-name>/*`.

> **Reference**: For the exact JSON policy structure, see the [Lambda Execution Role (Production)](backend/README.md#lambda-execution-role-production) section in [`backend/README.md`](backend/README.md).

Sample
```json
{
	"Version": "2012-10-17",
	"Statement": [
		{
			"Action": "dynamodb:Query",
			"Effect": "Allow",
			"Resource": "arn:aws:dynamodb:<region>:<account_id>:table/IoT_Telemetry",
			"Sid": "ReadTelemetry"
		},
		{
			"Action": [
				"dynamodb:Scan",
				"dynamodb:GetItem"
			],
			"Effect": "Allow",
			"Resource": "arn:aws:dynamodb:<region>:<account_id>:table/IoT_Metadata",
			"Sid": "ReadMetadata"
		},
		{
			"Action": [
				"s3:PutObject",
				"s3:GetObject"
			],
			"Effect": "Allow",
			"Resource": "arn:aws:s3:::pilambdachart-demo-charts/*",
			"Sid": "ReadWriteChartBucket"
		}
	]
}
```


---

### 3. Create & Deploy the Demo Lambda Function

Compile the backend Java project locally:

```bash
cd backend/lambda
mvn clean package
```

Deploy the compiled JAR (`target/chart-generator-lambda-1.0-SNAPSHOT.jar`) directly to a new Lambda function in your target region:

```bash
aws lambda create-function \
  --region <region> \
  --function-name pilambdachart-chart-generator-demo \
  --runtime java21 \
  --role arn:aws:iam::<your-aws-account-id>:role/<your-demo-lambda-execution-role> \
  --handler com.nobudev7.ChartGeneratorHandler::handleRequest \
  --zip-file fileb://backend/lambda/target/chart-generator-lambda-1.0-SNAPSHOT.jar \
  --timeout 30 \
  --memory-size 512 \
  --environment "Variables={S3_BUCKET_NAME=<your-demo-bucket-name>,TELEMETRY_TABLE_NAME=IoT_Telemetry,METADATA_TABLE_NAME=IoT_Metadata}"
```

#### Test Function Execution Manually
Test the function using the following event JSON payload to generate charts for 7 days ago:

```json
{
  "device": 1,
  "metrics": [1, 2, 3, 4, 5],
  "date": "7 days ago",
  "timezone": "America/New_York"
}
```

#### Future Code Updates
Whenever you compile an updated Java JAR, update the demo Lambda code with:

```bash
aws lambda update-function-code \
  --region <region> \
  --function-name pilambdachart-chart-generator-demo \
  --zip-file fileb://backend/lambda/target/chart-generator-lambda-1.0-SNAPSHOT.jar
```

---

### 4. Upload Frontend Web Assets & Optional Demo Banner

Upload static web files (`index.html`, `style.css`, `app.js`) to the demo S3 bucket using [`frontend/deploy.sh`](frontend/deploy.sh). Do **not** pass `--include-output` so local output files are excluded:

```bash
cd frontend
./deploy.sh --bucket <your-demo-bucket-name> --region <region>
```

#### Add Optional Demo Banner (Out-of-Band)
To display a notice banner on the demo site stating that data is 7 days delayed (without affecting production or committing files to git), upload an untracked `demo-config.json` directly to the demo S3 bucket:

```bash
aws s3 cp - s3://<your-demo-bucket-name>/output/demo-config.json --content-type application/json << 'EOF'
{
  "enabled": true,
  "message": "This is a demo site showing 7-day delayed data — the actual system supports near-real-time updates."
}
EOF
```

*Note: `demo-config.json` is listed in `.gitignore` so it will never be tracked or committed to Git.*

---

### 5. Set Up CloudFront CDN (Public Access)

1. Create a CloudFront Distribution pointing to `<your-demo-bucket-name>.s3.<region>.amazonaws.com`.
2. Configure **Origin Access Control (OAC)** to grant CloudFront read access while keeping the S3 bucket private.
3. Set **Default Root Object** to `index.html`.
4. Leave HTTP Basic Authentication **disabled** so the demo site is publicly accessible.
5. Verify access using the generated `*.cloudfront.net` domain name.
6. *(Optional)* Attach a custom domain name (e.g. `chartdemo.nobudev7.com`) with an ACM SSL certificate.

---

### 6. Set Up EventBridge Automated Schedule

Create a daily EventBridge schedule rule to trigger chart generation once per day (slightly after midnight in your local timezone):

#### Target JSON Payload:
```json
{
  "device": 1,
  "metrics": [1, 2, 3, 4, 5],
  "date": "7 days ago",
  "timezone": "America/New_York"
}
```

* **Schedule Expression**: e.g., `cron(5 0 * * ? *)` (runs daily at 12:05 AM UTC).
* **Target Type**: AWS Lambda Function (`pilambdachart-chart-generator-demo`).
* **Target Input**: Select **Constant (JSON text)** and paste the JSON payload above.
