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
            logger.info(f"Initialized physical {sensor_type} on pin {pin_attr}")
        else:
            self.simulation_mode = True
            self.sensor = None
            logger.info("Initializing DHT sensor in SIMULATION mode.")

    def _read_sync(self):
        if self.sensor is None:
            # Simulated read
            temp = round(random.uniform(18.0, 26.0), 1)
            humidity = round(random.uniform(35.0, 65.0), 1)
            return temp, humidity
        
        try:
            temp = self.sensor.temperature
            humidity = self.sensor.humidity
            if temp is not None and humidity is not None:
                return temp, humidity
        except RuntimeError as e:
            # DHT sensors often fail to read; log and return None to retry on next poll
            logger.debug(f"DHT runtime error (expected occasionally): {e}")
        except Exception as e:
            logger.error(f"Unexpected error reading DHT sensor: {e}")
        return None, None

    async def read(self) -> list:
        # Run blocking reading in a thread pool to avoid blocking the main event loop
        temp, humidity = await asyncio.to_thread(self._read_sync)
        
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
