import board  # pyright: ignore

# import machine
import digitalio  # pyright: ignore
import analogio
import time

import keypad  # pyright: ignore
import usb_cdc

ADC_PIN0 = board.GP26
ADC_PIN1 = board.GP27

# MUX 0 Pins
mux0_eb = digitalio.DigitalInOut(board.GP13)
mux0_eb.direction = digitalio.Direction.OUTPUT
mux0_eb.value = True # Initialize enable pin high (disabled, assuming active low)

mux0_S0 = digitalio.DigitalInOut(board.GP10)
mux0_S0.direction = digitalio.Direction.OUTPUT

mux0_S1 = digitalio.DigitalInOut(board.GP11)
mux0_S1.direction = digitalio.Direction.OUTPUT

mux0_S2 = digitalio.DigitalInOut(board.GP12)
mux0_S2.direction = digitalio.Direction.OUTPUT

# MUX 1 Pins
mux1_eb = digitalio.DigitalInOut(board.GP18)
mux1_eb.direction = digitalio.Direction.OUTPUT
mux1_eb.value = True # Initialize enable pin high (disabled, assuming active low)

mux1_S0 = digitalio.DigitalInOut(board.GP21)
mux1_S0.direction = digitalio.Direction.OUTPUT

mux1_S1 = digitalio.DigitalInOut(board.GP20)
mux1_S1.direction = digitalio.Direction.OUTPUT

mux1_S2 = digitalio.DigitalInOut(board.GP19)
mux1_S2.direction = digitalio.Direction.OUTPUT


def mux0(channel):
  """Sets the channel for MUX 0 and enables it (active low)."""
  # Extract bits for select lines
  b0 = bool(channel & 1)      # LSB
  b1 = bool((channel & 2) >> 1)
  b2 = bool((channel & 4) >> 2) # MSB

  # Set select pins
  # In CircuitPython digitalio, True is HIGH (1), False is LOW (0)
  mux0_S0.value = b0
  mux0_S1.value = b1
  mux0_S2.value = b2

  # Enable the multiplexer (assuming active low enable)
  mux0_eb.value = False
  # Optional small delay if needed for signal settling
  # time.sleep(0.00001) # 10 microseconds

def mux1(channel):
  """Sets the channel for MUX 1 and enables it (active low)."""
  # Extract bits for select lines
  b0 = bool(channel & 1)      # LSB
  b1 = bool((channel & 2) >> 1)
  b2 = bool((channel & 4) >> 2) # MSB

  # Set select pins
  mux1_S0.value = b0
  mux1_S1.value = b1
  mux1_S2.value = b2

  # Enable the multiplexer (assuming active low enable)
  mux1_eb.value = False
  # Optional small delay
  # time.sleep(0.00001) # 10 microseconds

def disable_mux0():
    """Disables MUX 0 (assuming active low enable)."""
    mux0_eb.value = True

def disable_mux1():
    """Disables MUX 1 (assuming active low enable)."""
    mux1_eb.value = True








data_channel = usb_cdc.data
data_channel.reset_input_buffer()


try:
    adc0 = analogio.AnalogIn(ADC_PIN0)
    adc1 = analogio.AnalogIn(ADC_PIN1)
except Exception as e:
    print(f"Error initializing ADC: {e}")

print(f"-I- ADC initialized (Vref={adc0.reference_voltage})")

mux0(0)
mux1(0)

i = 0
voltage0 = [0,0,0,0,0,0,0,0]
voltage1 = [0,0,0,0]
while True:

    raw_value1 = adc1.value
    for j in range(0,8):
        mux0(j)
        time.sleep(0.01)
        raw_value0 = adc0.value
        # voltage0[j] = (raw_value0 / 65535) * adc0.reference_voltage
        voltage0[j] = raw_value0


    for j in range(0,4):
        mux1(j)
        time.sleep(0.01)
        raw_value1 = adc1.value
        # voltage0[j] = (raw_value0 / 65535) * adc0.reference_voltage
        voltage1[j] = raw_value1


    #voltage1 = (raw_value1 / 65535) * adc1.reference_voltage

    #print(f"Raw ADC0 Value: {raw_value0:05} | Voltage: {voltage0:.2f} V")
    #print(f"Raw ADC1 Value: {raw_value1:05} | Voltage: {voltage1:.2f} V")
    v = voltage0
    print(f"1::{v[0]:05} {v[1]:05} {v[2]:05} {v[3]:05} {v[4]:05} {v[5]:05} {v[6]:05} {v[7]:05}")
    v = voltage1
    print(f"2::{v[0]:05} {v[1]:05} {v[2]:05} {v[3]:05}")


    i = i + 1
