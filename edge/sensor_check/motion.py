#!/usr/bin/env python3
"""
Diagnostic check script for PIR motion sensor.
Listens for real-time motion and clear events.
"""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Listen for real-time PIR motion events."
    )
    parser.add_argument(
        "--pin",
        "-p",
        type=int,
        default=23,
        help="BCM GPIO pin number connected to PIR OUT (default: 23)",
    )
    args = parser.parse_args()
    pin_num = args.pin

    try:
        from gpiozero import MotionSensor
        from signal import pause
    except ImportError:
        print("Error: 'gpiozero' library is not installed in this Python environment.")
        print("Please install it: pip install gpiozero")
        sys.exit(1)

    def motion_detected() -> None:
        print("Motion detected!")

    def motion_stopped() -> None:
        print("Area is clear.")

    try:
        pir = MotionSensor(pin_num)
        pir.when_motion = motion_detected
        pir.when_no_motion = motion_stopped

        print(f"PIR Sensor initializing on GPIO {pin_num}... Please wait.")
        print("Press Ctrl+C to stop.\n")
        pause()
    except KeyboardInterrupt:
        print("\nProgram stopped by user.")


if __name__ == "__main__":
    main()
