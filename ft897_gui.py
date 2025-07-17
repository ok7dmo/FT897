#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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

from serial.tools import list_ports

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton,
    QComboBox, QMessageBox, QAction, QSizePolicy, QFontDialog,
    QDialog, QRadioButton, QDialogButtonBox, QTabWidget, QFrame
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QFontMetrics





class FT897CAT:
    """Minimal CAT control for the Yaesu FT-897 using direct serial commands."""

    def __init__(self):
        self.port = None
        self.baudrate = 9600
        self.is_connected = False
        self.ptt_active = False
        self.serial_port = None
        self._lock = threading.Lock()

    def _send(self, data: bytes):
        with self._lock:
            try:
                self.serial_port.reset_input_buffer()
                self.serial_port.reset_output_buffer()
                self.serial_port.write(data)
                time.sleep(0.1)
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
                timeout=1,
            )
            self.is_connected = True
            return True
        except Exception as e:
            print(f"Chyba připojení: {e}")
            QMessageBox.warning(None, "Chyba", "Nelze se připojit.")
            self.is_connected = False
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
        """Read raw RX status byte and extract scaled S-meter value (0-255)."""
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
        raw = resp[0]
        if raw & 0x02:
            return 0
        s_raw = (raw & 0xF8) >> 3
        return s_raw * 8

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
        """Tune the radio to the specified frequency in Hz."""
        if not self.is_connected:
            return False
        units_10hz = int(freq_hz // 10)
        digits = f"{units_10hz:08d}"
        bcd = bytearray()
        for i in range(0, 8, 2):
            bcd.append((int(digits[i]) << 4) | int(digits[i + 1]))
        return self._send(bytes(bcd) + b"\x01")
class StatusThread(QThread):
    status_updated = pyqtSignal(int, int)  # frequency in Hz, smeter level

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
                if not self.cat.ptt_active:
                    sm = self.cat.get_smeter()
                if freq is not None and 100000 <= freq <= 500000000:
                    sm = sm if sm is not None else -1
                    self.status_updated.emit(freq, sm)
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

        self.current_font_family = "Courier New"
        self.freq_text = "000,00000"
        self.current_theme = "dark"
        self.last_valid_frequency = None

        self.band_presets = {
            "160 m": [1_835_000, 1_900_000],
            "80 m": [3_700_000, 3_795_000],
            "60 m": [5_357_000, 5_371_500],
            "40 m": [7_040_000, 7_190_000],
            "30 m": [10_136_000, 10_120_000],
            "20 m": [14_070_000, 14_200_000],
            "17 m": [18_100_000, 18_145_000],
            "15 m": [21_074_000, 21_250_000],
            "12 m": [24_915_000, 24_940_000],
            "10 m": [28_074_000, 28_400_000],
            "6 m": [50_313_000, 50_150_000],
            "2 m": [144_300_000, 145_500_000],
            "70 cm": [432_200_000, 433_500_000],
        }

        self.band_definitions = [
            ((87500, 108000), "FM rozhlas"),
            ((148, 283), "DLF/Morze"),
            ((108000, 137000), "Letecké pásmo"),
            ((446000, 446200), "PMR446"),
            ((1800, 2000), "160 m"),
            ((3500, 3800), "80 m"),
            ((5250, 5450), "60 m"),
            ((7000, 7200), "40 m"),
            ((10100, 10150), "30 m"),
            ((14000, 14350), "20 m"),
            ((18068, 18168), "17 m"),
            ((21000, 21450), "15 m"),
            ((24890, 24990), "12 m"),
            ((26500, 27500), "CB (11 m)"),
            ((28000, 29700), "10 m"),
            ((50000, 52000), "6 m"),
            ((70000, 70500), "4 m"),
            ((144000, 146000), "2 m"),
            ((430000, 440000), "70 cm (HAM)"),
            ((440000, 446000), "UHF obecné")
        ]

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
        self.freq_layout.addWidget(self.freq_label)

        self.band_label = QLabel("")
        self.band_label.setAlignment(Qt.AlignCenter)
        self.band_label.setStyleSheet("font-size: 18px;")
        self.freq_layout.addWidget(self.band_label)

        self.tabs.addTab(self.freq_tab, "Frekvence")

        self.smeter_tab = QWidget()
        self.smeter_layout = QVBoxLayout(self.smeter_tab)

        self.smeter_label = QLabel("S-metr: ---")
        self.smeter_label.setAlignment(Qt.AlignCenter)
        self.smeter_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.smeter_layout.addWidget(self.smeter_label)

        self.tabs.addTab(self.smeter_tab, "S-metr")

        self.swr_tab = QWidget()
        self.swr_layout = QVBoxLayout(self.swr_tab)

        self.swr_label = QLabel("SWR: ---")
        self.swr_label.setAlignment(Qt.AlignCenter)
        self.swr_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.swr_layout.addWidget(self.swr_label)

        self.tabs.addTab(self.swr_tab, "SWR")

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
        for band, freqs in self.band_presets.items():
            sub = band_menu.addMenu(band)
            for f in freqs:
                label = f"{f/1_000_000:.3f} MHz"
                act = QAction(label, self)
                act.setData(int(f))
                act.triggered.connect(self.tune_from_menu)
                sub.addAction(act)

        font_action = QAction("Nastavit písmo…", self)
        font_action.triggered.connect(self.choose_font)
        view_menu.addAction(font_action)

        color_scheme_action = QAction("Nastavit barevné schéma…", self)
        color_scheme_action.triggered.connect(self.choose_color_scheme)
        view_menu.addAction(color_scheme_action)

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
        self.adjust_all_fonts()

    def adjust_all_fonts(self):
        self.adjust_label_font(self.freq_label)
        self.adjust_label_font(self.smeter_label)
        self.adjust_label_font(self.swr_label)

    def adjust_label_font(self, label: QLabel):
        text = label.text()
        if not text:
            return
        width = label.width()
        height = label.height()
        font = QFont(self.current_font_family, 10)
        for size in range(10, 300):
            font.setPointSize(size)
            metrics = QFontMetrics(font)
            rect = metrics.boundingRect(text)
            if rect.width() > width or rect.height() > height:
                break
        font.setPointSize(size - 1)
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

    def update_status(self, freq_hz, sm_level):
        if freq_hz is None:
            return
        self.last_valid_frequency = freq_hz
        freq_mhz = freq_hz / 1_000_000.0
        formatted = f"{freq_mhz:.5f}".replace('.', ',')
        self.freq_label.setText(formatted)
        freq_khz = freq_hz / 1000.0
        self.band_label.setText(f"Pásmo: {self.get_band_label_from_khz(freq_khz)}")
        if sm_level >= 0:
            self.smeter_label.setText(f"S-metr: {self.format_smeter(sm_level)}")
        else:
            self.smeter_label.setText("S-metr: ---")
        self.adjust_all_fonts()

    def get_band_label_from_khz(self, freq_khz):
        for (start, end), label in self.band_definitions:
            if start <= freq_khz <= end:
                return label
        return f"Neznámé pásmo ({freq_khz/1000:.5f} MHz)"

    # Seznam prahových hodnot pro S-metr (bajtové hodnoty 0–255):
    #   - S0:     0 <= value < 16
    #   - S1:    16 <= value < 32
    #   - S2:    32 <= value < 48
    #   - S3:    48 <= value < 64
    #   - S4:    64 <= value < 80
    #   - S5:    80 <= value < 96
    #   - S6:    96 <= value <112
    #   - S7:   112 <= value <128
    #   - S8:   128 <= value <144
    #   - S9:   144 <= value <=255 -> pro hodnoty nad S9 přidej decibely:
    #         extra = value - 144
    #         db = (extra // 32) * 10
    #         výsledek = "S9+{db}"
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

    def tune_from_menu(self):
        action = self.sender()
        freq = action.data()
        if freq and self.cat.is_connected:
            self.cat.set_frequency(freq)

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
    main()
