from gpiozero import MotionSensor
import time

# Adjust the pin number to match your wiring (e.g., GPIO 4)
pir = MotionSensor(23)

def count_motion():
    print("Program started. Counting HIGH states in 10-second intervals...")

    while True:
        high_count = 0
        interval_start = time.time()

        # Run the polling loop for exactly 10 seconds
        while time.time() - interval_start < 10:
            if pir.value == 1:
                high_count += 1

            # Poll every half second (0.5 seconds)
            time.sleep(0.5)

        # Generate a readable timestamp for the end of the interval
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] HIGH states detected in the last 10 seconds: {high_count}")

# Run the counter loop
try:
    count_motion()
except KeyboardInterrupt:
    print("\nProgram stopped by user.")
