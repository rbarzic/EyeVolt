#pragma once

#include <cstddef>
#include <cstdint>

#include "pico/stdlib.h"
#include "pico/time.h"

#include "pins.h"

class Generator;

//
// Pre-computed waveform player for the EyeVolt 2.0 generator.
//
// A host uploads up to WF_MAX_STEPS steps of 8 channels × 16-bit into SRAM.
// play() arms a repeating hardware timer that, in IRQ context, writes each
// step's active channels directly to the PWM registers — the main loop keeps
// running (monitoring + command handling) during playback.
//
// Channels not present in active_mask_ are never touched, so they hold whatever
// manual value (SETMV/SETDAC) they were last given.
//
enum class WfState { IDLE, LOADED, PLAYING };

class WaveformPlayer {
public:
    // Prepare to receive nsteps × 8 × 2 bytes of binary waveform data.
    // Sets active_mask_ and resets the receive counter. Returns false if
    // nsteps is 0 or > WF_MAX_STEPS.
    bool begin_load(uint16_t nsteps, uint8_t mask);

    // Feed one received byte into the buffer (little-endian uint16 order).
    // Returns true once expected_bytes() have been received (upload complete).
    bool feed_byte(uint8_t b);

    // 32-bit additive checksum of the loaded waveform data (nsteps × 8 values).
    uint32_t checksum() const;

    // Number of bytes expected by the current upload (nsteps × 8 × 2).
    size_t expected_bytes() const;

    // Bytes received so far during the in-progress upload.
    size_t received() const { return rx_count_; }

    // Mark the just-finished upload as ready to play.
    void finish_load() { state_ = WfState::LOADED; }

    // Start playback. step_us = microseconds per step. loop = wrap at end.
    // Returns false if no waveform is loaded or the timer could not be armed.
    bool play(Generator &gen, bool loop, uint32_t step_us);

    // Stop playback (cancel the timer). DACs hold their last written values.
    void stop();

    // Reset to IDLE: stop playback and zero all DAC channels via the generator.
    void reset(Generator &gen);

    // ── Queries ──
    WfState  state() const      { return state_; }
    bool     is_loaded() const  { return state_ != WfState::IDLE; }
    bool     is_playing() const { return state_ == WfState::PLAYING; }
    uint16_t step() const       { return step_; }
    uint16_t nsteps() const     { return nsteps_; }
    uint8_t  mask() const       { return active_mask_; }
    uint32_t step_us() const    { return step_us_; }
    bool     loop() const       { return loop_; }

    // Human-readable state name for WFSTATUS.
    static const char *state_name(WfState s);

private:
    static bool timer_callback(repeating_timer_t *rt);

    uint16_t waveform_[pins::WF_MAX_STEPS][pins::NUM_DAC_CHANNELS];

    volatile WfState  state_       = WfState::IDLE;
    uint16_t          nsteps_      = 0;
    uint8_t           active_mask_ = 0;
    volatile uint16_t step_        = 0;
    bool              loop_        = false;
    uint32_t          step_us_     = pins::WF_DEFAULT_STEP_US;
    size_t            rx_count_    = 0;   // bytes received so far during upload
    repeating_timer_t timer_       = {};
    bool              timer_armed_ = false;
};
