#!/usr/bin/env python3
import argparse
import asyncio
import logging

import serial_asyncio
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Label, ProgressBar


def get_color(value: float) -> str:
    """
    Returns a color value based on the given voltage.
    - below 0.5: white
    - between 0.5 and 0.8: yellow
    - between 0.8 and 1.2: light green (#66FF66)
    - above 1.2: light red (#FF6666)
    """
    if value < 0.5:
        return "white"
    elif value < 0.8:
        return "yellow"
    elif value < 1.2:
        return "#66FF66"
    else:
        return "#FF6666"


class VoltageDisplay(Widget):
    """
    A composite widget to display a voltage reading with a progress bar.
    It shows a static text (prefix) and a numerical value (styled in bold and colored),
    followed by a progress bar below.
    If the channel is disabled, the value is replaced by "----" and the bar is cleared.
    """

    def __init__(self, static_text: str, index: int, enabled: bool = True, **kwargs) -> None:
        super().__init__(**kwargs)
        self.static_text = static_text
        self.index = index
        self.enabled = enabled

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label(f"{self.static_text}: 0.00", id=f"label_{self.index}"),
            ProgressBar(total=100, id=f"progress_{self.index}")
        )

    def update_value(self, new_value: float):
        label = self.query_one(f"#label_{self.index}", Label)
        progress_bar = self.query_one(f"#progress_{self.index}", ProgressBar)
        # If channel is disabled, display placeholder and clear progress.
        if not self.enabled:
            label.update(f"{self.static_text}: ----")
            progress_bar.progress = 0
            progress_bar.styles.bar_color = "grey"
            return

        max_val = 3.3 if self.index < 8 else 6.6
        pct = int(new_value / max_val * 100)
        color = get_color(new_value)
        # Update label: static text is unstyled; only the numerical value is bold with color.
        label.update(f"{self.static_text}: " + f"[bold][{color}]{new_value:.2f}[/{color}][/bold]")
        progress_bar.progress = pct
        progress_bar.styles.bar_color = color


class SerialProtocol(asyncio.Protocol):
    """
    Protocol for asynchronous serial reading.
    Expects lines beginning with "1::" (8 values) or "2::" (4 values) as ASCII decimal integers.
    """

    def __init__(self, tui_app: "SerialTUI"):
        self.app = tui_app
        self.buffer = bytearray()

    def connection_made(self, transport):
        self.transport = transport
        self.app.log("Serial connection established.")

    def data_received(self, data: bytes):
        self.buffer.extend(data)
        while b"\n" in self.buffer:
            line, sep, self.buffer = self.buffer.partition(b"\n")
            try:
                line = line.decode("ascii").strip()
            except UnicodeDecodeError:
                self.app.log("Error decoding line from serial port.")
                continue
            self.process_line(line)

    def process_line(self, line: str):
        if line.startswith("1::"):
            parts = line[3:].strip().split()
            if len(parts) != 8:
                self.app.log(f"Unexpected number of values in header 1: {parts}")
                return
            try:
                raw_values = [int(part) for part in parts]
            except ValueError:
                self.app.log("Header 1: one of the values is not an integer.")
                return
            conv_values = [raw / 65536.0 * 3.3 for raw in raw_values]
            self.app.update_values(list(range(0, 8)), conv_values)
        elif line.startswith("2::"):
            parts = line[3:].strip().split()
            if len(parts) != 4:
                self.app.log(f"Unexpected number of values in header 2: {parts}")
                return
            try:
                raw_values = [int(part) for part in parts]
            except ValueError:
                self.app.log("Header 2: one of the values is not an integer.")
                return
            conv_values = [raw / 65536.0 * 6.6 for raw in raw_values]
            self.app.update_values(list(range(8, 12)), conv_values)
        else:
            self.app.log(f"Unrecognized data: {line}")


class SerialTUI(App):
    """
    A TUI application that displays 12 voltage fields in a 3×4 grid.
    Each field shows a static label, a numerical voltage value (styled with bold and color),
    and a progress bar. Individual channels may be disabled via command-line options.
    """

    CSS = """
    Screen {
        layout: grid;
        grid-size: 3 4;
        align: center middle;
    }
    """

    def __init__(self, serial_port: str, static_texts: list[str], channel_config: list[bool], **kwargs):
        super().__init__(**kwargs)
        self.serial_port = serial_port
        self.static_texts = static_texts
        self.channel_config = channel_config
        self.current_values = [0.0] * 12
        self.displays = []

    def compose(self) -> ComposeResult:
        for i in range(12):
            yield VoltageDisplay(
                self.static_texts[i],
                i,
                enabled=self.channel_config[i],
                id=f"voltage_{i}"
            )

    async def on_mount(self) -> None:
        self.log(f"Mounting TUI with serial port: {self.serial_port}")
        self.displays = [self.query_one(f"#voltage_{i}", VoltageDisplay) for i in range(12)]
        asyncio.create_task(self.read_serial())

    async def read_serial(self):
        loop = asyncio.get_running_loop()
        self.log("Opening serial connection...")
        try:
            transport, protocol = await serial_asyncio.create_serial_connection(
                loop,
                lambda: SerialProtocol(self),
                self.serial_port,
                baudrate=9600,
            )
            self.log("Serial connection running.")
        except Exception as e:
            self.log(f"Failed to open serial port: {e}")

    def update_values(self, indices, new_values):
        for idx, val in zip(indices, new_values):
            self.current_values[idx] = val
            self.displays[idx].update_value(val)
        self.refresh()


def parse_text_options(text_option: str) -> dict:
    mapping = {}
    if text_option:
        for pair in text_option.split(","):
            if "=" in pair:
                key, value = pair.split("=", 1)
                mapping[key.strip()] = value.strip()
    return mapping


def parse_channel_options(channel_option: str) -> dict:
    mapping = {}
    if channel_option:
        for pair in channel_option.split(","):
            if "=" in pair:
                key, value = pair.split("=", 1)
                mapping[key.strip()] = value.strip().lower()
    return mapping


def main():
    parser = argparse.ArgumentParser(
        description="TUI application that reads 12 integer values via serial and displays them with progress bars."
    )
    parser.add_argument("port", help="Path to the serial port (e.g. /dev/ttyUSB0 or COM3)")
    parser.add_argument(
        "--text",
        help="Comma-separated key=value pairs to override label texts. "
             "Expected key format is 'val#' (zero-based), e.g., --text val0=NewText1,val3=NewText4",
        default="",
    )
    parser.add_argument(
        "--channel",
        help="Comma-separated key=value pairs to enable/disable channels. "
             "Expected key format is 'val#' (zero-based), e.g., --channel val0=off,val3=off,val4=on. "
             "Channels not listed are 'on' by default.",
        default="",
    )
    args = parser.parse_args()

    default_texts = [f"Value{i+1}" for i in range(12)]
    text_overrides = parse_text_options(args.text)
    for key, new_text in text_overrides.items():
        if key.startswith("val"):
            try:
                idx = int(key[3:])
                if 0 <= idx < 12:
                    default_texts[idx] = new_text
            except ValueError:
                pass

    channel_flags = [True] * 12
    channel_overrides = parse_channel_options(args.channel)
    for key, status in channel_overrides.items():
        if key.startswith("val"):
            try:
                idx = int(key[3:])
                if 0 <= idx < 12:
                    channel_flags[idx] = (status != "off")
            except ValueError:
                pass

    logging.basicConfig(level=logging.DEBUG)
    app = SerialTUI(serial_port=args.port, static_texts=default_texts, channel_config=channel_flags)
    app.title = "Serial Port TUI"
    app.run()


if __name__ == "__main__":
    main()
