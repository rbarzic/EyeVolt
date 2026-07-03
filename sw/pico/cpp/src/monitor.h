#pragma once

#include <cstdint>
#include "mux.h"
#include "pins.h"

//
// 12-channel voltage monitor for the EyeVolt 2.0 hardware.
//
// Reads the 8 low-voltage channels (0-7) and 4 high-voltage channels (8-11)
// through the cascaded MUX0 → MUX1 topology, all on ADC0 (GP26).
//
class Monitor {
public:
    void init();

    // Scan all 12 channels.
    //   lv[8] ← raw 16-bit codes for channels 0-7  (scale: raw/65536 * 3.3 V)
    //   hv[4] ← raw 16-bit codes for channels 8-11 (scale: raw/65536 * 6.6 V)
    void scan(uint16_t lv[8], uint16_t hv[4]);

private:
    Mux mux0_{pins::MUX0_S0, pins::MUX0_S1, pins::MUX0_S2, pins::MUX0_EN};
    Mux mux1_{pins::MUX1_S0, pins::MUX1_S1, pins::MUX1_S2, pins::MUX1_EN};
};
