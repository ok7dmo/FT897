from __future__ import annotations

from typing import List, Tuple, Optional

from .cat_controller import FT897CAT

class MemoryController:
    """Access FT-897 memory channels over CAT."""

    def __init__(self, cat: FT897CAT) -> None:
        self.cat = cat

    def _send(self, data: bytes) -> bool:
        return self.cat._send(data)

    def _read(self, length: int = 5) -> Optional[bytes]:
        return self.cat._read(length)

    def get_memory_channels(self) -> List[Tuple[int, int, str]]:
        """Return list of (index, freq_hz, mode)."""
        channels: List[Tuple[int, int, str]] = []
        if not self.cat.is_connected:
            return channels
        for idx in range(1, 101):
            cmd = bytes([0x00, idx & 0xFF, 0x00, 0x00, 0xB0])
            if not self._send(cmd):
                break
            resp = self._read(5)
            if not resp or len(resp) != 5:
                continue
            freq = 0
            for b in resp[:4]:
                freq = freq * 100 + ((b >> 4) & 0x0F) * 10 + (b & 0x0F)
            freq *= 10
            mode_code = resp[4] & 0x0F
            mode = next((n for n, v in FT897CAT.MODE_MAP.items() if v == mode_code), "FM")
            channels.append((idx, freq, mode))
        return channels

    def set_memory_channel(self, index: int, freq_hz: int, mode: str) -> bool:
        """Store a memory entry at ``index``."""
        if not self.cat.is_connected:
            return False
        units_10hz = int(freq_hz // 10)
        digits = f"{units_10hz:08d}"
        bcd = bytearray()
        for i in range(0, 8, 2):
            bcd.append((int(digits[i]) << 4) | int(digits[i+1]))
        mode_code = FT897CAT.MODE_MAP.get(mode, 0x08)
        cmd = bytes([0x00, index & 0xFF]) + bytes(bcd) + bytes([mode_code])
        cmd = cmd[:4] + b"\xB1"
        return self._send(cmd)

    def delete_memory_channel(self, index: int) -> bool:
        if not self.cat.is_connected:
            return False
        cmd = bytes([0x00, index & 0xFF, 0x00, 0x00, 0xB2])
        return self._send(cmd)
