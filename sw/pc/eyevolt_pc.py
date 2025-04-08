#!/usr/bin/env python3
import argparse
import asyncio
import logging

import serial_asyncio
from textual.app import App
from textual.widgets import Label


class SerialProtocol(asyncio.Protocol):
    """
    Protocol to handle asynchronous serial reading.
    It expects lines starting with "1::" (8 values) or "2::" (4 values),
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
        # Process the incoming line by header type.
        if line.startswith("1::"):
            # For header "1::": expect 8 integers.
            parts = line[3:].strip().split()
            if len(parts) != 8:
                self.app.log(f"Unexpected number of values in header 1: {parts}")
                return
            try:
                raw_values = [int(part) for part in parts]
            except ValueError:
                self.app.log("Header 1: one of the values is not an integer.")
                return
            # Convert raw int (0–65536) to float in range 0–3.3.
            conv_values = [raw / 65536.0 * 3.3 for raw in raw_values]
            # Update UI for channels 1–8 (indices 0–7).
            self.app.update_values(list(range(0, 8)), conv_values)

        elif line.startswith("2::"):
            # For header "2::": expect 4 integers.
            parts = line[3:].strip().split()
            if len(parts) != 4:
                self.app.log(f"Unexpected number of values in header 2: {parts}")
                return
            try:
                raw_values = [int(part) for part in parts]
            except ValueError:
                self.app.log("Header 2: one of the values is not an integer.")
                return
            # Convert raw int (0–65536) to float in range 0–6.6.
            conv_values = [raw / 65536.0 * 6.6 for raw in raw_values]
            # Update UI for channels 9–12 (indices 8–11).
            self.app.update_values(list(range(8, 12)), conv_values)
        else:
            self.app.log(f"Unrecognized data: {line}")


class SerialTUI(App):
    """
    A Textual TUI application that displays 12 numeric fields.
    The values are arranged in a 3-column grid (each column with 4 rows):
      - Column 1: channels 1–4
      - Column 2: channels 5–8
      - Column 3: channels 9–12

    Each field displays a static label (by default "Value#") followed by the current value.
    The static text can be overridden via command-line options.
    """

    CSS = """
    Screen {
        layout: grid;
        grid-size: 3 4;
        align: center middle;
    }
    Label {
        margin: 1;
    }
    """

    def __init__(self, serial_port: str, static_texts: list[str], **kwargs):
        """
        :param serial_port: The serial port to open.
        :param static_texts: A list of 12 strings containing the static text for each field.
        """
        super().__init__(**kwargs)
        self.serial_port = serial_port
        self.current_values = [0.0] * 12
        self.static_texts = static_texts  # List of 12 strings, one per field.
        self.labels = []  # Will be populated in compose().

    def compose(self):
        # Create 12 Label widgets, each showing "StaticText: 0.00"
        for i in range(12):
            label_text = f"{self.static_texts[i]}: 0.00"
            yield Label(label_text, id=f"label_{i}")

    async def on_mount(self) -> None:
        self.log(f"Mounting TUI with serial port: {self.serial_port}")
        # Retrieve references to the Label widgets by their IDs.
        self.labels = [self.query_one(f"#label_{i}", Label) for i in range(12)]
        # Start the serial port reading task.
        asyncio.create_task(self.read_serial())

    async def read_serial(self):
        loop = asyncio.get_running_loop()
        self.log("Opening serial connection...")
        try:
            # Create the serial connection using serial_asyncio.
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
        """
        Update the displayed values on the labels.
        :param indices: List of indices of the labels to update.
        :param new_values: List of new float values (already converted and scaled).
        """
        for idx, val in zip(indices, new_values):
            self.current_values[idx] = val
            # Update each label to include its static prefix and its current value.
            self.labels[idx].update(f"{self.static_texts[idx]}: {val:.2f}")
        self.refresh()


def parse_text_options(text_option: str) -> dict:
    """
    Parse a comma-separated list of key=value pairs into a dictionary.
    Expected keys are of the form "val#" where # is the zero-based field index.
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
    # Process command-line arguments.
    parser = argparse.ArgumentParser(
        description="TUI application that reads 12 integer values via serial and displays them."
    )
    parser.add_argument("port", help="Path to the serial port (e.g. /dev/ttyUSB0 or COM3)")
    parser.add_argument(
        "--text",
        help="Comma-separated key=value pairs to override label texts. "
             "Expected key format is 'val#' (zero-based), e.g., --text val0=NewText1,val3=NewText4",
        default="",
    )
    args = parser.parse_args()

    # Create default static texts for 12 fields: "Value1", "Value2", ..., "Value12"
    default_texts = [f"Value{i+1}" for i in range(12)]
    # Parse --text option
    text_overrides = parse_text_options(args.text)
    for key, new_text in text_overrides.items():
        if key.startswith("val"):
            try:
                idx = int(key[3:])
                if 0 <= idx < 12:
                    default_texts[idx] = new_text
            except ValueError:
                # Skip invalid keys
                pass

    # Enable logging (Textual will output detailed logs in development mode).
    logging.basicConfig(level=logging.DEBUG)

    # Create and run the Textual app.
    app = SerialTUI(serial_port=args.port, static_texts=default_texts)
    app.title = "Serial Port TUI"
    app.run()


if __name__ == "__main__":
    main()
