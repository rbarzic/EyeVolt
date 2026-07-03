#include <cstdint>
#include <cstdio>
#include <cstring>

#include "pico/stdlib.h"

#include "pins.h"
#include "monitor.h"
#include "generator.h"

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
    printf("  OFFALL              set all DAC channels to 0 V\n");
    printf("  VERSION             print firmware version\n");
    printf("  HELP                this message\n");
}

static void handle_command(const char *cmd, Generator &gen) {
    unsigned ch = 0, val = 0;

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
        gen.off_all();
        printf("OK all DAC=0\n");
    } else if (strncmp(cmd, "VERSION", 7) == 0) {
        printf("VERSION %s\n", EYEVOLT_VERSION);
    } else if (strncmp(cmd, "HELP", 4) == 0) {
        print_help();
    } else {
        printf("ERROR unknown command: '%s' (try HELP)\n", cmd);
    }
}

static void poll_commands(Generator &gen) {
    int c;
    while ((c = getchar_timeout_us(0)) != PICO_ERROR_TIMEOUT && c >= 0) {
        if (c == '\r' || c == '\n') {
            if (cmd_len > 0) {
                cmd_buf[cmd_len] = '\0';
                handle_command(cmd_buf, gen);
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

        generator.readback(dac);
        print_frame("3", dac, pins::NUM_DAC_CHANNELS);

        poll_commands(generator);
    }
}
