#!/usr/bin/env python3
"""Upload a binary waveform to the EyeVolt Pico and optionally play it.

Reads the .bin produced by pwl_to_waveform.py, sends it with the
WFLOAD/WFREADY/binary/ack handshake, verifies the firmware checksum against a
locally computed one, then optionally starts playback.

The active-channel mask is read from the companion <name>.meta sidecar written
by pwl_to_waveform.py; override it with --mask, or it defaults to 0xFF.
"""

import argparse
import json
import os
import struct
import sys
import time

try:
    import serial
except ImportError:
    sys.exit("error: pyserial not installed (pip install pyserial)")

CH_BYTES = 8 * 2  # 8 channels × uint16


def load_mask(binfile, override):
    if override is not None:
        return int(override, 0)
    meta_path = os.path.splitext(binfile)[0] + ".meta"
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            meta = json.load(f)
        return int(meta["mask"], 0)
    print(f"warning: no {meta_path}; defaulting mask to 0xFF", file=sys.stderr)
    return 0xFF


def read_line(s):
    return s.read_until(b"\n").decode(errors="replace").strip()


def upload(port, binfile, mask, play, loop, step_us, stop_after, baud):
    with open(binfile, "rb") as f:
        data = f.read()
    nbytes = len(data)
    if nbytes == 0 or nbytes % CH_BYTES != 0:
        sys.exit(f"error: {binfile} size {nbytes} is not a multiple of {CH_BYTES}")
    nsteps = nbytes // CH_BYTES
    checksum_local = sum(struct.unpack(f"<{nbytes // 2}H", data)) & 0xFFFFFFFF

    s = serial.Serial(port, baud, timeout=2)
    try:
        # Give USB CDC a moment and flush any pending monitor frames.
        time.sleep(0.2)
        s.reset_input_buffer()

        # 1. send WFLOAD, then wait for WFREADY (skipping monitor frames).
        s.write(f"WFLOAD {nsteps} 0x{mask:02X}\n".encode())
        ready = None
        deadline = time.time() + 3
        while time.time() < deadline:
            line = read_line(s)
            if line.startswith("WFREADY"):
                ready = line
                break
            if line.startswith("ERROR"):
                sys.exit(f"firmware rejected WFLOAD: {line}")
        if ready is None:
            sys.exit("error: no WFREADY from firmware")

        # 2. send the raw binary payload.
        s.write(data)
        s.flush()

        # 3. read the ack (skip any interleaved monitor frames).
        ack = None
        deadline = time.time() + 8
        while time.time() < deadline:
            line = read_line(s)
            if line.startswith("OK WFLOADED") or line.startswith("ERROR"):
                ack = line
                break
        if ack is None:
            sys.exit("error: no upload ack from firmware")
        if not ack.startswith("OK WFLOADED"):
            sys.exit(f"upload failed: {ack}")

        fw_checksum = int(ack.split()[-1], 16)
        if fw_checksum != checksum_local:
            sys.exit(f"checksum mismatch! fw=0x{fw_checksum:08X} local=0x{checksum_local:08X}")
        print(f"uploaded {nbytes} bytes, {nsteps} steps, "
              f"checksum 0x{checksum_local:08X} OK")

        if play or loop or stop_after:
            loop_i = 1 if loop else 0
            s.write(f"WFPLAY {loop_i} {step_us}\n".encode())
            deadline = time.time() + 3
            while time.time() < deadline:
                line = read_line(s)
                if line.startswith(("OK PLAYING", "ERROR")):
                    print(line)
                    break

        if stop_after:
            time.sleep(stop_after)
            s.write(b"WFSTOP\n")
            deadline = time.time() + 3
            while time.time() < deadline:
                line = read_line(s)
                if line.startswith(("OK STOPPED", "ERROR")):
                    print(line)
                    break
    finally:
        s.close()


def main():
    ap = argparse.ArgumentParser(
        description="Upload a binary waveform to the EyeVolt Pico and optionally play it.")
    ap.add_argument("port", metavar="PORT", help="serial device (e.g. /dev/ttyACM0)")
    ap.add_argument("binfile", metavar="BINFILE", help=".bin file from pwl_to_waveform.py")
    ap.add_argument("--play", action="store_true",
                    help="start playback immediately after upload")
    ap.add_argument("--loop", action="store_true", help="loop playback (implies --play)")
    ap.add_argument("--step-us", type=int, default=1000,
                    help="step period in microseconds (default: 1000)")
    ap.add_argument("--stop-after", type=float, metavar="S",
                    help="stop playback after S seconds (implies --play)")
    ap.add_argument("--mask", help="active-channel mask override (e.g. 0x09)")
    ap.add_argument("--baud", type=int, default=9600,
                    help="baud rate (default: 9600; ignored for USB CDC)")
    args = ap.parse_args()

    mask = load_mask(args.binfile, args.mask)
    upload(args.port, args.binfile, mask, args.play, args.loop,
           args.step_us, args.stop_after, args.baud)


if __name__ == "__main__":
    main()
