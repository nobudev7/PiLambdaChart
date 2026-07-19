import asyncio
import logging
import random
from datetime import datetime, timezone
from sensors.base_sensor import BaseSensor

logger = logging.getLogger(__name__)

try:
    import board
    import adafruit_bh1750
    HAS_BH1750_LIB = True
except ImportError:
    HAS_BH1750_LIB = False
    logger.warning("Could not import board or adafruit_bh1750. BH1750 sensor will run in simulation mode.")


class Bh1750Sensor(BaseSensor):
    async def setup(self) -> None:
        self.lux_metric_id = self.config.get("metrics", {}).get("lux", {}).get("metric_id")
        
        if not self.lux_metric_id:
            logger.warning("BH1750 sensor configured but no metric ID defined for lux.")

        if HAS_BH1750_LIB and not self.simulation_mode:
            try:
                self.i2c = board.I2C()  # uses board.SCL and board.SDA
                self.sensor = adafruit_bh1750.BH1750(self.i2c)
                logger.info("Initialized physical BH1750 sensor via I2C.")
            except Exception as e:
                logger.error(f"Failed to initialize BH1750 physical sensor: {e}. Falling back to simulation.")
                self.simulation_mode = True
                self.sensor = None
        else:
            self.simulation_mode = True
            self.sensor = None
            logger.info("Initializing BH1750 sensor in SIMULATION mode.")

    def _read_sync(self):
        if self.sensor is None:
            # Simulated read - lux can range from 0 (dark) to 1000+ (bright)
            return round(random.uniform(50.0, 500.0), 2)
        
        try:
            return self.sensor.lux
        except Exception as e:
            logger.error(f"Error reading BH1750 sensor: {e}")
            return None

    async def read(self) -> list:
        lux = await asyncio.to_thread(self._read_sync)
        
        data_points = []
        now = datetime.now(timezone.utc)
        
        if lux is not None and self.lux_metric_id is not None:
            data_points.append({
                "device_id": self.device_id,
                "metric_id": self.lux_metric_id,
                "value": float(lux),
                "timestamp": now
            })
            
        return data_points
