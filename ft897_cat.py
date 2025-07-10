"""CAT control module for Yaesu FT-897 using pyserial."""

import threading
from typing import Optional

import serial


class FT897CAT:
    """Provide minimal CAT commands for Yaesu FT-897."""

    def __init__(self) -> None:
        self.serial: Optional[serial.Serial] = None
        self.lock = threading.Lock()
        # Cache band table once
        self._bands = [
            (1.8e6, 2.0e6, "160m"),
            (3.5e6, 4.0e6, "80m"),
            (7.0e6, 7.3e6, "40m"),
            (14.0e6, 14.35e6, "20m"),
            (21.0e6, 21.45e6, "15m"),
            (28.0e6, 29.7e6, "10m"),
        ]

    def open(self, port: str, baudrate: int = 9600) -> None:
        """Open the serial port."""
        if self.serial and self.serial.is_open:
            self.close()
        try:
            # PL2303 USB converters work with standard 8 data bits, no parity and
            # two stop bits as required by the FT‑897 CAT interface.
            self.serial = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_TWO,
                timeout=1,
                write_timeout=1,
                rtscts=False,
                dsrdtr=False,
            )
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
        except serial.SerialException as exc:
            raise IOError(f"Failed to open {port}: {exc}")

    def close(self) -> None:
        """Close serial port."""
        if self.serial and self.serial.is_open:
            try:
                self.serial.close()
            finally:
                self.serial = None

    def _write(self, data: bytes) -> None:
        if not self.serial or not self.serial.is_open:
            raise IOError("Serial port not open")
        with self.lock:
            self.serial.write(data)

    def _query(self, cmd: bytes, reply_bytes: int = 0) -> bytes:
        """Send command and optionally read reply."""
        if not self.serial or not self.serial.is_open:
            raise IOError("Serial port not open")
        with self.lock:
            self.serial.reset_input_buffer()
            self.serial.write(cmd)
            self.serial.flush()
            if reply_bytes:
                return self.serial.read(reply_bytes)
            # responses terminate with ';'
            return self.serial.read_until(b';')

    def get_frequency(self) -> Optional[float]:
        """Query current frequency in Hz."""
        try:
            data = self._query(b"FA;")  # typical Yaesu command
        except serial.SerialException:
            return None
        if not data:
            return None
        # Expect b'FA00014070000;'
        digits = bytes([b for b in data if 48 <= b <= 57])
        try:
            return float(int(digits)) / 1e6
        except (ValueError, TypeError):
            return None

    def get_smeter(self) -> Optional[int]:
        """Query S-meter level."""
        try:
            data = self._query(b"SM;")
        except serial.SerialException:
            return None
        digits = bytes([b for b in data if 48 <= b <= 57])
        try:
            return int(digits)
        except (ValueError, TypeError):
            return None

    def get_swr(self) -> Optional[float]:
        """Query SWR level."""
        try:
            data = self._query(b"SW;")
        except serial.SerialException:
            return None
        digits = bytes([b for b in data if 48 <= b <= 57])
        try:
            return float(digits) / 10.0
        except (ValueError, TypeError):
            return None

    def ptt_on(self) -> None:
        """Send PTT ON command."""
        try:
            self._write(b"TX1;")
        except serial.SerialException:
            pass

    def ptt_off(self) -> None:
        """Send PTT OFF command."""
        try:
            self._write(b"TX0;")
        except serial.SerialException:
            pass

    def band_from_frequency(self, freq_mhz: float) -> str:
        """Return band label for frequency in MHz."""
        for low, high, name in self._bands:
            if low / 1e6 <= freq_mhz <= high / 1e6:
                return name
        return ""
