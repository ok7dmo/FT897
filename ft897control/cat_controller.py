import serial
import threading
import time
from typing import Optional

class FT897CAT:
    """Low-level CAT controller for the Yaesu FT-897."""

    MODE_MAP = {
        "LSB": 0x00,
        "USB": 0x01,
        "CW": 0x02,
        "CWR": 0x03,
        "AM": 0x04,
        "FM": 0x08,
        "DIG": 0x06,
    }

    def __init__(self) -> None:
        self.port: Optional[str] = None
        self.baudrate: int = 9600
        self.serial_port: Optional[serial.Serial] = None
        self.is_connected: bool = False
        self.ptt_active: bool = False
        self._lock = threading.Lock()

    def _send(self, data: bytes) -> bool:
        """Send raw bytes to the radio."""
        with self._lock:
            try:
                assert self.serial_port
                self.serial_port.reset_input_buffer()
                self.serial_port.reset_output_buffer()
                self.serial_port.write(data)
                self.serial_port.flush()
                time.sleep(0.05)
                return True
            except Exception:
                return False

    def _read(self, length: int = 5) -> Optional[bytes]:
        """Read raw bytes from the radio."""
        with self._lock:
            try:
                assert self.serial_port
                return self.serial_port.read(length)
            except Exception:
                return None

    # connection ---------------------------------------------------------
    def connect(self, port: str, baudrate: int = 9600) -> bool:
        """Open the serial port."""
        self.port = port
        self.baudrate = baudrate
        try:
            self.serial_port = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.2,
                write_timeout=0.2,
            )
            self.is_connected = True
            return True
        except Exception:
            self.serial_port = None
            self.is_connected = False
            return False

    def disconnect(self) -> None:
        """Close the serial port."""
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.close()
            except Exception:
                pass
        self.serial_port = None
        self.is_connected = False

    # radio queries ------------------------------------------------------
    def get_frequency(self) -> Optional[int]:
        """Return current VFO frequency in Hz."""
        if not self.is_connected:
            return None
        if not self._send(b"\x00\x00\x00\x00\x03"):
            return None
        resp = self._read(5)
        if not resp or len(resp) != 5:
            return None
        units_10hz = 0
        for b in resp[:4]:
            units_10hz = units_10hz * 100 + ((b >> 4) & 0x0F) * 10 + (b & 0x0F)
        return units_10hz * 10

    def set_frequency(self, freq_hz: int) -> bool:
        """Tune the radio to ``freq_hz``."""
        if not self.is_connected:
            return False
        units_10hz = int(freq_hz // 10)
        digits = f"{units_10hz:08d}"
        bcd = bytearray()
        for i in range(0, 8, 2):
            bcd.append((int(digits[i]) << 4) | int(digits[i + 1]))
        return self._send(bytes(bcd) + b"\x01")

    def read_rx_status(self) -> Optional[int]:
        """Return RX status byte (opcode ``0xE7``)."""
        if not self.is_connected:
            return None
        if not self._send(b"\x00\x00\x00\x00\xe7"):
            return None
        resp = self._read(1)
        return resp[0] if resp else None

    def read_tx_status(self) -> Optional[int]:
        """Return TX status byte (opcode ``0xF7``)."""
        if not self.is_connected:
            return None
        if not self._send(b"\x00\x00\x00\x00\xf7"):
            return None
        resp = self._read(1)
        return resp[0] if resp else None

    def get_mode(self) -> Optional[str]:
        """Return mode name decoded from RX status."""
        status = self.read_rx_status()
        if status is None:
            return None
        code = status & 0x0F
        for name, val in self.MODE_MAP.items():
            if val == code:
                return name
        return None

    def set_mode(self, mode: str) -> bool:
        """Switch the radio to the specified mode name."""
        if not self.is_connected:
            return False
        code = self.MODE_MAP.get(mode)
        if code is None:
            return False
        cmd = bytes([code, 0x00, 0x00, 0x00, 0x07])
        return self._send(cmd)

    # ptt ---------------------------------------------------------------
    def ptt_on(self) -> bool:
        if not self.is_connected:
            return False
        self.ptt_active = True
        return self._send(b"\x00\x00\x00\x00\x08")

    def ptt_off(self) -> bool:
        if not self.is_connected:
            return False
        self.ptt_active = False
        return self._send(b"\x00\x00\x00\x00\x88")
