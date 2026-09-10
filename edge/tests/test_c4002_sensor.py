"""
Unit tests for C4002 sensor plugin and LED configuration handling.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure edge/src is in sys.path
EDGE_SRC = Path(__file__).resolve().parent.parent / "src"
if str(EDGE_SRC) not in sys.path:
    sys.path.insert(0, str(EDGE_SRC))

from sensors.c4002_sensor import C4002Sensor, LED_KEEP, LED_OFF, LED_ON


def test_parse_led_mode() -> None:
    # Boolean values
    assert C4002Sensor._parse_led_mode(True) == LED_ON
    assert C4002Sensor._parse_led_mode(False) == LED_OFF

    # String values (case-insensitive)
    assert C4002Sensor._parse_led_mode("on") == LED_ON
    assert C4002Sensor._parse_led_mode("ON") == LED_ON
    assert C4002Sensor._parse_led_mode("true") == LED_ON
    assert C4002Sensor._parse_led_mode("True") == LED_ON
    assert C4002Sensor._parse_led_mode("enable") == LED_ON
    assert C4002Sensor._parse_led_mode("enabled") == LED_ON
    assert C4002Sensor._parse_led_mode("1") == LED_ON

    assert C4002Sensor._parse_led_mode("off") == LED_OFF
    assert C4002Sensor._parse_led_mode("OFF") == LED_OFF
    assert C4002Sensor._parse_led_mode("false") == LED_OFF
    assert C4002Sensor._parse_led_mode("False") == LED_OFF
    assert C4002Sensor._parse_led_mode("disable") == LED_OFF
    assert C4002Sensor._parse_led_mode("0") == LED_OFF

    assert C4002Sensor._parse_led_mode("keep") == LED_KEEP
    assert C4002Sensor._parse_led_mode("default") == LED_KEEP
    assert C4002Sensor._parse_led_mode("unchanged") == LED_KEEP

    # Integer values
    assert C4002Sensor._parse_led_mode(0) == 0
    assert C4002Sensor._parse_led_mode(1) == 1
    assert C4002Sensor._parse_led_mode(255) == 255

    # Fallbacks and invalid values
    assert C4002Sensor._parse_led_mode(None, default=LED_OFF) == LED_OFF
    assert C4002Sensor._parse_led_mode(None, default=LED_ON) == LED_ON
    assert C4002Sensor._parse_led_mode("unknown_val", default=LED_OFF) == LED_OFF


def test_format_led_mode() -> None:
    assert C4002Sensor._format_led_mode(LED_ON) == "ON"
    assert C4002Sensor._format_led_mode(LED_OFF) == "OFF"
    assert C4002Sensor._format_led_mode(LED_KEEP) == "KEEP"


def run_async(coro):
    return asyncio.run(coro)


@patch("sensors.c4002_sensor.C4002Driver")
def test_setup_led_off_by_default(mock_driver_cls) -> None:
    mock_sensor = MagicMock()
    mock_sensor.ser = MagicMock()
    mock_driver_cls.return_value = mock_sensor

    config = {
        "port": "/dev/serial0",
        "simulation": False,
        "metrics": {"occupancy": {"metric_id": 6}},
    }
    sensor = C4002Sensor(device_id=1, config=config)
    run_async(sensor.setup())

    mock_sensor.connect.assert_called_once()
    mock_sensor.turn_off_leds.assert_called_once()
    mock_sensor.set_report_period.assert_called_once_with(10)
    mock_sensor.ser.reset_input_buffer.assert_called_once()

    # Verify execution order: connect -> turn_off_leds -> set_report_period -> reset_input_buffer
    calls = [call[0] for call in mock_sensor.method_calls]
    assert calls.index("connect") < calls.index("turn_off_leds")
    assert calls.index("turn_off_leds") < calls.index("set_report_period")
    run_async(sensor.cleanup())


@patch("sensors.c4002_sensor.C4002Driver")
def test_setup_led_on_boolean(mock_driver_cls) -> None:
    mock_sensor = MagicMock()
    mock_sensor.ser = MagicMock()
    mock_driver_cls.return_value = mock_sensor

    config = {
        "port": "/dev/serial0",
        "simulation": False,
        "led": True,
        "metrics": {"occupancy": {"metric_id": 6}},
    }
    sensor = C4002Sensor(device_id=1, config=config)
    run_async(sensor.setup())

    mock_sensor.set_led.assert_called_once_with(run_led=True, out_led=True)
    run_async(sensor.cleanup())


@patch("sensors.c4002_sensor.C4002Driver")
def test_setup_led_on_string(mock_driver_cls) -> None:
    mock_sensor = MagicMock()
    mock_sensor.ser = MagicMock()
    mock_driver_cls.return_value = mock_sensor

    config = {
        "port": "/dev/serial0",
        "simulation": False,
        "led": "on",
        "metrics": {"occupancy": {"metric_id": 6}},
    }
    sensor = C4002Sensor(device_id=1, config=config)
    run_async(sensor.setup())

    mock_sensor.set_led.assert_called_once_with(run_led=True, out_led=True)
    run_async(sensor.cleanup())


@patch("sensors.c4002_sensor.C4002Driver")
def test_setup_led_off_string(mock_driver_cls) -> None:
    mock_sensor = MagicMock()
    mock_sensor.ser = MagicMock()
    mock_driver_cls.return_value = mock_sensor

    config = {
        "port": "/dev/serial0",
        "simulation": False,
        "led": "off",
        "metrics": {"occupancy": {"metric_id": 6}},
    }
    sensor = C4002Sensor(device_id=1, config=config)
    run_async(sensor.setup())

    mock_sensor.turn_off_leds.assert_called_once()
    run_async(sensor.cleanup())


@patch("sensors.c4002_sensor.C4002Driver")
def test_setup_led_dict(mock_driver_cls) -> None:
    mock_sensor = MagicMock()
    mock_sensor.ser = MagicMock()
    mock_driver_cls.return_value = mock_sensor

    config = {
        "port": "/dev/serial0",
        "simulation": False,
        "led": {"run": "off", "out": "on"},
        "metrics": {"occupancy": {"metric_id": 6}},
    }
    sensor = C4002Sensor(device_id=1, config=config)
    run_async(sensor.setup())

    mock_sensor.set_led.assert_called_once_with(run_led=LED_OFF, out_led=LED_ON)
    run_async(sensor.cleanup())


def test_aggregator_arg_parser() -> None:
    import subprocess

    cmd_help = [sys.executable, "edge/sensor_check/c4002-aggregator.py", "--help"]
    res = subprocess.run(cmd_help, capture_output=True, text=True)
    assert res.returncode == 0
    assert "--led-on" in res.stdout
    assert "--led-off" in res.stdout

    # Test mutually exclusive conflict
    cmd_conflict = [sys.executable, "edge/sensor_check/c4002-aggregator.py", "--led-on", "--led-off"]
    res = subprocess.run(cmd_conflict, capture_output=True, text=True)
    assert res.returncode != 0
    assert "not allowed with argument" in res.stderr


if __name__ == "__main__":
    test_parse_led_mode()
    test_format_led_mode()
    test_setup_led_off_by_default()
    test_setup_led_on_boolean()
    test_setup_led_on_string()
    test_setup_led_off_string()
    test_setup_led_dict()
    test_aggregator_arg_parser()
    print("All C4002 tests passed successfully!")
