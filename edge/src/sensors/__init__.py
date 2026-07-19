from sensors.dht_sensor import DhtSensor
from sensors.bh1750_sensor import Bh1750Sensor
from sensors.pir_motion import PirMotionSensor
from sensors.ultrasonic import UltrasonicSensor

# Map sensor names in config.yaml to their Python classes
SENSOR_REGISTRY = {
    "dht22": DhtSensor,
    "dht11": DhtSensor,
    "bh1750": Bh1750Sensor,
    "pir_motion": PirMotionSensor,
    "ultrasonic": UltrasonicSensor
}
