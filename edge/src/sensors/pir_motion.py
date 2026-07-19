import asyncio
import logging
import random
import threading
from datetime import datetime, timezone
from sensors.base_sensor import BaseSensor

logger = logging.getLogger(__name__)

try:
    from gpiozero import MotionSensor
    HAS_GPIO_LIB = True
except ImportError:
    HAS_GPIO_LIB = False
    logger.warning("Could not import gpiozero. PIR Motion sensor will run in simulation mode.")


class PirMotionSensor(BaseSensor):
    async def setup(self) -> None:
        self.motion_metric_id = self.config.get("metrics", {}).get("motion_count", {}).get("metric_id")
        
        if not self.motion_metric_id:
            logger.warning("PIR Motion sensor configured but no metric ID defined for motion_count.")

        self.trigger_count = 0
        self.counter_lock = threading.Lock()
        self.sim_task = None

        if HAS_GPIO_LIB and not self.simulation_mode:
            pin_num = self.config.get("pin", 23)
            try:
                self.pir = MotionSensor(pin_num)
                self.pir.when_motion = self._motion_triggered
                logger.info(f"Initialized physical PIR Motion sensor on pin {pin_num}")
            except Exception as e:
                logger.error(f"Failed to initialize PIR Motion sensor: {e}. Falling back to simulation.")
                self.simulation_mode = True
                self.pir = None
        else:
            self.simulation_mode = True
            self.pir = None
            logger.info("Initializing PIR Motion sensor in SIMULATION mode.")

        if self.simulation_mode:
            # Start background simulator to increment trigger_count randomly
            self.sim_task = asyncio.create_task(self._run_simulator())

    def _motion_triggered(self):
        with self.counter_lock:
            self.trigger_count += 1
            logger.debug("PIR motion trigger detected physically.")

    async def _run_simulator(self):
        try:
            while True:
                # Randomly trigger motion every 5 to 20 seconds
                await asyncio.sleep(random.uniform(5.0, 20.0))
                with self.counter_lock:
                    self.trigger_count += 1
                    logger.debug("PIR motion trigger simulated.")
        except asyncio.CancelledError:
            pass

    async def read(self) -> list:
        # Securely read and reset the count
        with self.counter_lock:
            current_count = self.trigger_count
            self.trigger_count = 0
            
        data_points = []
        now = datetime.now(timezone.utc)
        
        if self.motion_metric_id is not None:
            data_points.append({
                "device_id": self.device_id,
                "metric_id": self.motion_metric_id,
                "value": float(current_count),
                "timestamp": now
            })
            logger.debug(f"PIR Motion Count: read count {current_count}")
            
        return data_points

    async def cleanup(self) -> None:
        if self.sim_task:
            self.sim_task.cancel()
            try:
                await self.sim_task
            except asyncio.CancelledError:
                pass
        
        if self.pir is not None:
            try:
                self.pir.close()
            except Exception as e:
                logger.error(f"Error closing PIR sensor: {e}")
