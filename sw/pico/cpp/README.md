# EyeVolt 2.0 — C++ firmware (Pico / RP2040)

C++ reimplementation of the EyeVolt firmware for the **2.0 hardware**, built with
the [pico-sdk](https://github.com/raspberrypi/pico-sdk) via the
[pico-bootstrap](https://github.com/rbarzic/pico-bootstrap) submodule.

It replaces the v1.1 MicroPython code (`../micropython/main.py`) and adds the
two new v2.0 features: **8-channel voltage generation** (PWM + filter + buffer)
and **output readback**.

---

## What this firmware does

| Function | Detail |
|---|---|
| **12-channel monitoring** | Scans the cascaded MUX0 → MUX1 topology on **GP26/ADC0** (v2.0 routing). Emits the same `1::` / `2::` frames as v1.1 so the PC TUI/MCP software is unchanged. |
| **8-channel generation** | 8 PWM outputs on **GP2-GP9** → 2nd-order RC LPF → OPA316 buffer → J2. Set per-channel via serial commands. |
| **Output readback** | Feedback mux **U12** reads the 8 generated outputs back on **GP27/ADC1**; emitted as `3::` frames. |

---

## Build & flash

> The `pico-bootstrap` submodule is at `../imported/pico-bootstrap`. These
> targets reuse its downloaded SDK + tools (in `../imported/pico-bootstrap/deps`).

```bash
# One-time: download the SDK + build picotool/openocd (if not already done)
make download
make install

# Build the firmware
make build                       # → build/eyevolt.uf2 (and .elf/.hex/.bin)

# Flash over a Raspberry Pi Debug Probe
make identify-probe              # find the probe serial
make flash PROBE_SERIAL=<serial>
```

The Pico then enumerates as a USB-CDC serial port; the existing PC software
connects to it directly (`eyevolt_mcp.py /dev/ttyACM0`).

---

## Serial protocol

USB-CDC, ASCII text, line-based. The Pico streams continuously; the host
synchronises on the `N::` headers.

### Pico → host (data frames)

```
1::VVVVV VVVVV VVVVV VVVVV VVVVV VVVVV VVVVV VVVVV      ← 8 low-voltage  (0-3.3 V)
2::VVVVV VVVVV VVVVV VVVVV                              ← 4 high-voltage (0-6.6 V)
3::VVVVV VVVVV VVVVV VVVVV VVVVV VVVVV VVVVV VVVVV      ← 8 DAC readback (0-3.3 V)
```

Values are raw 16-bit ADC/PWM codes (0-65535). PC scaling:

* `1::` → `raw / 65536 * 3.3` V
* `2::` → `raw / 65536 * 6.6` V  (on-board ÷2 divider restored)
* `3::` → `raw / 65536 * 3.3` V

`1::` and `2::` are backward-compatible with v1.1. `3::` is new and ignored by
the current PC software.

### Host → Pico (commands, newline-terminated)

| Command | Effect | Reply |
|---|---|---|
| `SETDAC <ch> <raw>` | Set DAC channel `ch` (0-7) duty `raw` (0-65535) | `OK DAC<ch>=<raw>` |
| `SETMV <ch> <mv>` | Set DAC channel `ch` (0-7) to `mv` millivolts (0-3300) | `OK DAC<ch>=<mv>mV` |
| `OFF <ch>` | Set DAC channel `ch` (0-7) to 0 V | `OK DAC<ch>=0` |
| `OFFALL` | All DAC channels to 0 V | `OK all DAC=0` |
| `WFLOAD <nsteps> <mask_hex>` | Upload a binary waveform (see below) | `WFREADY <nbytes>` then `OK WFLOADED 0x<checksum>` |
| `WFPLAY [loop=0] [step_us=1000]` | Play the loaded waveform | `OK PLAYING nsteps=.. mask=.. loop=.. step_us=..` |
| `WFSTOP` | Stop playback (DACs hold last values) | `OK STOPPED step=<n>` |
| `WFSTATUS` | Query playback state | `WFSTAT <state> <step> <nsteps> <mask>` |
| `VERSION` | Print firmware version | `VERSION <ver>` |
| `HELP` | List commands | (help text) |

Errors reply `ERROR ...`. Commands are uppercase.

---

## Waveform playback

Upload a pre-computed waveform (8 channels × up to 2048 steps × 16-bit) into
Pico SRAM and play it back at a fixed step rate (default 1 ms/step → 2.048 s for
a full 2048-step run). A hardware repeating timer writes each step's active
channels to the PWM registers in IRQ context, so monitoring (`1::`/`2::`) keeps
running during playback. The `3::` readback frame is suppressed while playing.

Channels are marked **active** or **inactive** via the mask. Inactive channels
are never touched by playback — they hold whatever manual (`SETMV`/`SETDAC`)
value they had, so you can mix a driven waveform with static offsets.

### `WFLOAD` upload sequence

```
host → pico : WFLOAD 2048 0xFF\n
pico → host : WFREADY 32768\n              (nsteps × 8 × 2 bytes expected)
host → pico : <32768 raw bytes>            uint16 little-endian, step-major
pico → host : OK WFLOADED 0x0BFF7801\n      (32-bit additive checksum)
```

Binary layout: `byte_offset = (step × 8 + channel) × 2`, value
`round(mv / 3300 × 65535)` as little-endian `uint16`. Upload aborts with
`ERROR timeout (n/N bytes)` after 5 s.

### Host tools (`../tools/`)

```bash
# 1. Convert a PWL text description to a .bin (+ .meta sidecar with the mask)
python3 ../tools/pwl_to_waveform.py ../tools/examples/demo.pwl -o demo.bin

# 2. Upload and play (mask read from demo.meta automatically)
python3 ../tools/wf_upload.py /dev/ttyACM0 demo.bin --play
python3 ../tools/wf_upload.py /dev/ttyACM0 demo.bin --loop --step-us 500
```

See `../tools/` for the PWL format and example waveforms under
`../tools/examples/`.

---

## v2.0 hardware pin map

| GPIO | Direction | Net | Purpose |
|------|-----------|-----|---------|
| GP2-GP9 | out (PWM) | DAC_PWM0..7 | 8 generation outputs |
| GP10 | out | MUX0_S2 | MUX0 address bit 2 |
| GP11 | out | MUX0_S1 | MUX0 address bit 1 |
| GP12 | out | MUX0_S0 | MUX0 address bit 0 |
| GP13 | out | MUX0_EB | MUX0 enable (~E) |
| GP14 | out | DACMUX_S1 | DAC feedback mux bit 1 |
| GP15 | out | DACMUX_S0 | DAC feedback mux bit 0 |
| GP16 | out | DACMUX_S2 | DAC feedback mux bit 2 |
| GP17 | out | DACMUX_EB | DAC feedback mux enable (~E) |
| GP18 | out | MUX1_EB | MUX1 enable (~E) |
| GP19 | out | MUX1_S0 | MUX1 address bit 0 |
| GP20 | out | MUX1_S1 | MUX1 address bit 1 |
| GP21 | out | MUX1_S2 | MUX1 address bit 2 |
| GP26 | in (ADC0) | MON_ADC | all 12 monitor channels (via cascaded MUX1) |
| GP27 | in (ADC1) | DAC_FB | 8 generated-output readback (via U12) |

### Monitoring cascade (v2.0 vs v1.1)

In v1.1 the two muxes were independent, each feeding its own ADC pin. In v2.0:

1. **MUX0's common** is wired to **MUX1 channel 4** (cascade).
2. To read the 8 LV channels: hold MUX1 on CH4, cycle MUX0 0..7, read GP26.
3. To read the 4 HV channels: select MUX1 CH0..3 directly, read GP26.
4. S0 and S2 are swapped on both muxes vs v1.1.

### Generation chain

```
GPn (PWM, ~1.9 kHz) → R 10k → C 1µF → R 10k → C 1µF → OPA316 buffer → 0R → DAC_OUTn → J2
                       (2nd-order RC LPF, ~16 Hz cutoff)                              ↑ readback via U12 → GP27
```

---

## Source layout

```
src/
├── main.cpp        main loop: scan → emit 1::/2::/3:: → poll commands
├── pins.h          v2.0 hardware pin map & timing constants
├── mux.h           generic 74HCT4051 driver (header-only)
├── monitor.{h,cpp} 12-channel cascade scan on GP26
└── generator.{h,cpp} 8-channel PWM generation + U12 readback on GP27
```

---

## Notes

* ADC readings are 4× oversampled (vs single sample in MicroPython) to reduce the
  RP2040 ADC noise. The 16-bit output format is unchanged.
* The mux settle time is 1 ms (vs 10 ms in MicroPython); the buffers and switches
  settle in well under 1 µs, so this only raises the refresh rate (~50 Hz). Adjust
  `MUX_SETTLE_US` in `pins.h` if needed.
* USB CDC is used for stdio (`printf`/`getchar`), matching the MicroPython version.
  The "9600 baud" requested by the PC is irrelevant for USB CDC.
