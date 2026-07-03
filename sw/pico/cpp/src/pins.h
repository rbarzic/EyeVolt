#pragma once

//
// EyeVolt 2.0 — Pico (RP2040) hardware pin map.
//
// Source of truth for the v2.0 PCB. See the project README.md section
// "Pico pin mapping (2.0 hardware)". Key differences from v1.1:
//   * MUX0 and MUX1 are CASCADED; all 12 monitor channels exit on GP26 only.
//   * S0 and S2 are swapped on both monitor muxes vs v1.1.
//   * GP27 is now the DAC-feedback ADC (was MUX1 monitor ADC in v1.1).
//   * GP2-GP9 drive the 8 PWM generation outputs (new in v2.0).
//

namespace pins {

// ── Monitor mux MUX0 (U11): 8 low-voltage channels ──────────────────────────
// (S0/S2 swapped vs v1.1: v1.1 had S0=GP10, S2=GP12)
constexpr unsigned MUX0_S0 = 12;
constexpr unsigned MUX0_S1 = 11;
constexpr unsigned MUX0_S2 = 10;
constexpr unsigned MUX0_EN = 13;   // ~E, active low

// ── Monitor mux MUX1 (U10): HV channels CH0-3, cascade MUX0 on CH4 ───────────
// (S0/S2 swapped vs v1.1: v1.1 had S0=GP21, S2=GP19)
constexpr unsigned MUX1_S0 = 19;
constexpr unsigned MUX1_S1 = 20;
constexpr unsigned MUX1_S2 = 21;
constexpr unsigned MUX1_EN = 18;   // ~E, active low

// MUX1 channel that taps the cascaded MUX0 bank (low-voltage inputs).
constexpr unsigned MUX1_CASCADE_CHANNEL = 4;

// ── DAC feedback mux U12: reads back 8 generated outputs ─────────────────────
constexpr unsigned DACMUX_S0 = 15;
constexpr unsigned DACMUX_S1 = 14;
constexpr unsigned DACMUX_S2 = 16;
constexpr unsigned DACMUX_EN = 17;   // ~E, active low

// ── ADC inputs ───────────────────────────────────────────────────────────────
// RP2040 ADC input number (not the GPIO number): input 0 = GP26, input 1 = GP27.
constexpr unsigned ADC_MONITOR  = 0;   // GP26 — all 12 monitor channels (via MUX1)
constexpr unsigned ADC_READBACK = 1;   // GP27 — 8 generated-output readback (via U12)

constexpr unsigned ADC_MONITOR_PIN  = 26;
constexpr unsigned ADC_READBACK_PIN = 27;

// ── PWM generation outputs (GP2-GP9 → DAC_PWM0..7) ───────────────────────────
constexpr unsigned DAC_PWM_FIRST = 2;    // DAC_PWM0 = GP2
constexpr unsigned NUM_DAC_CHANNELS = 8;

// ── Channel counts ───────────────────────────────────────────────────────────
constexpr unsigned NUM_LV_CHANNELS      = 8;   // channels 0-7  (0 - 3.3 V)
constexpr unsigned NUM_HV_CHANNELS      = 4;   // channels 8-11 (0 - 6.6 V)
constexpr unsigned NUM_MONITOR_CHANNELS = 12;

// ── Timing ───────────────────────────────────────────────────────────────────
// Settle time after switching a mux before sampling the ADC.
// The buffers (MCP6L04 / OPA316) and the 74HCT4051 settle in well under 1 us;
// 1 ms is a very safe margin and yields a fast (~50 Hz) refresh.
constexpr unsigned MUX_SETTLE_US      = 1000;
constexpr unsigned READBACK_SETTLE_US = 1000;

// ADC samples averaged per reading to suppress RP2040 ADC noise.
constexpr unsigned ADC_OVERSAMPLE = 4;

// Full-scale of the generation outputs (3.3 V rail), in millivolts.
constexpr unsigned DAC_FULLSCALE_MV = 3300;
constexpr unsigned DAC_MAX_RAW      = 65535;

}  // namespace pins
