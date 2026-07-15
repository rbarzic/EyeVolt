# ─── EyeVolt 2.0 — Pico firmware top-level convenience Makefile ────────────────
#
# Thin wrapper over the C++ firmware in cpp/ (which itself pulls in the
# pico-bootstrap submodule for the SDK, picotool and openocd). Provides the
# three everyday actions plus a combined default:
#
#   make build     compile the firmware        (-> cpp/build/eyevolt.elf/.uf2)
#   make upload    build + flash over the probe (openocd, resets after program)
#   make reset     reset the board via the debug probe
#   make all       build + upload + reset       (default)
#
# `flash` is a synonym for `upload`. Use PROBE_SERIAL=<serial> when more than
# one debug probe is attached (find it with `make identify-probe`):
#
#   make upload PROBE_SERIAL=E6647C740383232F

FW_DIR             := cpp
PICO_BOOTSTRAP_DIR := imported/pico-bootstrap
INSTALL_DIR        := $(abspath $(PICO_BOOTSTRAP_DIR)/deps)
OPENOCD_BIN        := $(INSTALL_DIR)/bin/openocd
OPENOCD_SCRIPTS    := $(INSTALL_DIR)/share/openocd/scripts

# rp2040.cfg for Pico, rp2350.cfg for Pico 2.
PICO_TARGET_CFG ?= rp2040.cfg

# Optional — only needed when several CMSIS-DAP probes are connected.
PROBE_SERIAL    ?=

.PHONY: all build upload flash reset identify-probe clean help

all: build upload reset

help:
	@echo "EyeVolt 2.0 Pico firmware:"
	@echo "  make build            compile the firmware (-> $(FW_DIR)/build/eyevolt.elf)"
	@echo "  make upload           build + flash over the debug probe (resets after)"
	@echo "  make reset            reset the board via the debug probe"
	@echo "  make all              build + upload + reset (default)"
	@echo "  make identify-probe   list attached debug probes by serial"
	@echo "  make clean            remove the build directory"
	@echo "  optional: PROBE_SERIAL=<serial>  when multiple probes are attached"

build:
	@$(MAKE) -C $(FW_DIR) build

upload flash:
	@$(MAKE) -C $(FW_DIR) flash PROBE_SERIAL=$(PROBE_SERIAL)

reset: | $(OPENOCD_BIN)
	@echo ">>> Resetting the Pico via debug probe..."
	@$(OPENOCD_BIN) \
	    -s $(OPENOCD_SCRIPTS) \
	    -f interface/cmsis-dap.cfg \
	    $(if $(PROBE_SERIAL),-c "adapter serial $(PROBE_SERIAL)") \
	    -f target/$(PICO_TARGET_CFG) \
	    -c "adapter speed 5000" \
	    -c "init; reset run; exit"

# openocd is built/installed by the pico-bootstrap layer on first flash.
$(OPENOCD_BIN):
	@$(MAKE) -C $(FW_DIR) install-openocd

identify-probe:
	@$(MAKE) -C $(FW_DIR) identify-probe

clean:
	@$(MAKE) -C $(FW_DIR) clean
