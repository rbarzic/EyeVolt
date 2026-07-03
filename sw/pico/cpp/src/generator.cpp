#include "generator.h"
#include "pins.h"

#include "hardware/adc.h"
#include "hardware/pwm.h"

static uint16_t adc_read16_fb() {
    adc_select_input(pins::ADC_READBACK);
    uint32_t sum = 0;
    for (uint i = 0; i < pins::ADC_OVERSAMPLE; i++) {
        sum += adc_read();
    }
    uint32_t raw12 = sum / pins::ADC_OVERSAMPLE;
    return (uint16_t)(raw12 << 4);
}

void Generator::init() {
    adc_gpio_init(pins::ADC_READBACK_PIN);   // GP27
    fb_mux_.init();

    // Configure all 8 PWM outputs (GP2-GP9 → slices 1-4, channels A/B).
    // 16-bit wrap (65535) gives duty 0-65535 mapping 1:1 to the protocol scale;
    // at 125 MHz sys clock the carrier is ~1.9 kHz, well above the 16 Hz filter.
    for (uint ch = 0; ch < pins::NUM_DAC_CHANNELS; ch++) {
        uint pin = pins::DAC_PWM_FIRST + ch;
        gpio_set_function(pin, GPIO_FUNC_PWM);
        uint slice = pwm_gpio_to_slice_num(pin);
        pwm_set_wrap(slice, pins::DAC_MAX_RAW);
        pwm_set_chan_level(slice, pwm_gpio_to_channel(pin), 0);
        pwm_set_enabled(slice, true);
        duty_[ch] = 0;
    }
}

void Generator::set_raw(uint ch, uint16_t duty16) {
    if (ch >= pins::NUM_DAC_CHANNELS) return;
    uint pin = pins::DAC_PWM_FIRST + ch;
    uint slice = pwm_gpio_to_slice_num(pin);
    uint chan = pwm_gpio_to_channel(pin);
    pwm_set_chan_level(slice, chan, duty16);
    duty_[ch] = duty16;
}

void Generator::set_millivolts(uint ch, uint16_t millivolts) {
    if (millivolts > pins::DAC_FULLSCALE_MV) millivolts = pins::DAC_FULLSCALE_MV;
    uint32_t duty = (uint32_t)millivolts * pins::DAC_MAX_RAW / pins::DAC_FULLSCALE_MV;
    set_raw(ch, (uint16_t)duty);
}

void Generator::off(uint ch) { set_raw(ch, 0); }

void Generator::off_all() {
    for (uint ch = 0; ch < pins::NUM_DAC_CHANNELS; ch++) {
        off(ch);
    }
}

uint16_t Generator::duty(uint ch) const {
    return (ch < pins::NUM_DAC_CHANNELS) ? duty_[ch] : 0;
}

void Generator::readback(uint16_t out[8]) {
    for (uint ch = 0; ch < pins::NUM_DAC_CHANNELS; ch++) {
        fb_mux_.select(ch);
        sleep_us(pins::READBACK_SETTLE_US);
        out[ch] = adc_read16_fb();
    }
    fb_mux_.disable();
}
