# Presentation

![General concept](./doc/images/concept.png)

EyeVolt is a **12-channel DC voltage monitor** built around a Raspberry Pi Pico.
The Pico continuously samples up to twelve voltages, streams the raw ADC readings
out over USB-serial, and a Python **Terminal User Interface (TUI)** on the PC
displays live values, progress bars and sparkline trends. The PC software can
optionally expose the readings through an **MCP (Model Context Protocol) server**
so that AI assistants / automation can query the voltages programmatically.

The board has two measurement domains:

| Group | Channels | Full-scale | Conditioning | Routed to |
|-------|----------|-----------|--------------|-----------|
| Low-voltage  | 0 - 7  (8 ch) | 0 - 3.3 V | unity-gain buffer only               | MUX0 -> ADC0 (GP26) |
| High-voltage | 8 - 11 (4 ch) | 0 - 6.6 V | buffer + 2:1 resistive divider (÷2)  | MUX1 -> ADC1 (GP27) |

Because the Pico ADC only accepts 0 - 3.3 V, the high-voltage channels are
divided by two on the board (so 6.6 V at the input => 3.3 V at the ADC); the PC
software then multiplies back by two to display the true input voltage.

---

# Hardware

## Architecture (block-level)

```
                                                          Raspberry Pi Pico (U1)
 +-----------+        +-----------------------+            +--------------------+
 |           | V33IN0>+-->|U3/U5 buffer x8 |----VBUFF0..7->|A0..A7          A -->|ADC0 GP26
 |  J1 input | V33IN1> |  (0-3.3V domain)    |             |  74HCT4051 MUX0 (U4)|
 | connector |   ...  |                       |            |                     | S0<-GP10
 | 2x10 box  | V33IN7>+-->                    |            |                     | S1<-GP11
 | header    |        +-----------------------+            |                     | S2<-GP12
 |           | V55IN0>--+-->|U6 buffer x4 |--+  +---+      |                     | ~E<-GP13
 |           |   ...   |   | (high-V in)  |  +->|/2 |      +--------------------+
 |           | V55IN3>--+   +--------------+--+  +---+      +--------------------+
 +-----------+              +-->|U2 buffer x4|----VBUFF8.11>|A0..A3          A -->|ADC1 GP27
                                |(after div) |              |  74HCT4051 MUX1 (U7)|
                                +------------+              |                     | S0<-GP21
                                                            |                     | S1<-GP20
                                                            |                     | S2<-GP19
                                                            |                     | ~E<-GP18
                                                            +--------------------+
        USB-CDC serial  (9600 8N1)  ----> PC running eyevolt_mcp.py
```

In words:

1. The voltages to be measured arrive on connector **J1** (a 2x10 box header).
2. Every input is **buffered** by a rail-to-rail CMOS op-amp (MCP6L04, quad)
   configured as a unity-gain voltage follower. This gives the circuit a very
   high input impedance so it does not perturb the device under test.
3. The 4 high-voltage inputs additionally pass through a **100 k / 100 k
   divider** (÷2) and are buffered a second time on the divided side so the
   divider is not loaded by the multiplexer.
4. The 8 low-voltage buffered signals feed the 8 channels of **MUX0** (a
   74HCT4051 8:1 analog multiplexer, U4); its common output `A` goes to **ADC0
   (GP26)**.
5. The 4 high-voltage buffered signals feed 4 channels of **MUX1** (U7, also a
   74HCT4051); its common output goes to **ADC1 (GP27)**.
6. The Pico selects one MUX channel at a time via three select lines (S0/S1/S2)
   and an active-low enable (`~E`), reads the ADC, then steps to the next
   channel and repeats.

## Bill of materials (main components)

| Ref | Part | Function |
|-----|------|----------|
| U1  | Raspberry Pi Pico | MCU + dual ADC + USB-serial |
| U4  | 74HCT4051 | 8:1 analog multiplexer for the 3.3 V channels (MUX0) |
| U7  | 74HCT4051 | 8:1 analog multiplexer for the high-voltage channels (MUX1) |
| U3, U5 | MCP6L04x (quad op-amp) | unity-gain buffers for the 8 low-voltage channels |
| U6 | MCP6L04x (quad op-amp) | input buffers for the 4 high-voltage channels |
| U2 | MCP6L04x (quad op-amp) | post-divider buffers for the 4 high-voltage channels |
| R1-R4 | 100 k | top leg of the 2:1 divider (one per HV channel) |
| R5-R8 | 100 k | bottom leg of the divider to GND (one per HV channel) |
| C1-C6 | decoupling | local bypassing for the op-amps and the muxes |
| J1 | Conn_02x10 (2.54 mm box header) | voltage inputs + GND |
| J2, J3 | Conn_01x15 (2x 1x15 headers) | on-board TFT/touchscreen interface (see below) |
| H1-H4 | Mounting holes | mechanical |

The op-amps are Microchip **MCP6L04**: quad, 1 MHz, 85 µA, rail-to-rail input
and output — well suited as low-cost, low-bias unity-gain buffers operating from
the Pico's 3.3 V rail. (Datasheets for the pin-compatible MCP6024 and OPA4316
are kept in `doc/datasheets/opamp/`.)

## Input connector J1 pinout

J1 is a 2x10 (2.54 mm) header. The odd-numbered row carries the eight
low-voltage inputs (V33IN0..7); the even-numbered row carries the four
high-voltage inputs (V55IN0..3) plus ground.

> Pinout below is taken from the generated netlist (`hw/pcb/eyevolt.net`).
> Verify against the current schematic if in doubt.

| J1 pin | Signal   | Range      | EyeVolt channel |
|--------|----------|------------|-----------------|
| 1      | V33IN0   | 0 - 3.3 V  | ch 0  (MUX0 A0) |
| 3      | V33IN1   | 0 - 3.3 V  | ch 1  (MUX0 A1) |
| 5      | V33IN2   | 0 - 3.3 V  | ch 2  (MUX0 A2) |
| 7      | V33IN3   | 0 - 3.3 V  | ch 3  (MUX0 A3) |
| 9      | V33IN4   | 0 - 3.3 V  | ch 4  (MUX0 A4) |
| 11     | V33IN5   | 0 - 3.3 V  | ch 5  (MUX0 A5) |
| 13     | V33IN6   | 0 - 3.3 V  | ch 6  (MUX0 A6) |
| 15     | V33IN7   | 0 - 3.3 V  | ch 7  (MUX0 A7) |
| 2      | V55IN0   | 0 - 6.6 V  | ch 8  (MUX1 A0) |
| 4      | V55IN1   | 0 - 6.6 V  | ch 9  (MUX1 A1) |
| 6      | V55IN2   | 0 - 6.6 V  | ch 10 (MUX1 A2) |
| 8      | V55IN3   | 0 - 6.6 V  | ch 11 (MUX1 A3) |
| 10,12,14,16 | NC  | —          | not connected   |
| 17,18,19,20 | GND | —          | signal / return ground |

## Analog conditioning detail

* **Low-voltage channels (0-7):** each input drives the `+` input of an op-amp
  voltage follower whose output is shorted to its `-` input. The output
  (VBUFF0..7) goes directly to one of MUX0's analog inputs. No scaling — the
  displayed voltage equals the measured voltage (up to the 3.3 V rail).

* **High-voltage channels (8-11):** each input is first buffered (U6, high
  impedance), then split by a 100 k / 100 k divider to GND, then buffered again
  (U2) before reaching MUX1. The two-stage buffering keeps the divider node
  high-impedance and accurate. The ADC therefore sees `Vin / 2`, and the PC
  software restores the real value by multiplying by 2 (`* 6.6 / 65536`).

## Multiplexing (74HCT4051)

Each 74HCT4051 selects one of 8 analog inputs onto a common pin `A` according to
the 3-bit address `S2 S1 S0`, while `~E` (active-low enable) gates the output.
When `~E = 1` the switch is high-impedance. The Pico drives these logic pins
directly. On the board, VEE is tied to GND (single-supply operation, 0 - VCC
analog range) and VCC is the 3.3 V rail.

## Display / touchscreen interface (J2, J3)

The schematic also carries two 1x15 pin headers (J2, J3) wired to an
**SPI TFT display based on the RA8875 controller, with a resistive touch
panel**. The net labels `MOSI / MISO / SCK / CS / INT / RST / LITE / WAIT / 3Vo
/ X+ / X- / Y+ / Y-` match an Adafruit-style RA8875 touchscreen breakout. The
RA8875 datasheet and application notes are kept in `doc/datasheets/screen/`.

> These connectors are **not used by the current firmware**. Monitoring is done
> entirely over USB-serial and rendered by the PC-side TUI. The headers are
> reserved for a possible future standalone, display-based UI.

## Power

The board is powered by the Pico's USB connection. The 3.3 V rail (VDD33)
powers the op-amps and the multiplexers and serves as the ADC reference. A 5 V
rail (VDD50) is also present on the display headers.

---

# Firmware (Pico, MicroPython)

Location: `sw/pico/micropython/main.py`. It is plain MicroPython using the
`machine` module; `boot.py` is empty (USB-CDC is configured in the firmware
image, not at run time).

## Pico pin mapping

| GPIO | Direction | Net (schematic) | Purpose |
|------|-----------|-----------------|---------|
| GP10 | out | MUX0_S0 | MUX0 address bit 0 |
| GP11 | out | MUX0_S1 | MUX0 address bit 1 |
| GP12 | out | MUX0_S2 | MUX0 address bit 2 |
| GP13 | out | MUX0_EB | MUX0 enable (`~E`, active low) |
| GP18 | out | MUX1_EB | MUX1 enable (`~E`, active low) |
| GP19 | out | MUX1_S2 | MUX1 address bit 2 |
| GP20 | out | MUX1_S1 | MUX1 address bit 1 |
| GP21 | out | MUX1_S0 | MUX1 address bit 0 |
| GP26 | in (ADC0) | MUX0_A | MUX0 common -> reads channels 0-7 |
| GP27 | in (ADC1) | MUX1_A | MUX1 common -> reads channels 8-11 |

(The select-line order matches `sw/pico/micropython/main.py:7-19`.)

## Principle of operation

The main loop (`main.py:66-85`) repeatedly:

1. Scans **MUX0** channels 0..7: for each channel it writes the 3-bit address,
   asserts `~E`, waits **10 ms** for the analog switch and buffer to settle, then
   reads `ADC0` (`read_u16()`).
2. Scans **MUX1** channels 0..3 the same way, reading `ADC1`.
3. Prints two text lines (one per group) over USB-serial.

Each full scan therefore takes roughly 8*10 + 4*10 = **120 ms**, i.e. the whole
12-channel set is refreshed about **8 times per second**.

`read_u16()` returns a 16-bit value (0..65535) proportional to the voltage at
the ADC pin relative to the 3.3 V reference. The firmware sends the *raw* value
unchanged; all scaling is done on the PC side.

## Serial protocol

USB-CDC, **9600 baud, 8N1**, ASCII text. The Pico emits two lines per cycle:

```
1::VVVVV VVVVV VVVVV VVVVV VVVVV VVVVV VVVVV VVVVV
2::VVVVV VVVVV VVVVV VVVVV
```

* `1::` introduces the 8 low-voltage channels (0..7), space-separated,
  zero-padded to 5 digits.
* `2::` introduces the 4 high-voltage channels (8..11), space-separated.
* Values are raw 16-bit ADC codes (0..65535).

There is no request/response framing and no checksum: the device streams
continuously and the host synchronises on the `1::` / `2::` headers.

---

# PC software

The recommended version is `sw/pc/eyevolt_mcp.py` (a richer superset of the
older `sw/pc/eyevolt_pc.py`). It is a single-file Python application built with
**Textual** (TUI), **pyserial-asyncio** (serial), and an optional **MCP over
SSE** server (Starlette + Uvicorn).

## Serial acquisition & scaling

`SerialProtocol` (`eyevolt_mcp.py:79`) buffers bytes until a newline, then
`process_line()` (`:99`) decodes each frame:

* `1::` frame -> 8 integers, converted with `raw / 65536 * 3.3`  (volts, 0-3.3 V)
* `2::` frame -> 4 integers, converted with `raw / 65536 * 6.6`  (volts, 0-6.6 V)

The resulting 12 float values are pushed into the 12 display widgets.

## Terminal User Interface (TUI)

`SerialTUI` (`:276`) lays out **12 `VoltageDisplay` widgets in a 3x4 grid**
(`:277`). Each widget (`:35`) contains:

* a **Label** with the channel name and current value (e.g. `VCORE: 1.21`),
* a **ProgressBar** showing the value as a percentage of the channel full-scale
  (3.3 V for channels 0-7, 6.6 V for channels 8-11),
* a **Sparkline** showing the recent history as percentages (rolling window,
  default 128 samples).

A colour scheme highlights abnormal rails:

| Voltage | Colour |
|---------|--------|
| < 0.5 V | white  |
| 0.5 - 0.8 V | yellow |
| 0.8 - 1.2 V | green  |
| >= 1.2 V    | red    |

(See `get_color()` at `:24`.)

## MCP server

When started with `--mcp`, an `EyeVoltMCPServer` (`:128`) runs an MCP server
over Server-Sent Events (SSE) on `127.0.0.1:8088` by default, in a background
thread. It exposes the live readings as tools that an MCP-compatible client
(e.g. an AI coding assistant) can call:

| Tool | Description |
|------|-------------|
| `get_voltages`        | All enabled channels as `{name: voltage}` |
| `get_voltage`         | One channel by name |
| `get_voltage_idx`     | One channel by index (0-11) |
| `get_channel_info`    | Full per-channel info (name, enabled, voltage, max) |
| `get_channel_history` | Sparkline history (percentages 0-100) for a named channel |

This lets an assistant answer questions like "what is VCORE right now?" or
"is any rail out of range?" without the user reading the TUI.

## Command-line usage

```
eyevolt_mcp.py [-h] [--text VAL=NAME,...] [--channel VAL=on|off,...]
               [--history N] [--mcp] [--mcp-host H] [--mcp-port P] [-v]
               PORT
```

* `PORT` — serial device, e.g. `/dev/ttyACM0` (Linux/macOS) or `COM3` (Windows).
* `--text` — rename channels, zero-based, e.g. `val0=VCORE,val1=VIO`.
* `--channel` — enable/disable channels, e.g. `val8=off,val9=off`. Channels not
  listed default to **on**; disabled channels show `----`.
* `--history` — sparkline length (default 128).
* `--mcp` — start the MCP/SSE server.
* `--mcp-host` / `--mcp-port` — MCP bind address (default `127.0.0.1:8088`).
* `-v` / `-vv` — info / debug logging.

Examples (see `sw/pc/readme.txt`):

```
./eyevolt_mcp.py --text val0=VCORE,val1=VIO /dev/ttyACM0

./eyevolt_mcp.py \
    --text val0=VCORE,val1=VMAX,val2=VMAIN,val3=VULP,val4=VPERIPH,\
val5=VCOREDIG,val6=VCORERAD,val7=VIO \
    --channel val8=off,val9=off,val10=off,val11=off \
    /dev/ttyACM0

./eyevolt_mcp.py --mcp /dev/ttyACM0        # also expose readings to MCP clients
```

---

# Running the system end-to-end

1. **Flash the Pico** with a MicroPython image (USB-CDC enabled), then copy
   `sw/pico/micropython/main.py` onto it (the `sw/pico/micropython/Makefile`
   provides `make copy` via `rshell` and `make run` via `mpremote`). On power-up
   the Pico starts streaming `1::`/`2::` lines at 9600 baud.
2. **Set up the PC environment** (`requirements.txt`):
   `pip install -r requirements.txt` (textual, pyserial-asyncio, mcp, starlette,
   uvicorn, rich, ...).
3. **Run the TUI**, pointing it at the Pico's serial port and labelling the
   channels to match your DUT (example above).
4. **(Optional)** add `--mcp` and connect an MCP client to `http://127.0.0.1:8088/sse`.

---

# End-to-end data path (summary)

```
DUT rail -- J1 -- op-amp buffer (+÷2 divider on HV channels)
        -- 74HCT4051 (selected by GP10/11/12/13 or GP21/20/19/18)
        -- Pico ADC0 (GP26) / ADC1 (GP27)
        -- MicroPython reads raw 16-bit codes, prints "1::.." / "2::.."
        -- USB-CDC @9600 baud
        -- eyevolt_mcp.py (async serial reader)
        -- Textual TUI (value + bar + sparkline) and/or MCP/SSE server
```
