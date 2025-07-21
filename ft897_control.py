#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import subprocess
import time
import threading
from typing import Optional, List, Tuple

# Ensure required packages
required = ["pyserial", "PyQt5"]
for module in required:
    try:
        __import__(module)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", module])

import serial
from serial.tools import list_ports
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton,
    QComboBox, QMessageBox, QAction, QSizePolicy, QTabWidget
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont


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

    # ------------------------------------------------------------------
    def _send(self, data: bytes) -> bool:
        with self._lock:
            try:
                assert self.serial_port
                self.serial_port.reset_input_buffer()
                self.serial_port.reset_output_buffer()
                self.serial_port.write(data)
                self.serial_port.flush()
                time.sleep(0.05)
                return True
            except Exception as e:
                print(f"Chyba serial write: {e}")
                return False

    def _read(self, length: int = 5) -> Optional[bytes]:
        with self._lock:
            try:
                assert self.serial_port
                return self.serial_port.read(length)
            except Exception as e:
                print(f"Chyba serial read: {e}")
                return None

    # connection -------------------------------------------------------
    def connect(self, port: str, baudrate: int = 9600) -> bool:
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
            self.serial_port = None
            self.is_connected = False
            return False

    def disconnect(self) -> None:
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.close()
            except Exception:
                pass
        self.serial_port = None
        self.is_connected = False

    # radio queries ----------------------------------------------------
    def get_frequency(self) -> Optional[int]:
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
        if not self.is_connected:
            return False
        units_10hz = int(freq_hz // 10)
        digits = f"{units_10hz:08d}"
        bcd = bytearray()
        for i in range(0, 8, 2):
            bcd.append((int(digits[i]) << 4) | int(digits[i + 1]))
        return self._send(bytes(bcd) + b"\x01")

    def read_rx_status(self) -> Optional[int]:
        if not self.is_connected:
            return None
        if not self._send(b"\x00\x00\x00\x00\xe7"):
            return None
        resp = self._read(1)
        return resp[0] if resp else None

    def read_tx_status(self) -> Optional[int]:
        if not self.is_connected:
            return None
        if not self._send(b"\x00\x00\x00\x00\xf7"):
            return None
        resp = self._read(1)
        return resp[0] if resp else None

    def get_mode(self) -> Optional[str]:
        status = self.read_rx_status()
        if status is None:
            return None
        code = status & 0x0F
        for name, val in self.MODE_MAP.items():
            if val == code:
                return name
        return None

    def set_mode(self, mode: str) -> bool:
        if not self.is_connected:
            return False
        code = self.MODE_MAP.get(mode)
        if code is None:
            return False
        cmd = bytes([code, 0x00, 0x00, 0x00, 0x07])
        return self._send(cmd)

    # ptt --------------------------------------------------------------
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


class MemoryController:
    """Access FT-897 memory channels over CAT."""

    def __init__(self, cat: FT897CAT) -> None:
        self.cat = cat

    def _send(self, data: bytes) -> bool:
        return self.cat._send(data)

    def _read(self, length: int = 5) -> Optional[bytes]:
        return self.cat._read(length)

    def get_memory_channel(self, index: int) -> Optional[Tuple[int, int, str]]:
        """Read a single memory channel from the radio."""
        if not self.cat.is_connected:
            return None
        cmd = bytes([0x00, index & 0xFF, 0x00, 0x00, 0xB0])
        if not self._send(cmd):
            return None
        resp = self._read(5)
        if not resp or len(resp) != 5:
            return None
        freq = 0
        for b in resp[:4]:
            freq = freq * 100 + ((b >> 4) & 0x0F) * 10 + (b & 0x0F)
        freq *= 10
        mode_code = resp[4] & 0x0F
        mode = next((n for n, v in FT897CAT.MODE_MAP.items() if v == mode_code), "FM")
        return (index, freq, mode)

    def get_memory_channels(self) -> List[Tuple[int, int, str]]:
        channels: List[Tuple[int, int, str]] = []
        if not self.cat.is_connected:
            return channels
        for idx in range(1, 101):
            ch = self.get_memory_channel(idx)
            if ch:
                channels.append(ch)
        return channels

    def set_memory_channel(self, index: int, freq_hz: int, mode: str) -> bool:
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

    def memory_to_vfo(self, index: int) -> bool:
        """Recall a memory channel to the VFO."""
        if not self.cat.is_connected:
            return False
        cmd = bytes([0x00, index & 0xFF, 0x00, 0x00, 0xB3])
        return self._send(cmd)

    def vfo_to_memory(self, index: int) -> bool:
        """Store the current VFO settings into a memory channel."""
        if not self.cat.is_connected:
            return False
        cmd = bytes([0x00, index & 0xFF, 0x00, 0x00, 0xB4])
        return self._send(cmd)


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

    def recall_to_vfo(self, index: int) -> None:
        """Load the specified memory channel into the VFO."""
        if 0 <= index < len(self.entries):
            self.ctrl.memory_to_vfo(index + 1)

    def store_from_vfo(self, index: int) -> None:
        """Save the current VFO settings into the specified memory channel."""
        self.ctrl.vfo_to_memory(index + 1)


class StatusThread(QThread):
    status_updated = pyqtSignal(int, int, int, int, int, str)

    def __init__(self, cat: FT897CAT) -> None:
        super().__init__()
        self.cat = cat
        self.running = False

    def run(self) -> None:
        self.running = True
        while self.running:
            if self.cat.is_connected:
                freq = self.cat.get_frequency() or 0
                rx = self.cat.read_rx_status() or 0
                tx = self.cat.read_tx_status() or 0
                sm = (rx >> 4) & 0x0F
                mode_code = rx & 0x0F
                mode = next((n for n, v in FT897CAT.MODE_MAP.items() if v == mode_code), "")
                ptt = 0 if (tx & 0x80) else 1
                power = tx & 0x0F if ptt else -1
                swr = 1 if (ptt and (tx & 0x40)) else (0 if ptt else -1)
                self.status_updated.emit(freq, sm, power, swr, ptt, mode)
            self.msleep(150)

    def stop(self) -> None:
        self.running = False


class RadioControlApp(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.cat = FT897CAT()
        self.mem_manager = MemoryManager(self.cat)
        self.status_thread = StatusThread(self.cat)
        self.status_thread.status_updated.connect(self.update_status)
        self.ptt_heartbeat = QTimer(self)
        self.ptt_heartbeat.setInterval(100)
        self.ptt_heartbeat.timeout.connect(self.cat.ptt_on)
        self.last_freq = None

        self.init_ui()

    # ------------------------------------------------------------------
    def init_ui(self) -> None:
        self.setWindowTitle("FT-897 CAT Control")
        self.resize(800, 400)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        self.port_combo = QComboBox()
        for p in list_ports.comports():
            self.port_combo.addItem(p.device)
        layout.addWidget(self.port_combo)
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.toggle_connection)
        layout.addWidget(self.connect_btn)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.freq_label = QLabel("000,00000")
        self.freq_label.setAlignment(Qt.AlignCenter)
        self.freq_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.freq_label.setFont(QFont("Courier New", 16, QFont.Bold))
        freq_tab = QWidget(); v = QVBoxLayout(freq_tab); v.addWidget(self.freq_label)
        self.tabs.addTab(freq_tab, "Frekvence")

        self.smeter_label = QLabel("S-metr: ---")
        self.smeter_label.setAlignment(Qt.AlignCenter)
        sm_tab = QWidget(); sm_l = QVBoxLayout(sm_tab); sm_l.addWidget(self.smeter_label)
        self.tabs.addTab(sm_tab, "S-metr")

        self.swr_label = QLabel("SWR: ---")
        swr_tab = QWidget(); swr_l = QVBoxLayout(swr_tab); swr_l.addWidget(self.swr_label)
        self.tabs.addTab(swr_tab, "SWR")

        self.power_label = QLabel("Výkon: ---")
        pw_tab = QWidget(); pw_l = QVBoxLayout(pw_tab); pw_l.addWidget(self.power_label)
        self.tabs.addTab(pw_tab, "Výkon")

        self.ptt_label = QLabel("Příjem")
        ptt_tab = QWidget(); pt_l = QVBoxLayout(ptt_tab); pt_l.addWidget(self.ptt_label)
        self.tabs.addTab(ptt_tab, "PTT")

        self.mode_label = QLabel("Mód: ---")
        mode_tab = QWidget(); mo_l = QVBoxLayout(mode_tab); mo_l.addWidget(self.mode_label)
        self.tabs.addTab(mode_tab, "Mód")

        self.ptt_btn = QPushButton("PTT")
        self.ptt_btn.setCheckable(True)
        self.ptt_btn.pressed.connect(self.handle_ptt_on)
        self.ptt_btn.released.connect(self.handle_ptt_off)
        self.ptt_btn.setEnabled(False)
        layout.addWidget(self.ptt_btn)

        self.init_menu()

    def init_menu(self) -> None:
        menubar = self.menuBar()
        self.memory_menu = menubar.addMenu("Paměti")
        self.rebuild_memory_menu()

    def rebuild_memory_menu(self) -> None:
        self.memory_menu.clear()
        for idx, (name, freq, mode) in enumerate(self.mem_manager.entries, 1):
            act = QAction(f"{idx:02d} {name}", self)
            act.setData((freq, mode))
            act.triggered.connect(self.tune_from_action)
            self.memory_menu.addAction(act)

    def tune_from_action(self) -> None:
        act = self.sender()
        if not act or not self.cat.is_connected:
            return
        freq, mode = act.data()
        self.cat.set_frequency(freq)
        self.cat.set_mode(mode)

    # ------------------------------------------------------------------
    def toggle_connection(self) -> None:
        if not self.cat.is_connected:
            port = self.port_combo.currentText()
            if self.cat.connect(port):
                self.mem_manager.load_from_radio()
                self.rebuild_memory_menu()
                self.status_thread.start()
                self.ptt_btn.setEnabled(True)
                self.connect_btn.setText("Disconnect")
            else:
                QMessageBox.warning(self, "Chyba", "Nelze se připojit")
        else:
            self.status_thread.stop(); self.status_thread.wait()
            self.cat.disconnect()
            self.ptt_btn.setEnabled(False)
            self.connect_btn.setText("Connect")

    def update_status(self, freq, sm, power, swr, ptt, mode) -> None:
        self.last_freq = freq
        self.freq_label.setText(f"{freq/1_000_000:.5f}".replace('.', ','))
        self.smeter_label.setText(f"S-metr: {sm}" if sm >= 0 else "S-metr: ---")
        self.power_label.setText(f"Výkon: {power}" if power >= 0 else "Výkon: ---")
        if swr == 1:
            self.swr_label.setText("SWR: High")
        elif swr == 0:
            self.swr_label.setText("SWR: Normal")
        else:
            self.swr_label.setText("SWR: ---")
        self.ptt_label.setText("Vysílání" if ptt else "Příjem")
        self.mode_label.setText(f"Mód: {mode}" if mode else "Mód: ---")

    def handle_ptt_on(self) -> None:
        if self.cat.ptt_on():
            self.ptt_heartbeat.start()

    def handle_ptt_off(self) -> None:
        self.ptt_heartbeat.stop()
        self.cat.ptt_off()


def main() -> None:
    app = QApplication(sys.argv)
    win = RadioControlApp()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
