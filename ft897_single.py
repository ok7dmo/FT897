#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import subprocess
import time
import threading
import json
import csv
from pathlib import Path
from dataclasses import dataclass
from typing import Callable, Iterable, List


def int_to_bcd(value: int, digits: int) -> bytes:
    """Convert integer to big-endian BCD."""
    s = f"{value:0{digits}d}"
    out = bytearray()
    for i in range(0, digits, 2):
        out.append((int(s[i]) << 4) | int(s[i + 1]))
    return bytes(out)


def bcd_to_int(data: bytes) -> int:
    """Decode big-endian BCD to integer."""
    val = 0
    for b in data:
        val = val * 100 + ((b >> 4) & 0x0F) * 10 + (b & 0x0F)
    return val

required = ["pyserial", "PyQt5"]
for module in required:
    try:
        if module == "pyserial":
            import serial
        elif module == "PyQt5":
            from PyQt5.QtWidgets import QApplication
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", module])

from serial.tools import list_ports

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton,
    QComboBox, QMessageBox, QAction, QSizePolicy, QFontDialog,
    QDialog, QRadioButton, QDialogButtonBox, QTabWidget, QFrame,
    QInputDialog, QFileDialog, QProgressDialog
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QObject
from PyQt5.QtGui import QFont, QFontMetrics


class FT897CAT:
    """Minimal CAT control for the Yaesu FT-897 using direct serial commands."""

    MODE_MAP = {
        "LSB": 0x00,
        "USB": 0x01,
        "CW": 0x02,
        "CWR": 0x03,
        "AM": 0x04,
        "FM": 0x08,
        "DIG": 0x06,
    }

    def __init__(self):
        self.port = None
        self.baudrate = 9600
        self.is_connected = False
        self.ptt_active = False
        self.serial_port = None
        self._lock = threading.Lock()

    def _send(self, data: bytes, flush: bool = True) -> bool:
        """Write raw CAT bytes to the radio."""
        with self._lock:
            try:
                if flush:
                    self.serial_port.reset_input_buffer()
                    self.serial_port.reset_output_buffer()
                self.serial_port.write(data)
                self.serial_port.flush()
                time.sleep(0.05)
                return True
            except Exception as e:
                print(f"Chyba serial write: {e}")
                return False

    def _read(self, length=5):
        with self._lock:
            try:
                return self.serial_port.read(length)
            except Exception as e:
                print(f"Chyba serial read: {e}")
                return None

    def connect(self, port, baudrate=9600):
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
        except Exception as e:
            print(f"Chyba připojení: {e}")
            return False

    def disconnect(self):
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.close()
            except Exception:
                pass
        self.is_connected = False

    def get_frequency(self):
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

    def get_smeter(self):
        """Return raw S-meter value (0-15) using RX status command."""
        if not self.is_connected:
            return None
        with self._lock:
            try:
                self.serial_port.reset_input_buffer()
                self.serial_port.reset_output_buffer()
                self.serial_port.write(b'\x00\x00\x00\x00\xe7')
                time.sleep(0.1)
                resp = self.serial_port.read(1)
            except Exception as e:
                print(f"Chyba při čtení S-metu: {e}")
                return None

        if not resp:
            return None
        return resp[0] & 0x0F

    def get_swr(self, tx_status: int | None = None) -> int | None:
        """Return 1 if high VSWR, 0 if normal, None if not transmitting."""
        if not self.is_connected:
            return None
        if tx_status is None:
            tx_status = self.read_tx_status()
            if tx_status is None:
                return None
        if tx_status & 0x80:
            return None
        return 1 if (tx_status & 0x40) else 0

    def get_power_level(self):
        status = self.read_tx_status()
        if status is None:
            return None
        if status & 0x80:
            return None
        return status & 0x0F

    def ptt_on(self):
        if not self.is_connected:
            return False
        self.ptt_active = True
        return self._send(b"\x00\x00\x00\x00\x08")

    def ptt_off(self):
        if not self.is_connected:
            return False
        self.ptt_active = False
        return self._send(b"\x00\x00\x00\x00\x88")

    def set_frequency(self, freq_hz: int):
        if not self.is_connected:
            return False
        units_10hz = int(freq_hz // 10)
        digits = f"{units_10hz:08d}"
        bcd = bytearray()
        for i in range(0, 8, 2):
            bcd.append((int(digits[i]) << 4) | int(digits[i + 1]))
        return self._send(bytes(bcd) + b"\x01")

    def set_mode(self, mode: str):
        if not self.is_connected:
            return False
        code = self.MODE_MAP.get(mode)
        if code is None:
            return False
        cmd = bytes([code, 0x00, 0x00, 0x00, 0x07])
        return self._send(cmd)

    def toggle_vfo(self):
        if not self.is_connected:
            return False
        return self._send(b"\x00\x00\x00\x00\x81")

    def split_on(self):
        if not self.is_connected:
            return False
        return self._send(b"\x00\x00\x00\x00\x02")

    def split_off(self):
        if not self.is_connected:
            return False
        return self._send(b"\x00\x00\x00\x00\x82")

    def lock_on(self):
        if not self.is_connected:
            return False
        return self._send(b"\x00\x00\x00\x00\x00")

    def lock_off(self):
        if not self.is_connected:
            return False
        return self._send(b"\x00\x00\x00\x00\x80")

    def clar_on(self):
        if not self.is_connected:
            return False
        return self._send(b"\x00\x00\x00\x00\x05")

    def clar_off(self):
        if not self.is_connected:
            return False
        return self._send(b"\x00\x00\x00\x00\x85")

    def set_clar_frequency(self, offset_hz: int, sign: int = 1):
        if not self.is_connected:
            return False
        sign_byte = 0x00 if sign >= 0 else 0xFF
        units_10hz = int(abs(offset_hz) // 10)
        digits = f"{units_10hz:04d}"
        bcd = bytearray([sign_byte, 0x00])
        for i in range(0, 4, 2):
            bcd.append((int(digits[i]) << 4) | int(digits[i + 1]))
        bcd.append(0xF5)
        return self._send(bytes(bcd))

    def set_repeater_offset_mode(self, mode: str):
        if not self.is_connected:
            return False
        mapping = {
            "minus": 0x09,
            "plus": 0x49,
            "simplex": 0x89,
        }
        code = mapping.get(mode)
        if code is None:
            return False
        cmd = bytes([code, 0x00, 0x00, 0x00, 0x09])
        return self._send(cmd)

    def set_repeater_offset_frequency(self, freq_hz: int):
        if not self.is_connected:
            return False
        units_10hz = int(freq_hz // 10)
        digits = f"{units_10hz:08d}"
        bcd = bytearray()
        for i in range(0, 8, 2):
            bcd.append((int(digits[i]) << 4) | int(digits[i + 1]))
        bcd.append(0xF9)
        return self._send(bytes(bcd))

    def set_ctcss_dcs_mode(self, mode: str):
        if not self.is_connected:
            return False
        mapping = {
            "dcs": 0x0A,
            "ctcss": 0x2A,
            "ctcss_dec": 0x3A,
            "ctcss_enc": 0x4A,
            "off": 0x8A,
        }
        code = mapping.get(mode)
        if code is None:
            return False
        cmd = bytes([code, 0x00, 0x00, 0x00, 0x0A])
        return self._send(cmd)

    def set_ctcss_tone(self, tx_hz: float, rx_hz: float):
        if not self.is_connected:
            return False
        tx = int(round(tx_hz * 10))
        rx = int(round(rx_hz * 10))
        digits_tx = f"{tx:04d}"
        digits_rx = f"{rx:04d}"
        data = bytearray()
        for i in range(0, 4, 2):
            data.append((int(digits_tx[i]) << 4) | int(digits_tx[i + 1]))
        for i in range(0, 4, 2):
            data.append((int(digits_rx[i]) << 4) | int(digits_rx[i + 1]))
        data.append(0x0B)
        return self._send(bytes(data))

    def set_dcs_code(self, tx_code: int, rx_code: int):
        if not self.is_connected:
            return False
        digits_tx = f"{tx_code:03d}".rjust(3, '0')
        digits_rx = f"{rx_code:03d}".rjust(3, '0')
        data = bytearray()
        for digits in (digits_tx, digits_rx):
            if len(digits) == 3:
                digits = '0' + digits
            for i in range(0, 4, 2):
                data.append((int(digits[i]) << 4) | int(digits[i + 1]))
        data.append(0x0C)
        return self._send(bytes(data))

    def read_tx_status(self):
        if not self.is_connected:
            return None
        if not self._send(b"\x00\x00\x00\x00\xf7"):
            return None
        resp = self._read(1)
        if not resp:
            return None
        return resp[0]


class FT897Clone:
    """Handle CLONE mode transfers of complete memory images."""

    def __init__(self, port: str, baudrate: int = 9600, timeout: float = 1.0):
        self.serial = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=timeout,
            write_timeout=timeout,
        )

    @staticmethod
    def enter_clone_mode_instructions() -> str:
        return (
            "1. Turn off the FT-897.\n"
            "2. Hold [FAST] while powering on to enter CLONE mode.\n"
            "3. Press [SEND] on the radio to start transfer."
        )

    def recv_image(
        self,
        expected: int = 6509,
        progress: Callable[[int, int], None] | None = None,
        stop_flag: Callable[[], bool] | None = None,
    ) -> bytes:
        """Receive a CLONE image from the radio."""
        buf = bytearray(expected)
        mv = memoryview(buf)
        total = 0
        while total < expected:
            if stop_flag and stop_flag():
                break
            n = self.serial.readinto(mv[total:expected])
            if n:
                total += n
                if progress:
                    progress(total, expected)
            else:
                # timeout, keep trying
                continue
        return bytes(mv[:total])

    def send_image(
        self,
        image: bytes,
        progress: Callable[[int, int], None] | None = None,
        stop_flag: Callable[[], bool] | None = None,
    ) -> None:
        """Send a CLONE image to the radio."""
        sent = 0
        mv = memoryview(image)
        total = len(image)
        while sent < total:
            if stop_flag and stop_flag():
                break
            n = self.serial.write(mv[sent : sent + 1024])
            if n:
                sent += n
                if progress:
                    progress(sent, total)
            else:
                continue
        self.serial.flush()


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
    raw: bytes = b""


# Memory layout of the FT-897 image. The radio stores 200 memory
# channels beginning at offset ``0x4DF``. Each entry is 28 bytes long
# and the full CLONE image is ``7341`` bytes. The structure matches the
# FT-857 implementation used by CHIRP.
MEMORY_OFFSET = 0x4DF
CHANNEL_SIZE = 28
TOTAL_CHANNELS = 200
IMAGE_SIZE = 7341


def parse_image(image: bytes) -> List[MemoryChannel]:
    """Parse a binary memory image from the FT-897."""

    channels: List[MemoryChannel] = []
    for idx in range(TOTAL_CHANNELS):
        start = MEMORY_OFFSET + idx * CHANNEL_SIZE
        chunk = image[start : start + CHANNEL_SIZE]
        if len(chunk) < CHANNEL_SIZE:
            break

        # first ten bytes contain flags and tone settings
        b0, b1, b2, b3, b4, b5, b6, b7, b8, b9 = chunk[:10]

        mode_code = b0 & 0x07
        mode = {
            0: "LSB",
            1: "USB",
            2: "CW",
            3: "CWR",
            4: "AM",
            5: "FM",
            6: "DIG",
            7: "PKT",
        }.get(mode_code, "FM")

        duplex_code = (b1 >> 6) & 0x03
        skip = bool(b2 & 0x80)

        tmode = b4 & 0x0F
        tone_raw = b6 & 0x3F
        dcs_raw = b8 & 0x7F

        rx_freq = bcd_to_int(chunk[12:16]) * 10
        off_val = bcd_to_int(chunk[16:20]) * 10

        if duplex_code == 0:
            tx_freq = rx_freq
            offset_dir = ""
            offset_hz = 0
        elif duplex_code == 1:
            tx_freq = rx_freq - off_val
            offset_dir = "-"
            offset_hz = off_val
        elif duplex_code == 2:
            tx_freq = rx_freq + off_val
            offset_dir = "+"
            offset_hz = off_val
        else:  # split
            tx_freq = off_val
            offset_dir = "split"
            offset_hz = 0

        ctcss = None
        dcs = None
        if tmode in (0x04, 0x05):
            ctcss = tone_raw / 10.0
        elif tmode == 0x0A:
            dcs = dcs_raw

        step_code = b3 & 0x07
        step_hz = {
            0: 5000,
            1: 10000,
            2: 12500,
            3: 20000,
            4: 25000,
            5: 50000,
            6: 100000,
            7: 6250,
        }.get(step_code, 5000)

        name = (
            chunk[20:28].replace(b"\xff", b" ").decode("ascii", "ignore").strip()
        )

        channels.append(
            MemoryChannel(
                index=idx,
                rx_freq_hz=rx_freq,
                tx_freq_hz=tx_freq,
                mode=mode,
                ctcss=ctcss,
                dcs=dcs,
                offset_dir=offset_dir,
                offset_hz=offset_hz,
                step_hz=step_hz,
                name=name,
                skip=skip,
                raw=bytes(chunk),
            )
        )

    return channels


def build_image(channels: Iterable[MemoryChannel]) -> bytes:
    """Build a binary memory image for uploading to the radio."""

    image = bytearray(b"\x00" * IMAGE_SIZE)
    for ch in channels:
        if ch.index >= TOTAL_CHANNELS:
            continue

        start = MEMORY_OFFSET + ch.index * CHANNEL_SIZE
        block = bytearray(ch.raw or b"\x00" * CHANNEL_SIZE)

        rx_units = int(ch.rx_freq_hz // 10)

        if ch.tx_freq_hz == ch.rx_freq_hz:
            duplex_code = 0
            off_units = 0
        elif ch.offset_dir == "+":
            duplex_code = 2
            off_units = int(ch.offset_hz // 10)
        elif ch.offset_dir == "-":
            duplex_code = 1
            off_units = int(ch.offset_hz // 10)
        elif ch.offset_dir == "split":
            duplex_code = 3
            off_units = int(ch.tx_freq_hz // 10)
        else:
            duplex_code = 0
            off_units = 0

        mode_code = {
            "LSB": 0,
            "USB": 1,
            "CW": 2,
            "CWR": 3,
            "AM": 4,
            "FM": 5,
            "DIG": 6,
            "PKT": 7,
        }.get(ch.mode, 5)

        block[0] = (block[0] & 0xF8) | (mode_code & 0x07)
        block[1] = (block[1] & 0x3F) | ((duplex_code & 0x03) << 6)
        if ch.skip:
            block[2] |= 0x80
        else:
            block[2] &= 0x7F

        step_reverse = {
            5000: 0,
            10000: 1,
            12500: 2,
            20000: 3,
            25000: 4,
            50000: 5,
            100000: 6,
            6250: 7,
        }
        step_code = step_reverse.get(ch.step_hz, 0)
        block[3] = (block[3] & 0xF8) | step_code

        if ch.dcs is not None:
            block[4] = (block[4] & 0xF0) | 0x0A
            block[8] = (block[8] & 0x80) | (ch.dcs & 0x7F)
            block[9] = (block[9] & 0x80) | (ch.dcs & 0x7F)
            block[6] &= 0xC0
            block[7] &= 0xC0
        elif ch.ctcss is not None:
            block[4] = (block[4] & 0xF0) | 0x05
            tone_val = int(ch.ctcss * 10) & 0x3F
            block[6] = (block[6] & 0xC0) | tone_val
            block[7] = (block[7] & 0xC0) | tone_val
            block[8] &= 0x80
            block[9] &= 0x80
        else:
            block[4] &= 0xF0
            block[6] &= 0xC0
            block[7] &= 0xC0
            block[8] &= 0x80
            block[9] &= 0x80

        block[12:16] = int_to_bcd(rx_units, 8)
        block[16:20] = int_to_bcd(off_units, 8)

        name = (ch.name or "").ljust(8)[:8]
        block[20:28] = name.encode("ascii", "ignore")

        image[start : start + CHANNEL_SIZE] = block

    return bytes(image)


def verify_image(image: bytes) -> tuple[bool, str]:
    """Basic validation of a memory image."""
    if len(image) != IMAGE_SIZE:
        return False, f"Invalid size {len(image)}, expected {IMAGE_SIZE}"
    if MEMORY_OFFSET + CHANNEL_SIZE > len(image):
        return False, "Image too short"
    return True, "OK"


def export_json(channels: Iterable[MemoryChannel], fp) -> None:
    data = []
    for ch in channels:
        d = ch.__dict__.copy()
        d.pop("raw", None)
        data.append(d)
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
            "ctcss",
            "dcs",
            "offset_dir",
            "offset_hz",
            "step_hz",
            "skip",
            "name",
        ]
    )
    for ch in channels:
        writer.writerow(
            [
                ch.index,
                ch.rx_freq_hz,
                ch.tx_freq_hz,
                ch.mode,
                ch.ctcss if ch.ctcss is not None else "",
                ch.dcs if ch.dcs is not None else "",
                ch.offset_dir,
                ch.offset_hz,
                ch.step_hz,
                int(ch.skip),
                ch.name,
            ]
        )


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
                ctcss=float(row["ctcss"]) if row.get("ctcss") else None,
                dcs=int(row["dcs"]) if row.get("dcs") else None,
                offset_dir=row.get("offset_dir", ""),
                offset_hz=int(row.get("offset_hz", 0)),
                step_hz=int(row.get("step_hz", 0)),
                skip=row.get("skip", "0") in ("1", "true", "True"),
                name=row.get("name", ""),
            )
        )
    return channels


def backup(port: str, out_file: str) -> None:
    clone = FT897Clone(port)
    image = clone.recv_image()
    with open(out_file, "wb") as f:
        f.write(image)


def restore(port: str, image_file: str) -> None:
    with open(image_file, "rb") as f:
        image = f.read()
    clone = FT897Clone(port)
    clone.send_image(image)


def export_cmd(image_file: str, dest: str) -> None:
    with open(image_file, "rb") as f:
        image = f.read()
    channels = parse_image(image)
    if dest.lower().endswith(".json"):
        with open(dest, "w", encoding="utf-8") as out:
            export_json(channels, out)
    else:
        with open(dest, "w", newline="", encoding="utf-8") as out:
            export_csv(channels, out)


def cli_main(argv: List[str] | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd")

    b = sub.add_parser("backup")
    b.add_argument("port")
    b.add_argument("outfile")

    r = sub.add_parser("restore")
    r.add_argument("port")
    r.add_argument("image")

    e = sub.add_parser("export")
    e.add_argument("image")
    e.add_argument("dest")

    t = sub.add_parser("selftest")
    t.add_argument("image")

    args = parser.parse_args(argv)
    if args.cmd == "backup":
        backup(args.port, args.outfile)
    elif args.cmd == "restore":
        restore(args.port, args.image)
    elif args.cmd == "export":
        export_cmd(args.image, args.dest)
    elif args.cmd == "selftest":
        with open(args.image, "rb") as f:
            img = f.read()
        ok, msg = verify_image(img)
        if not ok:
            print(msg)
            sys.exit(1)
        rebuilt = build_image(parse_image(img))
        if rebuilt != img:
            print("Round-trip mismatch")
            sys.exit(1)
        print("Self-test OK")
    else:
        parser.print_help()


class MemoryModel(QObject):
    updated = pyqtSignal()
    def __init__(self):
        super().__init__()
        self.channels: list[MemoryChannel] = []

    def set_from_image(self, image: bytes):
        self.channels = parse_image(image)
        self.updated.emit()

    def build_image(self) -> bytes:
        return build_image(self.channels)

class StatusThread(QThread):
    status_updated = pyqtSignal(int, int, int, int)  # frequency, smeter, power, swr

    def __init__(self, cat: FT897CAT):
        super().__init__()
        self.cat = cat
        self.running = False

    def run(self):
        self.running = True
        while self.running:
            if self.cat.is_connected:
                freq = self.cat.get_frequency()
                sm = None
                power = None

                status = self.cat.read_tx_status()
                ptt = status is not None and (status & 0x80) == 0

                if ptt:
                    power = status & 0x0F
                    swr_flag = self.cat.get_swr(status)
                else:
                    sm = self.cat.get_smeter()
                    swr_flag = None

                if freq is not None and 100000 <= freq <= 500000000:
                    sm = sm if sm is not None else -1
                    power = power if power is not None else -1
                    swr_val = -1 if swr_flag is None else swr_flag
                    self.status_updated.emit(freq, sm, power, swr_val)
            self.msleep(150)

    def stop(self):
        self.running = False


class CloneWorker(QThread):
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(bytes, str)

    def __init__(self, port: str, send: bool = False, image: bytes | None = None):
        super().__init__()
        self.port = port
        self.send = send
        self.image = image or b""
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            clone = FT897Clone(self.port)
            if self.send:
                clone.send_image(
                    self.image,
                    progress=lambda c, t: self.progress.emit(c, t),
                    stop_flag=lambda: self._stop,
                )
                data = b""
            else:
                data = clone.recv_image(
                    expected=IMAGE_SIZE,
                    progress=lambda c, t: self.progress.emit(c, t),
                    stop_flag=lambda: self._stop,
                )
            clone.serial.close()
            self.finished.emit(data, "")
        except Exception as e:
            self.finished.emit(b"", str(e))


class RadioControlApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cat = FT897CAT()
        self.status_thread = StatusThread(self.cat)
        self.status_thread.status_updated.connect(self.update_status)

        self.ptt_heartbeat = QTimer(self)
        self.ptt_heartbeat.setInterval(100)
        self.ptt_heartbeat.timeout.connect(self.cat.ptt_on)

        self.current_font_family = "Courier New"
        self.freq_text = "000,00000"
        self.current_theme = "dark"
        self.last_valid_frequency = None
        self.font_adjust_needed = True

        self.memory_model = MemoryModel()
        # Define frequency ranges and default modes
        self.band_configs = {
            "160 m": {"range": (1_800_000, 2_000_000), "step": 1000, "mode": "LSB"},
            "80 m": {"range": (3_500_000, 3_799_000), "step": 1000, "mode": "LSB"},
            "60 m": {"list": [5_357_000, 5_371_500], "mode": "USB"},
            "40 m": {"range": (7_000_000, 7_200_000), "step": 1000, "mode": "LSB"},
            "30 m": {"range": (10_100_000, 10_150_000), "step": 1000, "mode": "USB"},
            "20 m": {"range": (14_000_000, 14_350_000), "step": 1000, "mode": "USB"},
            "17 m": {"range": (18_068_000, 18_168_000), "step": 1000, "mode": "USB"},
            "15 m": {"range": (21_000_000, 21_450_000), "step": 1000, "mode": "USB"},
            "12 m": {"range": (24_890_000, 24_990_000), "step": 1000, "mode": "USB"},
            "10 m": {"list": [28_070_000, 28_074_000, 28_400_000], "mode": "USB"},
            "6 m": {"range": (50_000_000, 54_000_000), "step": 5000, "mode": "USB"},
            "FM rozhlas": {"range": (87_500_000, 108_000_000), "step": 100_000, "mode": "FM"},
            "2 m": {"submenus": {
                "144 MHz": {"range": (144_000_000, 144_400_000), "step": 1000, "mode": "USB"},
                "145 MHz": {"range": (145_000_000, 145_800_000), "step": 12500, "mode": "FM"}
            }},
            "70 cm": {"submenus": {
                "432 MHz": {"range": (432_000_000, 434_000_000), "step": 1000, "mode": "USB"},
                "438 MHz": {"range": (438_000_000, 440_000_000), "step": 12500, "mode": "FM"}
            }},
            "CB": {"range": (26_965_000, 27_405_000), "step": 10000, "mode": "AM"},
            "Letecké": {"range": (118_000_000, 137_000_000), "step": 25000, "mode": "AM"},
            "AM rozhlas": {"range": (500_000, 1_700_000), "step": 10000, "mode": "AM"},
            "PMR446": {"range": (446_006_250, 446_193_750), "step": 12500, "mode": "FM"},
            "SW 120 m": {"range": (2_300_000, 2_495_000), "step": 5000, "mode": "AM"},
            "SW 90 m": {"range": (3_200_000, 3_400_000), "step": 5000, "mode": "AM"},
            "SW 75 m": {"range": (3_900_000, 4_000_000), "step": 5000, "mode": "AM"},
            "SW 60 m": {"range": (4_750_000, 5_000_000), "step": 5000, "mode": "AM"},
            "SW 49 m": {"range": (5_900_000, 6_200_000), "step": 5000, "mode": "AM"},
            "SW 41 m": {"range": (7_200_000, 7_600_000), "step": 5000, "mode": "AM"},
            "SW 31 m": {"range": (9_400_000, 10_000_000), "step": 5000, "mode": "AM"},
            "SW 25 m": {"range": (11_600_000, 12_100_000), "step": 5000, "mode": "AM"},
            "SW 22 m": {"range": (13_570_000, 13_870_000), "step": 5000, "mode": "AM"},
            "SW 19 m": {"range": (15_100_000, 15_800_000), "step": 5000, "mode": "AM"},
            "SW 16 m": {"range": (17_480_000, 17_900_000), "step": 5000, "mode": "AM"},
            "SW 13 m": {"range": (21_450_000, 21_850_000), "step": 5000, "mode": "AM"},
            "SW 11 m": {"range": (25_670_000, 26_100_000), "step": 5000, "mode": "AM"},
        }

        # Preset memory channels split by category. Each entry is a tuple
        # (label, frequency_hz, mode) used by the Memory menu for quick tuning.
        self.memory_presets = {
            "FM rozhlas": [
                ("Evropa 2 – Kleť", 105_500_000, "FM"),
                ("ČRo Radiožurnál – Kleť", 91_100_000, "FM"),
                ("Frekvence 1 – Kleť", 94_100_000, "FM"),
                ("Rock Radio – Kleť", 99_700_000, "FM"),
                ("Rádio Beat – Kleť", 101_000_000, "FM"),
                ("Rádio Impuls – Kleť", 102_900_000, "FM"),
                ("Hitrádio Faktor – Kleť", 104_300_000, "FM"),
                ("ČRo Dvojka", 103_200_000, "FM"),
                ("Radio Niederösterreich", 95_700_000, "FM"),
                ("Ö1", 92_700_000, "FM"),
                ("FM4", 101_400_000, "FM"),
                ("Metro Life Radio", 100_800_000, "FM"),
                ("Ö1 – Jauerling", 97_500_000, "FM"),
                ("ČRo Plus", 95_400_000, "FM"),
                ("Frekvence 1 – Jihlava Strážník", 93_400_000, "FM"),
                ("Rádio Kiss", 97_700_000, "FM"),
                ("ČRo České Budějovice – Kleť", 106_400_000, "FM"),
                ("ČRo Radiožurnál – Votice Mezivrata", 93_100_000, "FM"),
                ("Country Radio", 92_000_000, "FM"),
            ],
            "CB kanály": [
                (f"CB {i}", 26_965_000 + (i - 1) * 10_000, "AM")
                for i in range(1, 81)
            ],
            "PMR446": [
                (f"Kanál {i+1}", 446_006_250 + i * 12_500, "FM") for i in range(16)
            ],
            "2 m": [
                ("145.500 FM", 145_500_000, "FM"),
                ("JČ direkt", 145_400_000, "FM"),
                ("144.300 USB", 144_300_000, "USB"),
            ],
        }

        self.band_max_power = {
            "160 m": 100,
            "80 m": 100,
            "60 m": 100,
            "40 m": 100,
            "30 m": 100,
            "20 m": 100,
            "17 m": 100,
            "15 m": 100,
            "12 m": 100,
            "10 m": 100,
            "6 m": 100,
            "2 m": 50,
            "70 cm": 20,
        }

        # Minimum selectable power is around 5 W on all bands
        self.band_min_power = {
            band: 5 for band in self.band_max_power
        }

        # Raw meter values observed at minimum and maximum power
        # for calibrating output power readings. Values default to 0–15
        # if a band is not specified here.
        # Power meter calibration: raw meter range to expect on each band
        # "min_raw" corresponds to the minimum selectable output power and
        # "max_raw" to the maximum.  For better sensitivity on 2 m we
        # stretch the range to cover the entire 0–15 values.
        # Power meter calibration: raw meter range to expect on each band.
        # "min_raw" corresponds to the value at minimum selectable power and
        # "max_raw" to the value at maximum power.  Using a wide range on 2 m
        # increases the effective sensitivity when displaying power up to 50 W.
        # Empirically the FT-897 only reports a very small change of the raw
        # power meter value on 2 m.  With high power (50 W) the reading tops out
        # around 7 while it drops to about 2 at the minimum selectable power.
        # Calibrating the meter using this observed range yields more accurate
        # wattage estimates.
        self.band_power_calibration = {
            # Default calibrations for output power meter readings
            # on individual bands. Values correspond to raw meter
            # readings observed at minimum and maximum selectable
            # power.  These can be fine tuned by the user via the
            # power calibration dialog.
            "160 m": {"min_raw": 1, "max_raw": 15},
            "80 m": {"min_raw": 1, "max_raw": 15},
            "60 m": {"min_raw": 1, "max_raw": 15},
            "40 m": {"min_raw": 1, "max_raw": 15},
            "30 m": {"min_raw": 1, "max_raw": 15},
            "20 m": {"min_raw": 1, "max_raw": 15},
            "17 m": {"min_raw": 1, "max_raw": 15},
            "15 m": {"min_raw": 1, "max_raw": 15},
            "12 m": {"min_raw": 1, "max_raw": 15},
            "10 m": {"min_raw": 1, "max_raw": 15},
            "6 m": {"min_raw": 1, "max_raw": 15},
            "2 m": {"min_raw": 2, "max_raw": 7},
            "70 cm": {"min_raw": 2, "max_raw": 7},
        }

        # Optional detailed mapping of raw meter values to watts for
        # improved precision.  When provided for a band, values are
        # linearly interpolated between the nearest points.
        self.band_power_curve = {
            # Calibrated from additional measurements to improve
            # resolution on the 2 m band. The radio reports only a
            # 4‑bit value (0‑15), so we interpolate these points to
            # estimate power output more accurately between 5 W and
            # 50 W.
            "2 m": {
                2: 5,   # ∼5 W at minimum power
                3: 14,  # ∼14 W
                4: 23,  # ∼23 W
                5: 34,  # ∼34 W
                6: 43,  # ∼43 W
                7: 50,  # ∼50 W at full power
            },
        }


        self.band_definitions = [
            ((87500, 108000), "FM rozhlas"),
            ((108000, 137000), "Letecké pásmo"),
            ((446000, 446200), "PMR446"),
            ((148, 283), "DLF/Morze"),
        ]
        for band, cfg in self.band_configs.items():
            if "range" in cfg:
                start, end = cfg["range"]
            elif "list" in cfg:
                start, end = min(cfg["list"]), max(cfg["list"])
            elif "submenus" in cfg:
                ranges = []
                for subcfg in cfg["submenus"].values():
                    if "range" in subcfg:
                        ranges.append(subcfg["range"])
                    elif "list" in subcfg:
                        ranges.append((min(subcfg["list"]), max(subcfg["list"])))
                if ranges:
                    start = min(r[0] for r in ranges)
                    end = max(r[1] for r in ranges)
                else:
                    continue
            else:
                continue
            self.band_definitions.append(((start / 1000, end / 1000), band))

        self.init_ui()
        self.apply_stylesheet(self.current_theme)

    def init_ui(self):
        self.setWindowTitle("FT-897 CAT Control")
        self.setGeometry(100, 100, 800, 400)

        self.central = QWidget()
        self.setCentralWidget(self.central)
        self.layout = QVBoxLayout(self.central)

        self.port_combo = QComboBox()
        ports = list_ports.comports()
        for port in ports:
            self.port_combo.addItem(port.device)
        self.layout.addWidget(self.port_combo)

        self.connect_btn = QPushButton("Připojit")
        self.connect_btn.clicked.connect(self.toggle_connection)
        self.layout.addWidget(self.connect_btn)

        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        self.freq_tab = QWidget()
        self.freq_layout = QVBoxLayout(self.freq_tab)

        self.freq_label = QLabel(self.freq_text)
        self.freq_label.setAlignment(Qt.AlignCenter)
        self.freq_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.freq_label.setFont(QFont(self.current_font_family, 10, QFont.Bold))
        self.freq_layout.addWidget(self.freq_label)

        self.band_label = QLabel("")
        self.band_label.setAlignment(Qt.AlignCenter)
        self.band_label.setStyleSheet("font-size: 18px;")
        self.freq_layout.addWidget(self.band_label)

        self.tabs.addTab(self.freq_tab, "Frekvence")

        self.smeter_tab = QWidget()
        self.smeter_layout = QVBoxLayout(self.smeter_tab)

        self.smeter_desc_label = QLabel("S-metr:")
        self.smeter_desc_label.setAlignment(Qt.AlignCenter)
        self.smeter_layout.addWidget(self.smeter_desc_label)

        self.smeter_value_label = QLabel("---")
        self.smeter_value_label.setAlignment(Qt.AlignCenter)
        self.smeter_value_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.smeter_value_label.setFont(QFont(self.current_font_family, 10, QFont.Bold))
        self.smeter_layout.addWidget(self.smeter_value_label)

        self.tabs.addTab(self.smeter_tab, "S-metr")

        self.swr_tab = QWidget()
        self.swr_layout = QVBoxLayout(self.swr_tab)

        self.swr_label = QLabel("SWR: ---")
        self.swr_label.setAlignment(Qt.AlignCenter)
        self.swr_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.swr_layout.addWidget(self.swr_label)

        self.tabs.addTab(self.swr_tab, "SWR")

        self.power_tab = QWidget()
        self.power_layout = QVBoxLayout(self.power_tab)
        self.power_label = QLabel("Výkon: ---")
        self.power_label.setAlignment(Qt.AlignCenter)
        self.power_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.power_label.setFont(QFont(self.current_font_family, 10, QFont.Bold))
        self.power_layout.addWidget(self.power_label)

        self.tabs.addTab(self.power_tab, "Výkon")

        self.ptt_container = QFrame()
        self.ptt_layout = QVBoxLayout(self.ptt_container)
        self.ptt_btn = QPushButton("PTT")
        self.ptt_btn.setFont(QFont("Arial", 20, QFont.Bold))
        self.ptt_btn.setCheckable(True)
        self.ptt_btn.pressed.connect(self.handle_ptt_on)
        self.ptt_btn.released.connect(self.handle_ptt_off)
        self.ptt_btn.setEnabled(False)
        self.ptt_layout.addWidget(self.ptt_btn)
        self.layout.addWidget(self.ptt_container)

        self.init_menu()

    def init_menu(self):
        menubar = self.menuBar()
        menubar.setStyleSheet(
            """
            QMenuBar {
                background-color: #333;
                color: white;
                font-weight: bold;
                font-size: 16px;
            }
            QMenuBar::item {
                background: transparent;
                padding: 6px 20px;
            }
            QMenuBar::item:selected {
                background: #555;
                color: yellow;
            }
            QMenu {
                background-color: #222;
                color: white;
                font-size: 15px;
            }
            QMenu::item {
                padding: 6px 24px;
            }
            QMenu::item:selected {
                background-color: #444;
                color: yellow;
            }
        """
        )
        view_menu = menubar.addMenu("Zobrazení")

        band_menu = menubar.addMenu("Pásma")
        for band, cfg in self.band_configs.items():
            if "submenus" in cfg:
                parent = band_menu.addMenu(band)
                for subname, subcfg in cfg["submenus"].items():
                    sub = parent.addMenu(subname)
                    if "list" in subcfg:
                        freqs = subcfg["list"]
                    else:
                        start, end = subcfg["range"]
                        step = subcfg.get("step", 1000)
                        freqs = list(range(start, end + 1, step))
                    for f in freqs:
                        label = f"{f/1_000_000:.3f} MHz"
                        act = QAction(label, self)
                        act.setData((int(f), subcfg["mode"]))
                        act.triggered.connect(self.tune_from_menu)
                        sub.addAction(act)
            else:
                sub = band_menu.addMenu(band)
                if "list" in cfg:
                    freqs = cfg["list"]
                else:
                    start, end = cfg["range"]
                    step = cfg.get("step", 1000)
                    freqs = list(range(start, end + 1, step))
                for f in freqs:
                    label = f"{f/1_000_000:.3f} MHz"
                    act = QAction(label, self)
                    act.setData((int(f), cfg["mode"]))
                    act.triggered.connect(self.tune_from_menu)
                    sub.addAction(act)
        memory_menu = menubar.addMenu("Paměť")
        load_act = QAction("Načíst paměti z rádia (CLONE)…", self)
        load_act.triggered.connect(self.load_from_radio)
        memory_menu.addAction(load_act)
        save_act = QAction("Nahrát do rádia…", self)
        save_act.triggered.connect(self.save_to_radio)
        memory_menu.addAction(save_act)
        import_act = QAction("Importovat z image/JSON/CSV…", self)
        import_act.triggered.connect(self.import_memories)
        memory_menu.addAction(import_act)
        export_act = QAction("Exportovat…", self)
        export_act.triggered.connect(self.export_memories)
        memory_menu.addAction(export_act)
        memory_menu.addSeparator()
        self.memory_list_menu = memory_menu.addMenu("Kanály")
        self.memory_model.updated.connect(self.refresh_memory_menu)
        self.refresh_memory_menu()
        font_action = QAction("Nastavit písmo…", self)
        font_action.triggered.connect(self.choose_font)
        view_menu.addAction(font_action)

        color_scheme_action = QAction("Nastavit barevné schéma…", self)
        color_scheme_action.triggered.connect(self.choose_color_scheme)
        view_menu.addAction(color_scheme_action)

        mode_menu = menubar.addMenu("Módy")
        for mode in ["LSB", "USB", "CW", "CWR", "AM", "FM", "DIG"]:
            act = QAction(mode, self)
            act.triggered.connect(lambda _, m=mode: self.cat.set_mode(m))
            mode_menu.addAction(act)

        cat_menu = menubar.addMenu("CAT příkazy")

        vfo_action = QAction("Přepnout VFO A/B", self)
        vfo_action.triggered.connect(self.cat.toggle_vfo)
        cat_menu.addAction(vfo_action)

        split_on = QAction("Split ON", self)
        split_on.triggered.connect(self.cat.split_on)
        cat_menu.addAction(split_on)

        split_off = QAction("Split OFF", self)
        split_off.triggered.connect(self.cat.split_off)
        cat_menu.addAction(split_off)

        cat_menu.addSeparator()

        lock_on = QAction("LOCK ON", self)
        lock_on.triggered.connect(self.cat.lock_on)
        cat_menu.addAction(lock_on)

        lock_off = QAction("LOCK OFF", self)
        lock_off.triggered.connect(self.cat.lock_off)
        cat_menu.addAction(lock_off)

        clar_on = QAction("CLAR ON", self)
        clar_on.triggered.connect(self.cat.clar_on)
        cat_menu.addAction(clar_on)

        clar_off = QAction("CLAR OFF", self)
        clar_off.triggered.connect(self.cat.clar_off)
        cat_menu.addAction(clar_off)

        clar_freq = QAction("Nastavit CLAR offset…", self)
        clar_freq.triggered.connect(self.prompt_clar_offset)
        cat_menu.addAction(clar_freq)

        rpt_minus = QAction("Opakovač -", self)
        rpt_minus.triggered.connect(lambda: self.cat.set_repeater_offset_mode("minus"))
        cat_menu.addAction(rpt_minus)

        rpt_plus = QAction("Opakovač +", self)
        rpt_plus.triggered.connect(lambda: self.cat.set_repeater_offset_mode("plus"))
        cat_menu.addAction(rpt_plus)

        rpt_simplex = QAction("Opakovač simplex", self)
        rpt_simplex.triggered.connect(lambda: self.cat.set_repeater_offset_mode("simplex"))
        cat_menu.addAction(rpt_simplex)

        rpt_freq = QAction("Nastavit offset…", self)
        rpt_freq.triggered.connect(self.prompt_offset_frequency)
        cat_menu.addAction(rpt_freq)

        ctcss_mode = QAction("CTCSS/DCS režim…", self)
        ctcss_mode.triggered.connect(self.prompt_ctcss_mode)
        cat_menu.addAction(ctcss_mode)

        ctcss_tone = QAction("Nastavit CTCSS tón…", self)
        ctcss_tone.triggered.connect(self.prompt_ctcss_tone)
        cat_menu.addAction(ctcss_tone)

        dcs_code = QAction("Nastavit DCS kód…", self)
        dcs_code.triggered.connect(self.prompt_dcs_code)
        cat_menu.addAction(dcs_code)


    def choose_font(self):
        font, ok = QFontDialog.getFont(QFont(self.current_font_family, 10), self)
        if ok:
            self.current_font_family = font.family()
            self.font_adjust_needed = True
            self.adjust_all_fonts()

    def choose_color_scheme(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Vyberte barevné schéma")
        layout = QVBoxLayout()
        dark = QRadioButton("Tmavý režim")
        light = QRadioButton("Světlý režim")
        contrast = QRadioButton("Vysoký kontrast")
        if self.current_theme == "dark":
            dark.setChecked(True)
        elif self.current_theme == "light":
            light.setChecked(True)
        else:
            contrast.setChecked(True)
        layout.addWidget(dark)
        layout.addWidget(light)
        layout.addWidget(contrast)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.setLayout(layout)
        if dialog.exec_() == QDialog.Accepted:
            if dark.isChecked():
                self.apply_stylesheet("dark")
            elif light.isChecked():
                self.apply_stylesheet("light")
            else:
                self.apply_stylesheet("contrast")

    def prompt_clar_offset(self):
        if not self.cat.is_connected:
            QMessageBox.warning(self, "Chyba", "Rádio není připojeno.")
            return
        val, ok = QInputDialog.getInt(self, "CLAR offset", "Zadejte offset v Hz:", 0, -9999, 9999)
        if ok:
            sign = 1 if val >= 0 else -1
            self.cat.set_clar_frequency(abs(val), sign)

    def prompt_offset_frequency(self):
        if not self.cat.is_connected:
            QMessageBox.warning(self, "Chyba", "Rádio není připojeno.")
            return
        val, ok = QInputDialog.getInt(self, "Offset", "Zadejte offset v Hz:", 0, 0, 9999999)
        if ok:
            self.cat.set_repeater_offset_frequency(val)

    def prompt_ctcss_mode(self):
        if not self.cat.is_connected:
            QMessageBox.warning(self, "Chyba", "Rádio není připojeno.")
            return
        modes = {
            "DCS": "dcs",
            "CTCSS": "ctcss",
            "CTCSS dekód": "ctcss_dec",
            "CTCSS enkód": "ctcss_enc",
            "Vypnuto": "off",
        }
        item, ok = QInputDialog.getItem(self, "CTCSS/DCS", "Režim:", list(modes.keys()), 0, False)
        if ok:
            self.cat.set_ctcss_dcs_mode(modes[item])

    def prompt_ctcss_tone(self):
        if not self.cat.is_connected:
            QMessageBox.warning(self, "Chyba", "Rádio není připojeno.")
            return
        tx, ok = QInputDialog.getDouble(self, "CTCSS TX", "Frekvence v Hz:", 88.5, 60.0, 300.0, 1)
        if not ok:
            return
        rx, ok = QInputDialog.getDouble(self, "CTCSS RX", "Frekvence v Hz:", tx, 60.0, 300.0, 1)
        if ok:
            self.cat.set_ctcss_tone(tx, rx)

    def prompt_dcs_code(self):
        if not self.cat.is_connected:
            QMessageBox.warning(self, "Chyba", "Rádio není připojeno.")
            return
        tx, ok = QInputDialog.getInt(self, "DCS TX", "Kód:", 23, 0, 511)
        if not ok:
            return
        rx, ok = QInputDialog.getInt(self, "DCS RX", "Kód:", tx, 0, 511)
        if ok:
            self.cat.set_dcs_code(tx, rx)

    def load_from_radio(self):
        if not self.cat.is_connected:
            QMessageBox.warning(self, "Chyba", "Rádio není připojeno.")
            return
        instr = QDialog(self)
        instr.setWindowTitle("CLONE")
        l = QVBoxLayout(instr)
        l.addWidget(QLabel(FT897Clone.enter_clone_mode_instructions()))
        start_btn = QPushButton("Start")
        l.addWidget(start_btn)
        instr.setModal(True)

        def on_start():
            instr.accept()
        start_btn.clicked.connect(on_start)
        if instr.exec_() != QDialog.Accepted:
            return

        progress = QProgressDialog("Příjem pamětí", "Storno", 0, IMAGE_SIZE, self)
        progress.setWindowTitle("CLONE")
        worker = CloneWorker(self.cat.port)

        worker.progress.connect(lambda c, t: progress.setValue(c))
        worker.finished.connect(lambda data, err: self._clone_recv_finished(data, err, progress))
        progress.canceled.connect(worker.stop)
        progress.show()
        worker.start()

    def save_to_radio(self):
        if not self.cat.is_connected:
            QMessageBox.warning(self, "Chyba", "Rádio není připojeno.")
            return
        QMessageBox.information(self, "Instrukce", FT897Clone.enter_clone_mode_instructions())
        image = self.memory_model.build_image()
        progress = QProgressDialog("Odesílání pamětí", "Storno", 0, len(image), self)
        progress.setWindowTitle("CLONE")
        worker = CloneWorker(self.cat.port, send=True, image=image)
        worker.progress.connect(lambda c, t: progress.setValue(c))
        worker.finished.connect(lambda _d, err: self._clone_send_finished(err, progress))
        progress.canceled.connect(worker.stop)
        progress.show()
        worker.start()

    def _clone_recv_finished(self, data: bytes, err: str, progress: QProgressDialog):
        progress.hide()
        if err:
            QMessageBox.critical(self, "Chyba", err)
            return
        ok, msg = verify_image(data)
        if not ok:
            QMessageBox.warning(self, "Chyba image", msg)
            return
        self.memory_model.set_from_image(data)
        QMessageBox.information(self, "Hotovo", f"Načteno {len(self.memory_model.channels)} kanálů")

    def _clone_send_finished(self, err: str, progress: QProgressDialog):
        progress.hide()
        if err:
            QMessageBox.critical(self, "Chyba", err)
        else:
            QMessageBox.information(self, "Hotovo", "Paměti nahrány")

    def import_memories(self):
        path, _ = QFileDialog.getOpenFileName(self, "Importovat", "", "All Files (*.*)")
        if not path:
            return
        if path.lower().endswith(".img"):
            try:
                data = Path(path).read_bytes()
                ok, msg = verify_image(data)
                if not ok:
                    QMessageBox.warning(self, "Chyba", msg)
                    return
                self.memory_model.set_from_image(data)
            except Exception as e:
                QMessageBox.critical(self, "Chyba", str(e))
        elif path.endswith(".json"):
            with open(path, "r", encoding="utf-8") as f:
                self.memory_model.channels = import_json(f)
                self.memory_model.updated.emit()
        else:
            with open(path, "r", encoding="utf-8") as f:
                self.memory_model.channels = import_csv(f)
                self.memory_model.updated.emit()

    def export_memories(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exportovat", "", "JSON (*.json);;CSV (*.csv);;IMG (*.img)")
        if not path:
            return
        if path.endswith(".img"):
            with open(path, "wb") as f:
                f.write(self.memory_model.build_image())
        elif path.endswith(".json"):
            with open(path, "w", encoding="utf-8") as f:
                export_json(self.memory_model.channels, f)
        else:
            with open(path, "w", encoding="utf-8", newline="") as f:
                export_csv(self.memory_model.channels, f)



    def apply_stylesheet(self, theme):
        self.current_theme = theme
        base_style = (
            "QWidget { font-family: 'Segoe UI'; }" \
            " QPushButton { padding: 6px; border-radius: 3px; }" \
            " QPushButton:checked { font-weight: bold; }"
        )
        if theme == "dark":
            extra = "QWidget { background-color: #1e1e1e; color: white; }"
        elif theme == "light":
            extra = "QWidget { background-color: #ffffff; color: black; }"
        else:
            extra = "QWidget { background-color: #000; color: yellow; }"
        self.setStyleSheet(base_style + extra)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.font_adjust_needed = True
        self.adjust_all_fonts()

    def adjust_all_fonts(self):
        self.adjust_label_font(self.freq_label)
        self.adjust_label_font(self.smeter_value_label)
        self.adjust_label_font(self.swr_label)
        self.adjust_label_font(self.power_label)

    def adjust_label_font(self, label: QLabel):
        text = label.text()
        if not text:
            return
        width = label.width()
        height = label.height()
        orig_weight = label.font().weight()
        font = QFont(self.current_font_family, 10)
        min_size, max_size = 10, 300
        while min_size <= max_size:
            mid = (min_size + max_size) // 2
            font.setPointSize(mid)
            metrics = QFontMetrics(font)
            rect = metrics.boundingRect(text)
            if rect.width() <= width and rect.height() <= height:
                min_size = mid + 1
            else:
                max_size = mid - 1
        font.setPointSize(max_size)
        font.setWeight(orig_weight)
        label.setFont(font)

    def toggle_connection(self):
        if not self.cat.is_connected:
            port = self.port_combo.currentText()
            if self.cat.connect(port):
                self.status_thread.start()
                self.ptt_btn.setEnabled(True)
                self.connect_btn.setText("Odpojit")
            else:
                QMessageBox.warning(self, "Chyba", "Nelze se připojit.")
        else:
            self.status_thread.stop()
            self.status_thread.wait()
            self.cat.disconnect()
            self.ptt_btn.setEnabled(False)
            self.connect_btn.setText("Připojit")

    def update_status(self, freq_hz, sm_level, power_level, swr_flag):
        if freq_hz is None:
            return
        self.last_valid_frequency = freq_hz
        freq_mhz = freq_hz / 1_000_000.0
        formatted = f"{freq_mhz:.5f}".replace('.', ',')
        self.freq_label.setText(formatted)
        freq_khz = freq_hz / 1000.0
        self.band_label.setText(f"Pásmo: {self.get_band_label_from_khz(freq_khz)}")
        if sm_level >= 0:
            self.smeter_value_label.setText(self.format_smeter(sm_level))
        else:
            self.smeter_value_label.setText("---")

        if power_level >= 0:
            band = self.get_band_label_from_khz(freq_khz)
            calib = self.band_power_calibration.get(band, {"min_raw": 0, "max_raw": 15})
            raw_min = calib.get("min_raw", 0)
            raw_max = calib.get("max_raw", 15)
            if raw_max == raw_min:
                percent = 0
            else:
                level = max(raw_min, min(power_level, raw_max))
                percent = int(round(100 * (level - raw_min) / (raw_max - raw_min)))
            self.power_label.setText(f"Výkon: {percent} %")
        else:
            self.power_label.setText("Výkon: ---")
        if swr_flag == 1:
            self.swr_label.setText("SWR: High")
        elif swr_flag == 0:
            self.swr_label.setText("SWR: Normal")
        else:
            self.swr_label.setText("SWR: ---")
        if self.font_adjust_needed:
            self.adjust_all_fonts()
            self.font_adjust_needed = False

    def get_band_label_from_khz(self, freq_khz):
        for (start, end), label in self.band_definitions:
            if start <= freq_khz <= end:
                return label
        return f"Neznámé pásmo ({freq_khz/1000:.5f} MHz)"

    def format_smeter(self, raw):
        """Return textual representation from raw S-meter value (0-15)."""
        if raw is None:
            return "---"
        if raw <= 9:
            return f"S{raw}"
        db = (raw - 9) * 10
        return f"S9+{db}"

    def refresh_memory_menu(self):
        self.memory_list_menu.clear()
        for ch in self.memory_model.channels:
            label = f"{ch.index+1}: {ch.name or ch.rx_freq_hz/1_000_000:.3f} MHz"
            act = QAction(label, self)
            act.setData((ch.rx_freq_hz, ch.mode))
            act.triggered.connect(self.tune_from_menu)
            self.memory_list_menu.addAction(act)

    def tune_from_menu(self):
        action = self.sender()
        data = action.data()
        if not data or not self.cat.is_connected:
            return
        freq, mode = data
        self.cat.set_frequency(freq)
        self.cat.set_mode(mode)

    def handle_ptt_on(self):
        if not self.cat.is_connected:
            return
        self.cat.ptt_on()
        self.ptt_heartbeat.start()
        self.ptt_container.setStyleSheet("background-color: #600;")

    def handle_ptt_off(self):
        if not self.cat.is_connected:
            return
        self.ptt_heartbeat.stop()
        self.cat.ptt_off()
        self.ptt_container.setStyleSheet("")

    def closeEvent(self, event):
        self.status_thread.stop()
        self.status_thread.wait()
        self.cat.disconnect()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = RadioControlApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cli_main(sys.argv[1:])
    else:
        main()
