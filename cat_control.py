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
                timeout=0.1,
                write_timeout=0.1,
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
        if not self.serial_port:
            return False
        try:
            # hold the lock only for the actual write to minimise blocking
            with self._lock:
                self.serial_port.write(data)
                self.serial_port.flush()
        except Exception as exc:
            print(f"Write error: {exc}")
            return False
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
        # opcode 0x79 writes menu parameters without altering frequency
        cmd = bytes([0x00, addr, raw, 0x00, 0x79])
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
        """Read full 5-byte meter block using the long 0xE7 command."""
        # Use the explicit command sequence as documented: FE FE 44 00 E7 FD
        if not self._send(b"\xFE\xFE\x44\x00\xE7\xFD"):
            return None
        resp = self._read(7)
        if not resp or len(resp) < 7:
            return None
        # Return only the five data bytes from the response
        return resp[2:7]

    def get_s_and_power(self) -> Tuple[Optional[int], Optional[int]]:
        """Return S-meter and power meter values using short CAT commands."""
        if not self._send(b"\x00\x00\x00\x00\xE7"):
            return None, None
        resp = self._read(5)
        s_val = resp[0] if resp and len(resp) >= 1 else None

        if not self._send(b"\x00\x00\x00\x00\xF7"):
            return s_val, None
        resp2 = self._read(5)
        p_val = resp2[0] if resp2 and len(resp2) >= 1 else None
        return s_val, p_val

    def get_full_status(self) -> Tuple[Optional[int], Optional[int], Optional[int], Optional[int]]:
        """Return frequency, mode, S-meter and power in one round trip."""
        cmds = (
            b"\x00\x00\x00\x00\x03"  # read frequency/mode
            b"\x00\x00\x00\x00\xE7"  # read S-meter
            b"\x00\x00\x00\x00\xF7"  # read power meter
        )
        if not self._send(cmds):
            return None, None, None, None
        resp = self._read(15)
        if not resp or len(resp) < 15:
            return None, None, None, None

        freq_bytes = resp[0:5]
        units_10hz = 0
        for b in freq_bytes[:4]:
            units_10hz = units_10hz * 100 + ((b >> 4) & 0x0F) * 10 + (b & 0x0F)
        freq_hz = units_10hz * 10
        mode = freq_bytes[4]

        s_val = resp[5]  # first byte after opcode echo
        p_val = resp[10]
        return freq_hz, mode, s_val, p_val

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
