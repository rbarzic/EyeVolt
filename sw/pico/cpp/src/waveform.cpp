#include "waveform.h"

#include "generator.h"
#include "pins.h"

#include "hardware/pwm.h"

// ── Upload ───────────────────────────────────────────────────────────────────

bool WaveformPlayer::begin_load(uint16_t nsteps, uint8_t mask) {
    if (nsteps == 0 || nsteps > pins::WF_MAX_STEPS) return false;
    nsteps_      = nsteps;
    active_mask_ = mask;
    rx_count_    = 0;
    step_        = 0;
    // Stay out of PLAYING while a fresh buffer is being filled.
    state_ = WfState::IDLE;
    return true;
}

bool WaveformPlayer::feed_byte(uint8_t b) {
    const size_t expected = expected_bytes();
    if (rx_count_ < expected) {
        // Buffer is step-major uint16 little-endian; write bytes in order.
        uint8_t *raw = reinterpret_cast<uint8_t *>(&waveform_[0][0]);
        raw[rx_count_++] = b;
    }
    return rx_count_ >= expected;
}

size_t WaveformPlayer::expected_bytes() const {
    return (size_t)nsteps_ * pins::NUM_DAC_CHANNELS * sizeof(uint16_t);
}

uint32_t WaveformPlayer::checksum() const {
    const uint16_t *p = &waveform_[0][0];
    const size_t n = (size_t)nsteps_ * pins::NUM_DAC_CHANNELS;
    uint32_t sum = 0;
    for (size_t i = 0; i < n; i++) sum += p[i];
    return sum;
}

// ── Playback ─────────────────────────────────────────────────────────────────

bool WaveformPlayer::play(Generator &gen, bool loop, uint32_t step_us) {
    (void)gen;  // playback writes PWM registers directly, not via Generator
    if (state_ == WfState::IDLE || nsteps_ == 0) return false;
    if (state_ == WfState::PLAYING) return false;

    if (step_us < pins::WF_MIN_STEP_US) step_us = pins::WF_MIN_STEP_US;
    if (step_us > pins::WF_MAX_STEP_US) step_us = pins::WF_MAX_STEP_US;

    step_    = 0;
    loop_    = loop;
    step_us_ = step_us;
    state_   = WfState::PLAYING;

    // Negative delay → period measured from the scheduled time, so ticks do
    // not drift by the callback's own execution time.
    if (!add_repeating_timer_us(-(int64_t)step_us_, &WaveformPlayer::timer_callback,
                                this, &timer_)) {
        state_ = WfState::LOADED;
        return false;
    }
    timer_armed_ = true;
    return true;
}

void WaveformPlayer::stop() {
    if (timer_armed_) {
        cancel_repeating_timer(&timer_);
        timer_armed_ = false;
    }
    if (state_ == WfState::PLAYING) {
        state_ = WfState::LOADED;
    }
}

void WaveformPlayer::reset(Generator &gen) {
    stop();
    gen.off_all();
    state_ = WfState::IDLE;
    nsteps_      = 0;
    active_mask_ = 0;
    step_        = 0;
    rx_count_    = 0;
}

const char *WaveformPlayer::state_name(WfState s) {
    switch (s) {
        case WfState::IDLE:    return "IDLE";
        case WfState::LOADED:  return "LOADED";
        case WfState::PLAYING: return "PLAYING";
    }
    return "?";
}

// ── Timer callback (IRQ context) ─────────────────────────────────────────────
//
// Must be short and non-blocking: no printf, no sleep, no allocation.
// pwm_set_chan_level() is a single MMIO write, safe from IRQ.
//
bool WaveformPlayer::timer_callback(repeating_timer_t *rt) {
    auto *self = static_cast<WaveformPlayer *>(rt->user_data);
    const uint16_t *row = self->waveform_[self->step_];

    for (uint ch = 0; ch < pins::NUM_DAC_CHANNELS; ch++) {
        if (self->active_mask_ & (1u << ch)) {
            uint pin  = pins::DAC_PWM_FIRST + ch;
            uint sl   = pwm_gpio_to_slice_num(pin);
            uint chan = pwm_gpio_to_channel(pin);
            pwm_set_chan_level(sl, chan, row[ch]);
        }
    }

    uint16_t next = self->step_ + 1;
    if (next >= self->nsteps_) {
        if (self->loop_) {
            self->step_ = 0;
            return true;   // keep running
        }
        // One-shot done: hold last values, cancel timer.
        self->step_        = self->nsteps_;   // report completion via step()
        self->state_       = WfState::LOADED;
        self->timer_armed_ = false;
        return false;
    }
    self->step_ = next;
    return true;
}
