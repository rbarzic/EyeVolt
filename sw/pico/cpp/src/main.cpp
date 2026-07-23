#include <cstdint>
#include <cstdio>
#include <cstring>

#include "pico/stdlib.h"

#include "pins.h"
#include "monitor.h"
#include "generator.h"
#include "waveform.h"

#ifndef EYEVOLT_VERSION
#define EYEVOLT_VERSION "2.0-cpp-?"
#endif

// ── Serial frame output ──────────────────────────────────────────────────────

static void print_frame(const char *tag, const uint16_t *vals, size_t n) {
    printf("%s::", tag);
    for (size_t i = 0; i < n; i++) {
        printf("%s%05u", i ? " " : "", (unsigned)vals[i]);
    }
    putchar('\n');
}

// ── Command protocol (host → Pico, newline-terminated ASCII) ─────────────────

static char cmd_buf[80];
static size_t cmd_len = 0;

static void print_help() {
    printf("HELP commands (newline-terminated):\n");
    printf("  SETDAC <ch> <raw>   set DAC ch 0-7 duty 0-65535 (-> 0-3.3 V)\n");
    printf("  SETMV  <ch> <mv>    set DAC ch 0-7 to millivolts 0-3300\n");
    printf("  OFF    <ch>         set DAC ch 0-7 to 0 V\n");
    printf("  OFFALL              stop playback + set all DAC channels to 0 V\n");
    printf("  WFLOAD <nsteps> <mask_hex>  upload binary waveform (expect WFREADY, then raw bytes)\n");
    printf("  WFPLAY [loop=0] [step_us=1000]  play loaded waveform\n");
    printf("  WFSTOP              stop playback\n");
    printf("  WFSTATUS            query playback state\n");
    printf("  VERSION             print firmware version\n");
    printf("  HELP                this message\n");
}

// Blocking binary receive for WFLOAD. Pauses monitoring for the ~0.5 s upload;
// USB backpressure (tinyUSB NAKs) provides flow control.
static void receive_waveform(WaveformPlayer &wf) {
    const size_t expected = wf.expected_bytes();
    printf("WFREADY %u\n", (unsigned)expected);

    absolute_time_t deadline = make_timeout_time_ms(pins::WF_UPLOAD_TIMEOUT_MS);
    bool complete = false;
    while (!complete && !time_reached(deadline)) {
        int c = getchar_timeout_us(500);
        if (c >= 0) {
            complete = wf.feed_byte((uint8_t)c);
        }
    }

    if (complete) {
        wf.finish_load();
        printf("OK WFLOADED 0x%08lX\n", (unsigned long)wf.checksum());
    } else {
        printf("ERROR timeout (%u/%u bytes)\n",
               (unsigned)wf.received(), (unsigned)expected);
    }
}

static void handle_command(const char *cmd, Generator &gen, WaveformPlayer &wf) {
    unsigned ch = 0, val = 0, mask = 0, loop = 0, step_us = 0;

    if (sscanf(cmd, " SETDAC %u %u", &ch, &val) == 2) {
        if (ch >= pins::NUM_DAC_CHANNELS || val > pins::DAC_MAX_RAW) {
            printf("ERROR bad args (ch 0-%u, raw 0-%u)\n",
                   pins::NUM_DAC_CHANNELS - 1, pins::DAC_MAX_RAW);
            return;
        }
        gen.set_raw(ch, (uint16_t)val);
        printf("OK DAC%u=%u\n", ch, val);
    } else if (sscanf(cmd, " SETMV %u %u", &ch, &val) == 2) {
        if (ch >= pins::NUM_DAC_CHANNELS || val > pins::DAC_FULLSCALE_MV) {
            printf("ERROR bad args (ch 0-%u, mv 0-%u)\n",
                   pins::NUM_DAC_CHANNELS - 1, pins::DAC_FULLSCALE_MV);
            return;
        }
        gen.set_millivolts(ch, (uint16_t)val);
        printf("OK DAC%u=%umV\n", ch, val);
    } else if (sscanf(cmd, " OFF %u", &ch) == 1) {
        if (ch >= pins::NUM_DAC_CHANNELS) {
            printf("ERROR bad channel (0-%u)\n", pins::NUM_DAC_CHANNELS - 1);
            return;
        }
        gen.off(ch);
        printf("OK DAC%u=0\n", ch);
    } else if (strncmp(cmd, "OFFALL", 6) == 0) {
        // Emergency "all to zero": stop any running waveform first, otherwise
        // the timer would re-drive the active channels on its next tick.
        wf.stop();
        gen.off_all();
        printf("OK all DAC=0\n");
    } else if (sscanf(cmd, " WFLOAD %u %x", &val, &mask) == 2) {
        // val = nsteps, mask = active-channel bitmask.
        if (wf.is_playing()) wf.stop();
        if (!wf.begin_load((uint16_t)val, (uint8_t)mask)) {
            printf("ERROR bad nsteps (1-%u)\n", pins::WF_MAX_STEPS);
            return;
        }
        receive_waveform(wf);   // prints WFREADY, then the ack or timeout
    } else if (strncmp(cmd, "WFPLAY", 6) == 0) {
        // Optional args: loop (0/1) and step_us. Missing args keep defaults.
        int n = sscanf(cmd, " WFPLAY %u %u", &loop, &step_us);
        if (n < 2) step_us = pins::WF_DEFAULT_STEP_US;
        if (n < 1) loop = 0;
        if (wf.state() == WfState::IDLE) {
            printf("ERROR no waveform loaded\n");
            return;
        }
        if (wf.is_playing()) {
            printf("ERROR already playing\n");
            return;
        }
        if (!wf.play(gen, loop != 0, step_us)) {
            printf("ERROR could not start playback\n");
            return;
        }
        printf("OK PLAYING nsteps=%u mask=0x%02X loop=%u step_us=%lu\n",
               wf.nsteps(), wf.mask(), (unsigned)(loop != 0),
               (unsigned long)wf.step_us());
    } else if (strncmp(cmd, "WFSTOP", 6) == 0) {
        uint16_t at = wf.step();
        wf.stop();
        printf("OK STOPPED step=%u\n", at);
    } else if (strncmp(cmd, "WFSTATUS", 8) == 0) {
        printf("WFSTAT %s %u %u 0x%02X\n",
               WaveformPlayer::state_name(wf.state()),
               wf.step(), wf.nsteps(), wf.mask());
    } else if (strncmp(cmd, "VERSION", 7) == 0) {
        printf("VERSION %s\n", EYEVOLT_VERSION);
    } else if (strncmp(cmd, "HELP", 4) == 0) {
        print_help();
    } else {
        printf("ERROR unknown command: '%s' (try HELP)\n", cmd);
    }
}

static void poll_commands(Generator &gen, WaveformPlayer &wf) {
    int c;
    while ((c = getchar_timeout_us(0)) != PICO_ERROR_TIMEOUT && c >= 0) {
        if (c == '\r' || c == '\n') {
            if (cmd_len > 0) {
                cmd_buf[cmd_len] = '\0';
                handle_command(cmd_buf, gen, wf);
                cmd_len = 0;
            }
        } else if (cmd_len < sizeof(cmd_buf) - 1) {
            cmd_buf[cmd_len++] = (char)c;
        }
    }
}

// ── Main loop ────────────────────────────────────────────────────────────────

int main() {
    stdio_init_all();

    Monitor monitor;
    Generator generator;
    static WaveformPlayer wf;   // 32 KB buffer — keep off the main stack
    monitor.init();
    generator.init();

    printf("-I- EyeVolt %s firmware started\n", EYEVOLT_VERSION);
    printf("-I- Monitoring: 1:: (8x LV) / 2:: (4x HV) / 3:: (8x DAC readback)\n");
    printf("-I- Type HELP for generation commands\n");

    uint16_t lv[pins::NUM_LV_CHANNELS];
    uint16_t hv[pins::NUM_HV_CHANNELS];
    uint16_t dac[pins::NUM_DAC_CHANNELS];

    while (true) {
        monitor.scan(lv, hv);

        print_frame("1", lv, pins::NUM_LV_CHANNELS);
        print_frame("2", hv, pins::NUM_HV_CHANNELS);

        // During playback the DACs are driven by the timer IRQ; skip the
        // readback scan (its 8×1 ms mux settle would only add USB/CPU load).
        if (!wf.is_playing()) {
            generator.readback(dac);
            print_frame("3", dac, pins::NUM_DAC_CHANNELS);
        }

        poll_commands(generator, wf);
    }
}
