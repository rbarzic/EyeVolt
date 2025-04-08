#!/usr/bin/env python3
import argparse
import asyncio
import logging

import serial_asyncio
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Label, ProgressBar


class VoltageDisplay(Widget):
    """
    Composite widget to display a voltage reading along with a progress bar.
    The widget displays a static text (prefix) and the current voltage value,
    then below shows a progress bar representing the voltage as a percentage
    of its maximum (3.3 for channels 1-8, 6.6 for channels 9-12).
    """

    def __init__(self, static_text: str, index: int, **kwargs) -> None:
        """
        :param static_text: The text label (prefix) for the field.
        :param index: The zero-based channel index.
        """
        super().__init__(**kwargs)
        self.static_text = static_text
        self.index = index

    def compose(self) -> ComposeResult:
        # Create a vertical container with a Label and a ProgressBar.
        yield Vertical(
            Label(f"{self.static_text}: 0.00", id=f"label_{self.index}"),
            ProgressBar(total=100, id=f"progress_{self.index}")
        )

    def update_value(self, new_value: float):
        """
        Update the text and progress bar for this field.
        :param new_value: The new voltage reading.
        """
        # Determine maximum voltage based on channel index.
        max_val = 3.3 if self.index < 8 else 6.6
        # Compute percentage (0 to 100).
        pct = int(new_value / max_val * 100)
        # Update the label with the formatted voltage value.
        self.query_one(f"#label_{self.index}", Label).update(f"{self.static_text}: {new_value:.2f}")
        # Update the progress bar by setting its 'progress' property.
        bar: ProgressBar = self.query_one(f"#progress_{self.index}", ProgressBar)
        bar.progress = pct


class SerialProtocol(asyncio.Protocol):
    """
    Protocol for asynchronous serial reading.
    Expects lines starting with "1::" (8 values) or "2::" (4 values),
    with each value represented as an ASCII decimal integer.
    """

    def __init__(self, tui_app: "SerialTUI"):
        self.app = tui_app
        self.buffer = bytearray()

    def connection_made(self, transport):
        self.transport = transport
        self.app.log("Serial connection established.")

    def data_received(self, data: bytes):
        # Accumulate data until a newline is received.
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
            # Parse header "1::": expect 8 integers.
            parts = line[3:].strip().split()
            if len(parts) != 8:
                self.app.log(f"Unexpected number of values in header 1: {parts}")
                return
            try:
                raw_values = [int(part) for part in parts]
            except ValueError:
                self.app.log("Header 1: one of the values is not an integer.")
                return
            # Convert raw integer (0–65536) to voltage in range 0–3.3.
            conv_values = [raw / 65536.0 * 3.3 for raw in raw_values]
            self.app.update_values(list(range(0, 8)), conv_values)

        elif line.startswith("2::"):
            # Parse header "2::": expect 4 integers.
            parts = line[3:].strip().split()
            if len(parts) != 4:
                self.app.log(f"Unexpected number of values in header 2: {parts}")
                return
            try:
                raw_values = [int(part) for part in parts]
            except ValueError:
                self.app.log("Header 2: one of the values is not an integer.")
                return
            # Convert raw integer (0–65536) to voltage in range 0–6.6.
            conv_values = [raw / 65536.0 * 6.6 for raw in raw_values]
            self.app.update_values(list(range(8, 12)), conv_values)

        else:
            self.app.log(f"Unrecognized data: {line}")


class SerialTUI(App):
    """
    A Textual TUI application that displays 12 voltage fields.
    The fields are arranged in a grid of 3 columns by 4 rows.
    Each field shows a static label and the measured voltage,
    with a progress bar below for visual representation.
    """

    CSS = """
    Screen {
        layout: grid;
        grid-size: 3 4;
        align: center middle;
    }
    """

    def __init__(self, serial_port: str, static_texts: list[str], **kwargs):
        """
        :param serial_port: The serial port to open.
        :param static_texts: A list of 12 static texts (one per channel).
        """
        super().__init__(**kwargs)
        self.serial_port = serial_port
        self.static_texts = static_texts
        self.current_values = [0.0] * 12
        self.displays = []  # List of VoltageDisplay widgets.

    def compose(self) -> ComposeResult:
        # Yield 12 VoltageDisplay widgets.
        for i in range(12):
            yield VoltageDisplay(self.static_texts[i], i, id=f"voltage_{i}")

    async def on_mount(self) -> None:
        self.log(f"Mounting TUI with serial port: {self.serial_port}")
        self.displays = [self.query_one(f"#voltage_{i}", VoltageDisplay) for i in range(12)]
        # Start the asynchronous serial reading task.
        asyncio.create_task(self.read_serial())

    async def read_serial(self):
        loop = asyncio.get_running_loop()
        self.log("Opening serial connection...")
        try:
            transport, protocol = await serial_asyncio.create_serial_connection(
                loop,
                lambda: SerialProtocol(self),
                self.serial_port,
                baudrate=9600,  # Adjust baudrate as needed.
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
    """
    Parse comma-separated key=value pairs into a dictionary.
    Expected keys use the format "val#" where # is the zero-based index.
    For example: "val0=NewText1,val3=NewText4"
    """
    mapping = {}
    if text_option:
        pairs = text_option.split(",")
        for pair in pairs:
            if "=" in pair:
                key, value = pair.split("=", 1)
                mapping[key.strip()] = value.strip()
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
    args = parser.parse_args()

    # Set default static texts "Value1" to "Value12".
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

    logging.basicConfig(level=logging.DEBUG)
    app = SerialTUI(serial_port=args.port, static_texts=default_texts)
    app.title = "Serial Port TUI"
    app.run()


if __name__ == "__main__":
    main()
