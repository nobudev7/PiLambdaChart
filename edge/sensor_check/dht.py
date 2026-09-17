#!/usr/bin/env python3
"""
Diagnostic check script for DHT11 / DHT22 temperature and humidity sensor.
"""

from __future__ import annotations

import argparse
import sys
import time


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check and verify DHT11/DHT22 temperature and humidity sensor."
    )
    parser.add_argument(
        "--pin",
        "-p",
        type=int,
        default=24,
        help="BCM GPIO pin number (default: 24)",
    )
    parser.add_argument(
        "--type",
        "-t",
        choices=["DHT22", "DHT11", "dht22", "dht11"],
        default="DHT22",
        help="DHT sensor model: DHT22 or DHT11 (default: DHT22)",
    )
    args = parser.parse_args()
    pin_num = args.pin
    sensor_model = args.type.upper()

    try:
        import board
        import adafruit_dht
    except ImportError:
        print("Error: 'adafruit-circuitpython-dht' and 'board' libraries are required.")
        print("Please install them: pip install adafruit-circuitpython-dht")
        sys.exit(1)

    pin_attr = f"D{pin_num}"
    if not hasattr(board, pin_attr):
        print(f"Error: Pin '{pin_attr}' not found on board module.")
        sys.exit(1)

    board_pin = getattr(board, pin_attr)
    if sensor_model == "DHT11":
        sensor = adafruit_dht.DHT11(board_pin)
    else:
        sensor = adafruit_dht.DHT22(board_pin)

    print(f"Reading {sensor_model} sensor on GPIO {pin_num} (board.{pin_attr})...")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            try:
                temperature_c = sensor.temperature
                if temperature_c is not None:
                    temperature_f = temperature_c * (9 / 5) + 32
                    humidity = sensor.humidity
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                    print(
                        f"[{timestamp}] Temp={temperature_c:0.1f}ºC, "
                        f"Temp={temperature_f:0.1f}ºF, "
                        f"Humidity={humidity:0.1f}%"
                    )
            except RuntimeError as error:
                # Errors happen fairly often, DHT's are hard to read, just keep going
                print(f"Read error: {error.args[0]}")
                time.sleep(2.0)
                continue
            except Exception as error:
                sensor.exit()
                raise error

            time.sleep(3.0)
    except KeyboardInterrupt:
        print("\nProgram stopped by user.")
    finally:
        sensor.exit()


if __name__ == "__main__":
    main()