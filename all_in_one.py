#!/usr/bin/env python3
"""Single-file FT-897 control application."""

import sys
import argparse
import threading
import time

import serial
import serial.tools.list_ports

from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QFont, QFontMetrics
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton,
    QComboBox, QMessageBox, QAction, QSizePolicy, QFontDialog,
    QDialog, QRadioButton, QDialogButtonBox, QTabWidget, QFrame, QMenu,
    QDialog, QHBoxLayout, QLineEdit, QTextEdit, QFileDialog
)

# ---------------------------------------------------------------------------
# Resources (mode codes, band definitions)
# ---------------------------------------------------------------------------

MODE_CODES = {
    "LSB": 0x00,
    "USB": 0x01,
    "CW": 0x02,
    "CWR": 0x03,
    "AM": 0x04,
    "FM": 0x08,
    "DIG": 0x0A,
    "PKT": 0x0C,
    "FMN": 0x88,
}

MODE_NAMES = {v: k for k, v in MODE_CODES.items()}

band_definitions = [
    ((1800, 2000), "160 m"),
    ((3500, 3800), "80 m"),
    ((5250, 5450), "60 m"),
    ((7000, 7200), "40 m"),
    ((10100, 10150), "30 m"),
    ((14000, 14350), "20 m"),
    ((18068, 18168), "17 m"),
    ((21000, 21450), "15 m"),
    ((24890, 24990), "12 m"),
    ((28000, 29700), "10 m"),
    ((50000, 52000), "6 m"),
    ((70000, 70500), "4 m"),
    ((144000, 146000), "2 m"),
    ((430000, 440000), "70 cm"),
    ((76000, 108000), "FM rozhlas"),
    ((118000, 136975), "Letecké pásmo"),
    ((137000, 174000), "Rozšířený VHF RX"),
    ((420000, 470000), "UHF RX"),
]

band_menu_items = [
    ("160 m", 1_850_000, MODE_CODES["LSB"]),
    ("80 m", 3_700_000, MODE_CODES["LSB"]),
    ("60 m", 5_357_000, MODE_CODES["USB"]),
    ("40 m", 7_100_000, MODE_CODES["LSB"]),
    ("30 m", 10_130_000, MODE_CODES["CW"]),
    ("20 m", 14_200_000, MODE_CODES["USB"]),
    ("17 m", 18_100_000, MODE_CODES["USB"]),
    ("15 m", 21_250_000, MODE_CODES["USB"]),
    ("12 m", 24_950_000, MODE_CODES["USB"]),
    ("10 m", 28_500_000, MODE_CODES["USB"]),
    ("6 m", 50_150_000, MODE_CODES["USB"]),
    ("4 m", 70_200_000, MODE_CODES["FM"]),
    ("2 m", 145_500_000, MODE_CODES["FM"]),
    ("70 cm", 433_500_000, MODE_CODES["FM"]),
    ("FM rozhlas", 100_000_000, MODE_CODES["FM"]),
    ("Letecké pásmo", 125_000_000, MODE_CODES["AM"]),
    ("Rozšířený VHF RX", 150_000_000, MODE_CODES["FM"]),
    ("UHF RX", 440_000_000, MODE_CODES["FM"]),
]

# ---------------------------------------------------------------------------
# Meter helpers
# ---------------------------------------------------------------------------

def format_smeter(raw_s: int) -> str:
    thresholds = [16 * i for i in range(1, 10)]
    if raw_s < thresholds[0]:
        return "S0"
    for i, t in enumerate(thresholds[1:], start=1):
        if raw_s < t:
            return f"S{i}"
    extra_db = ((raw_s - thresholds[-1]) // 32) * 10
    return f"S9+{extra_db}"


def format_power(raw_p: int, band_label: str) -> str:
    if band_label in {
        "160 m", "80 m", "60 m", "40 m", "30 m",
        "20 m", "17 m", "15 m", "12 m", "10 m", "6 m",
    }:
        pmax = 100
    elif band_label == "2 m":
        pmax = 50
    elif band_label == "70 cm":
        pmax = 20
    else:
        return "---"
    watts = round(pmax * raw_p / 255)
    return f"{watts} W"

# ---------------------------------------------------------------------------
# CAT control classes
# ---------------------------------------------------------------------------

class FT897CAT:
    """Minimal CAT control helper."""

    def __init__(self, debug: bool = False):
        self.serial_port = None
        self.is_connected = False
        self._lock = threading.Lock()
        self.ptt_active = False
        self.debug = debug

    def _log(self, direction: str, data: bytes) -> None:
        if self.debug:
            hex_str = " ".join(f"{b:02X}" for b in data)
            print(f"{direction} {hex_str}")

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
        if not self.serial_port:
            return False
        try:
            with self._lock:
                self._log('>>', data)
                self.serial_port.write(data)
            self.serial_port.flush()
        except Exception as exc:
            print(f"Write error: {exc}")
            return False
        return True

    def _read(self, length: int = 5):
        if not self.serial_port:
            return None
        timeout = self.serial_port.timeout or 0.2
        end = time.time() + timeout * max(1, length)
        data = bytearray()
        while len(data) < length and time.time() < end:
            try:
                chunk = self.serial_port.read(length - len(data))
            except Exception as exc:
                print(f"Read error: {exc}")
                return None
            if chunk:
                data.extend(chunk)
            else:
                break
        if data:
            self._log('<<', bytes(data))
        return bytes(data) if data else None

    def get_frequency_and_mode(self):
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
            "160 m", "80 m", "60 m", "40 m", "30 m",
            "20 m", "17 m", "15 m", "12 m", "10 m",
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
        cmd = bytes([0x00, addr, raw, 0x00, 0x79])
        return self._send(cmd)

    def ptt_on(self) -> bool:
        ok = self._send(b"\x00\x00\x00\x00\x08")
        if ok:
            self.ptt_active = True
        return ok

    def ptt_off(self) -> bool:
        ok = self._send(b"\x00\x00\x00\x00\x88")
        if ok:
            self.ptt_active = False
        return ok

    def get_meters(self):
        cmds = b"\x00\x00\x00\x00\xE7" + b"\x00\x00\x00\x00\xF7"
        if not self._send(cmds):
            return None, None
        resp = self._read(4)
        if not resp or len(resp) < 4:
            return None, None
        return resp[1], resp[3]

# ---------------------------------------------------------------------------
# Serial worker thread
# ---------------------------------------------------------------------------

class SerialWorker(QThread):
    status = pyqtSignal(int, int, int, int)
    connected = pyqtSignal(bool)

    # request signals
    set_frequency_req = pyqtSignal(int)
    set_mode_req = pyqtSignal(int)
    set_power_req = pyqtSignal(str, int)
    ptt_on_req = pyqtSignal()
    ptt_off_req = pyqtSignal()
    toggle_vfo_req = pyqtSignal()
    split_on_req = pyqtSignal()
    split_off_req = pyqtSignal()
    clar_on_req = pyqtSignal()
    clar_off_req = pyqtSignal()
    rpt_plus_req = pyqtSignal()
    rpt_minus_req = pyqtSignal()

    def __init__(self, port: str, baudrate: int = 9600, debug: bool = False):
        super().__init__()
        self.cat = FT897CAT(debug=debug)
        self.port = port
        self.baudrate = baudrate
        self._poll_timer = None
        self._last_freq = None
        self._last_meter_time = 0.0

        self.set_frequency_req.connect(self.set_frequency)
        self.set_mode_req.connect(self.set_mode)
        self.set_power_req.connect(self.set_power)
        self.ptt_on_req.connect(self.ptt_on)
        self.ptt_off_req.connect(self.ptt_off)
        self.toggle_vfo_req.connect(self.toggle_vfo)
        self.split_on_req.connect(self.split_on)
        self.split_off_req.connect(self.split_off)
        self.clar_on_req.connect(self.clarifier_on)
        self.clar_off_req.connect(self.clarifier_off)
        self.rpt_plus_req.connect(self.repeater_plus)
        self.rpt_minus_req.connect(self.repeater_minus)

    def run(self) -> None:
        ok = self.cat.connect(self.port, baudrate=self.baudrate)
        self.connected.emit(ok)
        if not ok:
            return
        self._poll_timer = QTimer()
        self._poll_timer.setInterval(400)
        self._poll_timer.timeout.connect(self.poll)
        self._poll_timer.start()
        self.exec_()
        if self._poll_timer is not None:
            self._poll_timer.stop()
        self.cat.disconnect()

    def stop(self) -> None:
        self.quit()
        self.wait()

    @pyqtSlot(int)
    def set_frequency(self, freq_hz: int) -> None:
        self.cat.set_frequency(freq_hz)

    @pyqtSlot(int)
    def set_mode(self, mode_code: int) -> None:
        self.cat.set_mode(mode_code)

    @pyqtSlot(str, int)
    def set_power(self, band_label: str, watts: int) -> None:
        self.cat.set_power(watts, band_label)

    @pyqtSlot()
    def ptt_on(self) -> None:
        self.cat.ptt_on()

    @pyqtSlot()
    def ptt_off(self) -> None:
        self.cat.ptt_off()

    @pyqtSlot()
    def toggle_vfo(self):
        self.cat.toggle_vfo()

    @pyqtSlot()
    def split_on(self):
        self.cat.split_on()

    @pyqtSlot()
    def split_off(self):
        self.cat.split_off()

    @pyqtSlot()
    def clarifier_on(self):
        self.cat.clarifier_on()

    @pyqtSlot()
    def clarifier_off(self):
        self.cat.clarifier_off()

    @pyqtSlot()
    def repeater_plus(self):
        self.cat.repeater_plus()

    @pyqtSlot()
    def repeater_minus(self):
        self.cat.repeater_minus()

    def poll(self) -> None:
        freq, mode = self.cat.get_frequency_and_mode()
        if freq is None or mode is None:
            return
        sm = pw = 0
        now = time.time()
        if freq != self._last_freq or now - self._last_meter_time > 1.0:
            self._last_freq = freq
            self._last_meter_time = now
            sm, pw = self.cat.get_meters()
            sm = sm or 0
            pw = pw or 0
        self.status.emit(freq, mode, sm, pw)

# ---------------------------------------------------------------------------
# Logging dialog
# ---------------------------------------------------------------------------

class LogWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Logování")
        self._file = None

        layout = QVBoxLayout(self)

        file_layout = QHBoxLayout()
        file_layout.addWidget(QLabel("Soubor:"))
        self.path_edit = QLineEdit()
        file_layout.addWidget(self.path_edit)
        browse = QPushButton("Vybrat…")
        browse.clicked.connect(self.choose_file)
        file_layout.addWidget(browse)
        layout.addLayout(file_layout)

        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.start_btn.clicked.connect(self.start_logging)
        btn_layout.addWidget(self.start_btn)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_logging)
        btn_layout.addWidget(self.stop_btn)
        layout.addLayout(btn_layout)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view)

    def choose_file(self):
        path, _ = QFileDialog.getSaveFileName(self, "Vyberte soubor logu", "log.txt", "Text files (*.txt);;All files (*)")
        if path:
            self.path_edit.setText(path)

    def start_logging(self):
        if self._file:
            return
        path = self.path_edit.text()
        if not path:
            QMessageBox.warning(self, "Chyba", "Nejprve vyberte soubor")
            return
        try:
            self._file = open(path, "a", encoding="utf-8")
        except Exception as exc:
            QMessageBox.warning(self, "Chyba", f"Nelze otevřít soubor:\n{exc}")
            self._file = None
            return
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.log_view.append(f"== Logging started {time.ctime()} ==")
        self._file.write(f"# start {time.ctime()}\n")
        self._file.flush()

    def stop_logging(self):
        if not self._file:
            return
        self.log_view.append(f"== Logging stopped {time.ctime()} ==")
        try:
            self._file.write(f"# stop {time.ctime()}\n")
            self._file.close()
        except Exception:
            pass
        self._file = None
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def is_logging(self):
        return self._file is not None

    def log(self, message: str):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        line = f"{timestamp} {message}"
        self.log_view.append(line)
        if self._file:
            try:
                self._file.write(line + "\n")
                self._file.flush()
            except Exception:
                pass

    def closeEvent(self, event):
        self.stop_logging()
        event.accept()

# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------

class RadioControlApp(QMainWindow):
    def __init__(self, debug: bool = False, port: str = None, baudrate: int = 9600):
        super().__init__()
        self.debug = debug
        self.worker = None
        self._cmd_port = port
        self._cmd_baud = baudrate

        self.ptt_heartbeat = QTimer(self)
        self.ptt_heartbeat.setInterval(300)
        self.ptt_heartbeat.timeout.connect(self.send_ptt_on)

        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.adjust_all_fonts)

        self.log_window = LogWindow(self)

        self.current_font_family = "Courier New"
        self.freq_text = "000,00000"
        self.current_theme = "dark"
        self.last_valid_frequency = None
        self.last_mode = None
        self._last_s = None
        self._last_p = None
        self._last_power_band = None

        self.band_definitions = band_definitions
        self.band_menu_items = band_menu_items

        self.band_range_map = {label: rng for rng, label in self.band_definitions}
        self.band_mode_map = {label: mode for label, _f, mode in self.band_menu_items}

        self.init_ui()
        self.apply_stylesheet(self.current_theme)

    # UI setup -------------------------------------------------------------
    def init_ui(self):
        self.setWindowTitle("Ovládání rádia")
        self.setGeometry(100, 100, 800, 400)

        self.central = QWidget()
        self.setCentralWidget(self.central)
        self.layout = QVBoxLayout(self.central)

        self.port_combo = QComboBox()
        for port in serial.tools.list_ports.comports():
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
        self.freq_layout.addWidget(self.freq_label)

        self.band_label = QLabel("")
        self.band_label.setAlignment(Qt.AlignCenter)
        self.band_label.setStyleSheet("font-size: 18px;")
        self.freq_layout.addWidget(self.band_label)

        self.mode_label = QLabel("Mód: ---")
        self.mode_label.setAlignment(Qt.AlignCenter)
        self.mode_label.setStyleSheet("font-size: 18px;")
        self.mode_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.freq_layout.addWidget(self.mode_label)

        self.tabs.addTab(self.freq_tab, "Frekvence")

        self.smeter_tab = QWidget()
        self.smeter_layout = QVBoxLayout(self.smeter_tab)

        self.smeter_label = QLabel("S-metr: ---")
        self.smeter_label.setAlignment(Qt.AlignCenter)
        self.smeter_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.smeter_layout.addWidget(self.smeter_label)

        self.tabs.addTab(self.smeter_tab, "S-metr")

        self.power_tab = QWidget()
        self.power_layout = QVBoxLayout(self.power_tab)

        self.power_label = QLabel("Výkon: ---")
        self.power_label.setAlignment(Qt.AlignCenter)
        self.power_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
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
            QMenuBar { background-color: #333; color: white; font-weight: bold; font-size: 16px; }
            QMenuBar::item { background: transparent; padding: 6px 20px; }
            QMenuBar::item:selected { background: #555; color: yellow; }
            QMenu { background-color: #222; color: white; font-size: 15px; }
            QMenu::item { padding: 6px 24px; }
            QMenu::item:selected { background-color: #444; color: yellow; }
        """
        )
        view_menu = menubar.addMenu("Zobrazení")

        font_action = QAction("Nastavit písmo…", self)
        font_action.triggered.connect(self.choose_font)
        view_menu.addAction(font_action)

        color_scheme_action = QAction("Nastavit barevné schéma…", self)
        color_scheme_action.triggered.connect(self.choose_color_scheme)
        view_menu.addAction(color_scheme_action)

        band_menu = menubar.addMenu("Pásmo")
        self.power_menu = menubar.addMenu("Výkon")
        for label, _freq, mode in self.band_menu_items:
            if label == "2 m":
                two_m = QMenu("2 m", self)
                sub144 = QMenu("144 MHz", self)
                for khz in range(144000, 145000):
                    act = QAction(f"{khz} kHz", self)
                    act.triggered.connect(lambda _=False, f=khz * 1000, m=0x01: self.goto_band(f, m))
                    sub144.addAction(act)
                sub145 = QMenu("145 MHz", self)
                for khz in range(145000, 146001):
                    act = QAction(f"{khz} kHz", self)
                    act.triggered.connect(lambda _=False, f=khz * 1000, m=0x08: self.goto_band(f, m))
                    sub145.addAction(act)
                two_m.addMenu(sub144)
                two_m.addMenu(sub145)
                band_menu.addMenu(two_m)
                continue
            if label == "6 m":
                menu6 = QMenu("6 m", self)
                sub_usb = QMenu("50-52 MHz", self)
                for khz in range(50000, 52000):
                    act = QAction(f"{khz} kHz", self)
                    act.triggered.connect(lambda _=False, f=khz * 1000, m=MODE_CODES["USB"]: self.goto_band(f, m))
                    sub_usb.addAction(act)
                sub_fm = QMenu("52-54 MHz", self)
                for khz in range(52000, 54001):
                    act = QAction(f"{khz} kHz", self)
                    act.triggered.connect(lambda _=False, f=khz * 1000, m=MODE_CODES["FM"]: self.goto_band(f, m))
                    sub_fm.addAction(act)
                menu6.addMenu(sub_usb)
                menu6.addMenu(sub_fm)
                band_menu.addMenu(menu6)
                continue
            if label == "70 cm":
                menu70 = QMenu("70 cm", self)
                sub_usb = QMenu("432-434 MHz", self)
                for khz in range(432000, 434000):
                    act = QAction(f"{khz} kHz", self)
                    act.triggered.connect(lambda _=False, f=khz * 1000, m=MODE_CODES["USB"]: self.goto_band(f, m))
                    sub_usb.addAction(act)
                sub_fm = QMenu("434-440 MHz", self)
                for khz in range(434000, 440001):
                    act = QAction(f"{khz} kHz", self)
                    act.triggered.connect(lambda _=False, f=khz * 1000, m=MODE_CODES["FM"]: self.goto_band(f, m))
                    sub_fm.addAction(act)
                menu70.addMenu(sub_usb)
                menu70.addMenu(sub_fm)
                band_menu.addMenu(menu70)
                continue
            if label == "10 m":
                menu10 = QMenu("10 m", self)
                rng = self.band_range_map.get(label)
                if rng:
                    start_khz, end_khz = rng
                    for khz in range(start_khz, end_khz + 1, 3):
                        mcode = MODE_CODES["USB"] if khz < 29000 else MODE_CODES["FM"]
                        act = QAction(f"{khz} kHz", self)
                        act.triggered.connect(lambda _=False, f=khz * 1000, m=mcode: self.goto_band(f, m))
                        menu10.addAction(act)
                band_menu.addMenu(menu10)
                continue
            if label == "FM rozhlas":
                menu_fm = QMenu("FM rozhlas", self)
                rng = self.band_range_map.get(label)
                if rng:
                    start_khz, end_khz = rng
                    for khz in range(start_khz, end_khz + 1, 200):
                        act = QAction(f"{khz} kHz", self)
                        act.triggered.connect(lambda _=False, f=khz * 1000, m=MODE_CODES["FM"]: self.goto_band(f, m))
                        menu_fm.addAction(act)
                band_menu.addMenu(menu_fm)
                continue
            if label == "Letecké pásmo":
                menu_air = QMenu("Letecké pásmo", self)
                rng = self.band_range_map.get(label)
                if rng:
                    start_khz, end_khz = rng
                    for khz in range(start_khz, end_khz + 1, 25):
                        act = QAction(f"{khz} kHz", self)
                        act.triggered.connect(lambda _=False, f=khz * 1000, m=MODE_CODES["AM"]: self.goto_band(f, m))
                        menu_air.addAction(act)
                band_menu.addMenu(menu_air)
                continue
            if label in {"Rozšířený VHF RX", "UHF RX"}:
                sub = QMenu(label, self)
                rng = self.band_range_map.get(label)
                if rng:
                    start_khz, end_khz = rng
                    for khz in range(start_khz, end_khz + 1):
                        act = QAction(f"{khz} kHz", self)
                        act.triggered.connect(lambda _=False, f=khz * 1000, m=MODE_CODES["FM"]: self.goto_band(f, m))
                        sub.addAction(act)
                band_menu.addMenu(sub)
                continue
            sub = QMenu(label, self)
            rng = self.band_range_map.get(label)
            if rng:
                start_khz, end_khz = rng
                step = 3 if label in {"160 m", "80 m", "60 m", "40 m", "30 m", "20 m", "17 m", "15 m", "12 m"} else 1
                for khz in range(start_khz, end_khz + 1, step):
                    act = QAction(f"{khz} kHz", self)
                    act.triggered.connect(lambda _=False, f=khz * 1000, m=mode: self.goto_band(f, m))
                    sub.addAction(act)
            band_menu.addMenu(sub)

        cmd_menu = menubar.addMenu("Příkazy")
        vfo_act = QAction("Přepnout VFO A/B", self)
        vfo_act.triggered.connect(lambda: self.worker and self.worker.toggle_vfo_req.emit())
        cmd_menu.addAction(vfo_act)

        split_on_act = QAction("Split ON", self)
        split_on_act.triggered.connect(lambda: self.worker and self.worker.split_on_req.emit())
        cmd_menu.addAction(split_on_act)

        split_off_act = QAction("Split OFF", self)
        split_off_act.triggered.connect(lambda: self.worker and self.worker.split_off_req.emit())
        cmd_menu.addAction(split_off_act)

        clar_on_act = QAction("Clarifier ON", self)
        clar_on_act.triggered.connect(lambda: self.worker and self.worker.clar_on_req.emit())
        cmd_menu.addAction(clar_on_act)

        clar_off_act = QAction("Clarifier OFF", self)
        clar_off_act.triggered.connect(lambda: self.worker and self.worker.clar_off_req.emit())
        cmd_menu.addAction(clar_off_act)

        rpt_plus_act = QAction("Repeater +", self)
        rpt_plus_act.triggered.connect(lambda: self.worker and self.worker.rpt_plus_req.emit())
        cmd_menu.addAction(rpt_plus_act)

        rpt_minus_act = QAction("Repeater -", self)
        rpt_minus_act.triggered.connect(lambda: self.worker and self.worker.rpt_minus_req.emit())
        cmd_menu.addAction(rpt_minus_act)

        log_menu = menubar.addMenu("Log")
        log_action = QAction("Logovací okno", self)
        log_action.triggered.connect(self.log_window.show)
        log_menu.addAction(log_action)

    # dialogs ---------------------------------------------------------------
    def choose_font(self):
        font, ok = QFontDialog.getFont(QFont(self.current_font_family, 10), self)
        if ok:
            self.current_font_family = font.family()
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

    def apply_stylesheet(self, theme: str):
        self.current_theme = theme
        base_style = (
            "QWidget { font-family: 'Segoe UI'; }"
            " QPushButton { padding: 6px; border-radius: 3px; }"
            " QPushButton:checked { font-weight: bold; }"
        )
        if theme == "dark":
            extra = "QWidget { background-color: #1e1e1e; color: white; }"
        elif theme == "light":
            extra = "QWidget { background-color: #ffffff; color: black; }"
        else:
            extra = "QWidget { background-color: #000; color: yellow; }"
        self.setStyleSheet(base_style + extra)

    # font autosize ---------------------------------------------------------
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resize_timer.start(100)

    def adjust_all_fonts(self):
        for lbl in [self.freq_label, self.band_label, self.mode_label, self.smeter_label, self.power_label]:
            self.adjust_label_font(lbl)

    def adjust_label_font(self, label: QLabel):
        text = label.text()
        if not text:
            return
        width, height = label.width(), label.height()
        font = QFont(self.current_font_family, 10)
        low, high, best = 10, 300, 10
        while low <= high:
            mid = (low + high) // 2
            font.setPointSize(mid)
            metrics = QFontMetrics(font)
            rect = metrics.boundingRect(text)
            if rect.width() <= width and rect.height() <= height:
                best = mid
                low = mid + 1
            else:
                high = mid - 1
        font.setPointSize(best)
        label.setFont(font)

    # connection / updates --------------------------------------------------
    def toggle_connection(self):
        if not self.worker:
            port = self._cmd_port or self.port_combo.currentText()
            baud = self._cmd_baud
            self.worker = SerialWorker(port, baud, debug=self.debug)
            self.worker.status.connect(self.update_status)
            self.worker.connected.connect(self.on_worker_connected)
            self.worker.start()
        else:
            self.ptt_heartbeat.stop()
            self.worker.stop()
            self.worker = None
            self.ptt_btn.setEnabled(False)
            self.connect_btn.setText("Připojit")

    def on_worker_connected(self, ok: bool):
        if ok:
            self.ptt_btn.setEnabled(True)
            self.connect_btn.setText("Odpojit")
        else:
            QMessageBox.warning(self, "Chyba", "Nelze se připojit.")
            if self.worker is not None:
                self.worker.wait()
            self.worker = None

    @pyqtSlot(int, int, int, int)
    def update_status(self, freq_hz: int, mode: int, raw_s: int, raw_p: int):
        freq_changed = freq_hz != self.last_valid_frequency
        self.last_valid_frequency = freq_hz
        self.last_mode = mode
        freq_mhz = freq_hz / 1_000_000.0
        formatted = f"{freq_mhz:.5f}".replace('.', ',')
        if formatted != self.freq_label.text():
            self.freq_label.setText(formatted)
        freq_khz = freq_hz / 1000.0
        band_label = self.get_band_label_from_khz(freq_khz)
        band_str = f"Pásmo: {band_label}"
        if band_str != self.band_label.text():
            self.band_label.setText(band_str)
        mode_name = MODE_NAMES.get(mode, f"0x{mode:02X}")
        mode_str = f"Mód: {mode_name}"
        if mode_str != self.mode_label.text():
            self.mode_label.setText(mode_str)
        self.update_power_menu(band_label)
        if raw_s != self._last_s:
            self._last_s = raw_s
            self.smeter_label.setText(f"S-metr: {format_smeter(raw_s)}")
        if raw_p != self._last_p:
            self._last_p = raw_p
            self.power_label.setText(f"Výkon: {format_power(raw_p, band_label)}")
        if self.log_window.is_logging():
            self.log_window.log(f"{freq_hz}Hz {band_label} S={raw_s} P={raw_p}")

    def get_band_label_from_khz(self, freq_khz: float) -> str:
        for (start, end), label in self.band_definitions:
            if start <= freq_khz <= end:
                return label
        return f"Neznámé pásmo ({freq_khz/1000:.5f} MHz)"

    def handle_ptt_on(self):
        if not self.worker:
            return
        self.worker.ptt_on_req.emit()
        self.ptt_heartbeat.start()
        self.ptt_container.setStyleSheet("background-color: #600;")

    def send_ptt_on(self):
        if self.worker:
            self.worker.ptt_on_req.emit()

    def handle_ptt_off(self):
        if not self.worker:
            return
        self.ptt_heartbeat.stop()
        self.worker.ptt_off_req.emit()
        self.ptt_container.setStyleSheet("")

    def goto_band(self, freq_hz: int, mode_code: int):
        if not self.worker:
            return
        self.worker.set_frequency_req.emit(freq_hz)
        self.worker.set_mode_req.emit(mode_code)

    def closeEvent(self, event):
        if self.worker:
            self.worker.stop()
        event.accept()

    # power menu ------------------------------------------------------------
    def update_power_menu(self, band_label: str):
        if not hasattr(self, "power_menu"):
            return
        if band_label == self._last_power_band:
            return
        self._last_power_band = band_label
        self.power_menu.clear()
        band_map = {**{b: 100 for b in ["160 m", "80 m", "60 m", "40 m", "30 m", "20 m", "17 m", "15 m", "12 m", "10 m", "6 m"]}, "2 m": 50, "70 cm": 20}
        pmax = band_map.get(band_label, 0)
        for w in range(5, pmax + 1, 5):
            act = QAction(f"{w} W", self)
            act.triggered.connect(lambda _=False, watt=w, band=band_label: self.set_power_level(band, watt))
            self.power_menu.addAction(act)

    def set_power_level(self, band_label: str, watts: int) -> None:
        if self.worker:
            self.worker.set_power_req.emit(band_label, watts)
            self.power_label.setText(f"Výkon: {watts} W")
            if self.log_window.is_logging():
                self.log_window.log(f"SET POWER {band_label} {watts}W")

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="FT-897 control GUI (single file)")
    parser.add_argument("--debug", action="store_true", help="log CAT bytes")
    parser.add_argument("--port", help="serial port, e.g. /dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=9600, help="baud rate")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    window = RadioControlApp(debug=args.debug, port=args.port, baudrate=args.baud)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
