# EyeVolt waveform host tools

Host-side tools to build and upload pre-computed waveforms for the EyeVolt 2.0
firmware (`../cpp`). A waveform is 8 channels × up to 2048 steps × 16-bit,
played back on the Pico at a fixed step rate (default 1 ms/step).

| Tool | Purpose |
|------|---------|
| `pwl_to_waveform.py` | Convert a PWL text description → `.bin` (+ `.meta` sidecar) |
| `wf_upload.py` | Upload a `.bin` to the Pico over USB serial and optionally play it |

Requires Python 3 and, for uploading, `pyserial` (`pip install pyserial`).

---

## PWL format

A PWL file lists the channels you want to drive. Each channel is defined by a
set of piecewise-linear points; the converter linearly interpolates between them
to fill every step. Channels **not** listed are inactive: their mask bit is 0
and the firmware never drives them during playback (they hold their manual
`SETMV`/`SETDAC` value).

```text
# Comments start with '#'. Blank lines are ignored.

STEPS 2048              # required, 1..2048

# CH<n>  <mv>@<step>  <mv>@<step>  ...   (n = 0..7, at least 2 points)
# millivolts 0..3300, steps ascending, 0..STEPS-1.

CH0  0@0  3300@1024  0@2047     # triangle 0 -> 3.3 V -> 0
CH3  1650@0  1650@2047          # constant 1.65 V
```

### Rules

| Rule | Detail |
|------|--------|
| `STEPS <n>` | Required. `1 ≤ n ≤ 2048`. |
| `CH<n> <mv>@<step> ...` | ≥ 2 points, steps ascending, `0 ≤ step < STEPS`. |
| Duplicate `CHn` | Error. |
| `mv` outside `0..3300` | Error. |
| Channel not listed | Inactive (mask bit 0, data zeroed). |

### Interpolation

For points `(t0,v0), (t1,v1), ...`:

- `step ≤ t0` → `v0` (hold first)
- `ti ≤ step ≤ ti+1` → linear between the two points
- `step ≥ t_last` → `v_last` (hold last)

Raw code: `raw = round(mv / 3300 × 65535)`, clamped to `0..65535`.

---

## Usage

```bash
# Preview a per-channel summary (no files written)
python3 pwl_to_waveform.py examples/demo.pwl --preview

# Convert → demo.bin + demo.meta
python3 pwl_to_waveform.py examples/demo.pwl -o demo.bin

# Upload and play once
python3 wf_upload.py /dev/ttyACM0 demo.bin --play

# Upload, loop at 500 µs/step, stop after 5 s
python3 wf_upload.py /dev/ttyACM0 demo.bin --loop --step-us 500 --stop-after 5
```

`pwl_to_waveform.py` writes a `.meta` sidecar (`{"mask", "nsteps", "checksum"}`)
next to the `.bin`. `wf_upload.py` reads it automatically to pick the active
mask; override with `--mask 0x09` or it defaults to `0xFF`.

`wf_upload.py` computes the same 32-bit additive checksum the firmware reports
and aborts on mismatch.

---

## Examples

| File | Shape |
|------|-------|
| `examples/triangle.pwl` | CH0 triangle 0 → 3.3 V → 0 over 2048 steps |
| `examples/demo.pwl` | CH0 triangle, CH1 square wave, CH3 constant 1.65 V |


### Polaris


```bash
make play
make off
```

