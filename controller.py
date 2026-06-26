# Geometry Dash controller for Raspberry Pi Pico W (CircuitPython)
# ----------------------------------------------------------------
# Physical jump (accelerometer)  -> quick SPACE tap   (cube / ball / UFO)
# Joystick pushed UP (held)      -> sustained SPACE    (ship / wave / robot)
# Joystick LEFT / RIGHT          -> arrow keys         (menu scrolling)
#
# The two "jump" inputs are OR'd together: space is down if you're
# mid-jump OR the joystick is held up. So either works in ship sections.
#
# Assumes:  MPU6050 accelerometer on I2C0, standard analog joystick.
# If your parts differ, only the two "SETUP" blocks below need changing.

import time
import math
import board
import busio
import analogio
import digitalio
import usb_hid

from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keycode import Keycode
import adafruit_mpu6050

# ---------------------------------------------------------------- HID
kbd = Keyboard(usb_hid.devices)

# ---------------------------------------------------------------- SETUP: accelerometer
# MPU6050:  VCC->3V3  GND->GND  SDA->GP4  SCL->GP5
i2c = busio.I2C(scl=board.GP5, sda=board.GP4)
mpu = adafruit_mpu6050.MPU6050(i2c)

# ---------------------------------------------------------------- SETUP: joystick
# Joystick: VCC->3V3  GND->GND  VRy->GP26(ADC0)  VRx->GP27(ADC1)  SW->GP16
joy_y = analogio.AnalogIn(board.GP26)   # vertical  -> ship control
joy_x = analogio.AnalogIn(board.GP27)   # horizontal-> menu scroll
joy_btn = digitalio.DigitalInOut(board.GP16)
joy_btn.direction = digitalio.Direction.INPUT
joy_btn.pull = digitalio.Pull.UP

# ---------------------------------------------------------------- TUNABLES
JUMP_G        = 1.7     # accel magnitude (g) that counts as a jump push-off
JUMP_HOLD     = 0.08    # seconds to hold SPACE for one detected jump
JUMP_COOLDOWN = 0.40    # min seconds between jumps (ignores the landing spike)

JOY_UP_THRESH   = 12000 # how far up before "ship climb" engages (0..32767)
JOY_SIDE_THRESH = 12000 # how far sideways before a menu arrow fires
JOY_INVERT_Y    = False # set True if pushing up does NOT trigger climb

G = 9.80665             # 1 g in m/s^2

# ---------------------------------------------------------------- CENTERING
# Leave the joystick centered when the board powers on.
time.sleep(0.3)
center_x = joy_x.value
center_y = joy_y.value

# ---------------------------------------------------------------- STATE
last_jump   = 0.0
jump_until  = 0.0
space_down  = False
left_down   = False
right_down  = False


def set_key(want_down, currently_down, keycode):
    """Press/release a key only on a change of state."""
    if want_down and not currently_down:
        kbd.press(keycode)
    elif (not want_down) and currently_down:
        kbd.release(keycode)
    return want_down


while True:
    now = time.monotonic()

    # --- Accelerometer: detect a physical jump (push-off spike) ---------
    ax, ay, az = mpu.acceleration                 # m/s^2
    mag_g = math.sqrt(ax * ax + ay * ay + az * az) / G
    if mag_g > JUMP_G and (now - last_jump) > JUMP_COOLDOWN:
        last_jump  = now
        jump_until = now + JUMP_HOLD
    accel_jump = now < jump_until

    # --- Joystick vertical: sustained hold for ship / wave -------------
    dy = joy_y.value - center_y
    if JOY_INVERT_Y:
        dy = -dy
    joy_up = dy > JOY_UP_THRESH

    # --- Combine into the single GD action button ----------------------
    space_down = set_key(accel_jump or joy_up, space_down, Keycode.SPACE)

    # --- Joystick horizontal: menu scrolling ---------------------------
    dx = joy_x.value - center_x
    right_down = set_key(dx >  JOY_SIDE_THRESH, right_down, Keycode.RIGHT_ARROW)
    left_down  = set_key(dx < -JOY_SIDE_THRESH, left_down,  Keycode.LEFT_ARROW)

    time.sleep(0.002)   # ~500 Hz loop; plenty fast for GD timing