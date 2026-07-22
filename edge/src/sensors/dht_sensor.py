import asyncio
import logging
import random
from datetime import datetime, timezone
from sensors.base_sensor import BaseSensor

logger = logging.getLogger(__name__)

try:
    import board
    import adafruit_dht
    HAS_DHT_LIB = True
except ImportError:
    HAS_DHT_LIB = False
    logger.warning("Could not import board or adafruit_dht. DHT sensor will run in simulation mode.")


class DhtSensor(BaseSensor):
    async def setup(self) -> None:
        self.temp_metric_id = self.config.get("metrics", {}).get("temperature", {}).get("metric_id")
        self.humidity_metric_id = self.config.get("metrics", {}).get("humidity", {}).get("metric_id")

        # Retry configuration: DHT sensors are electrically noisy and frequently
        # raise RuntimeError on individual reads. The agent will retry up to
        # retry_count times, waiting retry_delay_seconds between each attempt,
        # before giving up and returning no data for this poll cycle.
        self.retry_count = int(self.config.get("retry_count", 3))
        self.retry_delay_seconds = float(self.config.get("retry_delay_seconds", 2.0))

        if not self.temp_metric_id and not self.humidity_metric_id:
            logger.warning("DHT sensor configured but no metric IDs defined for temperature or humidity.")

        if HAS_DHT_LIB and not self.simulation_mode:
            pin_num = self.config.get("pin", 24)
            # Dynamically map pin number string to board GPIO pin objects if needed
            # For simplicity, we assume gpio 24 corresponds to board.D24
            pin_attr = f"D{pin_num}"
            if hasattr(board, pin_attr):
                board_pin = getattr(board, pin_attr)
            else:
                raise ValueError(f"Pin D{pin_num} not found on board module.")

            sensor_type = self.config.get("sensor_type", "DHT22").upper()
            if sensor_type == "DHT11":
                self.sensor = adafruit_dht.DHT11(board_pin)
            else:
                self.sensor = adafruit_dht.DHT22(board_pin)
            logger.info(f"Initialized physical {sensor_type} on pin {pin_attr} "
                        f"(retry_count={self.retry_count}, retry_delay={self.retry_delay_seconds}s)")
        else:
            self.simulation_mode = True
            self.sensor = None
            logger.info("Initializing DHT sensor in SIMULATION mode.")

    def _read_once_sync(self):
        """Attempt a single blocking read from the physical sensor.

        Returns (temp, humidity) on success, raises RuntimeError on a transient
        read failure, or raises Exception for unexpected errors.
        """
        if self.sensor is None:
            # Simulated read
            temp = round(random.uniform(18.0, 26.0), 1)
            humidity = round(random.uniform(35.0, 65.0), 1)
            return temp, humidity

        temp = self.sensor.temperature
        humidity = self.sensor.humidity
        if temp is not None and humidity is not None:
            return temp, humidity
        # Sensor returned None values — treat as a transient failure
        raise RuntimeError("DHT sensor returned None for temperature or humidity.")

    async def read(self) -> list:
        """Read sensor data with up to retry_count retries on RuntimeError.

        Each retry waits retry_delay_seconds (default 2 s) on the asyncio event
        loop so other sensor tasks continue running while this one backs off.
        """
        temp, humidity = None, None

        for attempt in range(1, self.retry_count + 1):
            try:
                temp, humidity = await asyncio.to_thread(self._read_once_sync)
                # Successful read — exit retry loop
                if attempt > 1:
                    logger.debug(f"DHT read succeeded on attempt {attempt}/{self.retry_count}.")
                break
            except RuntimeError as e:
                if attempt < self.retry_count:
                    logger.debug(
                        f"DHT RuntimeError on attempt {attempt}/{self.retry_count}: {e}. "
                        f"Retrying in {self.retry_delay_seconds}s..."
                    )
                    await asyncio.sleep(self.retry_delay_seconds)
                else:
                    logger.warning(
                        f"DHT read failed after {self.retry_count} attempt(s). "
                        f"Skipping this poll cycle. Last error: {e}"
                    )
            except Exception as e:
                logger.error(f"Unexpected error reading DHT sensor: {e}")
                break

        data_points = []
        now = datetime.now(timezone.utc)

        if temp is not None and self.temp_metric_id is not None:
            data_points.append({
                "device_id": self.device_id,
                "metric_id": self.temp_metric_id,
                "value": float(temp),
                "timestamp": now
            })

        if humidity is not None and self.humidity_metric_id is not None:
            data_points.append({
                "device_id": self.device_id,
                "metric_id": self.humidity_metric_id,
                "value": float(humidity),
                "timestamp": now
            })

        return data_points

    async def cleanup(self) -> None:
        if self.sensor is not None:
            try:
                self.sensor.exit()
            except Exception as e:
                logger.error(f"Error calling exit() on DHT sensor: {e}")
