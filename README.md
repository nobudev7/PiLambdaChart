# PiLambdaChart

PiLambdaChart is an end-to-end serverless IoT telemetry platform that ingests environmental sensor data from Raspberry Pi edge devices into AWS DynamoDB, renders chart dashboards using a Java Lambda function, and serves interactive web dashboards globally via CloudFront and S3.

*PiLambdaChart Web Dashboard — Interactive multi-device, multi-metric telemetry charts with synchronized crosshairs and dark-slate aesthetics.*<br/>
![PiLambdaChart Telemetry Dashboard](documents/images/telemetry_dashboard.png)


### Key Features
- **Static File Web Hosting (No Web Server Required)**: Served directly via Amazon S3 and Amazon CloudFront CDN without running or managing web servers.
- **100% Serverless AWS Infrastructure**: Utilizes Amazon DynamoDB for telemetry storage, EventBridge schedules, and Java AWS Lambda functions for automated chart generation.
- **Multi-Device & Multi-Sensor Support**: Scalable asynchronous architecture supporting multiple Raspberry Pi devices and arbitrary hardware sensors.
- **Modern Browser Dashboard with Synchronized Crosshairs**: Dark-slate aesthetic with dynamic metadata loading, sub-pixel accurate crosshair tooltips, sticky date headers, and lightbox modals.

---

## System Architecture

PiLambdaChart connects asynchronous edge sensors on Raspberry Pi devices with a serverless AWS backend and a static single-page web application.

![PiLambdaChart System Architecture Diagram](documents/images/PiLambdaChart%20Architecture%20Flow.png)

### Component Overview
1. **Edge Client (`agent.py`)**: Asynchronous Python daemon running on Raspberry Pi edge devices that samples attached hardware sensors, buffers failed uploads in an in-memory retry queue, and uploads telemetry readings to DynamoDB.
2. **Amazon DynamoDB**: Fully managed serverless NoSQL database storing time-series telemetry data (`IoT_Telemetry`) and device/metric metadata registries (`IoT_Metadata`).
3. **Amazon EventBridge**: Automated schedule rule (e.g. `rate(5 minutes)`) that triggers the Lambda function periodically to generate updated charts.
4. **AWS Lambda (`ChartGeneratorHandler`)**: Serverless Java handler that queries telemetry from DynamoDB, calculates dynamic Y-axis bounds, renders JFreeChart PNGs and JSON sidecars, and uploads assets to S3.
5. **Amazon S3**: Static website storage hosting dashboard files (`index.html`, `style.css`, `app.js`), chart PNGs, JSON data sidecars, `file-list.json` indexes, and `metadata.json` exports.
6. **Amazon CloudFront**: Global Content Delivery Network (CDN) providing low-latency edge caching, Origin Access Control (OAC) to keep S3 private, HTTPS encryption, and optional HTTP Basic Authentication.
7. **Web Browser (`app.js`)**: Static single-page client application that fetches catalog indexes and sidecars, initializes `METRIC_META` dynamically, renders chart tile grids, and powers interactive synchronized crosshairs.

---

## Folder Structure

The repository is modularized into four component tiers. Click each module's link for detailed setup and usage documentation:

*   [`backend/`](backend/README.md) — **Java Compute Tier & CLI**: Java Maven project (`ChartGeneratorHandler` & `ChartGeneratorCLI`) querying DynamoDB telemetry and rendering JFreeChart PNGs and JSON sidecars.
*   [`edge/`](edge/README.md) — **Raspberry Pi Edge Client**: Asynchronous Python agent (`agent.py`) running on Raspberry Pi edge devices to gather sensor data (temperature, humidity, light, motion, water level), manage retry buffers, and upload readings to DynamoDB.
*   [`frontend/`](frontend/README.md) — **Web Telemetry Dashboard**: HSL dark-slate static web dashboard (`app.js`, `style.css`, `index.html`) featuring dynamic metadata loading, sticky date dividers, synchronized crosshairs, and lightbox modals.
*   [`infrastructure/`](infrastructure/README.md) — **Terraform Infrastructure as Code**: Declarative AWS IaC provisioning DynamoDB tables, S3 chart bucket, Java Lambda function, EventBridge schedules, CloudFront CDN, and IAM least-privilege security policies.

---

## Requirements

To recreate and deploy this system from scratch, you will need the following hardware, developer tools, and AWS account access:

### 1. Hardware Requirements
*   **Edge Device**: One or more Raspberry Pi single-board computers (e.g. Raspberry Pi 3, 4, 5, or Pi Zero W) running Raspberry Pi OS (Debian Bullseye or Bookworm).
*   **Sensors & Electronics**:
    *   **Temperature & Humidity**: DHT22 or DHT11 GPIO sensor.
    *   **Ambient Light**: BH1750 I2C lux sensor.
    *   **Motion**: PIR Motion sensor.
    *   **Water / Fluid Level**: HC-SR04 ultrasonic distance sensor.
    *   Breadboard, resistors, and GPIO jumper wires.

### 2. Developer Tooling & Runtimes
*   **Python 3.9+**: For the edge client daemon (`edge/agent.py`). Requires `venv` and GPIO library (`RPi.GPIO` for Pi 3/4 or `lgpio` for Pi 5).
*   **Java JDK 21+ & Maven 3.8+**: For building the backend chart generator fat/shaded JAR (`backend/lambda/`) and running the developer CLI tool (`ChartGeneratorCLI`).
*   **Terraform 1.5+**: For declarative AWS infrastructure provisioning (`infrastructure/`).
*   **AWS CLI v2**: Configured locally (`aws configure`) with credentials to deploy Terraform resources and sync frontend static files.
*   **Local HTTP Server**: Python's built-in `http.server` or VS Code Live Server for local frontend testing (`frontend/public/`).

### 3. AWS Cloud Account & Permissions
*   An active **AWS Account** with permissions to provision:
    *   **Amazon DynamoDB**: `IoT_Telemetry` (time-series) and `IoT_Metadata` (registry) tables.
    *   **AWS Lambda**: Java runtime execution.
    *   **Amazon EventBridge**: Scheduled cron rules (`rate(5 minutes)`).
    *   **Amazon S3**: Private chart output and static website bucket.
    *   **Amazon CloudFront**: CDN distribution with Origin Access Control (OAC) and HTTP Basic Auth.
    *   **AWS IAM**: Roles and policies for Lambda execution and edge client uploading.

---

## Step-by-Step Setup Guide

Follow these steps to recreate and deploy the complete PiLambdaChart platform from scratch. Detailed configuration guides for each module are linked in their respective steps.

### Step 1: Set Up Raspberry Pi & Test Sensors Locally
1. Wire physical sensors (DHT22, BH1750, PIR motion, HC-SR04) to Raspberry Pi GPIO/I2C pins.
2. Run standalone test scripts under [`edge/sensor_check/`](edge/sensor_check/) to verify sensor hardware functionality locally.
   - *Details: [`edge/README.md`](edge/README.md)*

### Step 2: Provision Base AWS Storage & Database (Terraform)
1. Customize device and metric seed definitions in [`infrastructure/seeding.tf`](infrastructure/seeding.tf) (names, units, icons, `MinYRange`).
2. Run `terraform init` and `terraform apply` in `infrastructure/` to provision DynamoDB tables (`IoT_Telemetry`, `IoT_Metadata`), S3 chart bucket, and Edge IAM user.
   - *Details: [`infrastructure/README.md`](infrastructure/README.md)*

### Step 3: Start Edge Ingestion & Verify DynamoDB Data
1. Retrieve edge user access keys (`terraform output client_access_key_id` & `terraform output -raw client_secret_access_key`) and configure `~/.aws/credentials` on the Pi.
2. Start the Python edge daemon (`python src/agent.py` or `systemd` service [`pilambdachart-agent.service`](edge/pilambdachart-agent.service)).
3. Verify incoming data points in the `IoT_Telemetry` table on the AWS DynamoDB Console.

### Step 4: Build Backend Java Code
1. Compile and package the Java backend:
   ```bash
   cd backend/lambda && mvn clean package
   ```
2. Generates `target/chart-generator-lambda-1.0-SNAPSHOT.jar`.
   - *Details: [`backend/README.md`](backend/README.md)*

### Step 5: Render Initial Charts via Developer CLI
1. Run [`ChartGeneratorCLI`](backend/lambda/src/main/java/com/nobudev7/ChartGeneratorCLI.java) to fetch DynamoDB telemetry and render sample chart assets into [`frontend/public/output/`](frontend/public/output/):
   ```bash
   cd backend/lambda
   mvn compile exec:java -Dexec.args="-d 1 -m 1,2,3,4,5 --date today"
   ```

### Step 6: Test Web Dashboard Locally
1. Launch local Python HTTP server:
   ```bash
   cd frontend/public && python3 -m http.server 8080
   ```
2. Open `http://localhost:8080` in your browser to verify dashboard layout, sticky date headers, and crosshairs.
   - *Details: [`frontend/README.md`](frontend/README.md)*

### Step 7: Deploy Static Site & CloudFront CDN
1. Enable CloudFront in `infrastructure/terraform.tfvars` (`enable_cloudfront = true`) and run `terraform apply`.
2. Sync frontend static assets and initial chart output to S3 using [`frontend/deploy.sh`](frontend/deploy.sh):
   ```bash
   cd frontend
   ./deploy.sh --bucket <bucket-name> --cloudfront <dist-id> --include-output
   ```
3. Open your assigned `*.cloudfront.net` or custom domain URL to verify CloudFront CDN hosting.

### Step 8: Deploy Automated AWS Lambda Chart Generator
1. Enable Lambda provisioning in `infrastructure/terraform.tfvars` (`enable_lambda = true`).
2. Run `terraform apply` in `infrastructure/` to deploy the Java Lambda function and EventBridge 5-minute schedule trigger.

---

## Real-World Example & Hardware Setup

In a production environment, PiLambdaChart runs **Raspberry Pi** devices connected to hardware sensors:

- **Temperature & Humidity**: DHT22 / DHT11 GPIO sensor
- **Ambient Light**: BH1750 I2C lux sensor
- **Motion Events**: PIR motion sensor (GPIO interrupt counting)
- **Water / Fluid Level**: HC-SR04 ultrasonic distance sensor

*Raspberry Pi edge device connected to 3 sensors - DHT22, BH1750, and PIR motion sensor.*<br/>
![Raspberry Pi & Physical Sensors Setup](documents/images/raspi_with_3_sensors.jpg)

*HC-SR04 ultrasonic distance sensor for samp water level.*<br/>
![Raspberry Pi & Physical Sensors Setup](documents/images/raspi_with_ultrasonic.jpg)

