# PiLambdaChart Edge Client

This folder contains the Python telemetry agent running on Raspberry Pi edge devices. It collects environmental data from attached hardware sensors asynchronously and uploads it to AWS DynamoDB.

## Folder Structure
*   `config.yaml.example`: Configuration template for device IDs, AWS regions, and active sensor plugins. Copy to `config.yaml` to configure locally.
*   `src/agent.py`: Main event loop daemon managing asynchronous sensor reading tasks and DynamoDB uploading queues.
*   `src/put_datapoint.py`: Standalone CLI to upload a single data point to DynamoDB without running the full agent.
*   `src/sensors/`: Decoupled sensor driver plugins:
    *   `base_sensor.py`: Abstract Base Class (`BaseSensor`) for all sensor plugins.
    *   `dht_sensor.py`: Driver for DHT11 and DHT22 Temperature/Humidity sensors.
    *   `bh1750_sensor.py`: Driver for BH1750 ambient light lux sensors.
    *   `pir_motion.py`: Driver for PIR Motion sensors, counting motion events over interval windows.
    *   `ultrasonic.py`: Driver for HC-SR04 ultrasonic sensors measuring water/fluid levels.
*   `src/uploaders/`: Upload target drivers:
    *   `dynamodb.py`: Decoupled AWS DynamoDB uploader formatting keys (`{DeviceID}#{MetricID}#{UTCYear}`) and executing async batch uploads.
*   `requirements.txt`: Python dependencies for Raspberry Pi 3 / 4 (`RPi.GPIO`).
*   `requirements-lgpio.txt`: Python dependencies for Raspberry Pi 5 (`lgpio`).
*   `pilambdachart-agent.service`: `systemd` service unit file for automated background execution on boot.
*   `sensor_check/`: Standalone Python scripts to test sensor hardware functionality and pin connections.

---

## System Architecture

The PiLambdaChart Edge Client is built on a modular, decoupled, and event-driven architecture designed to ensure stable sensor reading and resilient database uploads even under intermittent network connectivity:

1. **Decoupled Sensor Interface & Registry**:
   * All hardware sensors inherit from the `BaseSensor` abstract class in `base_sensor.py`, separating physical driver implementation from agent operational logic.
   * `sensors/__init__.py` exposes a centralized registry mapping sensor configuration strings in `config.yaml` to their respective Python driver classes.

2. **Asynchronous Sensor Driver Plugins**:
   * **DHT Sensor** (`dht_sensor.py`): Gathers temperature and humidity. Uses `asyncio.to_thread` to execute blocking sensor library calls without stalling the main event loop.
   * **BH1750 Sensor** (`bh1750_sensor.py`): Collects ambient light lux readings via I2C bus.
   * **PIR Motion Sensor** (`pir_motion.py`): Hooks into hardware GPIO interrupts to accumulate motion trigger counts over interval windows.
   * **Ultrasonic Sensor** (`ultrasonic.py`): Measures fluid/water levels.
   * *Hardware Simulation Fallback*: All drivers feature an automatic fallback to simulation/mock telemetry data if physical GPIO libraries fail to load (e.g., when running on standard laptops/desktops).

3. **Database Uploader Integration**:
   * **DynamoDB Uploader** (`dynamodb.py`): Formats partition keys (`{DeviceID}#{MetricID}#{UTCYear}`) and sort keys (`ISO-8601 UTC timestamp`) for time-series querying. Supports local dry-run logging when AWS uploads are disabled.

4. **Asynchronous Daemon Agent**:
   * **Core Orchestration** (`agent.py`): Spawns independent `asyncio` tasks for each configured sensor based on their respective polling intervals. Telemetry points are placed into a thread-safe `asyncio.Queue`.
   * A background worker task consumes the queue and handles uploads. If internet connectivity drops, failed uploads are buffered in a memory-capped retry queue and automatically flushed once connectivity is restored.

---

## Virtual Environment (`venv`) Recommendation

Running Python scripts inside a virtual environment (`venv`) is **mandatory** on modern Raspberry Pi OS releases (Debian Bookworm / PEP 668). This isolates dependencies and prevents modifications to the system-wide Python environment.

---

## Configuration Management & Fleet Deployment

To run this project across multiple Raspberry Pi edge devices:
1. **Security**: Never commit configurations containing sensitive credentials or account IDs. `edge/config.yaml` is gitignored by default.
2. **Template Copy**: Copy `config.yaml.example` to `config.yaml` on each target Pi and customize attached sensors.
3. **Environment Overrides**: Override settings dynamically at runtime using environment variables:
   * `DEVICE_ID`: Overrides the device ID integer (e.g. `DEVICE_ID=2`).
   * `AWS_REGION`: Overrides the AWS Region string (e.g. `AWS_REGION=us-east-1`).
   * `AWS_TELEMETRY_TABLE`: Overrides the DynamoDB table name (e.g. `AWS_TELEMETRY_TABLE=IoT_Telemetry`).
   * `AWS_ENABLED`: Toggles live AWS uploading (`true` / `false`).

---

## Local Development & Simulation

The agent features automatic hardware fallback. If run on a non-Raspberry Pi machine, or if `simulation: true` is configured in `config.yaml`, it generates simulated measurements and logs them to stdout instead of failing.

### Running with Mock Telemetry

1. **Create and activate virtual environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
   *(Windows: `.venv\Scripts\activate`)*

2. **Install requirements**:
   ```bash
   pip install -r requirements.txt
   ```
   *(On non-Raspberry Pi desktop machines, install `Mock.GPIO` if `RPi.GPIO` compilation is skipped: `pip install Mock.GPIO`)*

3. **Initialize local configuration**:
   ```bash
   cp config.yaml.example config.yaml
   ```

4. **Start agent in dry-run mode**:
   ```bash
   python src/agent.py --dry-run
   ```

---

## Single Data Point Upload (`put_datapoint.py`)

A standalone CLI for uploading a single data point to DynamoDB without running the full agent. Useful for manual data injection, testing, or scripted one-shot uploads.

### Usage

```bash
python src/put_datapoint.py --timestamp <TIMESTAMP> --value <VALUE> --device-id <ID> --metric-id <ID> [options]
```

### Required Arguments

| Argument | Description |
| :--- | :--- |
| `--timestamp` | ISO-8601 timestamp (e.g. `2026-08-04T20:30:00Z`, `2026-08-04T16:30:00-04:00`) or `now` |
| `--value` | Numeric value of the data point |
| `--metric-id` | Metric ID (integer) |
| `--device-id` | Device ID (integer). Falls back to `DEVICE_ID` env or `config.yaml` |

### Optional Arguments

| Argument | Env Variable | Config Key | Default |
| :--- | :--- | :--- | :--- |
| `--region` | `AWS_REGION` | `aws.region` | `us-east-1` |
| `--profile` | `AWS_PROFILE` | `aws.profile` | *(none)* |
| `--table` | `AWS_TELEMETRY_TABLE` | `aws.telemetry_table` | `IoT_Telemetry` |
| `--config` | — | — | `edge/config.yaml` (if exists) |
| `--dry-run` | — | `aws.enabled: false` | off |

### Examples

```bash
# Upload a temperature reading with explicit device ID
python src/put_datapoint.py --timestamp "2026-08-04T20:30:00Z" --value 23.5 --device-id 2 --metric-id 1

# Use current UTC time
python src/put_datapoint.py --timestamp now --value 42.0 --device-id 2 --metric-id 3

# Device ID from environment variable, dry-run mode
DEVICE_ID=2 python src/put_datapoint.py --timestamp now --value 18.7 --metric-id 1 --dry-run

# Use a specific AWS profile
python src/put_datapoint.py --timestamp now --value 65.2 --device-id 2 --metric-id 2 --profile pilambdachart
```

### Output

- **Success:** `OK 2#1#2026 2026-08-04T20:30:00Z 23.5` (exit code 0)
- **Dry run:** `[DRY-RUN] OK 2#1#2026 2026-08-04T20:30:00Z 23.5` (exit code 0)
- **Failure:** Error message to stderr (exit code 1)

---

## Production Deployment on Raspberry Pi

1. Clone repository (or use `sparse-checkout` for the `edge` folder only):
   ```bash
   git clone --filter=blob:none --no-checkout https://github.com/nobudev7/PiLambdaChart.git
   cd PiLambdaChart
   git sparse-checkout init --cone
   git sparse-checkout set edge
   git checkout main
   cd edge
   ```

2. **Create virtual environment**:
   ```bash
   python3 -m venv pienv
   source pienv/bin/activate
   ```

3. **Install hardware dependencies** matching your Pi model:

   | Raspberry Pi Model | OS | Backend | Command |
   | :--- | :--- | :--- | :--- |
   | **Pi 1, 2, 3, 4, Zero, Zero 2 W** | Debian Bullseye or earlier | `RPi.GPIO` | `pip install -r requirements.txt` |
   | **Pi 5** | Debian Bookworm | `lgpio` | `pip install -r requirements-lgpio.txt` |


4. **Configure production sensors**:
   ```bash
   cp config.yaml.example config.yaml
   ```
   Edit `config.yaml` to set `simulation: false` and list attached sensors.

5. **Configure AWS Credentials**: Set up `~/.aws/credentials` or environment variables.

---

## Running as a `systemd` Service

Running as a `systemd` service ensures automatic startup on boot, auto-restart on failure, and central logging via `journald`.

### Step 1 — Install Service Unit

Edit [`pilambdachart-agent.service`](pilambdachart-agent.service) with your user and paths, then install:

```bash
sudo cp pilambdachart-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
```

### Step 2 — Enable and Start

```bash
sudo systemctl enable pilambdachart-agent
sudo systemctl start pilambdachart-agent
sudo systemctl status pilambdachart-agent
```

### Viewing Logs

```bash
# Live tail
journalctl -u pilambdachart-agent -f

# Last 100 lines
journalctl -u pilambdachart-agent -n 100
```

---

## AWS IAM Credentials Setup for Edge Client

The Raspberry Pi edge client uploads telemetry data to AWS DynamoDB (`IoT_Telemetry` table) using a dedicated least-privilege IAM user (`pilambdachart-edge-client-user`) provisioned by Terraform in [`infrastructure/iam_client.tf`](../infrastructure/iam_client.tf). For infrastructure setup instructions and output descriptions, see [infrastructure/README.md](../infrastructure/README.md).

### 1. Retrieve Access Keys from Terraform Outputs

On your local machine (where Terraform is deployed), run the following commands in the `infrastructure/` directory to display the credentials:

```bash
cd infrastructure/

# 1. Print the Access Key ID
terraform output client_access_key_id

# 2. Print the Secret Access Key (unconcealed)
terraform output -raw client_secret_access_key
```

### 2. Configure Credentials on the Raspberry Pi

Log into your Raspberry Pi terminal and set up the AWS credentials file at `~/.aws/credentials`:

```bash
mkdir -p ~/.aws
nano ~/.aws/credentials
```

Paste the credentials retrieved from Terraform (using default or a named profile):

```ini
# Default profile (single app on Pi)
[default]
aws_access_key_id     = AKIA... (your client_access_key_id from terraform output)
aws_secret_access_key = ...     (your client_secret_access_key from terraform output)

# Named profile (if multiple AWS apps run on the same Pi)
[pilambdachart]
aws_access_key_id     = AKIA...
aws_secret_access_key = ...
```

Configure your target AWS region in `~/.aws/config`:

```bash
nano ~/.aws/config
```

```ini
[default]
region = us-east-1

[profile pilambdachart]
region = us-east-1
```

Set secure file permissions on the credential files:

```bash
chmod 600 ~/.aws/credentials ~/.aws/config
```

#### Using Named AWS Profiles
If your Raspberry Pi already runs another AWS application using `[default]`, configure PiLambdaChart to use the `[pilambdachart]` profile:

1. **Via `config.yaml`**:
   ```yaml
   aws:
     profile: "pilambdachart"
     region: "us-east-1"
   ```
2. **Via Environment Variable**:
   ```bash
   AWS_PROFILE=pilambdachart python src/agent.py
   ```

> **Note:** With `~/.aws/credentials` configured, both standard execution (`python src/agent.py`) and background `systemd` execution will automatically resolve your AWS credentials.

