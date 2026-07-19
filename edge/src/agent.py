import argparse
import asyncio
import logging
import os
import signal
import sys
from datetime import datetime, timezone
import yaml

from sensors import SENSOR_REGISTRY
from uploaders.dynamodb import DynamoDbUploader

# Set up logging format and levels
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("agent")


class IoTAgent:
    def __init__(self, config_path: str, dry_run_override: bool = False):
        self.config_path = config_path
        self.dry_run_override = dry_run_override
        self.config = {}
        self.device_id = None
        
        self.sensors = []
        self.uploader = None
        self.queue = asyncio.Queue()
        self.retry_buffer = []
        self.max_retry_buffer_size = 1000  # Cap the buffer size to avoid memory bloat
        
        self.running = False
        self.tasks = []

    def load_config(self):
        """Load and validate config.yaml configuration."""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        with open(self.config_path, "r") as f:
            self.config = yaml.safe_load(f)
            
        # Apply environment variable overrides if they exist
        env_device_id = os.environ.get("DEVICE_ID")
        if env_device_id:
            try:
                self.config["device_id"] = int(env_device_id)
                logger.info(f"Overriding device_id via env: {self.config['device_id']}")
            except ValueError:
                logger.error(f"Invalid DEVICE_ID environment variable value: '{env_device_id}'. Must be an integer.")

        if "aws" not in self.config:
            self.config["aws"] = {}
            
        env_aws_region = os.environ.get("AWS_REGION")
        if env_aws_region:
            self.config["aws"]["region"] = env_aws_region
            logger.info(f"Overriding AWS region via env: {env_aws_region}")

        env_telemetry_table = os.environ.get("AWS_TELEMETRY_TABLE")
        if env_telemetry_table:
            self.config["aws"]["telemetry_table"] = env_telemetry_table
            logger.info(f"Overriding AWS telemetry table via env: {env_telemetry_table}")

        env_aws_enabled = os.environ.get("AWS_ENABLED")
        if env_aws_enabled:
            is_enabled = env_aws_enabled.lower() in ("true", "1", "yes", "on")
            self.config["aws"]["enabled"] = is_enabled
            logger.info(f"Overriding AWS enabled status via env: {is_enabled}")

        self.device_id = self.config.get("device_id")
        if not self.device_id:
            raise ValueError("Configuration missing required field: 'device_id'")
        
        logger.info(f"Loaded configuration for Device ID: {self.device_id}")

    def setup_components(self):
        """Instantiate configured sensors and the DynamoDB uploader."""
        aws_cfg = self.config.get("aws", {})
        region = aws_cfg.get("region", "us-east-1")
        table_name = aws_cfg.get("telemetry_table", "IoT_Telemetry")
        
        # Determine if we should perform actual uploads or local dry-runs
        aws_enabled = aws_cfg.get("enabled", True)
        if self.dry_run_override:
            aws_enabled = False
            logger.info("Dry-run mode overridden via command-line arguments.")

        self.uploader = DynamoDbUploader(region=region, table_name=table_name, enabled=aws_enabled)
        self.uploader.setup()

        sensors_list = self.config.get("sensors", [])
        for sensor_cfg in sensors_list:
            sensor_type = sensor_cfg.get("type")
            if not sensor_type:
                logger.warning("Sensor configuration is missing required 'type' field. Skipping.")
                continue
            
            sensor_class = SENSOR_REGISTRY.get(sensor_type)
            if not sensor_class:
                logger.warning(f"Sensor type '{sensor_type}' is not registered in SENSOR_REGISTRY. Skipping.")
                continue
            
            # Construct the sensor plugin passing device_id and its configuration block
            sensor_inst = sensor_class(device_id=self.device_id, config=sensor_cfg)
            self.sensors.append(sensor_inst)
            logger.info(f"Initialized sensor plugin: {sensor_type} for Device {self.device_id} (polls every {sensor_inst.poll_interval}s)")

    async def run_sensor_loop(self, sensor):
        """Asynchronous execution loop for an individual sensor plugin."""
        logger.info(f"Starting async loop for sensor: {sensor.__class__.__name__}")
        try:
            await sensor.setup()
        except Exception as e:
            logger.error(f"Setup failed for sensor {sensor.__class__.__name__}: {e}")
            return

        while self.running:
            start_time = asyncio.get_event_loop().time()
            try:
                data_points = await sensor.read()
                if data_points:
                    for dp in data_points:
                        await self.queue.put(dp)
                        logger.debug(f"Queued telemetry point: {dp}")
            except Exception as e:
                logger.error(f"Error reading from sensor {sensor.__class__.__name__}: {e}")

            # Calculate sleep time to align with poll interval
            elapsed = asyncio.get_event_loop().time() - start_time
            sleep_time = max(0.1, sensor.poll_interval - elapsed)
            
            # Sleep until the next poll cycle or until agent is stopped
            try:
                await asyncio.sleep(sleep_time)
            except asyncio.CancelledError:
                break

        logger.info(f"Cleaning up sensor: {sensor.__class__.__name__}")
        try:
            await sensor.cleanup()
        except Exception as e:
            logger.error(f"Cleanup failed for sensor {sensor.__class__.__name__}: {e}")

    async def run_uploader_loop(self):
        """Asynchronous worker that consumes queued telemetry data and uploads it to AWS."""
        logger.info("Starting DynamoDB uploader background worker task...")
        
        while self.running or not self.queue.empty():
            try:
                # Retrieve next data point from queue
                try:
                    # Use a short timeout so the loop doesn't block indefinitely on empty queue when stopping
                    data_point = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                
                # Attempt to upload retry buffer first if there is connection
                if self.retry_buffer:
                    logger.info(f"Attempting to upload {len(self.retry_buffer)} previously failed data points...")
                    still_failed = []
                    for buffered_dp in self.retry_buffer:
                        success = await self.uploader.upload(buffered_dp)
                        if not success:
                            still_failed.append(buffered_dp)
                    self.retry_buffer = still_failed
                    if not self.retry_buffer:
                        logger.info("Retry buffer cleared successfully.")
                    else:
                        logger.warning(f"Retry buffer still contains {len(self.retry_buffer)} data points.")
                
                # Upload current data point
                success = await self.uploader.upload(data_point)
                
                if not success:
                    # Push back to retry buffer if upload failed (e.g. offline)
                    if len(self.retry_buffer) < self.max_retry_buffer_size:
                        self.retry_buffer.append(data_point)
                        logger.warning(f"Upload failed. Buffered data point. Current buffer size: {len(self.retry_buffer)}")
                    else:
                        logger.error("Retry buffer is full. Dropping oldest failed data point.")
                        self.retry_buffer.pop(0)
                        self.retry_buffer.append(data_point)
                        
                self.queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Uploader worker encountered unexpected error: {e}")
                await asyncio.sleep(2)
                
        logger.info("Uploader loop stopped.")

    async def start(self):
        """Start the agent and all asynchronous tasks."""
        self.running = True
        
        # Start sensor loops
        for sensor in self.sensors:
            task = asyncio.create_task(self.run_sensor_loop(sensor))
            self.tasks.append(task)
            
        # Start uploader loop
        uploader_task = asyncio.create_task(self.run_uploader_loop())
        self.tasks.append(uploader_task)
        
        logger.info("Agent started successfully. Processing telemetry...")
        
        # Keep agent running until cancelled
        try:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        except asyncio.CancelledError:
            logger.info("Agent execution cancelled.")

    def stop(self):
        """Initiate graceful shutdown by canceling active tasks."""
        logger.info("Stopping agent gracefully...")
        self.running = False
        for task in self.tasks:
            task.cancel()


def find_default_config():
    """Look for config.yaml in common locations."""
    locations = [
        "config.yaml",
        "src/config.yaml",
        "../config.yaml",
        os.path.join(os.path.dirname(__file__), "config.yaml"),
        os.path.join(os.path.dirname(__file__), "..", "config.yaml"),
    ]
    for loc in locations:
        if os.path.exists(loc):
            return os.path.abspath(loc)
    return None


def main():
    parser = argparse.ArgumentParser(description="PiLambdaChart Edge IoT Telemetry Agent Daemon")
    parser.add_argument(
        "-c", "--config",
        type=str,
        help="Path to config.yaml configuration file"
    )
    parser.add_argument(
        "-d", "--dry-run",
        action="store_true",
        help="Dry run mode (logs measurements without uploading to AWS DynamoDB)"
    )
    args = parser.parse_args()

    config_path = args.config
    if not config_path:
        config_path = find_default_config()
        if not config_path:
            logger.error("Could not find config.yaml. Please specify using -c/--config.")
            sys.exit(1)
            
    logger.info(f"Using configuration file: {config_path}")

    agent = IoTAgent(config_path=config_path, dry_run_override=args.dry_run)
    
    try:
        agent.load_config()
        agent.setup_components()
    except Exception as e:
        logger.exception(f"Fatal error configuring agent: {e}")
        sys.exit(1)

    # Set up signal handlers for graceful exit
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    def handle_signal():
        logger.info("Shutdown signal received.")
        agent.stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, handle_signal)
        except NotImplementedError:
            # Signal handlers are not fully supported on some platforms (e.g. Windows)
            pass

    try:
        loop.run_until_complete(agent.start())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received during startup.")
    finally:
        # Run cleanup of remaining tasks
        loop.close()
        logger.info("Agent cleanup complete. Exit.")


if __name__ == "__main__":
    main()
