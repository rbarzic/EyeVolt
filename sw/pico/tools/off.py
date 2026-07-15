#!/usr/bin/env python3
"""Set all EyeVolt generator outputs to 0 V at once.

Sends OFFALL, which (in firmware) stops any running waveform and then zeros all
8 DAC channels. The serial port is auto-detected; override it as the first
argument.

    ./off.py                 # auto-detect the EyeVolt board
    ./off.py /dev/ttyACM1    # explicit port
"""

import glob
import sys
import time

import serial


def find_port():
    for pattern in ("/dev/serial/by-id/usb-EyeVolt_*",
                    "/dev/serial/by-id/usb-Raspberry_Pi_Pico_*"):
        matches = sorted(glob.glob(pattern))
        if matches:
            return matches[0]
    return "/dev/ttyACM0"


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else find_port()
    s = serial.Serial(port, 9600, timeout=1)
    try:
        time.sleep(0.2)
        s.reset_input_buffer()
        s.write(b"OFFALL\n")
        s.flush()
        deadline = time.time() + 2
        while time.time() < deadline:
            line = s.read_until(b"\n").decode(errors="replace").strip()
            if line.startswith(("OK", "ERROR")):
                print(f"{port}: {line}")
                return
        print(f"{port}: (no reply)")
    finally:
        s.close()


if __name__ == "__main__":
    main()
