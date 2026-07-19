from gpiozero import MotionSensor
from signal import pause
import time
import threading

# Detection mode = H
# Delay = minimum (all the way counter-clock wise)

# Adjust the pin number to match your wiring (e.g., GPIO 4)
pir = MotionSensor(23)
trigger_count = 0
start_time = time.time()

# Create a lock to protect shared variables
counter_lock = threading.Lock()

def motion_triggered():
    global trigger_count
    # Securely increment the count
    with counter_lock:
        trigger_count += 1

def monitor_triggers():
    global trigger_count, start_time
    while True:
        time.sleep(60)  # Monitor over a 1-minute interval
        current_time = time.time()

        # Securely read and reset the count
        with counter_lock:
            current_count = trigger_count
            trigger_count = 0

        elapsed_min = (current_time - start_time) / 60
        print(f"Triggers in the last minute: {current_count}")

        start_time = current_time

# Attach callback to sensor
pir.when_motion = motion_triggered

# Start monitoring in a background loop
monitor_thread = threading.Thread(target=monitor_triggers, daemon=True)
monitor_thread.start()

print("Motion sensor monitoring started. Counting triggers per minute...")
pause()
