#!/usr/bin/env python3
"""
Diagnostic check script for DFRobot C4002 mmWave radar sensor.

Samples C4002 telemetry at 1 Hz and prints windowed aggregations (occupancy ratio,
average distance, peak motion energy, average light) to verify sensor operation.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time

try:
    from c4002 import C4002Sensor
except ImportError:
    print("Error: 'c4002' library is not installed in this Python environment.")
    print("Please install it from https://github.com/nobudev7/c4002-python")
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check and verify DFRobot C4002 mmWave radar sensor with windowed aggregations."
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
        "--interval",
        type=int,
        default=60,
        help="Aggregation window in seconds (default: 60; use e.g. 10 for quick testing)",
    )
    led_group = parser.add_mutually_exclusive_group()
    led_group.add_argument(
        "--led-on",
        "--led",
        dest="led_on",
        action="store_true",
        default=False,
        help="Turn ON onboard blue RUN and detection LEDs (restore default)",
    )
    led_group.add_argument(
        "--led-off",
        dest="led_off",
        action="store_true",
        default=False,
        help="Turn OFF onboard blue RUN and detection LEDs (dark/stealth mode)",
    )
    args = parser.parse_args()

    if args.led_on:
        led_display = "ON"
    elif args.led_off:
        led_display = "OFF"
    else:
        led_display = "OFF (default stealth mode)"

    print("==========================================================")
    print("      DFRobot C4002 mmWave Radar Diagnostic Check        ")
    print("==========================================================")
    print(f"  • Serial Port       : {args.port}")
    print(f"  • Baudrate          : {args.baudrate}")
    print(f"  • Aggregation Window: {args.interval} seconds")
    print(f"  • Onboard LEDs      : {led_display}")
    print("Press Ctrl+C to stop.\n")

    sensor = C4002Sensor(port=args.port, baudrate=args.baudrate)

    try:
        sensor.connect()

        # Configure onboard LEDs (default: off / stealth mode)
        if hasattr(sensor, "set_led"):
            if args.led_on:
                sensor.set_led(run_led=True, out_led=True)
                time.sleep(0.05)
            else:
                if hasattr(sensor, "turn_off_leds"):
                    sensor.turn_off_leds()
                else:
                    sensor.set_led(run_led=False, out_led=False)
                time.sleep(0.05)

        # Set hardware reporting interval to 1.0s (10 * 100ms)
        if hasattr(sensor, "set_report_period"):
            sensor.set_report_period(10)
            time.sleep(0.1)

        # Flush any stale packets that were buffered before starting
        if sensor.ser and hasattr(sensor.ser, "reset_input_buffer"):
            sensor.ser.reset_input_buffer()

        print("Connected to C4002. Collecting 1-second samples...\n")

        window_samples = []
        window_start = time.time()

        while True:
            # Blocks until the next packet arrives from the sensor (1.0s pacing)
            packet = sensor.read_packet()
            if packet and not getattr(packet, "is_calibrating", False):
                window_samples.append(packet)

            now = time.time()
            elapsed = now - window_start
            if elapsed >= args.interval:
                if window_samples:
                    total_samples = len(window_samples)

                    # 1. Occupancy percentage
                    present_samples = [s for s in window_samples if s.presence_detected]
                    occupancy_pct = round((len(present_samples) / total_samples) * 100.0, 1)

                    # 2. Average distance when occupied
                    if present_samples:
                        avg_distance = round(
                            statistics.mean(s.presence_distance_m for s in present_samples), 2
                        )
                        dist_display = f"{avg_distance:.2f} m"
                    else:
                        dist_display = "Vacant"

                    # 3. Peak motion energy
                    max_motion = max(s.motion_energy for s in window_samples)

                    # 4. Average ambient light
                    avg_light = round(
                        statistics.mean(s.ambient_light_lux for s in window_samples), 1
                    )

                    timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
                    print(
                        f"[{timestamp_str}] Occupancy: {occupancy_pct:5.1f}% | "
                        f"Distance: {dist_display:<8} | "
                        f"Max Motion: {max_motion:3d} | "
                        f"Light: {avg_light:5.1f} Lux ({total_samples} samples)"
                    )

                window_samples.clear()
                window_start = now

    except KeyboardInterrupt:
        print("\nStopping C4002 diagnostic check...")
    finally:
        sensor.close()
        print("Sensor connection closed.")


if __name__ == "__main__":
    main()
