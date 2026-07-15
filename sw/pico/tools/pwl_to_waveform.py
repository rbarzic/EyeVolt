#!/usr/bin/env python3
"""Convert a PWL text description to an EyeVolt binary waveform file.

A PWL file describes up to 8 piecewise-linear channel waveforms. Channels that
are not listed are marked INACTIVE (their mask bit stays 0): the firmware never
drives them during playback, so they hold whatever manual value they had.

Output:
  * <name>.bin   raw memory dump of waveform[step][channel], uint16 little-endian
  * <name>.meta  JSON sidecar {"mask", "nsteps", "checksum"} read by wf_upload.py

PWL format
----------
    STEPS 2048
    CH0  0@0  3300@1024  0@2047          # triangle: 0 -> 3.3 V -> 0
    CH3  1650@0  1650@2047               # constant 1.65 V

Each CHn point is <millivolts>@<step>; points ascend by step. See README.
"""

import argparse
import json
import os
import struct
import sys

MAX_STEPS = 2048
NUM_CH = 8
FULLSCALE_MV = 3300
MAX_RAW = 65535


def parse_pwl(path):
    """Return (steps, channels) where channels[ch] = [(step, mv), ...]."""
    steps = None
    channels = {}
    with open(path) as f:
        for lineno, line in enumerate(f, 1):
            line = line.split('#')[0].strip()
            if not line:
                continue
            parts = line.split()
            kw = parts[0].upper()
            if kw == 'STEPS':
                if len(parts) != 2:
                    sys.exit(f"line {lineno}: STEPS takes exactly one value")
                try:
                    steps = int(parts[1])
                except ValueError:
                    sys.exit(f"line {lineno}: STEPS value '{parts[1]}' is not an integer")
            elif kw.startswith('CH'):
                try:
                    ch = int(kw[2:])
                except ValueError:
                    sys.exit(f"line {lineno}: bad channel token '{parts[0]}'")
                if not 0 <= ch < NUM_CH:
                    sys.exit(f"line {lineno}: channel {ch} out of range (0-{NUM_CH - 1})")
                if ch in channels:
                    sys.exit(f"line {lineno}: CH{ch} defined twice")
                if len(parts) < 3:
                    sys.exit(f"line {lineno}: CH{ch} needs at least 2 points")
                points = []
                for tok in parts[1:]:
                    if '@' not in tok:
                        sys.exit(f"line {lineno}: '{tok}' is not <mv>@<step>")
                    mv_s, step_s = tok.split('@', 1)
                    try:
                        mv = float(mv_s)
                        step = int(step_s)
                    except ValueError:
                        sys.exit(f"line {lineno}: bad point '{tok}'")
                    if not 0 <= mv <= FULLSCALE_MV:
                        sys.exit(f"line {lineno}: {mv} mV out of range (0-{FULLSCALE_MV})")
                    points.append((step, mv))
                pts_steps = [s for s, _ in points]
                if pts_steps != sorted(pts_steps):
                    sys.exit(f"line {lineno}: steps not in ascending order")
                channels[ch] = points
            else:
                sys.exit(f"line {lineno}: unknown keyword '{parts[0]}'")
    if steps is None:
        sys.exit("error: STEPS not defined")
    if not 1 <= steps <= MAX_STEPS:
        sys.exit(f"error: STEPS must be 1..{MAX_STEPS}")
    # Validate step ranges now that STEPS is known.
    for ch, points in channels.items():
        for step, _ in points:
            if not 0 <= step < steps:
                sys.exit(f"error: CH{ch} step {step} out of range (0..{steps - 1})")
    return steps, channels


def interpolate(points, nsteps):
    """Linear-interpolate points to fill nsteps raw16 samples."""
    pts = sorted(points)
    result = []
    for step in range(nsteps):
        if step <= pts[0][0]:
            mv = pts[0][1]
        elif step >= pts[-1][0]:
            mv = pts[-1][1]
        else:
            mv = pts[-1][1]
            for i in range(len(pts) - 1):
                t0, v0 = pts[i]
                t1, v1 = pts[i + 1]
                if t0 <= step <= t1:
                    frac = (step - t0) / (t1 - t0) if t1 > t0 else 0.0
                    mv = v0 + (v1 - v0) * frac
                    break
        raw = round(mv / FULLSCALE_MV * MAX_RAW)
        result.append(max(0, min(MAX_RAW, raw)))
    return result


def build_waveform(steps, channels):
    """Return (data_bytes, mask). data = waveform[step][ch] uint16 LE dump."""
    mask = 0
    cols = []
    for ch in range(NUM_CH):
        if ch in channels:
            mask |= (1 << ch)
            cols.append(interpolate(channels[ch], steps))
        else:
            cols.append([0] * steps)

    flat = []
    for step in range(steps):
        for ch in range(NUM_CH):
            flat.append(cols[ch][step])
    data = struct.pack(f"<{len(flat)}H", *flat)
    return data, mask, cols


def preview(steps, channels, cols):
    print(f"STEPS {steps}")
    for ch in range(NUM_CH):
        if ch in channels:
            col = cols[ch]
            def to_mv(raw):
                return raw / MAX_RAW * FULLSCALE_MV
            print(f"  CH{ch}  ACTIVE   "
                  f"start={to_mv(col[0]):7.1f}mV  end={to_mv(col[-1]):7.1f}mV  "
                  f"min={to_mv(min(col)):7.1f}mV  max={to_mv(max(col)):7.1f}mV")
        else:
            print(f"  CH{ch}  inactive")


def main():
    ap = argparse.ArgumentParser(
        description="Convert a PWL waveform description to an EyeVolt binary waveform file.")
    ap.add_argument("input", metavar="input.pwl", help="PWL description file")
    ap.add_argument("-o", dest="output", help="output .bin file (default: <input>.bin)")
    ap.add_argument("--steps", type=int, help="override STEPS count from file")
    ap.add_argument("--preview", action="store_true",
                    help="print a per-channel summary and exit")
    args = ap.parse_args()

    steps, channels = parse_pwl(args.input)
    if args.steps is not None:
        if not 1 <= args.steps <= MAX_STEPS:
            sys.exit(f"error: --steps must be 1..{MAX_STEPS}")
        steps = args.steps
        for ch, points in channels.items():
            for step, _ in points:
                if step >= steps:
                    sys.exit(f"error: CH{ch} step {step} exceeds --steps {steps}")

    data, mask, cols = build_waveform(steps, channels)

    if args.preview:
        preview(steps, channels, cols)
        return

    output = args.output or (os.path.splitext(args.input)[0] + ".bin")
    with open(output, "wb") as f:
        f.write(data)

    checksum = sum(struct.unpack(f"<{len(data) // 2}H", data)) & 0xFFFFFFFF

    meta_path = os.path.splitext(output)[0] + ".meta"
    meta = {"mask": f"0x{mask:02X}", "nsteps": steps, "checksum": f"0x{checksum:08X}"}
    with open(meta_path, "w") as f:
        json.dump(meta, f)
        f.write("\n")

    print(f"mask=0x{mask:02X} nsteps={steps} checksum=0x{checksum:08X} bytes={len(data)}")
    print(f"wrote: {output}")
    print(f"wrote: {meta_path}")


if __name__ == "__main__":
    main()
