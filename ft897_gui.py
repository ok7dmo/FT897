#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Simple PyQt5 CAT control for the Yaesu FT-897."""

import sys
import subprocess
import time
import threading

# Ensure required packages
required = ["pyserial", "PyQt5"]
for module in required:
    try:
        if module == "pyserial":
            import serial
        elif module == "PyQt5":
            from PyQt5.QtWidgets import QApplication
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", module])

import serial
import serial.tools.list_ports

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel,
    QPushButton, QComboBox, QMessageBox, QAction, QSizePolicy, QFontDialog,
    QDialog, QRadioButton, QDialogButtonBox, QTabWidget, QFrame
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QFontMetrics


class FT897CAT:
    """Minimal CAT control for the Yaesu FT-897."""

    def __init__(self):
        self.serial_port = None
        self.is_connected = False
        self._lock = threading.Lock()

    def connect(self, port, baudrate=9600):
        try:
            self.serial_port = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1
            )
            self.is_connected = True
            return True
        except Exception as e:
            print(f"Chyba připojení: {e}")
            return False

    def disconnect(self):
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        self.is_connected = False

    def _send(self, data: bytes):
        with self._lock:
            try:
                self.serial_port.reset_input_buffer()
                self.serial_port.reset_output_buffer()
            except Exception:
                pass
            try:
                self.serial_port.write(data)
                time.sleep(0.1)
                return True
            except Exception as e:
                print(f"Chyba při zápisu do sériového portu: {e}")
                return False

    def _read(self, length=5):
        with self._lock:
            try:
                return self.serial_port.read(length)
            except Exception as e:
                print(f"Chyba při čtení ze sériového portu: {e}")
                return None

    def get_frequency_and_mode(self):
        """Return tuple of (frequency in Hz, mode byte)."""
        if not self._send(b'\x00\x00\x00\x00\x03'):
            return None, None
        resp = self._read(5)
        if not resp or len(resp) != 5:
            return None, None
        units_10hz = 0
        for b in resp[:4]:
            units_10hz = units_10hz * 100 + ((b >> 4) & 0x0F) * 10 + (b & 0x0F)
        return units_10hz * 10, resp[4]

    def get_frequency(self):
        freq, _mode = self.get_frequency_and_mode()
        return freq

    def set_frequency(self, freq_hz):
        """Set the VFO frequency in Hz."""
        units = freq_hz // 10
        digits = []
        for _ in range(8):
            digits.insert(0, units % 10)
            units //= 10
        bcd = bytes(((digits[i] << 4) | digits[i + 1]) for i in range(0, 8, 2))
        return self._send(bcd + b'\x01')

    def set_mode(self, mode_code):
        """Set operating mode using the given mode code."""
        cmd = bytes([0x00, 0x00, 0x00, mode_code, 0x07])
        return self._send(cmd)

    def set_power(self, percent):
        """Set the transmitter power level (0-100%)."""
        if percent < 0:
            percent = 0
        if percent > 100:
            percent = 100
        cmd = f"I-009B-{percent:02X}-00-00-01".encode()
        return self._send(cmd)

    def toggle_vfo(self):
        return self._send(b'\x00\x00\x00\x00\x81')

    def split_on(self):
        return self._send(b'\x00\x00\x00\x00\x02')

    def split_off(self):
        return self._send(b'\x00\x00\x00\x00\x82')

    def clarifier_on(self):
        return self._send(b'\x00\x00\x00\x00\x05')

    def clarifier_off(self):
        return self._send(b'\x00\x00\x00\x00\x85')

    def repeater_plus(self):
        return self._send(b'\x49\x09')

    def repeater_minus(self):
        return self._send(b'\x89\x09')

    def get_smeter(self):
        """Return S-meter level as 0-255 or None on failure."""
        if not self._send(b'\x00\x00\x00\x00\xe7'):
            return None
        resp = self._read(1)
        if not resp:
            return None
        return resp[0]

    def ptt_on(self):
        return self._send(b'\x00\x00\x00\x00\x08')

    def ptt_off(self):
        return self._send(b'\x00\x00\x00\x00\x88')


class StatusThread(QThread):
    status_updated = pyqtSignal(int, int, int)  # frequency Hz, S-meter, mode

    def __init__(self, cat: FT897CAT):
        super().__init__()
        self.cat = cat
        self.running = False

    def run(self):
        self.running = True
        while self.running:
            if self.cat.is_connected:
                freq, mode = self.cat.get_frequency_and_mode()
                sm = self.cat.get_smeter()
                if freq is not None and 100000 <= freq <= 500000000:
                    sm = sm if sm is not None else -1
                    mode = mode if mode is not None else -1
                    self.status_updated.emit(freq, sm, mode)
            self.msleep(300)

    def stop(self):
        self.running = False


class RadioControlApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cat = FT897CAT()
        self.status_thread = StatusThread(self.cat)
        self.status_thread.status_updated.connect(self.update_status)

        self.ptt_heartbeat = QTimer(self)
        self.ptt_heartbeat.setInterval(100)
        self.ptt_heartbeat.timeout.connect(self.cat.ptt_on)


        self.band_order = []
        self.current_band_index = None

        self.current_font_family = "Courier New"
        self.freq_text = "000,00000"
        self.current_theme = "dark"
        self.last_valid_frequency = None
        self.last_mode = None
        self.last_smeter = None
        self.cached_freq_font = None
        self.cached_smeter_font = None

        self.band_definitions = [
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
            ((430000, 440000), "70 cm")
        ]
        # Preset frequencies for quick tuning. Each tuple contains
        # (label, frequency in Hz, mode code).
        freqs_80m = [
            (f"{freq/1000:.3f} MHz", freq * 1000, 0x03)
            for freq in range(3500, 3801)
        ]
        freqs_40m = [
            (f"{freq/1000:.3f} MHz", freq * 1000, 0x03)
            for freq in range(7000, 7201)
        ]
        freqs_20m = [
            (f"{freq/1000:.3f} MHz", freq * 1000, 0x01)
            for freq in range(14000, 14351)
        ]
        self.band_presets = {
            "80 m": freqs_80m,
            "40 m": freqs_40m,
            "20 m": freqs_20m,
            "15 m": [("21.200 MHz", 21200000, 0x01)],
            "10 m": [("28.400 MHz", 28400000, 0x01)],
            "6 m": [("50.150 MHz", 50150000, 0x01)],
            "2 m": [("145.500 MHz", 145500000, 0x08)],
            "70 cm": [("433.500 MHz", 433500000, 0x08)],
        }
        for key in self.band_presets:
            self.band_presets[key] = sorted(self.band_presets[key], key=lambda t: t[1])
        self.band_order = list(self.band_presets.keys())
        self.init_ui()
        self.apply_stylesheet(self.current_theme)

        # adjust fonts after the window is created and then fix the initial size
        QTimer.singleShot(0, self._initial_setup)

    def _initial_setup(self):
        self.adjust_all_fonts(fix_min=True)
        self.adjustSize()
        self.setMinimumSize(self.size())
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            frame = self.frameGeometry()
            frame.moveCenter(geo.center())
            self.move(frame.topLeft())

    def init_ui(self):
        self.setWindowTitle("FT-897 CAT Control")
        self.setGeometry(100, 100, 800, 400)

        self.central = QWidget()
        self.setCentralWidget(self.central)
        self.layout = QVBoxLayout(self.central)

        self.port_combo = QComboBox()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.port_combo.addItem(port.device)
        self.layout.addWidget(self.port_combo)

        self.connect_btn = QPushButton("Připojit")
        self.connect_btn.clicked.connect(self.toggle_connection)
        self.layout.addWidget(self.connect_btn)

        # Removed band navigation buttons (pásmo nahoru/dolů/domů)



        self.tabs = QTabWidget()
        # enlarge tab font and height (100% bigger)
        self.tabs.setStyleSheet(
            "QTabBar::tab { font-size: 24px; height: 48px; padding: 8px; }")
        self.layout.addWidget(self.tabs)

        self.freq_tab = QWidget()
        self.freq_layout = QVBoxLayout(self.freq_tab)

        self.freq_label = QLabel(self.freq_text)
        self.freq_label.setAlignment(Qt.AlignCenter)
        self.freq_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.freq_layout.addWidget(self.freq_label)

        self.band_label = QLabel("")
        self.band_label.setAlignment(Qt.AlignCenter)
        # enlarge band label for better readability (100% bigger)
        self.band_label.setStyleSheet("font-size: 44px; font-weight: bold;")
        self.freq_layout.addWidget(self.band_label)

        self.tabs.addTab(self.freq_tab, "Frekvence")

        self.smeter_tab = QWidget()
        self.smeter_layout = QVBoxLayout(self.smeter_tab)

        self.smeter_label = QLabel("S-metr: ---")
        self.smeter_label.setAlignment(Qt.AlignCenter)
        self.smeter_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.smeter_layout.addWidget(self.smeter_label)

        self.tabs.addTab(self.smeter_tab, "S-metr")


        self.ptt_container = QFrame()
        self.ptt_layout = QVBoxLayout(self.ptt_container)
        self.ptt_btn = QPushButton("PTT")
        # make PTT button more visible (100% larger)
        self.ptt_btn.setFont(QFont("Arial", 40, QFont.Bold))
        self.ptt_btn.setCheckable(True)
        self.ptt_btn.pressed.connect(self.handle_ptt_on)
        self.ptt_btn.released.connect(self.handle_ptt_off)
        self.ptt_btn.setEnabled(False)
        self.ptt_layout.addWidget(self.ptt_btn)
        self.layout.addWidget(self.ptt_container)

        self.init_menu()
        # fonts will be adjusted later in _initial_setup

    def init_menu(self):
        menubar = self.menuBar()
        menubar.setStyleSheet(
            """
            QMenuBar {
                background-color: #333;
                color: white;
                font-weight: bold;
                font-size: 32px;
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
                font-size: 31px;
                font-weight: bold;
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

        font_action = QAction("Nastavit písmo…", self)
        font_action.triggered.connect(self.choose_font)
        view_menu.addAction(font_action)

        color_scheme_action = QAction("Nastavit barevné schéma…", self)
        color_scheme_action.triggered.connect(self.choose_color_scheme)
        view_menu.addAction(color_scheme_action)

        band_menu = menubar.addMenu("Pásmo")
        band_menu.setToolTip("Každá podnabídka obsahuje všechny dostupné frekvence pro dané pásmo")
        for b_label, items in self.band_presets.items():
            sub = band_menu.addMenu(b_label)
            for name, freq, mode in items:
                act = QAction(name, self)
                act.triggered.connect(lambda _=False, f=freq, m=mode: self.goto_band(f, m))
                sub.addAction(act)
        cmd_menu = menubar.addMenu("Příkazy")
        vfo_act = QAction("Přepnout VFO A/B", self)
        vfo_act.triggered.connect(self.cat.toggle_vfo)
        cmd_menu.addAction(vfo_act)

        split_on_act = QAction("Split ON", self)
        split_on_act.triggered.connect(self.cat.split_on)
        cmd_menu.addAction(split_on_act)

        split_off_act = QAction("Split OFF", self)
        split_off_act.triggered.connect(self.cat.split_off)
        cmd_menu.addAction(split_off_act)

        clar_on_act = QAction("Clarifier ON", self)
        clar_on_act.triggered.connect(self.cat.clarifier_on)
        cmd_menu.addAction(clar_on_act)

        clar_off_act = QAction("Clarifier OFF", self)
        clar_off_act.triggered.connect(self.cat.clarifier_off)
        cmd_menu.addAction(clar_off_act)

        rpt_plus_act = QAction("Repeater +", self)
        rpt_plus_act.triggered.connect(self.cat.repeater_plus)
        cmd_menu.addAction(rpt_plus_act)

        rpt_minus_act = QAction("Repeater -", self)
        rpt_minus_act.triggered.connect(self.cat.repeater_minus)
        cmd_menu.addAction(rpt_minus_act)

    def choose_font(self):
        font, ok = QFontDialog.getFont(QFont(self.current_font_family, 10), self)
        if ok:
            self.current_font_family = font.family()
            self.adjust_all_fonts(fix_min=True)
            self.adjustSize()
            self.setMinimumSize(self.size())

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

    def apply_stylesheet(self, theme):
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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Recompute fonts when the window is resized but keep label geometry
        self.adjust_all_fonts()

    def adjust_all_fonts(self, fix_min=False):
        """Adjust fonts to fit current label sizes.

        When *fix_min* is True, also update the minimum sizes of the labels
        based on a worst case string so the layout remains stable.
        """
        sample_freq = "999,99999"
        sample_sm = "S-metr: S9+60"

        def best_size(label, text):
            width = label.width()
            height = label.height()
            if width <= 0 or height <= 0:
                return 10
            low, high = 1, 300
            best = low
            font = QFont(self.current_font_family)
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
            return best

        freq_size = best_size(self.freq_label, sample_freq)
        sm_size = best_size(self.smeter_label, sample_sm)

        freq_font = QFont(self.current_font_family, freq_size, QFont.Bold)
        sm_font = QFont(self.current_font_family, sm_size, QFont.Bold)

        self.cached_freq_font = freq_font
        self.cached_smeter_font = sm_font

        self.freq_label.setFont(freq_font)
        self.smeter_label.setFont(sm_font)

        if fix_min:
            freq_metrics = QFontMetrics(freq_font)
            sm_metrics = QFontMetrics(sm_font)
            freq_rect = freq_metrics.boundingRect(sample_freq)
            sm_rect = sm_metrics.boundingRect(sample_sm)
            margin = 20
            min_w = max(freq_rect.width(), sm_rect.width()) + margin
            self.freq_label.setMinimumWidth(min_w)
            self.smeter_label.setMinimumWidth(min_w)
            self.freq_label.setMinimumHeight(freq_rect.height() + margin)
            self.smeter_label.setMinimumHeight(sm_rect.height() + margin)
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

    def update_status(self, freq_hz, sm_level, mode):
        if freq_hz is None:
            return
        self.last_valid_frequency = freq_hz
        self.last_mode = mode
        freq_mhz = freq_hz / 1_000_000.0
        formatted = f"{freq_mhz:.5f}".replace('.', ',')
        self.freq_label.setText(formatted)
        freq_khz = freq_hz / 1000.0
        band = self.get_band_label_from_khz(freq_khz)
        self.band_label.setText(f"Pásmo: {band}")
        if band in self.band_presets:
            self.current_band_index = self.band_order.index(band)
        if sm_level >= 0:
            self.last_smeter = sm_level
        if self.last_smeter is not None:
            self.smeter_label.setText(f"S-metr: {self.format_smeter(self.last_smeter)}")
        else:
            self.smeter_label.setText("S-metr: ---")
        if self.cached_freq_font:
            self.freq_label.setFont(self.cached_freq_font)
        if self.cached_smeter_font:
            self.smeter_label.setFont(self.cached_smeter_font)
    def get_band_label_from_khz(self, freq_khz):
        for (start, end), label in self.band_definitions:
            if start <= freq_khz <= end:
                return label
        return f"Neznámé pásmo ({freq_khz/1000:.5f} MHz)"

    def format_smeter(self, value):
        """Return human friendly S meter value from 0-255."""
        thresholds = [16 * i for i in range(1, 10)]
        if value < thresholds[0]:
            return "S0"
        for i, t in enumerate(thresholds[1:], start=1):
            if value < t:
                return f"S{i}"
        extra = value - thresholds[-1]
        db = (extra // 32) * 10
        return f"S9+{db}"

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



    def goto_band(self, freq_hz, mode_code):
        if not self.cat.is_connected:
            return
        self.cat.set_frequency(freq_hz)
        self.cat.set_mode(mode_code)
        # update current band index based on requested frequency
        freq_khz = freq_hz / 1000
        band = self.get_band_label_from_khz(freq_khz)
        if band in self.band_presets:
            self.current_band_index = self.band_order.index(band)

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
    main()
