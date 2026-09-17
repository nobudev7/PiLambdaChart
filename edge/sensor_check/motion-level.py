#!/usr/bin/env python3
"""
Diagnostic check script for PIR motion sensor.
Polls sensor state and counts HIGH detections in intervals.
"""

from __future__ import annotations

import argparse
import sys
import time


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Count PIR motion sensor HIGH states in polling intervals."
    )
    parser.add_argument(
        "--pin",
        "-p",
        type=int,
        default=23,
        help="BCM GPIO pin number connected to PIR OUT (default: 23)",
    )
    parser.add_argument(
        "--interval",
        "-i",
        type=int,
        default=10,
        help="Polling window in seconds (default: 10)",
    )
    args = parser.parse_args()
    pin_num = args.pin

    try:
        from gpiozero import MotionSensor
    except ImportError:
        print("Error: 'gpiozero' library is not installed in this Python environment.")
        print("Please install it: pip install gpiozero")
        sys.exit(1)

    try:
        pir = MotionSensor(pin_num)
        print(f"Counting HIGH states on GPIO {pin_num} in {args.interval}-second intervals...")
        print("Press Ctrl+C to stop.\n")

        while True:
            high_count = 0
            interval_start = time.time()

            while time.time() - interval_start < args.interval:
                if pir.value == 1:
                    high_count += 1
                time.sleep(0.5)

            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] HIGH states detected in the last {args.interval} seconds: {high_count}")
    except KeyboardInterrupt:
        print("\nProgram stopped by user.")


if __name__ == "__main__":
    main()
