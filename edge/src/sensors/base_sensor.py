import asyncio
from datetime import datetime, timezone

class BaseSensor:
    def __init__(self, device_id: int, config: dict):
        """
        Initialize the sensor.
        :param device_id: Numeric ID of the edge device.
        :param config: Dictionary configuration block for this sensor.
        """
        self.device_id = device_id
        self.config = config
        self.poll_interval = config.get("poll_interval", 60)
        self.simulation_mode = config.get("simulation", False)

    async def setup(self) -> None:
        """
        Perform any initialization (e.g. GPIO configuration, hardware connection).
        Can be synchronous or asynchronous.
        """
        pass

    async def read(self) -> list:
        """
        Read the telemetry values from the sensor.
        Returns a list of dictionaries matching the format:
        [
            {
                "device_id": int,
                "metric_id": int,
                "value": float,
                "timestamp": datetime (in UTC)
            }
        ]
        """
        raise NotImplementedError

    async def cleanup(self) -> None:
        """
        Clean up resources (e.g. cleanup GPIO, close connections).
        """
        pass
