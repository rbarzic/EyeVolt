#!/usr/bin/env python3
import argparse
import asyncio
import json
import logging
import queue
import threading
from statistics import mean

import serial_asyncio
import uvicorn
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from rich.logging import RichHandler
from starlette.applications import Starlette
from starlette.routing import Route
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Label, ProgressBar, Sparkline


def get_color(value: float) -> str:
    if value < 0.5:
        return "white"
    elif value < 0.8:
        return "yellow"
    elif value < 1.2:
        return "#66FF66"
    else:
        return "#FF6666"


class VoltageDisplay(Widget):
    def __init__(self, static_text: str, index: int, enabled: bool = True, history_limit: int = 128, **kwargs) -> None:
        super().__init__(**kwargs)
        self.static_text = static_text
        self.index = index
        self.enabled = enabled
        self.history: list[int] = []
        self.history_limit = history_limit

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label(f"{self.static_text}: 0.00", id=f"label_{self.index}"),
            ProgressBar(total=100, id=f"progress_{self.index}"),
            Sparkline(data=self.history, summary_function=mean, id=f"spark_{self.index}")
        )

    def update_value(self, new_value: float):
        label = self.query_one(f"#label_{self.index}", Label)
        progress_bar = self.query_one(f"#progress_{self.index}", ProgressBar)
        sparkline = self.query_one(f"#spark_{self.index}", Sparkline)

        if not self.enabled:
            label.update(f"{self.static_text}: ----")
            progress_bar.progress = 0
            progress_bar.styles.bar_color = "grey"
            sparkline.data = []
            sparkline.refresh()
            return

        max_val = 3.3 if self.index < 8 else 6.6
        pct = int(new_value / max_val * 100)
        color = get_color(new_value)

        label.update(f"{self.static_text}: " + f"[bold][{color}]{new_value:.2f}[/{color}][/bold]")
        progress_bar.progress = pct
        progress_bar.styles.bar_color = color

        self.history.append(pct)
        if len(self.history) > self.history_limit:
            self.history.pop(0)
        sparkline.data = [0, 100] + self.history
        sparkline.refresh()


class DacDisplay(Widget):
    """Compact DAC readback: a single live label (no graph / progress bar)."""

    DEFAULT_CSS = """
    DacDisplay {
        height: 1;
        padding: 0 1;
        content-align: center middle;
    }
    """

    def __init__(self, label_text: str, index: int, **kwargs) -> None:
        super().__init__(**kwargs)
        self.label_text = label_text
        self.index = index

    def compose(self) -> ComposeResult:
        yield Label(f"{self.label_text}: 0.00", id=f"dac_label_{self.index}")

    def update_value(self, voltage: float) -> None:
        color = get_color(voltage)
        self.query_one(f"#dac_label_{self.index}", Label).update(
            f"{self.label_text}: [bold][{color}]{voltage:.2f}[/{color}][/bold]"
        )


class SerialProtocol(asyncio.Protocol):
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
        elif line.startswith("3::"):
            parts = line[3:].strip().split()
            if len(parts) != 8:
                self.app.log(f"Unexpected number of values in header 3: {parts}")
                return
            try:
                raw_values = [int(part) for part in parts]
            except ValueError:
                self.app.log("Header 3: one of the values is not an integer.")
                return
            conv_values = [raw / 65536.0 * 3.3 for raw in raw_values]
            self.app.update_dac(conv_values)
        else:
            self.app.log(f"Unrecognized data: {line}")


class EyeVoltMCPServer:
    def __init__(self, app: "SerialTUI"):
        self.app = app
        self.host = app.mcp_host
        self.port = app.mcp_port
        self.server = Server("eyevolt")
        self._setup_handlers()

    def log(self, msg: str):
        self.app.mcp_log_queue.put(f"[MCP] {msg}")

    def _setup_handlers(self):
        @self.server.list_tools()
        async def list_tools():
            return [
                Tool(
                    name="get_voltages",
                    description="Get all enabled voltages with their names",
                    inputSchema={"type": "object", "properties": {}}
                ),
                Tool(
                    name="get_voltage",
                    description="Get voltage reading for a channel by its name",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Channel name"
                            }
                        },
                        "required": ["name"]
                    }
                ),
                Tool(
                    name="get_voltage_idx",
                    description="Get voltage reading for a channel by its index (0-11)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "channel": {
                                "type": "integer",
                                "description": "Channel index (0-11)"
                            }
                        },
                        "required": ["channel"]
                    }
                ),
                Tool(
                    name="get_channel_info",
                    description="Get information about all channels (name, enabled status, current value)",
                    inputSchema={"type": "object", "properties": {}}
                ),
                Tool(
                    name="get_channel_history",
                    description="Get history data for a channel by its name as percentages (0-100)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Channel name"
                            }
                        },
                        "required": ["name"]
                    }
                ),
                Tool(
                    name="set_voltage",
                    description="Set the output voltage of a DAC generation channel (0-7). "
                                "Voltage is in volts over the 0-3.3 V range.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "channel": {
                                "type": "integer",
                                "description": "DAC channel index (0-7)"
                            },
                            "voltage": {
                                "type": "number",
                                "description": "Target voltage in volts (0-3.3)"
                            }
                        },
                        "required": ["channel", "voltage"]
                    }
                )
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict):
            self.log(f"Tool called: {name}({arguments})")
            
            if name == "get_voltages":
                result = {}
                for i in range(12):
                    if self.app.channel_config[i]:
                        result[self.app.static_texts[i]] = self.app.current_values[i]
                return [TextContent(type="text", text=json.dumps(result, indent=2))]
            
            elif name == "get_voltage":
                channel_name = arguments.get("name", "")
                for i in range(12):
                    if self.app.static_texts[i] == channel_name:
                        return [TextContent(type="text", text=str(self.app.current_values[i]))]
                self.log(f"Error: Channel '{channel_name}' not found")
                return [TextContent(type="text", text=f"Error: Channel '{channel_name}' not found")]
            
            elif name == "get_voltage_idx":
                channel = arguments.get("channel", 0)
                if channel < 0 or channel >= 12:
                    self.log(f"Error: Invalid channel {channel}")
                    return [TextContent(type="text", text=f"Error: Channel must be 0-11")]
                return [TextContent(type="text", text=str(self.app.current_values[channel]))]
            
            elif name == "get_channel_info":
                info = []
                for i in range(12):
                    max_val = 3.3 if i < 8 else 6.6
                    info.append({
                        "channel": i,
                        "name": self.app.static_texts[i],
                        "enabled": self.app.channel_config[i],
                        "voltage": self.app.current_values[i],
                        "max_voltage": max_val
                    })
                return [TextContent(type="text", text=json.dumps(info, indent=2))]
            
            elif name == "get_channel_history":
                channel_name = arguments.get("name", "")
                for i in range(12):
                    if self.app.static_texts[i] == channel_name:
                        display = self.app.displays[i] if self.app.displays else None
                        history = display.history if display else []
                        return [TextContent(type="text", text=json.dumps(history))]
                self.log(f"Error: Channel '{channel_name}' not found")
                return [TextContent(type="text", text=f"Error: Channel '{channel_name}' not found")]

            elif name == "set_voltage":
                channel = arguments.get("channel", -1)
                voltage = arguments.get("voltage", 0.0)
                if not isinstance(channel, int) or channel < 0 or channel >= 8:
                    self.log(f"Error: Invalid DAC channel {channel}")
                    return [TextContent(type="text", text=f"Error: DAC channel must be 0-7")]
                try:
                    voltage = float(voltage)
                except (TypeError, ValueError):
                    return [TextContent(type="text", text="Error: voltage must be a number")]
                if voltage < 0 or voltage > 3.3:
                    return [TextContent(type="text", text="Error: voltage must be 0-3.3 V")]
                millivolts = round(voltage * 1000)
                sent = self.app.send_command(f"SETMV {channel} {millivolts}")
                if not sent:
                    return [TextContent(type="text", text="Error: serial connection not available")]
                self.log(f"Set DAC{channel} to {voltage:.3f} V ({millivolts} mV)")
                return [TextContent(type="text",
                                    text=f"Set DAC{channel} to {voltage:.3f} V ({millivolts} mV)")]

            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    def create_app(self):
        sse = SseServerTransport("/messages")

        async def handle_sse(request):
            self.log(f"SSE connection from {request.client.host if request.client else 'unknown'}")
            async with sse.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                await self.server.run(
                    streams[0], streams[1], self.server.create_initialization_options()
                )

        async def handle_messages(request):
            await sse.handle_post_message(request.scope, request.receive, request._send)

        return Starlette(
            routes=[
                Route("/sse", endpoint=handle_sse),
                Route("/messages", endpoint=handle_messages, methods=["POST"])
            ]
        )

    def serve(self):
        self.log(f"Server listening on {self.host}:{self.port}")
        starlette_app = self.create_app()
        uvicorn.run(starlette_app, host=self.host, port=self.port, log_level="warning")


class SerialTUI(App):
    CSS = """
    Screen {
        layout: grid;
        grid-size: 3 4;
        align: center middle;
    }
    #dac_section {
        dock: bottom;
        height: 4;
        border-top: solid $primary;
        padding: 0 1;
    }
    #dac_title {
        height: 1;
        text-style: bold;
    }
    #dac_grid {
        layout: grid;
        grid-size: 4 2;
        height: 2;
        align: center middle;
    }
    Sparkline {
        min-height: 4;
    }
    """

    def __init__(self, serial_port: str, static_texts: list[str], channel_config: list[bool], 
                 history_limit: int, mcp_enabled: bool = False, mcp_host: str = "127.0.0.1", 
                 mcp_port: int = 8088, **kwargs):
        super().__init__(**kwargs)
        self.serial_port = serial_port
        self.static_texts = static_texts
        self.channel_config = channel_config
        self.history_limit = history_limit
        self.current_values = [0.0] * 12
        self.displays = []
        self.dac_values = [0.0] * 8
        self.dac_displays = []
        self.serial_protocol: SerialProtocol | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self.mcp_enabled = mcp_enabled
        self.mcp_host = mcp_host
        self.mcp_port = mcp_port
        self.mcp_server: EyeVoltMCPServer | None = None
        self.mcp_log_queue: queue.Queue = queue.Queue()
        self.logger = logging.getLogger("eyevolt")

    def compose(self) -> ComposeResult:
        for i in range(12):
            yield VoltageDisplay(
                self.static_texts[i],
                i,
                enabled=self.channel_config[i],
                history_limit=self.history_limit,
                id=f"voltage_{i}"
            )
        with Vertical(id="dac_section"):
            yield Label("DAC readback", id="dac_title")
            with Vertical(id="dac_grid"):
                for i in range(8):
                    yield DacDisplay(f"DAC{i}", i, id=f"dac_{i}")

    async def on_mount(self) -> None:
        self.log(f"Mounting TUI with serial port: {self.serial_port}")
        self.displays = [self.query_one(f"#voltage_{i}", VoltageDisplay) for i in range(12)]
        self.dac_displays = [self.query_one(f"#dac_{i}", DacDisplay) for i in range(8)]
        asyncio.create_task(self.read_serial())
        
        if self.mcp_enabled:
            self.set_interval(0.2, self.poll_mcp_logs)
            self.log(f"Starting MCP server on {self.mcp_host}:{self.mcp_port}")
            self.mcp_server = EyeVoltMCPServer(self)
            thread = threading.Thread(target=self.mcp_server.serve, daemon=True)
            thread.start()

    def poll_mcp_logs(self):
        try:
            while True:
                msg = self.mcp_log_queue.get_nowait()
                self.log(msg)
        except queue.Empty:
            pass

    async def read_serial(self):
        loop = asyncio.get_running_loop()
        self._loop = loop
        self.log("Opening serial connection...")
        try:
            transport, protocol = await serial_asyncio.create_serial_connection(
                loop,
                lambda: SerialProtocol(self),
                self.serial_port,
                baudrate=9600,
            )
            self.serial_protocol = protocol
            self.log("Serial connection running.")
        except Exception as e:
            self.log(f"Failed to open serial port: {e}")

    def send_command(self, command: str) -> bool:
        """Thread-safe send of an ASCII command to the Pico over serial.

        Returns True if the command was scheduled, False if no serial
        connection is available.
        """
        if (self._loop is None or self.serial_protocol is None
                or self.serial_protocol.transport is None):
            return False
        data = (command + "\n").encode("ascii")
        self._loop.call_soon_threadsafe(self.serial_protocol.transport.write, data)
        return True

    def update_values(self, indices, new_values):
        for idx, val in zip(indices, new_values):
            self.current_values[idx] = val
            self.displays[idx].update_value(val)
        self.refresh()

    def update_dac(self, new_values):
        for i, val in enumerate(new_values):
            self.dac_values[i] = val
            self.dac_displays[i].update_value(val)
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
        description="TUI application that reads 12 voltage values via serial with optional MCP server support."
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
             "Channels not listed default to 'on'.",
        default="",
    )
    parser.add_argument(
        "--history",
        type=int,
        help="Maximum history length for the sparkline (default: 128)",
        default=128,
    )
    parser.add_argument(
        "--mcp",
        action="store_true",
        help="Start MCP server alongside TUI",
    )
    parser.add_argument(
        "--mcp-port",
        type=int,
        default=8088,
        help="MCP server port (default: 8088)",
    )
    parser.add_argument(
        "--mcp-host",
        default="127.0.0.1",
        help="MCP server host (default: 127.0.0.1)",
    )
    parser.add_argument("-v", "--verbose", action="count", default=0)
    args = parser.parse_args()

    logging_level = logging.WARNING
    if args.verbose == 1:
        logging_level = logging.INFO
    if args.verbose >= 2:
        logging_level = logging.DEBUG
    logging.basicConfig(
        level=logging_level,
        format="[%(funcName)20s() ] %(levelname)s %(message)s",
        handlers=[RichHandler()],
    )

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

    app = SerialTUI(
        serial_port=args.port,
        static_texts=default_texts,
        channel_config=channel_flags,
        history_limit=args.history,
        mcp_enabled=args.mcp,
        mcp_host=args.mcp_host,
        mcp_port=args.mcp_port,
    )
    app.title = "EyeVolt Serial Port TUI"
    app.run()


if __name__ == "__main__":
    main()
