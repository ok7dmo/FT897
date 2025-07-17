#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import subprocess
import time
import threading

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

    def get_power_level(self):
        """Return raw power meter level (0-15) using TX meter command."""
        if not self.is_connected:
            return None
        with self._lock:
            try:
                self.serial_port.reset_input_buffer()
                self.serial_port.reset_output_buffer()
                # 0xbd requests TX meter data: first byte contains power (high
                # nibble) and ALC (low nibble)
                self.serial_port.write(b'\x00\x00\x00\x00\xbd')
                time.sleep(0.1)
                resp = self.serial_port.read(2)
            except Exception as e:
                print(f"Chyba při čtení výkonu: {e}")
                return None

        if not resp or len(resp) < 1 or resp[0] == 0xFF:
            return None
        return (resp[0] >> 4) & 0x0F

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

    def set_mode(self, mode: str):
        if not self.is_connected:
            return False
        code = self.MODE_MAP.get(mode)
        if code is None:
            return False
        cmd = bytes([0x00, 0x00, 0x00, code, 0x07])
        return self._send(cmd)


class StatusThread(QThread):
    status_updated = pyqtSignal(int, int, int)  # frequency, smeter, power

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
                if not self.cat.ptt_active:
                    sm = self.cat.get_smeter()
                power = self.cat.get_power_level()
                if freq is not None and 100000 <= freq <= 500000000:
                    sm = sm if sm is not None else -1
                    power = power if power is not None else -1
                    self.status_updated.emit(freq, sm, power)
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
        self.font_adjust_needed = True

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
            "10 m": {"range": (28_000_000, 29_700_000), "step": 1000, "mode": "USB"},
            "6 m": {"range": (50_000_000, 54_000_000), "step": 5000, "mode": "USB"},
            "2 m": {"range": (144_000_000, 146_000_000), "step": 12500, "mode": "FM"},
            "70 cm": {"range": (430_000_000, 440_000_000), "step": 25000, "mode": "FM"},
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
            "2 m": {"min_raw": 2, "max_raw": 7},
        }

        # Optional detailed mapping of raw meter values to watts for
        # improved precision.  When provided for a band, values are
        # linearly interpolated between the nearest points.
        self.band_power_curve = {
            # These values were estimated from measurements on a test rig.
            # They ensure the 2 m readout is more accurate across the range
            # from 5 W to 50 W.
            "2 m": {
                2: 5,
                3: 12,
                4: 20,
                5: 30,
                6: 40,
                7: 50,
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
            else:
                start, end = min(cfg["list"]), max(cfg["list"])
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

    def update_status(self, freq_hz, sm_level, power_level):
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
            max_pwr = self.band_max_power.get(band, 100)
            min_pwr = self.band_min_power.get(band, 5)
            calib = self.band_power_calibration.get(band, {"min_raw": 0, "max_raw": 15})
            raw_min = calib.get("min_raw", 0)
            raw_max = calib.get("max_raw", 15)
            curve = self.band_power_curve.get(band)
            if curve:
                # Interpolate using the provided calibration curve
                points = sorted(curve.items())
                if power_level <= points[0][0]:
                    watts = points[0][1]
                elif power_level >= points[-1][0]:
                    watts = points[-1][1]
                else:
                    for i in range(1, len(points)):
                        raw_prev, w_prev = points[i - 1]
                        raw_next, w_next = points[i]
                        if raw_prev <= power_level <= raw_next:
                            ratio = (power_level - raw_prev) / (raw_next - raw_prev)
                            watts = w_prev + ratio * (w_next - w_prev)
                            break
                watts = int(round(watts))
            elif raw_max == raw_min:
                watts = min_pwr
            else:
                level = max(raw_min, min(power_level, raw_max))
                ratio = (level - raw_min) / (raw_max - raw_min)
                watts = int(round(min_pwr + ratio * (max_pwr - min_pwr)))
            self.power_label.setText(f"Výkon: {watts} W")
        else:
            self.power_label.setText("Výkon: ---")
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
    main()
