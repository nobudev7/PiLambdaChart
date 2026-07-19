import time
import board
import adafruit_bh1750

i2c = board.I2C()  # uses board.SCL and board.SDA
# i2c = board.STEMMA_I2C() # For using the built-in STEMMA QT connector on a microcontroller

sensor = adafruit_bh1750.BH1750(i2c)

try:
    while True:
        print(f"{sensor.lux:.2f} Lux")
        time.sleep(1)
except KeyboardInterrupt:
    print("\nProgram stopped by user.")
