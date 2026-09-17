#!/usr/bin/env python3
"""
Environmental background noise calibration utility for DFRobot C4002 mmWave radar sensor.

Triggers automatic background calibration to measure stationary radar reflections
(walls, monitors, curtains, fans) and sets dynamic noise thresholds to eliminate
false presence detection.
"""

from __future__ import annotations

import argparse
import sys
import time

try:
    from c4002 import C4002Sensor
except ImportError:
    print("Error: 'c4002' library is not installed in this Python environment.")
    print("Please install it: pip install c4002-python")
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run automated environmental background noise calibration for DFRobot C4002 sensor."
    )
    parser.add_argument(
        "--port",
        default="/dev/serial0",
        help="Serial port path (default: /dev/serial0)",
    )
    parser.add_argument(
        "--baudrate",
        type=int,
        default=115200,
        help="Serial baud rate (default: 115200)",
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=10,
        help="Delay time in seconds before calibration begins (time to exit room; default: 10)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Duration of background noise measurement in seconds (default: 30; minimum: 15)",
    )
    args = parser.parse_args()

    if args.delay < 0:
        parser.error("--delay must be non-negative")
    if args.duration < 15:
        parser.error("--duration must be at least 15 seconds")

    total_time = args.delay + args.duration

    print("==========================================================")
    print("      DFRobot C4002 Environmental Calibration Utility     ")
    print("==========================================================")
    print(f"  • Serial Port       : {args.port}")
    print(f"  • Baudrate          : {args.baudrate}")
    print(f"  • Delay Time        : {args.delay} seconds (time to exit the room)")
    print(f"  • Calibration Time  : {args.duration} seconds (measuring background noise)")
    print(f"  • Total Duration    : {total_time} seconds")
    print()
    print("⚠️  PLEASE LEAVE THE ROOM IMMEDIATELY!")
    print("   Ensure the sensor has an unobstructed view and no persons are nearby.")
    print("   Press Ctrl+C to cancel.\n")

    sensor = C4002Sensor(port=args.port, baudrate=args.baudrate)

    try:
        sensor.connect()
        print("Connected to sensor. Initiating calibration sequence...\n")

        # Flush any stale packets that were buffered before starting
        if sensor.ser and hasattr(sensor.ser, "reset_input_buffer"):
            sensor.ser.reset_input_buffer()

        sensor.start_env_calibration(delay_time=args.delay, cont_time=args.duration)

        last_countdown = None

        while True:
            packet = sensor.read_packet()
            if packet and getattr(packet, "is_calibrating", False):
                cd = packet.countdown_s
                if cd != last_countdown:
                    last_countdown = cd
                    timestamp = time.strftime("%H:%M:%S")
                    print(f"[{timestamp}] Calibration countdown: {cd:2d} seconds remaining...")

                if cd == 0:
                    print()
                    print("✅ Calibration complete! Sensor has stored the room's noise floor.")
                    print("   Run 'python sensor_check/c4002-aggregator.py' to test detection.")
                    break

    except KeyboardInterrupt:
        print("\nCalibration cancelled by user.")
    finally:
        sensor.close()
        print("Sensor connection closed.")


if __name__ == "__main__":
    main()
