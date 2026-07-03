#pragma once

#include "pico/stdlib.h"

//
// Generic 74HCT4051 8:1 analog multiplexer driver.
//
// Drives three select lines (S0, S1, S2) and an active-low enable (~E).
// select(channel) routes one of 8 inputs to the common pin; disable() puts
// the common pin in high-impedance.
//
class Mux {
public:
    constexpr Mux(uint s0, uint s1, uint s2, uint en)
        : s0_(s0), s1_(s1), s2_(s2), en_(en) {}

    void init() const {
        gpio_init(s0_); gpio_set_dir(s0_, GPIO_OUT);
        gpio_init(s1_); gpio_set_dir(s1_, GPIO_OUT);
        gpio_init(s2_); gpio_set_dir(s2_, GPIO_OUT);
        gpio_init(en_); gpio_set_dir(en_, GPIO_OUT);
        disable();
    }

    // Select channel 0-7 and enable the mux (assert ~E low).
    void select(uint channel) const {
        gpio_put(s0_, channel & 1u);
        gpio_put(s1_, (channel >> 1) & 1u);
        gpio_put(s2_, (channel >> 2) & 1u);
        gpio_put(en_, 0);
    }

    // Disable the mux (deassert ~E high → high-impedance common pin).
    void disable() const { gpio_put(en_, 1); }

private:
    uint s0_, s1_, s2_, en_;
};
