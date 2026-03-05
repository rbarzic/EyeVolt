# pip install pyserial==3.4
# pip install  rshell
# eventually:
# pip install --ignore-installed  -U rshell

# but do a rehash
#
# pip install mpremote
PROJECT=eyevolt
SERIAL_PORT?=/dev/ttyACM1
SOFTWARE?=main.py

SHELL := /bin/bash

copy:
	rshell -p $(SERIAL_PORT) --buffer-size=512 cp $(SOFTWARE) /pyboard/$(SOFTWARE)


reset:
	rshell -p $(SERIAL_PORT) "repl ~ import machine ~ machine.soft_reset() ~" 

run:
	mpremote connect $(SERIAL_PORT)  run $(SOFTWARE)


.PHONY: mkvenv

mkvenv:
	@VENV_WRAPPER=$$(which virtualenvwrapper.sh 2>/dev/null); \
	if [ -z "$$VENV_WRAPPER" ] || [ ! -f "$$VENV_WRAPPER" ]; then \
	VENV_WRAPPER=/usr/share/virtualenvwrapper/virtualenvwrapper.sh; \
	fi; \
	. $$VENV_WRAPPER && mkvirtualenv -p python3 $(PROJECT) -r requirements.txt
