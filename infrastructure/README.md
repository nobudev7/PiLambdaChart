# PiLambdaChart Infrastructure as Code (IaC)

This directory contains the Terraform configuration files to provision all required AWS resources.

## Resources Provisioned
*   **DynamoDB Telemetry Table**: Bounded by year partitions (`IoT_Telemetry`).
*   **S3 Website Bucket**: Hosts the static web presentation assets.
*   **S3 Output Bucket**: Hosts the compiled telemetry charts.
*   **CloudFront CDN**: Delivers web assets and charts globally.
*   **AWS Lambda**: Runs the Java-based JFreeChart compiler on trigger conditions.
*   **IAM Security Roles**: Grants scoped AWS credentials.
