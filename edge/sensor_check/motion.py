from gpiozero import MotionSensor
from signal import pause

# Initialize the sensor on GPIO 23
pir = MotionSensor(23)

def motion_detected():
    print("Motion detected!")

def motion_stopped():
    print("Area is clear.")

# Assign callback functions to events
pir.when_motion = motion_detected
pir.when_no_motion = motion_stopped

print("PIR Sensor Initializing... Please wait.")
# Keep the program running to listen for events
pause()
