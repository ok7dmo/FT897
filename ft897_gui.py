#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import subprocess

# Ensure required packages
required = ["pyserial", "PyQt5", "python-hamlib"]
for module in required:
    try:
        if module == "pyserial":
            import serial
        elif module == "PyQt5":
            from PyQt5.QtWidgets import QApplication
        elif module == "python-hamlib":
            import hamlib
    except ImportError:
        if module == "python-hamlib":
            subprocess.check_call([sys.executable, "-m", "pip", "install", "python-hamlib"])
        else:
            subprocess.check_call([sys.executable, "-m", "pip", "install", module])

import serial
import serial.tools.list_ports
import hamlib

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton,
    QComboBox, QMessageBox, QAction, QSizePolicy, QFontDialog,
    QDialog, QRadioButton, QDialogButtonBox, QTabWidget, QFrame
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QFontMetrics


class FT897CAT:
    """CAT control for Yaesu FT-897 via Hamlib Python API."""

    def __init__(self):
        self.rig = None
        self.is_connected = False

    def connect(self, port, baudrate=9600):
        try:
            # Model 2 corresponds to FT-897
            self.rig = hamlib.Rig(hamlib.RIG_MODEL_FT897, port)
            self.rig.open()
            self.is_connected = True
            return True
        except Exception as e:
            print(f"Chyba připojení: {e}")
            return False

    def disconnect(self):
        try:
            if self.rig:
                self.rig.close()
        except Exception:
            pass
        self.is_connected = False

    def get_frequency(self):
        if not self.is_connected:
            return None
        try:
            return self.rig.get_freq()
        except Exception:
            return None

    def get_squelch_status(self):
        if not self.is_connected:
            return None
        try:
            sq = self.rig.get_level(hamlib.RIG_VFO_CURR, hamlib.RIG_LEVEL_SQ)
            return bool(sq > 0)
        except Exception:
            return None

    def ptt_on(self):
        if not self.is_connected:
            return False
        try:
            self.rig.set_ptt(hamlib.RIG_PTT_ON)
            return True
        except Exception:
            return False

    def ptt_off(self):
        if not self.is_connected:
            return False
        try:
            self.rig.set_ptt(hamlib.RIG_PTT_OFF)
            return True
        except Exception:
            return False


class StatusThread(QThread):
    status_updated = pyqtSignal(object, object)  # frequency in Hz, squelch status

    def __init__(self, cat: FT897CAT):
        super().__init__()
        self.cat = cat
        self.running = False
        self.last_freq = None

    def run(self):
        self.running = True
        while self.running:
            if self.cat.is_connected:
                freq = self.cat.get_frequency()
                if freq is not None and 100000 <= freq <= 500000000:
                    self.last_freq = freq
                else:
                    freq = self.last_freq

                sq = self.cat.get_squelch_status()

                if freq is not None or sq is not None:
                    self.status_updated.emit(freq, sq)
            self.msleep(500)

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
        ports = serial.tools.list_ports.comports()
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


        self.swr_tab = QWidget()
        self.swr_layout = QVBoxLayout(self.swr_tab)

        self.swr_label = QLabel("SWR: ---")
        self.swr_label.setAlignment(Qt.AlignCenter)
        self.swr_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.swr_layout.addWidget(self.swr_label)

        self.tabs.addTab(self.swr_tab, "SWR")

        self.squares_tab = QWidget()
        self.squares_layout = QVBoxLayout(self.squares_tab)

        self.squelch_status_label = QLabel("Šumová brána: ---")
        self.squelch_status_label.setAlignment(Qt.AlignCenter)
        self.squelch_status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.squares_layout.addWidget(self.squelch_status_label)

        self.tabs.addTab(self.squares_tab, "Šumová brána")

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
        self.adjust_label_font(self.swr_label)
        self.adjust_label_font(self.squelch_status_label)

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

    def update_status(self, freq_hz, sq_open):
        if freq_hz is not None:
            self.last_valid_frequency = freq_hz
            freq_mhz = freq_hz / 1_000_000.0
            formatted = f"{freq_mhz:.5f}".replace('.', ',')
            self.freq_label.setText(formatted)
            freq_khz = freq_hz / 1000.0
            self.band_label.setText(f"Pásmo: {self.get_band_label_from_khz(freq_khz)}")
        if sq_open is True:
            self.squelch_status_label.setText("Šumová brána: otevřená")
        elif sq_open is False:
            self.squelch_status_label.setText("Šumová brána: zavřená")
        else:
            self.squelch_status_label.setText("Šumová brána: ---")
        self.adjust_all_fonts()

    def get_band_label_from_khz(self, freq_khz):
        for (start, end), label in self.band_definitions:
            if start <= freq_khz <= end:
                return label
        return f"Neznámé pásmo ({freq_khz/1000:.5f} MHz)"


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
