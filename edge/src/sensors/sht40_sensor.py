import asyncio
import logging
import random
from datetime import datetime, timezone
from sensors.base_sensor import BaseSensor

logger = logging.getLogger(__name__)

try:
    import board
    import adafruit_sht4x
    HAS_SHT40_LIB = True
except ImportError:
    board = None
    adafruit_sht4x = None
    HAS_SHT40_LIB = False
    logger.warning(
        "Could not import board or adafruit_sht4x. "
        "Install via 'pip install adafruit-circuitpython-sht4x'. "
        "SHT40 sensor will run in simulation mode."
    )


class Sht40Sensor(BaseSensor):
    """Sensor plugin for Sensirion SHT40 I2C temperature and humidity sensor."""

    DEFAULT_I2C_ADDRESS = 0x44
    DEFAULT_MODE = "NOHEAT_HIGHPRECISION"

    @staticmethod
    def _parse_i2c_address(value) -> int:
        """Parse and validate a 7-bit I2C address from int, hex/dec string, or None."""
        if value is None:
            return Sht40Sensor.DEFAULT_I2C_ADDRESS
        if isinstance(value, bool):
            raise ValueError(f"Invalid I2C address: {value!r}")
        if isinstance(value, int):
            addr = value
        elif isinstance(value, str):
            try:
                addr = int(value.strip(), 0)
            except ValueError as exc:
                raise ValueError(f"Invalid I2C address string: {value!r}") from exc
        else:
            raise ValueError(f"Unsupported I2C address type: {type(value).__name__}")

        if not (0x03 <= addr <= 0x77):
            raise ValueError(f"I2C address 0x{addr:02x} out of valid 7-bit range (0x03..0x77).")
        return addr

    async def setup(self) -> None:
        metrics_cfg = self.config.get("metrics", {})
        self.temp_metric_id = metrics_cfg.get("temperature", {}).get("metric_id")
        self.humidity_metric_id = metrics_cfg.get("humidity", {}).get("metric_id")

        if self.temp_metric_id is None and self.humidity_metric_id is None:
            logger.warning("SHT40 sensor configured but no metric IDs defined for temperature or humidity.")

        raw_addr = self.config.get("address", self.config.get("i2c_address", self.DEFAULT_I2C_ADDRESS))
        self.i2c_address = self._parse_i2c_address(raw_addr)
        self.mode_name = str(self.config.get("mode", self.DEFAULT_MODE)).strip().upper()
        self.i2c = None

        if HAS_SHT40_LIB and not self.simulation_mode:
            try:
                self.i2c = board.I2C()  # uses board.SCL and board.SDA
                self.sensor = adafruit_sht4x.SHT4x(self.i2c, address=self.i2c_address)
                if hasattr(adafruit_sht4x, "Mode"):
                    mode_val = getattr(adafruit_sht4x.Mode, self.mode_name, None)
                    if mode_val is not None:
                        self.sensor.mode = mode_val
                    else:
                        logger.warning(
                            f"Unknown SHT40 mode '{self.mode_name}'; falling back to {self.DEFAULT_MODE}."
                        )
                        self.sensor.mode = adafruit_sht4x.Mode.NOHEAT_HIGHPRECISION
                        self.mode_name = self.DEFAULT_MODE
                logger.info(
                    f"Initialized physical SHT40 sensor via I2C "
                    f"(address=0x{self.i2c_address:02x}, mode={self.mode_name})."
                )
            except Exception as e:
                logger.error(f"Failed to initialize SHT40 physical sensor: {e}. Falling back to simulation.")
                self.simulation_mode = True
                self.sensor = None
        else:
            self.simulation_mode = True
            self.sensor = None
            logger.info("Initializing SHT40 sensor in SIMULATION mode.")

    def _read_sync(self):
        if self.sensor is None:
            temp = round(random.uniform(18.0, 26.0), 2)
            humidity = round(random.uniform(35.0, 65.0), 2)
            return temp, humidity

        try:
            temp, humidity = self.sensor.measurements
            if temp is None or humidity is None:
                logger.warning("SHT40 sensor returned None for temperature or humidity.")
                return None, None
            return round(float(temp), 2), round(float(humidity), 2)
        except Exception as e:
            logger.error(f"Error reading SHT40 sensor: {e}")
            return None, None

    async def read(self) -> list:
        temp, humidity = await asyncio.to_thread(self._read_sync)

        data_points = []
        now = datetime.now(timezone.utc)

        if temp is not None and self.temp_metric_id is not None:
            data_points.append({
                "device_id": self.device_id,
                "metric_id": self.temp_metric_id,
                "value": float(temp),
                "timestamp": now,
            })

        if humidity is not None and self.humidity_metric_id is not None:
            data_points.append({
                "device_id": self.device_id,
                "metric_id": self.humidity_metric_id,
                "value": float(humidity),
                "timestamp": now,
            })

        return data_points

    async def cleanup(self) -> None:
        # Do not call self.i2c.deinit(): board.I2C() returns a shared singleton bus
        # that other I2C sensors (such as BH1750) may still be using.
        self.sensor = None
