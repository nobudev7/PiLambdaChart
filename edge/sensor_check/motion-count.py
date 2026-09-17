#!/usr/bin/env python3
"""
Diagnostic check script for PIR motion sensor.
Monitors motion events and counts triggers over interval windows.
"""

from __future__ import annotations

import argparse
import sys
import threading
import time


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Monitor PIR motion sensor and count triggers per interval."
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
        default=60,
        help="Monitoring window in seconds (default: 60)",
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

    trigger_count = 0
    start_time = time.time()
    counter_lock = threading.Lock()

    def motion_triggered() -> None:
        nonlocal trigger_count
        with counter_lock:
            trigger_count += 1

    def monitor_triggers() -> None:
        nonlocal trigger_count, start_time
        while True:
            time.sleep(args.interval)
            current_time = time.time()
            with counter_lock:
                current_count = trigger_count
                trigger_count = 0

            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] Triggers in the last {args.interval}s: {current_count}")
            start_time = current_time

    try:
        pir = MotionSensor(pin_num)
        pir.when_motion = motion_triggered

        monitor_thread = threading.Thread(target=monitor_triggers, daemon=True)
        monitor_thread.start()

        print(f"Motion sensor monitoring started on GPIO {pin_num} (window: {args.interval}s).")
        print("Press Ctrl+C to stop.\n")
        pause()
    except KeyboardInterrupt:
        print("\nProgram stopped by user.")


if __name__ == "__main__":
    main()
