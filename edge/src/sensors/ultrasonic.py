import asyncio
import logging
import random
import time
from datetime import datetime, timezone
from sensors.base_sensor import BaseSensor

logger = logging.getLogger(__name__)

try:
    import RPi.GPIO as GPIO
    HAS_GPIO_LIB = True
except ImportError:
    HAS_GPIO_LIB = False
    logger.warning("Could not import RPi.GPIO. Ultrasonic sensor will run in simulation mode.")


class UltrasonicSensor(BaseSensor):
    async def setup(self) -> None:
        self.water_level_metric_id = self.config.get("metrics", {}).get("water_level", {}).get("metric_id")
        
        if not self.water_level_metric_id:
            logger.warning("Ultrasonic sensor configured but no metric ID defined for water_level.")

        self.trig_pin = self.config.get("trig_pin", 18)
        self.echo_pin = self.config.get("echo_pin", 24)
        self.hole_depth = self.config.get("hole_depth", 100.0) # in cm

        if HAS_GPIO_LIB and not self.simulation_mode:
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(self.trig_pin, GPIO.OUT)
                GPIO.setup(self.echo_pin, GPIO.IN)
                GPIO.output(self.trig_pin, GPIO.LOW)
                logger.info(f"Initialized physical Ultrasonic sensor (Trig={self.trig_pin}, Echo={self.echo_pin})")
            except Exception as e:
                logger.error(f"Failed to initialize physical GPIO for Ultrasonic sensor: {e}. Falling back to simulation.")
                self.simulation_mode = True
        else:
            self.simulation_mode = True
            logger.info("Initializing Ultrasonic sensor in SIMULATION mode.")

    def _read_sync(self):
        if self.simulation_mode:
            # Simulated water level (0 to 100 cm)
            # Simulates a slow rise and fall or slight fluctuation
            return round(50.0 + random.uniform(-5.0, 5.0), 1)

        try:
            # Trigger ultrasonic pulse
            GPIO.output(self.trig_pin, GPIO.HIGH)
            time.sleep(0.00001)
            GPIO.output(self.trig_pin, GPIO.LOW)

            pulse_start = time.time()
            pulse_end = time.time()

            # Timeout after 0.1 seconds to avoid infinite loops if echo is missed
            timeout_start = time.time()
            while GPIO.input(self.echo_pin) == 0:
                pulse_start = time.time()
                if pulse_start - timeout_start > 0.1:
                    logger.error("Ultrasonic echo start timeout.")
                    return None

            timeout_start = time.time()
            while GPIO.input(self.echo_pin) == 1:
                pulse_end = time.time()
                if pulse_end - timeout_start > 0.1:
                    logger.error("Ultrasonic echo end timeout.")
                    return None

            pulse_duration = pulse_end - pulse_start
            # Speed of sound is ~34300 cm/s. The pulse travels to the object and back, so:
            distance = (pulse_duration * 34300) / 2
            
            # Water level = hole depth - distance to water surface
            water_level = self.hole_depth - distance
            if water_level < 0:
                water_level = 0.0
                
            return round(water_level, 1)

        except Exception as e:
            logger.error(f"Error reading ultrasonic sensor: {e}")
            return None

    async def read(self) -> list:
        water_level = await asyncio.to_thread(self._read_sync)
        
        data_points = []
        now = datetime.now(timezone.utc)
        
        if water_level is not None and self.water_level_metric_id is not None:
            data_points.append({
                "device_id": self.device_id,
                "metric_id": self.water_level_metric_id,
                "value": float(water_level),
                "timestamp": now
            })
            
        return data_points

    async def cleanup(self) -> None:
        if not self.simulation_mode and HAS_GPIO_LIB:
            try:
                # Only clean up pins we initialized
                GPIO.cleanup([self.trig_pin, self.echo_pin])
            except Exception as e:
                logger.error(f"Error cleaning up GPIO for Ultrasonic sensor: {e}")
