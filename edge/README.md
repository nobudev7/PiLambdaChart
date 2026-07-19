# PiLambdaChart Edge Client

This folder contains the Python agent running on the Raspberry Pi edge device. It collects telemetry data from multiple connected sensors asynchronously and uploads it to AWS DynamoDB.

## Folder Structure
*   `config.yaml.example`: Template for device and sensor configuration. Copy to `config.yaml` to configure locally.
*   `src/agent.py`: Main event loop daemon managing asynchronous sensor reading tasks and DynamoDB uploading.
*   `src/sensors/`: Directory containing decoupling sensor interfaces:
    *   `base_sensor.py`: Abstract Base Class for all sensor plugins.
    *   `dht_sensor.py`: Driver for DHT11 and DHT22 Temperature/Humidity sensors.
    *   `bh1750_sensor.py`: Driver for BH1750 ambient light lux sensors.
    *   `pir_motion.py`: Driver for PIR Motion sensors, counting motion events in interval.
    *   `ultrasonic.py`: Driver for ultrasonic sensors measuring water/fluid levels.
*   `src/uploaders/`: Directory containing upload interfaces:
    *   `dynamodb.py`: Decoupled AWS DynamoDB uploader.
*   `requirements.txt`: Python package dependencies.
*   `sensor_check/`: Standalone Python scripts to test sensor hardware functionality and verify connections.

## System Architecture

The PiLambdaChart Edge Client is built on a modular, decoupled, and event-driven architecture designed to ensure stable sensor reading and resilient database upload even under intermittent network connectivity:

1. **Decoupled Sensor Interface & Registry**:
   * All hardware sensors inherit from the `BaseSensor` abstract class in `base_sensor.py`, separating driver implementation from operational agent code.
   * `sensors/__init__.py` exposes a centralized registry mapping sensor configuration strings in `config.yaml` to their respective Python driver classes.

2. **Asynchronous Sensor Driver Plugins**:
   * **DHT Sensor** (`dht_sensor.py`): Gathers temperature and humidity. Uses `asyncio.to_thread` to run blocking sensor library calls without pausing the main event loop.
   * **BH1750 Sensor** (`bh1750_sensor.py`): Collects ambient light lux readings.
   * **PIR Motion Sensor** (`pir_motion.py`): Hooks into hardware GPIO interrupts to accumulate counts of motion events over the polling interval.
   * **Ultrasonic Sensor** (`ultrasonic.py`): Measures fluid/water levels.
   * *Hardware Simulation Fallback*: All drivers feature an automatic fallback to simulation/mock telemetry data if underlying physical libraries (like `gpiozero` or `adafruit`) fail to load.

3. **Database Uploader Integration**:
   * **DynamoDB Uploader** (`dynamodb.py`): Forms and executes queries to upload telemetry records asynchronously. It formats keys dynamically based on the Device ID, Metric ID, and UTC timestamp year mapping schema (`{DeviceID}#{MetricID}#{UTCYear}`). Supports a dry-run local mode.

4. **Asynchronous Daemon Agent**:
   * **Core Orchestration** (`agent.py`): Spawns independent asyncio tasks for each configured sensor based on their respective polling intervals. Sensor telemetry points are placed into a thread-safe `asyncio.Queue`.
   * A background worker task consumes the queue and handles uploads. If internet connectivity drops, failed uploads are temporarily stored in a memory-capped retry buffer and successfully flushed once connection is restored.

## Virtual Environment (venv) Recommendation

It is **highly recommended** (and on modern Raspberry Pi OS versions like Debian Bookworm, **mandatory**) to run Python scripts within a virtual environment (`venv`). This prevents modifications to the system-wide Python installation (complying with Python PEP 668), isolates dependencies, and ensures smooth execution.

---

## Configuration Management & Fleet Deployment

To run this project as a clean open-source application and manage configuration across a fleet of multiple Raspberry Pi edge devices:
1. **Never commit physical configurations containing sensitive identifiers or regional keys.** `edge/config.yaml` is added to `.gitignore` to prevent accidental commits.
2. **Template copy**: On each target device, copy the committed template `config.yaml.example` to `config.yaml` and customize it.
3. **Environment Overrides**: You can deploy the exact same `config.yaml` to all devices and customize the operational parameters dynamically at startup using environment variables. The agent supports:
   * `DEVICE_ID`: Overrides the device ID integer (e.g. `DEVICE_ID=2`).
   * `AWS_REGION`: Overrides the AWS Region string (e.g. `AWS_REGION=us-west-2`).
   * `AWS_TELEMETRY_TABLE`: Overrides the DynamoDB table name (e.g. `AWS_TELEMETRY_TABLE=Prod_IoT_Telemetry`).
   * `AWS_ENABLED`: Overrides the upload toggle (e.g. `AWS_ENABLED=true` or `AWS_ENABLED=false`).

---

## Local Development & Simulation

The agent features automatic hardware fallback. If run on a non-Raspberry Pi machine, or if the config has `simulation: true` enabled, it will generate simulated measurements and log them instead of failing.

### Running with Mock Telemetry

1. **Create and activate a virtual environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
   *(Note: On Windows, use `.venv\Scripts\activate`)*

2. **Install requirements**:
   ```bash
   pip install -r requirements.txt
   ```

Note: On non-Raspberry Pi environment, the above command fails to install the RPi.GPIO library, which compiles low-level C code specifically for the Raspberry Pi hardware processor. It cannot be installed on standard laptops or desktops. To test the code, install Mock.GPIO library. 
    ```bash
    pip install Mock.GPIO
    ```

3. **Initialize the local configuration file**:
   ```bash
   cp config.yaml.example config.yaml
   ```

4. **Start the agent in dry-run mode**:
   ```bash
   python src/agent.py --dry-run
   ```

---

## Production Deployment on Raspberry Pi

1. Clone this repository on your Raspberry Pi.
2. **Create and activate a virtual environment** under the `edge` folder:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Create the configuration file**:
   ```bash
   cp config.yaml.example config.yaml
   ```
   Edit `config.yaml` to customize the list of active sensors physically attached to this specific Pi. You can also specify settings in `config.yaml` or override them dynamically.
5. Set up AWS credentials via standard environment variables or IAM instance profiles.
6. **Launch the agent** as a background daemon:
   * **Using Configuration Overrides (Highly Recommended for Fleets)**:
     ```bash
     # Run device 1 with custom region, uploading to AWS
     DEVICE_ID=1 AWS_REGION=us-east-1 AWS_ENABLED=true nohup .venv/bin/python src/agent.py > agent.log 2>&1 &
     ```
     ```bash
     # Run device 2 on another Pi using the same config file
     DEVICE_ID=2 AWS_REGION=us-east-1 AWS_ENABLED=true nohup .venv/bin/python src/agent.py > agent.log 2>&1 &
     ```
   * **Running standard copy**:
     ```bash
     nohup .venv/bin/python src/agent.py > agent.log 2>&1 &
     ```

