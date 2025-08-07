#!/usr/bin/env python3
"""Simple PyQt application for controlling Yaesu FT-897 with split operations."""
import sys
import time
import threading

try:
    import serial
    from serial.tools import list_ports
except Exception:  # pragma: no cover - allow running without serial
    serial = None
    list_ports = None

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QMessageBox, QAction, QTabWidget, QFrame,
    QInputDialog
)


class FT897CAT:
    """Small subset of CAT control commands for Yaesu FT‑897."""

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
        self.serial_port = None
        self.is_connected = False
        self.current_vfo = "A"
        self.split_active = False
        self._lock = threading.Lock()

    def connect(self, port: str, baudrate: int = 9600) -> bool:
        if serial is None:
            return False
        try:
            self.serial_port = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.2,
            )
            self.is_connected = True
            return True
        except Exception:
            self.is_connected = False
            return False

    def disconnect(self):
        if self.serial_port:
            try:
                self.serial_port.close()
            except Exception:
                pass
        self.is_connected = False

    # --- low level helpers -------------------------------------------------
    def _send(self, data: bytes) -> bool:
        if not self.is_connected:
            return False
        with self._lock:
            try:
                self.serial_port.write(data)
                self.serial_port.flush()
                time.sleep(0.05)
                return True
            except Exception:
                return False

    def _read(self, length: int = 5):
        if not self.is_connected:
            return None
        with self._lock:
            try:
                return self.serial_port.read(length)
            except Exception:
                return None

    # --- CAT commands ------------------------------------------------------
    def set_frequency(self, freq_hz: int) -> bool:
        units_10hz = int(freq_hz // 10)
        digits = f"{units_10hz:08d}"
        bcd = bytearray()
        for i in range(0, 8, 2):
            bcd.append((int(digits[i]) << 4) | int(digits[i+1]))
        return self._send(bytes(bcd) + b"\x01")

    def toggle_vfo(self) -> bool:
        ok = self._send(b"\x00\x00\x00\x00\x81")
        if ok:
            self.current_vfo = "B" if self.current_vfo == "A" else "A"
        return ok

    def split_on(self) -> bool:
        ok = self._send(b"\x00\x00\x00\x00\x02")
        if ok:
            self.split_active = True
        return ok

    def split_off(self) -> bool:
        ok = self._send(b"\x00\x00\x00\x00\x82")
        if ok:
            self.split_active = False
        return ok

    def set_mode(self, mode: str) -> bool:
        code = self.MODE_MAP.get(mode)
        if code is None:
            return False
        return self._send(bytes([code, 0, 0, 0, 0x07]))

    def read_tx_status(self) -> int | None:
        """Read the transmitter status byte from the radio."""
        if not self.is_connected:
            return None
        if not self._send(b"\x00\x00\x00\x00\xf7"):
            return None
        resp = self._read(1)
        if not resp:
            return None
        return resp[0]

    def get_swr(self, tx_status: int | None = None) -> int | None:
        """Return 1 if high VSWR, 0 if normal, None if not transmitting."""
        if tx_status is None:
            tx_status = self.read_tx_status()
            if tx_status is None:
                return None
        # Bit 7 is 0 when transmitting; VSWR information only valid then.
        if tx_status & 0x80:
            return None
        return 1 if (tx_status & 0x40) else 0

    def get_power_level(self) -> int | None:
        """Return raw power meter level (0-15) from the TX status byte."""
        status = self.read_tx_status()
        if status is None:
            return None
        # Bit 7 indicates PTT: 0 = transmit, 1 = receive.
        if status & 0x80:
            return None
        return status & 0x0F

    # --- high level helpers ------------------------------------------------
    def setup_split_operation(self, rx_freq_hz: int, tx_freq_hz: int, mode: str) -> bool:
        """Configure split operation with different RX/TX frequencies."""
        if not self.is_connected:
            return False
        # turn off split
        self.split_off()
        time.sleep(0.1)
        # set RX on current VFO
        if not self.set_frequency(rx_freq_hz):
            return False
        time.sleep(0.1)
        # switch to other VFO and set TX frequency
        if not self.toggle_vfo() or not self.set_frequency(tx_freq_hz):
            return False
        time.sleep(0.1)
        # return to original VFO
        if not self.toggle_vfo():
            return False
        time.sleep(0.1)
        # set mode and enable split
        if not self.set_mode(mode) or not self.split_on():
            return False
        return True


class StatusThread(QThread):
    """Background thread updating frequency/power/S‑meter info."""
    status_updated = pyqtSignal(int, bool, str)  # frequency, split_active, vfo

    def __init__(self, cat: FT897CAT):
        super().__init__()
        self.cat = cat
        self.running = False

    def run(self):
        self.running = True
        while self.running:
            if self.cat.is_connected:
                freq = self.cat.get_frequency() if hasattr(self.cat, 'get_frequency') else None
                if freq is not None:
                    self.status_updated.emit(freq, self.cat.split_active, self.cat.current_vfo)
            self.msleep(200)

    def stop(self):
        self.running = False


class RadioControlApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cat = FT897CAT()
        self.status_thread = StatusThread(self.cat)
        self.status_thread.status_updated.connect(self.update_status)

        self.current_font_family = "Courier New"
        self.current_theme = "dark"
        self.freq_text = "000.000000"
        self.last_valid_frequency = None

        # basic frequency config for demonstration
        self.band_configs = {
            "160 m": {"range": (1_800_000, 2_000_000), "step": 1000, "mode": "LSB"},
            "80 m": {"range": (3_500_000, 3_799_000), "step": 1000, "mode": "LSB"},
            "2 m": {"range": (144_000_000, 146_000_000), "step": 1000, "mode": "FM"},
        }

        self.init_ui()
        self.apply_stylesheet(self.current_theme)

    # ------------------------------------------------------------------ UI
    def init_ui(self):
        self.setWindowTitle("FT-897 CAT Control")
        self.setGeometry(100, 100, 800, 500)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # connection bar --------------------------------------------------
        conn_layout = QHBoxLayout()
        self.port_combo = QComboBox()
        if list_ports:
            for port in list_ports.comports():
                self.port_combo.addItem(port.device)
        conn_layout.addWidget(QLabel("Port:"))
        conn_layout.addWidget(self.port_combo)
        self.connect_btn = QPushButton("Připojit")
        self.connect_btn.clicked.connect(self.toggle_connection)
        conn_layout.addWidget(self.connect_btn)
        self.split_status_label = QLabel("Split: OFF")
        conn_layout.addWidget(self.split_status_label)
        self.vfo_status_label = QLabel("VFO: A")
        conn_layout.addWidget(self.vfo_status_label)
        conn_layout.addStretch()
        layout.addLayout(conn_layout)

        # tabs ------------------------------------------------------------
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.freq_tab = QWidget()
        freq_layout = QVBoxLayout(self.freq_tab)
        self.freq_label = QLabel(self.freq_text)
        self.freq_label.setAlignment(Qt.AlignCenter)
        self.freq_label.setFont(QFont(self.current_font_family, 10, QFont.Bold))
        freq_layout.addWidget(self.freq_label)
        self.band_label = QLabel("")
        self.band_label.setAlignment(Qt.AlignCenter)
        freq_layout.addWidget(self.band_label)
        self.tabs.addTab(self.freq_tab, "Frekvence")

        # PTT -------------------------------------------------------------
        self.ptt_container = QFrame()
        ptt_layout = QVBoxLayout(self.ptt_container)
        self.ptt_btn = QPushButton("PTT")
        self.ptt_btn.setFont(QFont("Arial", 20, QFont.Bold))
        self.ptt_btn.setCheckable(True)
        self.ptt_btn.pressed.connect(self.handle_ptt_on)
        self.ptt_btn.released.connect(self.handle_ptt_off)
        self.ptt_btn.setEnabled(False)
        ptt_layout.addWidget(self.ptt_btn)
        layout.addWidget(self.ptt_container)

        # menus -----------------------------------------------------------
        self.init_menu()

    def init_menu(self):
        menubar = self.menuBar()
        band_menu = menubar.addMenu("Pásma")
        for band, cfg in self.band_configs.items():
            sub = band_menu.addMenu(band)
            start, end = cfg["range"]
            step = cfg.get("step", 1000)
            for f in range(start, end + 1, step):
                label = f"{f/1_000_000:.3f} MHz"
                act = QAction(label, self)
                act.setData((f, cfg["mode"]))
                act.triggered.connect(self.tune_from_menu)
                sub.addAction(act)

        # simple split menu
        split_menu = menubar.addMenu("Split")
        setup_split_action = QAction("Nastavit Split ručně…", self)
        setup_split_action.triggered.connect(self.setup_split_dialog)
        split_menu.addAction(setup_split_action)
        disable_split_action = QAction("Vypnout Split", self)
        disable_split_action.triggered.connect(self.disable_split)
        split_menu.addAction(disable_split_action)

    # ----------------------------------------------------------------- slots
    def toggle_connection(self):
        if self.cat.is_connected:
            self.status_thread.stop()
            self.status_thread.wait()
            self.cat.disconnect()
            self.connect_btn.setText("Připojit")
            self.ptt_btn.setEnabled(False)
        else:
            port = self.port_combo.currentText()
            if self.cat.connect(port):
                self.status_thread.start()
                self.connect_btn.setText("Odpojit")
                self.ptt_btn.setEnabled(True)
            else:
                QMessageBox.warning(self, "Chyba", "Nelze se připojit k rádiu.")

    def tune_from_menu(self):
        freq, mode = self.sender().data()
        if self.cat.set_frequency(freq):
            self.cat.set_mode(mode)

    def handle_ptt_on(self):
        if hasattr(self.cat, 'ptt_on'):
            self.cat.ptt_on()

    def handle_ptt_off(self):
        if hasattr(self.cat, 'ptt_off'):
            self.cat.ptt_off()

    def update_status(self, freq: int, split: bool, vfo: str):
        self.last_valid_frequency = freq
        self.freq_label.setText(f"{freq/1_000_000:.6f} MHz")
        self.split_status_label.setText("Split: ON" if split else "Split: OFF")
        self.vfo_status_label.setText(f"VFO: {vfo}")

    # ----------------------------------------------------------------- split
    def setup_split_dialog(self):
        if not self.cat.is_connected:
            QMessageBox.warning(self, "Chyba", "Rádio není připojeno.")
            return
        current_freq = self.last_valid_frequency or 145_500_000
        rx_freq, ok = QInputDialog.getDouble(self, "RX", "RX frekvence (MHz)", current_freq/1_000_000, 0.1, 500.0, 6)
        if not ok:
            return
        tx_freq, ok = QInputDialog.getDouble(self, "TX", "TX frekvence (MHz)", current_freq/1_000_000, 0.1, 500.0, 6)
        if not ok:
            return
        mode, ok = QInputDialog.getItem(self, "Mód", "Mod", list(FT897CAT.MODE_MAP.keys()), 0, False)
        if not ok:
            return
        if self.cat.setup_split_operation(int(rx_freq*1_000_000), int(tx_freq*1_000_000), mode):
            QMessageBox.information(self, "Split", "Split operace nastavena.")
        else:
            QMessageBox.warning(self, "Chyba", "Split se nepodařilo nastavit.")

    def disable_split(self):
        if self.cat.split_off():
            QMessageBox.information(self, "Split", "Split vypnut.")

    # ----------------------------------------------------------------- style
    def apply_stylesheet(self, theme: str):
        if theme == "dark":
            self.setStyleSheet("""
            QMainWindow {background-color: #222; color: #ddd;}
            QPushButton {background-color: #555; color: #fff;}
            QPushButton:disabled {background-color: #333;}
            """)
        else:
            self.setStyleSheet("")


# ---------------------------------------------------------------------------
def main():
    app = QApplication(sys.argv)
    win = RadioControlApp()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
