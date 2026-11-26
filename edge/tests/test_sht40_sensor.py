"""
Unit tests for SHT40 I2C temperature and humidity sensor plugin.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# Ensure edge/src is in sys.path
EDGE_SRC = Path(__file__).resolve().parent.parent / "src"
if str(EDGE_SRC) not in sys.path:
    sys.path.insert(0, str(EDGE_SRC))

from sensors import SENSOR_REGISTRY
from sensors.sht40_sensor import Sht40Sensor


def run_async(coro):
    return asyncio.run(coro)


def test_registry_contains_sht40() -> None:
    assert "sht40" in SENSOR_REGISTRY
    assert SENSOR_REGISTRY["sht40"] is Sht40Sensor


def test_parse_i2c_address() -> None:
    assert Sht40Sensor._parse_i2c_address(None) == 0x44
    assert Sht40Sensor._parse_i2c_address(0x44) == 0x44
    assert Sht40Sensor._parse_i2c_address(0x45) == 0x45
    assert Sht40Sensor._parse_i2c_address("0x44") == 0x44
    assert Sht40Sensor._parse_i2c_address("0x45") == 0x45
    assert Sht40Sensor._parse_i2c_address("68") == 0x44

    for invalid in ("not_hex", True, 0x00, 0x80):
        try:
            Sht40Sensor._parse_i2c_address(invalid)
            raise AssertionError(f"Expected ValueError for {invalid!r}")
        except ValueError:
            pass


def test_simulation_mode_read() -> None:
    config = {
        "simulation": True,
        "metrics": {
            "temperature": {"metric_id": 1},
            "humidity": {"metric_id": 2},
        },
    }
    sensor = Sht40Sensor(device_id=4, config=config)
    run_async(sensor.setup())
    assert sensor.simulation_mode is True

    data_points = run_async(sensor.read())
    assert len(data_points) == 2

    by_metric = {dp["metric_id"]: dp for dp in data_points}
    assert set(by_metric.keys()) == {1, 2}

    temp_dp = by_metric[1]
    hum_dp = by_metric[2]
    assert temp_dp["device_id"] == 4
    assert isinstance(temp_dp["value"], float)
    assert 18.0 <= temp_dp["value"] <= 26.0
    assert temp_dp["timestamp"].tzinfo == timezone.utc

    assert hum_dp["device_id"] == 4
    assert isinstance(hum_dp["value"], float)
    assert 35.0 <= hum_dp["value"] <= 65.0
    assert hum_dp["timestamp"] == temp_dp["timestamp"]

    run_async(sensor.cleanup())


def test_partial_metrics_config() -> None:
    temp_only_cfg = {
        "simulation": True,
        "metrics": {"temperature": {"metric_id": 1}},
    }
    temp_sensor = Sht40Sensor(device_id=2, config=temp_only_cfg)
    run_async(temp_sensor.setup())
    temp_points = run_async(temp_sensor.read())
    assert len(temp_points) == 1
    assert temp_points[0]["metric_id"] == 1

    hum_only_cfg = {
        "simulation": True,
        "metrics": {"humidity": {"metric_id": 2}},
    }
    hum_sensor = Sht40Sensor(device_id=2, config=hum_only_cfg)
    run_async(hum_sensor.setup())
    hum_points = run_async(hum_sensor.read())
    assert len(hum_points) == 1
    assert hum_points[0]["metric_id"] == 2


def test_physical_setup_and_read() -> None:
    mock_i2c = MagicMock()
    mock_board = MagicMock()
    mock_board.I2C.return_value = mock_i2c

    mock_hw_sensor = MagicMock()
    # Include 0.0 C edge case to verify non-truthy temperature values are emitted
    mock_hw_sensor.measurements = (0.0, 48.256)

    mock_mode_enum = SimpleNamespace(
        NOHEAT_HIGHPRECISION=0xFD,
        NOHEAT_MEDPRECISION=0xF6,
    )
    mock_sht4x_mod = MagicMock()
    mock_sht4x_mod.Mode = mock_mode_enum
    mock_sht4x_mod.SHT4x.return_value = mock_hw_sensor

    with (
        patch("sensors.sht40_sensor.HAS_SHT40_LIB", True),
        patch("sensors.sht40_sensor.board", mock_board),
        patch("sensors.sht40_sensor.adafruit_sht4x", mock_sht4x_mod),
    ):
        config = {
            "address": "0x44",
            "mode": "NOHEAT_MEDPRECISION",
            "simulation": False,
            "metrics": {
                "temperature": {"metric_id": 1},
                "humidity": {"metric_id": 2},
            },
        }
        sensor = Sht40Sensor(device_id=3, config=config)
        run_async(sensor.setup())

        mock_board.I2C.assert_called_once_with()
        mock_sht4x_mod.SHT4x.assert_called_once_with(mock_i2c, address=0x44)
        assert mock_hw_sensor.mode == mock_mode_enum.NOHEAT_MEDPRECISION
        assert sensor.simulation_mode is False

        points = run_async(sensor.read())
        assert len(points) == 2
        assert points[0]["metric_id"] == 1
        assert points[0]["value"] == 0.0
        assert points[1]["metric_id"] == 2
        assert points[1]["value"] == 48.26

        run_async(sensor.cleanup())
        mock_i2c.deinit.assert_not_called()
        assert sensor.sensor is None


def test_physical_unknown_mode_fallback() -> None:
    mock_i2c = MagicMock()
    mock_board = MagicMock()
    mock_board.I2C.return_value = mock_i2c

    mock_hw_sensor = MagicMock()
    mock_mode_enum = SimpleNamespace(NOHEAT_HIGHPRECISION=0xFD)
    mock_sht4x_mod = MagicMock()
    mock_sht4x_mod.Mode = mock_mode_enum
    mock_sht4x_mod.SHT4x.return_value = mock_hw_sensor

    with (
        patch("sensors.sht40_sensor.HAS_SHT40_LIB", True),
        patch("sensors.sht40_sensor.board", mock_board),
        patch("sensors.sht40_sensor.adafruit_sht4x", mock_sht4x_mod),
    ):
        config = {
            "mode": "INVALID_MODE",
            "simulation": False,
            "metrics": {"temperature": {"metric_id": 1}},
        }
        sensor = Sht40Sensor(device_id=1, config=config)
        run_async(sensor.setup())

        assert mock_hw_sensor.mode == mock_mode_enum.NOHEAT_HIGHPRECISION
        assert sensor.mode_name == "NOHEAT_HIGHPRECISION"


def test_physical_init_failure_fallback() -> None:
    mock_board = MagicMock()
    mock_board.I2C.return_value = MagicMock()
    mock_sht4x_mod = MagicMock()
    mock_sht4x_mod.SHT4x.side_effect = OSError("Remote I/O error")

    with (
        patch("sensors.sht40_sensor.HAS_SHT40_LIB", True),
        patch("sensors.sht40_sensor.board", mock_board),
        patch("sensors.sht40_sensor.adafruit_sht4x", mock_sht4x_mod),
    ):
        config = {
            "simulation": False,
            "metrics": {
                "temperature": {"metric_id": 1},
                "humidity": {"metric_id": 2},
            },
        }
        sensor = Sht40Sensor(device_id=1, config=config)
        run_async(sensor.setup())

        assert sensor.simulation_mode is True
        assert sensor.sensor is None

        points = run_async(sensor.read())
        assert len(points) == 2


def test_physical_read_error_returns_empty() -> None:
    mock_board = MagicMock()
    mock_board.I2C.return_value = MagicMock()

    class BrokenSht40:
        mode = None

        @property
        def measurements(self):
            raise OSError("I2C read failed")

    mock_sht4x_mod = MagicMock()
    mock_sht4x_mod.Mode = SimpleNamespace(NOHEAT_HIGHPRECISION=0xFD)
    mock_sht4x_mod.SHT4x.return_value = BrokenSht40()

    with (
        patch("sensors.sht40_sensor.HAS_SHT40_LIB", True),
        patch("sensors.sht40_sensor.board", mock_board),
        patch("sensors.sht40_sensor.adafruit_sht4x", mock_sht4x_mod),
    ):
        config = {
            "simulation": False,
            "metrics": {
                "temperature": {"metric_id": 1},
                "humidity": {"metric_id": 2},
            },
        }
        sensor = Sht40Sensor(device_id=1, config=config)
        run_async(sensor.setup())

        points = run_async(sensor.read())
        assert points == []


if __name__ == "__main__":
    test_registry_contains_sht40()
    test_parse_i2c_address()
    test_simulation_mode_read()
    test_partial_metrics_config()
    test_physical_setup_and_read()
    test_physical_unknown_mode_fallback()
    test_physical_init_failure_fallback()
    test_physical_read_error_returns_empty()
    print("All SHT40 tests passed successfully!")
