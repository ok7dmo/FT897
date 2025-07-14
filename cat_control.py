"""Serial CAT control for the Yaesu FT-897."""

import threading
import time
from typing import Optional, Tuple

import serial


class FT897CAT:
    """Minimal CAT control helper."""

    def __init__(self):
        self.serial_port: Optional[serial.Serial] = None
        self.is_connected = False
        self._lock = threading.Lock()
        self.ptt_active = False

    def connect(self, port: str, baudrate: int = 9600) -> bool:
        try:
            self.serial_port = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1,
            )
            self.is_connected = True
            return True
        except Exception as exc:
            print(f"Connect error: {exc}")
            return False

    def disconnect(self) -> None:
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        self.is_connected = False

    def _send(self, data: bytes) -> bool:
        """Write raw bytes to the serial port in a thread-safe way."""
        try:
            with self._lock:
                self.serial_port.write(data)
            # flush outside the lock to shorten critical section
            self.serial_port.flush()
        except Exception as exc:
            print(f"Write error: {exc}")
            return False
        # short delay for radio command processing
        time.sleep(0.01)
        return True

    def _read(self, length: int = 5) -> Optional[bytes]:
        with self._lock:
            try:
                return self.serial_port.read(length)
            except Exception as exc:
                print(f"Read error: {exc}")
                return None

    def get_frequency_and_mode(self) -> Tuple[Optional[int], Optional[int]]:
        if not self._send(b"\x00\x00\x00\x00\x03"):
            return None, None
        resp = self._read(5)
        if not resp or len(resp) != 5:
            return None, None
        units_10hz = 0
        for b in resp[:4]:
            units_10hz = units_10hz * 100 + ((b >> 4) & 0x0F) * 10 + (b & 0x0F)
        return units_10hz * 10, resp[4]

    def set_frequency(self, freq_hz: int) -> bool:
        units = freq_hz // 10
        digits = []
        for _ in range(8):
            digits.insert(0, units % 10)
            units //= 10
        bcd = bytes(((digits[i] << 4) | digits[i + 1]) for i in range(0, 8, 2))
        return self._send(bcd + b"\x01")

    def set_mode(self, mode_code: int) -> bool:
        cmd = bytes([mode_code, 0x00, 0x00, 0x00, 0x07])
        return self._send(cmd)

    def toggle_vfo(self) -> bool:
        return self._send(b"\x00\x00\x00\x00\x81")

    def split_on(self) -> bool:
        return self._send(b"\x00\x00\x00\x00\x02")

    def split_off(self) -> bool:
        return self._send(b"\x00\x00\x00\x00\x82")

    def clarifier_on(self) -> bool:
        return self._send(b"\x00\x00\x00\x00\x05")

    def clarifier_off(self) -> bool:
        return self._send(b"\x00\x00\x00\x00\x85")

    def repeater_plus(self) -> bool:
        return self._send(b"\x49\x09")

    def repeater_minus(self) -> bool:
        return self._send(b"\x89\x09")

    def get_meters(self) -> Tuple[Optional[int], Optional[int]]:
        cmds = b"\x00\x00\x00\x00\xe7" + b"\x00\x00\x00\x00\xf7"
        if not self._send(cmds):
            return None, None
        resp = self._read(4)
        if not resp or len(resp) < 4:
            return None, None
        return resp[1], resp[3]

    def set_power(self, watts: int, band_label: str) -> bool:
        if band_label in {
            "160 m",
            "80 m",
            "60 m",
            "40 m",
            "30 m",
            "20 m",
            "17 m",
            "15 m",
            "12 m",
            "10 m",
        }:
            addr, min_raw, max_raw = 0x9B, 0x05, 0x64
        elif band_label == "6 m":
            addr, min_raw, max_raw = 0xAA, 0x05, 0x64
        elif band_label == "2 m":
            addr, min_raw, max_raw = 0xAB, 0x05, 0x32
        elif band_label == "70 cm":
            addr, min_raw, max_raw = 0xAC, 0x02, 0x14
        else:
            return False
        raw = max(min_raw, min(max_raw, watts))
        cmd = bytes([0x00, addr, raw, 0x00, 0x01])
        return self._send(cmd)

    def ptt_on(self) -> bool:
        success = self._send(b"\x00\x00\x00\x00\x08")
        if success:
            self.ptt_active = True
        return success

    def ptt_off(self) -> bool:
        success = self._send(b"\x00\x00\x00\x00\x88")
        if success:
            self.ptt_active = False
        return success

    # ---------------- Additional CAT commands from user list -----------------
    def get_smeter_alt(self) -> Optional[int]:
        """Alternative S-meter read using opcode 0x0F subcommand 0x02."""
        if not self._send(b"\x02\x00\x00\x00\x0F"):
            return None
        resp = self._read(2)
        if not resp or len(resp) < 2:
            return None
        return resp[1]

    def get_meter_block(self) -> Optional[bytes]:
        """Read full 5-byte meter block using opcode 0xE7."""
        if not self._send(b"\x00\x00\x00\x00\xE7"):
            return None
        resp = self._read(5)
        if not resp or len(resp) < 5:
            return None
        return resp

    def get_s_and_power(self) -> Tuple[Optional[int], Optional[int]]:
        """Return S-meter and power meter values."""
        block = self.get_meter_block()
        s_val = block[0] if block else None
        if not self._send(b"\x00\x00\x00\x00\xF7"):
            return s_val, None
        resp = self._read(2)
        p_val = resp[1] if resp and len(resp) >= 2 else None
        return s_val, p_val

    def get_voltage(self) -> Optional[int]:
        """Read supply voltage (opcode 0x1C)."""
        if not self._send(b"\x00\x00\x00\x00\x1C"):
            return None
        resp = self._read(2)
        if not resp or len(resp) < 2:
            return None
        return resp[1]

    def power_off(self) -> bool:
        """Turn the transceiver off using opcode 0x1F."""
        return self._send(b"\x00\x00\x00\x00\x1F")

    def sql_on(self) -> bool:
        return self._send(b"\x00\x00\x00\x00\x10")

    def sql_off(self) -> bool:
        return self._send(b"\x00\x00\x00\x00\x90")

    def lock_on(self) -> bool:
        return self._send(b"\x00\x00\x00\x00\x11")

    def lock_off(self) -> bool:
        return self._send(b"\x00\x00\x00\x00\x91")

    def vox_on(self) -> bool:
        return self._send(b"\x00\x00\x00\x00\x12")

    def vox_off(self) -> bool:
        return self._send(b"\x00\x00\x00\x00\x92")

    def tuner_toggle(self) -> bool:
        return self._send(b"\x00\x00\x00\x00\x14")
