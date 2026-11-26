"""
Unit tests for sensor_check command-line argument parsers.
"""

from __future__ import annotations

import subprocess
import sys


def test_dht_arg_parser() -> None:
    res = subprocess.run([sys.executable, "edge/sensor_check/dht.py", "--help"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "--pin" in res.stdout
    assert "-p PIN" in res.stdout
    assert "--type" in res.stdout
    assert "default: 24" in res.stdout

    # Reject positional pin argument
    res_pos = subprocess.run([sys.executable, "edge/sensor_check/dht.py", "24"], capture_output=True, text=True)
    assert res_pos.returncode != 0
    assert "unrecognized arguments" in res_pos.stderr


def test_motion_arg_parser() -> None:
    res = subprocess.run([sys.executable, "edge/sensor_check/motion.py", "--help"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "--pin" in res.stdout
    assert "-p PIN" in res.stdout
    assert "default: 23" in res.stdout

    # Reject positional pin argument
    res_pos = subprocess.run([sys.executable, "edge/sensor_check/motion.py", "23"], capture_output=True, text=True)
    assert res_pos.returncode != 0
    assert "unrecognized arguments" in res_pos.stderr


def test_motion_count_arg_parser() -> None:
    res = subprocess.run([sys.executable, "edge/sensor_check/motion-count.py", "--help"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "--pin" in res.stdout
    assert "-p PIN" in res.stdout
    assert "--interval" in res.stdout
    assert "default: 23" in res.stdout

    # Reject positional pin argument
    res_pos = subprocess.run([sys.executable, "edge/sensor_check/motion-count.py", "23"], capture_output=True, text=True)
    assert res_pos.returncode != 0
    assert "unrecognized arguments" in res_pos.stderr


def test_motion_level_arg_parser() -> None:
    res = subprocess.run([sys.executable, "edge/sensor_check/motion-level.py", "--help"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "--pin" in res.stdout
    assert "-p PIN" in res.stdout
    assert "--interval" in res.stdout
    assert "default: 23" in res.stdout

    # Reject positional pin argument
    res_pos = subprocess.run([sys.executable, "edge/sensor_check/motion-level.py", "23"], capture_output=True, text=True)
    assert res_pos.returncode != 0
    assert "unrecognized arguments" in res_pos.stderr


def test_sht40_arg_parser() -> None:
    res = subprocess.run([sys.executable, "edge/sensor_check/sht40.py", "--help"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "--address" in res.stdout
    assert "-a ADDRESS" in res.stdout
    assert "--interval" in res.stdout
    assert "--mode" in res.stdout
    assert "0x44" in res.stdout

    # Reject invalid interval
    res_interval = subprocess.run(
        [sys.executable, "edge/sensor_check/sht40.py", "--interval", "0"], capture_output=True, text=True
    )
    assert res_interval.returncode != 0

    # Reject out-of-range I2C address
    res_addr = subprocess.run(
        [sys.executable, "edge/sensor_check/sht40.py", "--address", "0x99"], capture_output=True, text=True
    )
    assert res_addr.returncode != 0

    # Reject unknown mode
    res_mode = subprocess.run(
        [sys.executable, "edge/sensor_check/sht40.py", "--mode", "BOGUS"], capture_output=True, text=True
    )
    assert res_mode.returncode != 0

    # Reject unexpected positional argument
    res_pos = subprocess.run(
        [sys.executable, "edge/sensor_check/sht40.py", "0x44"], capture_output=True, text=True
    )
    assert res_pos.returncode != 0
    assert "unrecognized arguments" in res_pos.stderr


if __name__ == "__main__":
    test_dht_arg_parser()
    test_motion_arg_parser()
    test_motion_count_arg_parser()
    test_motion_level_arg_parser()
    test_sht40_arg_parser()
    print("All sensor_check arg parser tests passed successfully!")
