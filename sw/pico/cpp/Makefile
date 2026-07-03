# ─── Project configuration ────────────────────────────────────────────────────
PROJECT_NAME    := eyevolt

# pico-bootstrap lives as a submodule one level up, under imported/
PICO_BOOTSTRAP_DIR := ../imported/pico-bootstrap

# Reuse the pico-bootstrap deps/ directory (shared SDK + tool install)
INSTALL_DIR     := $(abspath $(PICO_BOOTSTRAP_DIR)/deps)

# Debug Probe serial (find with: make identify-probe)
PROBE_SERIAL    ?=

# Pico (RP2040)
PICO_TARGET_CFG ?= rp2040.cfg

MONITOR_BAUD    ?= 115200

# ─── Pull in all pico-bootstrap targets ───────────────────────────────────────
include $(PICO_BOOTSTRAP_DIR)/Makefile

# ─── Project build ────────────────────────────────────────────────────────────
BUILD_DIR := build

.PHONY: build clean flash monitor-project

build: download-pico-sdk
	@echo ">>> Configuring $(PROJECT_NAME)..."
	@cmake -S . -B $(BUILD_DIR) \
	       -DPICO_SDK_PATH=$(PICO_SDK_PATH) \
	       -DPROJECT_NAME=$(PROJECT_NAME)
	@echo ">>> Building $(PROJECT_NAME)..."
	@$(MAKE) -C $(BUILD_DIR)
	@echo ">>> Built: $(BUILD_DIR)/$(PROJECT_NAME).elf"

clean:
	@rm -rf $(BUILD_DIR)

flash: build install-openocd
	$(MAKE) upload \
	    TARGET_ELF=$(BUILD_DIR)/$(PROJECT_NAME).elf \
	    PROBE_SERIAL=$(PROBE_SERIAL) \
	    PICO_TARGET_CFG=$(PICO_TARGET_CFG)

monitor-project:
	$(MAKE) monitor PROBE_SERIAL=$(PROBE_SERIAL) MONITOR_BAUD=$(MONITOR_BAUD)
