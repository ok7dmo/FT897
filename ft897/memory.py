"""Memory channel data structures and serialization."""

from __future__ import annotations

from dataclasses import dataclass
import json
import csv
from typing import List, Iterable


@dataclass
class MemoryChannel:
    index: int
    rx_freq_hz: int
    tx_freq_hz: int
    mode: str
    ctcss: float | None = None
    dcs: int | None = None
    offset_dir: str = ""
    offset_hz: int = 0
    step_hz: int = 0
    name: str = ""
    bank_id: int = 0
    skip: bool = False


CHANNEL_SIZE = 32  # placeholder for real layout
TOTAL_CHANNELS = 200
IMAGE_SIZE = CHANNEL_SIZE * TOTAL_CHANNELS


def parse_image(image: bytes) -> List[MemoryChannel]:
    """Parse binary image into memory channels."""
    channels: List[MemoryChannel] = []
    for idx in range(TOTAL_CHANNELS):
        start = idx * CHANNEL_SIZE
        chunk = image[start:start + CHANNEL_SIZE]
        if len(chunk) < CHANNEL_SIZE:
            break
        rx = int.from_bytes(chunk[0:4], "little")
        tx = int.from_bytes(chunk[4:8], "little")
        mode_code = chunk[8]
        mode = {0: "LSB", 1: "USB", 2: "CW", 3: "CWR", 4: "AM", 8: "FM", 6: "DIG"}.get(mode_code, "FM")
        name = chunk[9:17].decode("ascii", "ignore").strip("\x00")
        channels.append(MemoryChannel(index=idx, rx_freq_hz=rx, tx_freq_hz=tx, mode=mode, name=name))
    return channels


def build_image(channels: Iterable[MemoryChannel]) -> bytes:
    buf = bytearray(IMAGE_SIZE)
    for ch in channels:
        if ch.index >= TOTAL_CHANNELS:
            continue
        start = ch.index * CHANNEL_SIZE
        buf[start:start + 4] = int(ch.rx_freq_hz).to_bytes(4, "little")
        buf[start + 4:start + 8] = int(ch.tx_freq_hz).to_bytes(4, "little")
        mode_code = {"LSB": 0, "USB": 1, "CW": 2, "CWR": 3, "AM": 4, "FM": 8, "DIG": 6}.get(ch.mode, 8)
        buf[start + 8] = mode_code
        name = (ch.name or "")[:8].ljust(8, "\x00").encode("ascii")
        buf[start + 9:start + 17] = name
    return bytes(buf)


def export_json(channels: Iterable[MemoryChannel], fp) -> None:
    data = [ch.__dict__ for ch in channels]
    json.dump(data, fp, indent=2)


def import_json(fp) -> List[MemoryChannel]:
    data = json.load(fp)
    channels = [MemoryChannel(**item) for item in data]
    return channels


def export_csv(channels: Iterable[MemoryChannel], fp) -> None:
    writer = csv.writer(fp, delimiter=";")
    writer.writerow(
        [
            "index",
            "rx_freq_hz",
            "tx_freq_hz",
            "mode",
            "name",
        ]
    )
    for ch in channels:
        writer.writerow([ch.index, ch.rx_freq_hz, ch.tx_freq_hz, ch.mode, ch.name])


def import_csv(fp) -> List[MemoryChannel]:
    reader = csv.DictReader(fp, delimiter=";")
    channels = []
    for row in reader:
        channels.append(
            MemoryChannel(
                index=int(row["index"]),
                rx_freq_hz=int(row["rx_freq_hz"]),
                tx_freq_hz=int(row["tx_freq_hz"]),
                mode=row["mode"],
                name=row.get("name", ""),
            )
        )
    return channels

