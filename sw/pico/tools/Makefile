# ─── Polaris power-up sequence demo ───────────────────────────────────────────
#
# Convenience targets to build and play the Polaris power sequence waveform
# (examples/polaris_power.pwl → polaris.bin) on a connected EyeVolt 2.0 board.
#
#   make preview      # show the per-channel summary (no hardware)
#   make bin          # build polaris.bin + polaris.meta
#   make play         # upload + play once  (T = 400 * STEP_US)
#   make loop         # upload + play looping
#   make stop         # stop playback
#   make off          # zero all DAC outputs
#   make clean        # remove generated .bin/.meta
#
# Overridable variables:
#   make play PORT=/dev/ttyACM1     # pick the serial port explicitly
#   make play STEP_US=625           # T = 250 ms  (spec: 200 ms < T < 500 ms)
#   make play STEP_US=1250          # T = 500 ms

PYTHON  ?= python3

# Auto-detect the EyeVolt board's USB-CDC port (by-id survives re-enumeration);
# fall back to a default-descriptor Pico, then /dev/ttyACM0. Override with
# PORT=... on the command line.
PORT    ?= $(firstword $(wildcard /dev/serial/by-id/usb-EyeVolt_*) \
                       $(wildcard /dev/serial/by-id/usb-Raspberry_Pi_Pico_*) \
                       /dev/ttyACM0)

# Step period in microseconds. The waveform uses T = 400 steps, so the real
# per-interval time is T = 400 * STEP_US. Default 1000 us → T = 400 ms.
STEP_US ?= 1000

PWL      := examples/polaris_power.pwl
BIN      := polaris.bin
META     := polaris.meta
CONVERT  := $(PYTHON) pwl_to_waveform.py
UPLOAD   := $(PYTHON) wf_upload.py

# Send a single serial command to the board and print the reply.
define send_cmd
$(PYTHON) -c "import serial,time; s=serial.Serial('$(PORT)',9600,timeout=1); \
time.sleep(0.2); s.reset_input_buffer(); s.write(b'$(1)\n'); s.flush(); \
[print(l.decode(errors='replace').strip()) for l in [s.readline() for _ in range(20)] \
 if l.strip().startswith(b'$(2)')]; s.close()"
endef

.PHONY: help preview bin play loop stop off clean
help:
	@echo "Polaris power-up sequence demo (port: $(PORT), T = 400 * $(STEP_US)us = $$(( 400 * $(STEP_US) / 1000 ))ms)"
	@echo "  make preview   show per-channel summary (no hardware)"
	@echo "  make bin       build $(BIN) (+ $(META))"
	@echo "  make play      upload + play once"
	@echo "  make loop      upload + play looping"
	@echo "  make stop      stop playback"
	@echo "  make off       zero all DAC outputs"
	@echo "  make clean     remove generated files"
	@echo "  overrides: PORT=/dev/ttyACMx  STEP_US=<200000/400..500000/400>"

preview:
	@$(CONVERT) $(PWL) --preview

$(BIN): $(PWL) pwl_to_waveform.py
	@$(CONVERT) $(PWL) -o $(BIN)

bin: $(BIN)

play: $(BIN)
	@echo ">>> Playing Polaris sequence on $(PORT)  (T = $$(( 400 * $(STEP_US) / 1000 )) ms, ~$$(( 2048 * $(STEP_US) / 1000 )) ms total)"
	@$(UPLOAD) $(PORT) $(BIN) --play --step-us $(STEP_US)

loop: $(BIN)
	@echo ">>> Looping Polaris sequence on $(PORT)  (Ctrl-C to return; use 'make stop' to halt)"
	@$(UPLOAD) $(PORT) $(BIN) --loop --step-us $(STEP_US)

stop:
	@$(call send_cmd,WFSTOP,OK STOPPED)

off:
	@$(call send_cmd,OFFALL,OK)

clean:
	@rm -f $(BIN) $(META)
