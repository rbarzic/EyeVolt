#pragma once

#include <cstdint>
#include "mux.h"
#include "pins.h"

//
// 8-channel programmable voltage generator for the EyeVolt 2.0 hardware.
//
// Produces 8 independent 0-3.3 V outputs by PWM on GP2-GP9, each filtered by a
// 2nd-order RC low-pass and buffered (OPA316) before reaching the J2 connector.
// A feedback mux (U12) reads the 8 generated outputs back on ADC1 (GP27).
//
class Generator {
public:
    void init();

    // Set output of channel ch (0-7) from a 16-bit duty code (0-65535 → 0-3.3 V).
    void set_raw(uint ch, uint16_t duty16);

    // Set output of channel ch (0-7) to a target voltage in millivolts (0-3300).
    void set_millivolts(uint ch, uint16_t millivolts);

    // Drive channel ch (0-7) to 0 V.
    void off(uint ch);

    // Drive all channels to 0 V.
    void off_all();

    // Return the last duty code written to channel ch (0-7).
    uint16_t duty(uint ch) const;

    // Scan the feedback mux U12 and read back the 8 generated outputs.
    // out[8] ← raw 16-bit codes (scale: raw/65536 * 3.3 V).
    void readback(uint16_t out[8]);

private:
    Mux fb_mux_{pins::DACMUX_S0, pins::DACMUX_S1, pins::DACMUX_S2, pins::DACMUX_EN};
    uint16_t duty_[pins::NUM_DAC_CHANNELS] = {0};
};
