from __future__ import annotations

from typing import List, Tuple

from .cat_controller import FT897CAT
from .memory_controller import MemoryController

class MemoryManager:
    """Manage presets synchronized with the radio memories."""

    def __init__(self, cat: FT897CAT):
        self.cat = cat
        self.ctrl = MemoryController(cat)
        self.entries: List[Tuple[str, int, str]] = []

    def load_from_radio(self) -> None:
        self.entries.clear()
        for idx, freq, mode in self.ctrl.get_memory_channels():
            name = f"MEM {idx}"
            self.entries.append((name, freq, mode))

    def add_entry(self, name: str, freq_hz: int, mode: str) -> None:
        index = len(self.entries) + 1
        if self.ctrl.set_memory_channel(index, freq_hz, mode):
            self.entries.append((name, freq_hz, mode))

    def delete_entry(self, index: int) -> None:
        if 0 <= index < len(self.entries):
            if self.ctrl.delete_memory_channel(index + 1):
                self.entries.pop(index)
