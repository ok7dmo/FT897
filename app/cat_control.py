"""CAT control utilities for Yaesu FT-897."""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Optional

try:
    import serial  # type: ignore
except Exception:  # pragma: no cover - optional dependency during development
    serial = None  # type: ignore

LOGGER = logging.getLogger(__name__)


@dataclass
class CATConfig:
    """Configuration parameters for the CAT interface."""

    port: str = "/dev/ttyUSB0"
    baudrate: int = 9600
    timeout: float = 1.0
    simulate: bool = False


class FT897Controller:
    """Simple CAT controller for the Yaesu FT-897 transceiver.

    The implementation focuses on a subset of useful commands to keep the
    interface approachable while still allowing the user to send raw CAT
    commands for advanced operations.
    """

    def __init__(self, config: CATConfig):
        self._config = config
        self._serial: Optional["serial.Serial"] = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------
    def connect(self) -> None:
        """Establish a serial connection if it is not already open."""

        if self._config.simulate:
            LOGGER.debug("Simulation mode active; not opening serial port.")
            return

        if serial is None:
            raise RuntimeError(
                "pyserial is not available. Install it with 'pip install pyserial'."
            )

        if self._serial and self._serial.is_open:
            return

        LOGGER.info(
            "Opening CAT serial connection on %s at %d baud",
            self._config.port,
            self._config.baudrate,
        )
        self._serial = serial.Serial(  # type: ignore[call-arg]
            port=self._config.port,
            baudrate=self._config.baudrate,
            timeout=self._config.timeout,
        )

    def disconnect(self) -> None:
        """Close the serial connection."""

        if self._serial and self._serial.is_open:
            LOGGER.info("Closing CAT serial connection")
            self._serial.close()
            self._serial = None

    # ------------------------------------------------------------------
    # Command helpers
    # ------------------------------------------------------------------
    def send_raw_command(self, command: str) -> str:
        """Send a raw CAT command.

        The command string is automatically terminated with ``;`` if the caller
        does not add it manually. The response from the transceiver (if any) is
        returned as a plain string without the trailing delimiter.
        """

        command = command.strip().upper()
        if not command:
            raise ValueError("Command must not be empty")

        if not command.endswith(";"):
            command += ";"

        LOGGER.debug("Sending CAT command: %s", command)

        if self._config.simulate:
            return self._simulate_command(command)

        if serial is None:
            raise RuntimeError("pyserial is required for CAT communication")

        self.connect()
        assert self._serial is not None  # for type checkers

        with self._lock:
            self._serial.reset_input_buffer()
            self._serial.write(command.encode("ascii"))
            self._serial.flush()
            response = self._serial.read_until(b";")

        response_text = response.decode("ascii", errors="ignore").strip()
        LOGGER.debug("CAT response: %s", response_text)
        return response_text

    # ------------------------------------------------------------------
    # Convenience methods for common operations
    # ------------------------------------------------------------------
    def get_vfo_a_frequency(self) -> Optional[int]:
        """Return the current VFO-A frequency in Hertz."""

        response = self.send_raw_command("FA;")
        if not response.startswith("FA"):
            return None
        digits = response[2:].strip(";")
        try:
            return int(digits)
        except ValueError:
            LOGGER.warning("Unable to parse FA response: %s", response)
            return None

    def set_vfo_a_frequency(self, frequency_hz: int) -> None:
        """Set the VFO-A frequency (in Hertz)."""

        if not 100000 <= frequency_hz <= 500000000:
            raise ValueError("Frequency must be between 100 kHz and 500 MHz")
        command = f"FA{frequency_hz:011d}"
        self.send_raw_command(command)

    def get_ptt_status(self) -> Optional[bool]:
        """Return the Push-To-Talk status if available."""

        response = self.send_raw_command("TX;")
        if response in {"TX0", "TX0;"}:
            return False
        if response in {"TX1", "TX1;"}:
            return True
        return None

    def set_ptt(self, active: bool) -> None:
        """Toggle transmission."""

        command = "TX1" if active else "TX0"
        self.send_raw_command(command)

    # ------------------------------------------------------------------
    # Simulation helpers
    # ------------------------------------------------------------------
    def _simulate_command(self, command: str) -> str:
        """Return a fake response when running without a radio attached."""

        LOGGER.debug("Simulated CAT command: %s", command)
        command = command.strip(";")
        if command == "FA":
            return "FA0140740000;"  # Example frequency
        if command.startswith("FA"):
            return "OK;"
        if command == "TX":
            return "TX0;"
        if command in {"TX0", "TX1"}:
            return "OK;"
        return ";"


__all__ = ["CATConfig", "FT897Controller"]
