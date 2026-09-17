# Raspberry Pi I2C Configuration Guide

This guide provides detailed instructions for enabling, configuring, and verifying the **I2C (Inter-Integrated Circuit)** interface on Raspberry Pi edge devices running Raspberry Pi OS.

In the PiLambdaChart architecture, the **BH1750 ambient light sensor** communicates over the I2C bus. Because I2C is disabled by default on Raspberry Pi OS, it must be enabled before running the diagnostic check (`sensor_check/bh1750.py`) or starting the edge agent (`agent.py`).

---

## Hardware Pinout for BH1750

The Raspberry Pi exposes the primary I2C bus (**I2C-1**) on the first few pins of its 40-pin GPIO header:

| BH1750 Pin | Raspberry Pi Pin | Pin Function | Header Position |
| :--- | :--- | :--- | :--- |
| **VCC** | Pin 1 | 3.3V Power | Top Left |
| **GND** | Pin 6 or 9 | Ground | Header Ground |
| **SCL** | Pin 5 | GPIO 3 (I2C1 SCL) | Clock Line |
| **SDA** | Pin 3 | GPIO 2 (I2C1 SDA) | Data Line |
| **ADDR** | *(Floating or GND)* | Address Select | GND = `0x23` / 3.3V = `0x5c` |

> [!IMPORTANT]
> Always power the BH1750 module from the **3.3V** pin (Pin 1), not 5V. Raspberry Pi GPIO pins are 3.3V logic; supplying 5V to the I2C lines can damage the Raspberry Pi SoC.

---

## Enabling I2C

Choose one of the following methods to enable the I2C interface:

### Method 1: Fast One-Liner (Recommended)

Run the non-interactive `raspi-config` command from the terminal:

```bash
sudo raspi-config nonint do_i2c 0
```
*(In `raspi-config`, parameter `0` enables the interface).*

#### Does the one-liner require a reboot?
**Usually no.** On modern Raspberry Pi OS releases (Debian Bullseye and Debian Bookworm), `raspi-config` does two things:
1. **Dynamic Runtime Activation**: It immediately loads the `i2c-dev` kernel module and applies the runtime Device Tree overlay.
2. **Boot Persistence**: It adds `dtparam=i2c_arm=on` to your boot configuration and registers `i2c-dev` in `/etc/modules`.

Verify immediately with `ls -l /dev/i2c*`. If `/dev/i2c-1` appears, you can start using sensors right away without rebooting. If `/dev/i2c-1` does not appear, reboot once (`sudo reboot`).

---

### Method 2: Interactive Menu (`raspi-config`)

1. Open the configuration tool:
   ```bash
   sudo raspi-config
   ```
2. Use the arrow keys to navigate to **Interface Options** (or **Interfacing Options** on legacy releases).
3. Select **I2C**.
4. When prompted `"Would you like the ARM I2C interface to be enabled?"`, choose **\<Yes\>**.
5. Select **\<Ok\>**, then select **Finish**. Reboot if prompted (`sudo reboot`).

---

### Method 3: Manual Configuration (`config.txt`)

For headless provisioning or when editing the SD card directly from another computer:

1. Open the boot configuration file for your OS release:
   - **Raspberry Pi OS Bookworm (Pi 5 & recent releases)**:
     ```bash
     sudo nano /boot/firmware/config.txt
     ```
   - **Raspberry Pi OS Bullseye or earlier (Pi 1–4, Zero)**:
     ```bash
     sudo nano /boot/config.txt
     ```

2. Ensure the following line is present and uncommented:
   ```ini
   dtparam=i2c_arm=on
   ```

3. Ensure the `i2c-dev` kernel module loads on boot:
   ```bash
   echo "i2c-dev" | sudo tee -a /etc/modules
   ```

4. Reboot the Raspberry Pi:
   ```bash
   sudo reboot
   ```

---

## Verifying I2C & Detecting Sensors

### Step 1: Install `i2c-tools`
The `i2c-tools` package provides diagnostic commands such as `i2cdetect`:

```bash
sudo apt update && sudo apt install -y i2c-tools
```

### Step 2: Confirm the Device Node Exists
```bash
ls -l /dev/i2c*
```
Expected output:
```text
crw-rw---- 1 root i2c 89, 1 Sep 16 20:00 /dev/i2c-1
```

### Step 3: Scan the I2C Bus with `i2cdetect`
Scan the I2C bus (`bus 1` on modern Raspberry Pis):

```bash
sudo i2cdetect -y 1
```

If the BH1750 sensor is wired correctly, its 7-bit hex address will appear in the grid:
- **`0x23`**: Default address when the `ADDR` pin is connected to Ground or left floating.
- **`0x5c`**: Alternative address when the `ADDR` pin is pulled high to 3.3V.

Example output:
```text
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:                         -- -- -- -- -- -- -- -- 
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
20: -- -- -- 23 -- -- -- -- -- -- -- -- -- -- -- -- 
30: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
40: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
50: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
70: -- -- -- -- -- -- -- --                         
```

### Step 4: Run the Diagnostic Script
Run the standalone hardware test script located in `edge/sensor_check/`:

```bash
python sensor_check/bh1750.py
```
Expected output:
```text
235.50 Lux
236.10 Lux
234.80 Lux
```

---

## Troubleshooting

### 1. `FileNotFoundError: [Errno 2] No such file or directory: '/dev/i2c-1'`
- **Cause**: The I2C kernel module or device tree parameter is not active.
- **Fix**:
  1. Run `sudo raspi-config nonint do_i2c 0`.
  2. Run `sudo modprobe i2c-dev`.
  3. If the node still does not appear, reboot the Pi: `sudo reboot`.

### 2. `i2cdetect` shows only dashes (`--`) and no addresses
- **Wiring**: Check jumper wires connected to Pin 1 (3.3V), Pin 6 (GND), Pin 3 (SDA), and Pin 5 (SCL).
- **Loose Connections**: Breadboard jump wires often have loose pins. Reseat all wires.
- **Faulty Sensor**: Test with a secondary BH1750 breakout board if available.

### 3. `Permission denied: '/dev/i2c-1'`
- **Cause**: Current user does not belong to the `i2c` user group.
- **Fix**: Add your user to the `i2c` group and re-login:
  ```bash
  sudo usermod -a -G i2c $USER
  ```
