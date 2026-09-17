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


if __name__ == "__main__":
    test_dht_arg_parser()
    test_motion_arg_parser()
    test_motion_count_arg_parser()
    test_motion_level_arg_parser()
    print("All sensor_check arg parser tests passed successfully!")
