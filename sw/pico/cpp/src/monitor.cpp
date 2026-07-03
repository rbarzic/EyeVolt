#include "monitor.h"
#include "pins.h"

#include "hardware/adc.h"

// Read the ADC at the given input, oversampled, returned as a 16-bit code
// (0-65535) to match MicroPython's read_u16() and the PC-side scaling.
static uint16_t adc_read16(uint input) {
    adc_select_input(input);
    uint32_t sum = 0;
    for (uint i = 0; i < pins::ADC_OVERSAMPLE; i++) {
        sum += adc_read();
    }
    uint32_t raw12 = sum / pins::ADC_OVERSAMPLE;
    return (uint16_t)(raw12 << 4);
}

void Monitor::init() {
    adc_init();
    adc_gpio_init(pins::ADC_MONITOR_PIN);   // GP26
    mux0_.init();
    mux1_.init();
}

void Monitor::scan(uint16_t lv[8], uint16_t hv[4]) {
    // Low-voltage channels 0-7: hold MUX1 on the cascade channel (CH4) so the
    // MUX0 bank is routed to GP26, then cycle MUX0 through its 8 inputs.
    mux1_.select(pins::MUX1_CASCADE_CHANNEL);
    for (uint j = 0; j < pins::NUM_LV_CHANNELS; j++) {
        mux0_.select(j);
        sleep_us(pins::MUX_SETTLE_US);
        lv[j] = adc_read16(pins::ADC_MONITOR);
    }

    // High-voltage channels 8-11: select MUX1 CH0..3 directly (still on GP26).
    mux0_.disable();
    for (uint j = 0; j < pins::NUM_HV_CHANNELS; j++) {
        mux1_.select(j);
        sleep_us(pins::MUX_SETTLE_US);
        hv[j] = adc_read16(pins::ADC_MONITOR);
    }

    mux1_.disable();
}
