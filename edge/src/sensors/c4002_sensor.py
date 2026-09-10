import asyncio
import logging
import random
import statistics
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sensors.base_sensor import BaseSensor

logger = logging.getLogger(__name__)

try:
    from c4002 import (
        C4002Sensor as C4002Driver,
        LED_KEEP,
        LED_OFF,
        LED_ON,
        LedMode,
    )
    HAS_C4002_LIB = True
except ImportError:
    try:
        from c4002 import C4002Sensor as C4002Driver
        HAS_C4002_LIB = True
        LedMode = None
        LED_ON = 1
        LED_OFF = 0
        LED_KEEP = 255
    except ImportError:
        HAS_C4002_LIB = False
        LedMode = None
        LED_ON = 1
        LED_OFF = 0
        LED_KEEP = 255
        logger.warning("c4002 library not found. C4002 sensor will run in simulation mode.")


class C4002Sensor(BaseSensor):
    """
    Sensor plugin for DFRobot C4002 (SEN0691) 24GHz mmWave radar module.
    
    Continuously samples sensor telemetry at 1 Hz in a background task
    and computes clean 1-minute windowed aggregations:
      1. Occupancy Percentage (% of samples with presence detected)
      2. Average Presence Distance (meters, when occupied; 0.0 when vacant)
      3. Peak Motion Energy (maximum motion energy 0-100 observed in window)
      4. Average Ambient Light Intensity (Lux)
    """

    @staticmethod
    def _parse_led_mode(val: Any, default: int = LED_OFF) -> int:
        """
        Parse flexible LED configuration values into an integer mode:
        LED_OFF (0), LED_ON (1), or LED_KEEP (255 / 0xFF).
        Accepts bool, int, or case-insensitive string values ('on', 'off', 'keep', 'true', 'false').
        """
        if val is None:
            return default
        if isinstance(val, bool):
            return LED_ON if val else LED_OFF
        if isinstance(val, int):
            return val
        if isinstance(val, str):
            cleaned = val.strip().lower()
            if cleaned in ("on", "true", "1", "yes", "enable", "enabled"):
                return LED_ON
            if cleaned in ("off", "false", "0", "no", "disable", "disabled"):
                return LED_OFF
            if cleaned in ("keep", "unchanged", "default"):
                return LED_KEEP
        return default

    @staticmethod
    def _format_led_mode(mode: int) -> str:
        """Format LED mode integer for human-readable logging."""
        if mode == LED_ON:
            return "ON"
        if mode == LED_OFF:
            return "OFF"
        if mode == LED_KEEP:
            return "KEEP"
        return str(mode)

    def __init__(self, device_id: int, config: dict):
        super().__init__(device_id, config)
        self.port = self.config.get("port", "/dev/serial0")
        self.baudrate = int(self.config.get("baudrate", 115200))
        self.sample_interval = float(self.config.get("sample_interval", 1.0))
        
        # Metric ID bindings
        metrics_cfg = self.config.get("metrics", {})
        self.occupancy_metric_id = metrics_cfg.get("occupancy", {}).get("metric_id")
        self.distance_metric_id = metrics_cfg.get("distance", {}).get("metric_id")
        self.motion_metric_id = metrics_cfg.get("motion", {}).get("metric_id")
        self.light_metric_id = metrics_cfg.get("light", {}).get("metric_id")

        # LED configuration: False by default (dark/stealth mode). Set to True / "on" to enable.
        # Can also be a dict: {"run": False, "out": True}
        self.led_config = self.config.get("led", self.config.get("leds", False))

        self.sensor: Optional[Any] = None
        self._window_samples: List[Dict[str, Any]] = []
        self._lock = asyncio.Lock()
        self._sample_task: Optional[asyncio.Task] = None
        self._running = False

        # Internal state for realistic simulation mode
        self._sim_is_present = False
        self._sim_state_countdown = 0
        self._sim_current_dist = 2.0
        self._sim_base_lux = 45.0

    async def setup(self) -> None:
        """Initialize serial connection or fallback to simulation mode, and start sampling task."""
        if not any([self.occupancy_metric_id, self.distance_metric_id, self.motion_metric_id, self.light_metric_id]):
            logger.warning("C4002 sensor configured without any active metric IDs.")

        if HAS_C4002_LIB and not self.simulation_mode:
            try:
                self.sensor = C4002Driver(port=self.port, baudrate=self.baudrate)
                self.sensor.connect()

                # Configure onboard LEDs (default: turned off / stealth mode)
                if hasattr(self.sensor, "set_led"):
                    if isinstance(self.led_config, dict):
                        run_mode = self._parse_led_mode(self.led_config.get("run"), default=LED_OFF)
                        out_mode = self._parse_led_mode(self.led_config.get("out"), default=LED_OFF)
                        self.sensor.set_led(run_led=run_mode, out_led=out_mode)
                        logger.info(
                            f"C4002 onboard LEDs configured: RUN={self._format_led_mode(run_mode)}, "
                            f"OUT={self._format_led_mode(out_mode)}"
                        )
                    else:
                        led_mode = self._parse_led_mode(self.led_config, default=LED_OFF)
                        if led_mode == LED_ON:
                            self.sensor.set_led(run_led=LED_ON, out_led=LED_ON)
                            logger.info("C4002 onboard LEDs turned ON.")
                        elif led_mode == LED_KEEP:
                            logger.info("C4002 onboard LEDs preserved (hardware state unchanged).")
                        else:
                            if hasattr(self.sensor, "turn_off_leds"):
                                self.sensor.turn_off_leds()
                            else:
                                self.sensor.set_led(run_led=LED_OFF, out_led=LED_OFF)
                            logger.info("C4002 onboard LEDs turned OFF (default dark/stealth mode).")
                    await asyncio.sleep(0.05)

                # Set hardware reporting interval to 1.0s (10 * 100ms)
                if hasattr(self.sensor, "set_report_period"):
                    self.sensor.set_report_period(10)
                    await asyncio.sleep(0.1)

                # Flush any stale packets that were buffered before starting
                if self.sensor.ser and hasattr(self.sensor.ser, "reset_input_buffer"):
                    self.sensor.ser.reset_input_buffer()
                logger.info(f"Connected to physical C4002 sensor on {self.port} at {self.baudrate} baud.")
            except Exception as e:
                logger.error(f"Failed to connect to C4002 sensor: {e}. Falling back to simulation mode.")
                self.simulation_mode = True
                self.sensor = None
        else:
            self.simulation_mode = True
            self.sensor = None
            logger.info("Initializing C4002 sensor in SIMULATION mode.")

        # Start the background 1 Hz sampling task
        self._running = True
        self._sample_task = asyncio.create_task(self._sample_loop())

    def _generate_simulated_sample(self) -> Dict[str, Any]:
        """Generate realistic 1-second radar telemetry frame for simulation mode."""
        if self._sim_state_countdown <= 0:
            # Transition presence state: occupied for 20-80s, vacant for 30-120s
            self._sim_is_present = not self._sim_is_present
            self._sim_state_countdown = random.randint(20, 80) if self._sim_is_present else random.randint(30, 120)
            if self._sim_is_present:
                self._sim_current_dist = round(random.uniform(0.8, 3.5), 2)
        else:
            self._sim_state_countdown -= 1

        if self._sim_is_present:
            # Small jitter in distance while occupied
            dist = max(0.5, min(6.0, round(self._sim_current_dist + random.uniform(-0.05, 0.05), 2)))
            self._sim_current_dist = dist
            presence_energy = random.randint(50, 95)
            # Occasional motion activity while present
            has_motion = random.random() < 0.4
            motion_energy = random.randint(30, 99) if has_motion else random.randint(0, 5)
        else:
            dist = 0.0
            presence_energy = 0
            motion_energy = 0

        # Ambient light slow drift around base level
        lux = max(5.0, round(self._sim_base_lux + random.uniform(-2.0, 2.0), 1))
        self._sim_base_lux = lux

        return {
            "presence_detected": self._sim_is_present,
            "presence_distance_m": dist,
            "presence_energy": presence_energy,
            "motion_energy": motion_energy,
            "ambient_light_lux": lux,
        }

    def _read_packet_sync(self) -> Optional[Dict[str, Any]]:
        """Read a single packet from the physical sensor synchronously."""
        if not self.sensor:
            return None
        try:
            packet = self.sensor.read_packet()
            if packet and not getattr(packet, "is_calibrating", False):
                return {
                    "presence_detected": getattr(packet, "presence_detected", False),
                    "presence_distance_m": float(getattr(packet, "presence_distance_m", 0.0)),
                    "presence_energy": int(getattr(packet, "presence_energy", 0)),
                    "motion_energy": int(getattr(packet, "motion_energy", 0)),
                    "ambient_light_lux": float(getattr(packet, "ambient_light_lux", 0.0)),
                }
        except Exception as e:
            logger.debug(f"Transient error reading C4002 packet: {e}")
        return None

    async def _sample_loop(self) -> None:
        """Background loop sampling the sensor at 1 Hz."""
        logger.info(f"Started C4002 1 Hz background sampling task (window={self.poll_interval}s).")
        while self._running:
            start_time = asyncio.get_event_loop().time()
            sample = None
            try:
                if self.simulation_mode:
                    sample = self._generate_simulated_sample()
                else:
                    # In hardware mode, read_packet_sync() blocks until the next packet arrives
                    # from the sensor (1.0s pacing).
                    sample = await asyncio.to_thread(self._read_packet_sync)

                if sample:
                    async with self._lock:
                        self._window_samples.append(sample)
            except Exception as e:
                logger.error(f"Error in C4002 sampling loop: {e}")

            if self.simulation_mode:
                elapsed = asyncio.get_event_loop().time() - start_time
                sleep_time = max(0.05, self.sample_interval - elapsed)
                try:
                    await asyncio.sleep(sleep_time)
                except asyncio.CancelledError:
                    break
            else:
                # In hardware mode, read_packet_sync() already paces the loop at the sensor's
                # reporting interval (1.0s). Do not add a sleep after reading, which would cause
                # packets to accumulate in the serial buffer and create lag.
                if not sample:
                    # Brief backoff if no sample was returned (e.g. read timeout/error)
                    try:
                        await asyncio.sleep(0.1)
                    except asyncio.CancelledError:
                        break
                else:
                    # Cooperative yield to allow other coroutines on the event loop to execute
                    await asyncio.sleep(0)

    async def read(self) -> list:
        """
        Aggregate the collected 1-second samples over the window interval.
        Returns telemetry data points for the 4 metrics.
        """
        async with self._lock:
            samples = list(self._window_samples)
            self._window_samples.clear()

        if not samples:
            logger.debug("No samples collected during C4002 aggregation window.")
            return []

        total_samples = len(samples)
        present_samples = [s for s in samples if s["presence_detected"]]
        
        # 1. Occupancy ratio (% of window occupied)
        occupancy_pct = round((len(present_samples) / total_samples) * 100.0, 1)

        # 2. Average distance (when occupied; 0.0 when vacant)
        if present_samples:
            avg_distance = round(statistics.mean(s["presence_distance_m"] for s in present_samples), 2)
        else:
            avg_distance = 0.0

        # 3. Peak motion energy in window
        max_motion_energy = max(s["motion_energy"] for s in samples)

        # 4. Average ambient light in window
        avg_light = round(statistics.mean(s["ambient_light_lux"] for s in samples), 1)

        now = datetime.now(timezone.utc)
        data_points = []

        if self.occupancy_metric_id is not None:
            data_points.append({
                "device_id": self.device_id,
                "metric_id": self.occupancy_metric_id,
                "value": float(occupancy_pct),
                "timestamp": now
            })

        if self.distance_metric_id is not None:
            data_points.append({
                "device_id": self.device_id,
                "metric_id": self.distance_metric_id,
                "value": float(avg_distance),
                "timestamp": now
            })

        if self.motion_metric_id is not None:
            data_points.append({
                "device_id": self.device_id,
                "metric_id": self.motion_metric_id,
                "value": float(max_motion_energy),
                "timestamp": now
            })

        if self.light_metric_id is not None:
            data_points.append({
                "device_id": self.device_id,
                "metric_id": self.light_metric_id,
                "value": float(avg_light),
                "timestamp": now
            })

        logger.debug(
            f"C4002 Aggregated [{total_samples} samples]: "
            f"Occupancy={occupancy_pct}%, Dist={avg_distance}m, MaxMotion={max_motion_energy}, Light={avg_light}Lx"
        )
        return data_points

    async def cleanup(self) -> None:
        """Stop background sampling and close serial connection."""
        self._running = False
        if self._sample_task:
            self._sample_task.cancel()
            try:
                await self._sample_task
            except asyncio.CancelledError:
                pass
            self._sample_task = None

        if self.sensor and hasattr(self.sensor, "close"):
            try:
                self.sensor.close()
                logger.info("Closed C4002 serial connection.")
            except Exception as e:
                logger.error(f"Error closing C4002 serial connection: {e}")
            self.sensor = None
