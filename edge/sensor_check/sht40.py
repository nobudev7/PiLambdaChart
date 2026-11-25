#!/usr/bin/env python3
"""
Diagnostic check script for Sensirion SHT40 I2C temperature and humidity sensor.
"""

from __future__ import annotations

import argparse
import sys
import time

VALID_MODES = [
    "NOHEAT_HIGHPRECISION",
    "NOHEAT_MEDPRECISION",
    "NOHEAT_LOWPRECISION",
    "HIGHHEAT_1S",
    "HIGHHEAT_100MS",
    "MEDHEAT_1S",
    "MEDHEAT_100MS",
    "LOWHEAT_1S",
    "LOWHEAT_100MS",
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check and verify Sensirion SHT40 I2C temperature and humidity sensor."
    )
    parser.add_argument(
        "--address",
        "-a",
        default="0x44",
        help="I2C address in hex or decimal (default: 0x44)",
    )
    parser.add_argument(
        "--interval",
        "-i",
        type=float,
        default=2.0,
        help="Polling interval in seconds (default: 2.0)",
    )
    parser.add_argument(
        "--mode",
        "-m",
        type=str.upper,
        choices=VALID_MODES,
        default="NOHEAT_HIGHPRECISION",
        help="SHT40 precision/heater mode (default: NOHEAT_HIGHPRECISION)",
    )
    args = parser.parse_args()

    try:
        address = int(args.address, 0)
    except ValueError:
        parser.error(f"invalid I2C address: '{args.address}'")
    if not (0x03 <= address <= 0x77):
        parser.error(f"I2C address 0x{address:02x} out of valid 7-bit range (0x03..0x77)")
    if args.interval <= 0:
        parser.error("--interval must be greater than 0")

    try:
        import board
        import adafruit_sht4x
    except ImportError:
        print("Error: 'adafruit-circuitpython-sht4x' and 'board' libraries are required.")
        print("Please install them: pip install adafruit-circuitpython-sht4x")
        sys.exit(1)

    i2c = board.I2C()  # uses board.SCL and board.SDA
    sensor = adafruit_sht4x.SHT4x(i2c, address=address)
    sensor.mode = getattr(adafruit_sht4x.Mode, args.mode)

    serial_str = "unknown"
    try:
        serial_num = getattr(sensor, "serial_number", None)
        if serial_num is not None:
            serial_str = hex(serial_num)
    except Exception:
        pass

    print(
        f"Reading SHT40 sensor at I2C 0x{address:02x} "
        f"(mode={args.mode}, interval={args.interval}s, serial={serial_str})..."
    )
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            try:
                temperature_c, humidity = sensor.measurements
                temperature_f = temperature_c * (9 / 5) + 32
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                print(
                    f"[{timestamp}] Temp={temperature_c:0.2f}°C, "
                    f"Temp={temperature_f:0.2f}°F, "
                    f"Humidity={humidity:0.2f}%"
                )
            except (OSError, RuntimeError) as error:
                print(f"Read error: {error}")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nProgram stopped by user.")


if __name__ == "__main__":
    main()
