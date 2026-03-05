# CircuitPython to MicroPython Conversion Notes

This document summarizes the changes made when converting from CircuitPython to MicroPython for the Raspberry Pi Pico.

## File Structure Changes

- **CircuitPython**: Main code file is `code.py`
- **MicroPython**: Main code file is `main.py`
- **boot.py**: Both versions use this file, but CircuitPython uses it for USB CDC configuration while MicroPython typically doesn't need it

## Import Changes

| CircuitPython | MicroPython |
|---------------|-------------|
| `import board` | Not needed - use pin numbers directly |
| `import digitalio` | `import machine` |
| `import analogio` | `import machine` |
| `import usb_cdc` | Not needed - standard `print()` uses USB serial |
| `import keypad` | `import machine` (if needed) |

## Pin Configuration

### Digital I/O

**CircuitPython:**
```python
import board
import digitalio

pin = digitalio.DigitalInOut(board.GP13)
pin.direction = digitalio.Direction.OUTPUT
pin.value = True
```

**MicroPython:**
```python
import machine

pin = machine.Pin(13, machine.Pin.OUT)
pin.value(1)
```

### ADC (Analog Input)

**CircuitPython:**
```python
import board
import analogio

adc = analogio.AnalogIn(board.GP26)
raw_value = adc.value
voltage = (raw_value / 65535) * adc.reference_voltage
```

**MicroPython:**
```python
import machine

adc = machine.ADC(26)  # Use pin number directly
raw_value = adc.read_u16()
# Note: reference_voltage not directly available in MicroPython
```

## Key Differences

### 1. Pin Numbering
- **CircuitPython**: Uses `board.GPxx` objects
- **MicroPython**: Uses integer pin numbers directly (e.g., `13` for GP13)

### 2. Setting Pin Values
- **CircuitPython**: `pin.value = True/False`
- **MicroPython**: `pin.value(1/0)` or `pin.value(True/False)`

### 3. ADC Values
- **CircuitPython**: `adc.value` returns 16-bit value (0-65535)
- **MicroPython**: `adc.read_u16()` returns 16-bit value (0-65535)

### 4. Reference Voltage
- **CircuitPython**: `adc.reference_voltage` provides the ADC reference voltage
- **MicroPython**: No built-in property - typically 3.3V on Pico, calculate manually if needed

### 5. USB CDC (Serial Communication)
- **CircuitPython**: Requires `usb_cdc` module and configuration in `boot.py`
- **MicroPython**: Standard `print()` outputs to USB serial automatically

## Mux Control Functions

The multiplexer control logic remains the same, only the pin access syntax changed:

```python
# Setting select lines - same logic, different syntax
mux0_S0.value(b0)  # MicroPython
# vs
mux0_S0.value = b0  # CircuitPython
```

## Timing

Both use the same `time` module:
```python
import time
time.sleep(0.01)  # Works in both
```

## Notes

- MicroPython's `machine` module is more low-level and closer to hardware
- Pin numbers in MicroPython refer to GPIO numbers (GPxx → xx)
- The LSP errors you see when editing MicroPython code are normal - the `machine` module only exists on the device, not on your development machine
