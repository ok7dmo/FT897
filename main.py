#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import time
import threading

try:
    import serial
    from serial.tools import list_ports

    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton,
        QComboBox, QMessageBox, QAction, QSizePolicy, QFontDialog,
        QDialog, QRadioButton, QDialogButtonBox, QTabWidget, QFrame,
        QInputDialog
    )
    from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
    from PyQt5.QtGui import QFont, QFontMetrics
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Please install required packages from requirements.txt")
    sys.exit(1)


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
        """Return raw power meter level (0-15) from the TX status byte."""
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


class StatusThread(QThread):
    status_updated = pyqtSignal(int, int, int, int)

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

        self.band_configs = {
            "160 m": {"range": (1_800_000, 2_000_000), "step": 1000, "mode": "LSB"},
            "80 m": {"range": (3_500_000, 3_799_000), "step": 1000, "mode": "LSB"},
            "60 m": {"list": [5_357_000, 5_371_500], "mode": "USB"},
            "40 m": {"range": (7_000_000, 7_200_000), "step": 1000, "mode": "LSB"},
            "20 m": {"range": (14_000_000, 14_350_000), "step": 1000, "mode": "USB"},
            "2 m": {"range": (144_000_000, 145_800_000), "step": 1000, "mode": "FM"},
        }

        self.memory_presets = {
            "FM rozhlas": [
                ("Evropa 2 – Kleť", 105_500_000, "FM"),
                ("ČRo Radiožurnál – Kleť", 91_100_000, "FM"),
            ]
        }

        self.band_max_power = {
            "160 m": 100,
            "80 m": 100,
            "60 m": 100,
            "40 m": 100,
            "20 m": 100,
            "2 m": 50,
        }

        self.band_min_power = {band: 5 for band in self.band_max_power}

        self.band_power_calibration = {
            "160 m": {"min_raw": 1, "max_raw": 15},
            "80 m": {"min_raw": 1, "max_raw": 15},
            "60 m": {"min_raw": 1, "max_raw": 15},
            "40 m": {"min_raw": 1, "max_raw": 15},
            "20 m": {"min_raw": 1, "max_raw": 15},
            "2 m": {"min_raw": 2, "max_raw": 7},
        }

        self.band_power_curve = {
            "2 m": {
                2: 5,
                3: 14,
                4: 23,
                5: 34,
                6: 43,
                7: 50,
            },
        }

        self.band_definitions = [
            ((87500, 108000), "FM rozhlas"),
            ((144000, 145800), "2 m"),
        ]
        for band, cfg in self.band_configs.items():
            if "range" in cfg:
                start, end = cfg["range"]
            elif "list" in cfg:
                start, end = min(cfg["list"]), max(cfg["list"])
            else:
                continue
            self.band_definitions.append(((start / 1000, end / 1000), band))

        self.init_ui()
        self.apply_stylesheet(self.current_theme)
    def init_ui(self):
        self.setWindowTitle("FT-897 CAT Control")
        self.setGeometry(100, 100, 400, 200)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.port_combo = QComboBox()
        for port in list_ports.comports():
            self.port_combo.addItem(port.device)
        layout.addWidget(self.port_combo)

        self.connect_btn = QPushButton("Připojit")
        self.connect_btn.clicked.connect(self.toggle_connection)
        layout.addWidget(self.connect_btn)

        self.freq_label = QLabel(self.freq_text)
        self.freq_label.setAlignment(Qt.AlignCenter)
        self.freq_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.freq_label)

        self.ptt_btn = QPushButton("PTT")
        self.ptt_btn.setCheckable(True)
        self.ptt_btn.pressed.connect(self.handle_ptt_on)
        self.ptt_btn.released.connect(self.handle_ptt_off)
        self.ptt_btn.setEnabled(False)
        layout.addWidget(self.ptt_btn)

        self.init_menu()

    def init_menu(self):
        menubar = self.menuBar()
        ctcss_tone = QAction("Nastavit CTCSS tón…", self)
        ctcss_tone.triggered.connect(self.prompt_ctcss_tone)
        menubar.addAction(ctcss_tone)

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
        tones = [
            67.0, 69.3, 71.9, 74.4, 77.0, 79.7, 82.5, 85.4, 88.5, 91.5,
            94.8, 97.4, 100.0, 103.5, 107.2, 110.9, 114.8, 118.8, 123.0, 127.3,
            131.8, 136.5, 141.3, 146.2, 151.4, 156.7, 159.8, 162.2, 165.5, 167.9,
            171.3, 173.8, 177.3, 179.9, 183.5, 186.2, 189.9, 192.8, 196.6, 199.5,
            203.5, 206.5, 210.7, 218.1, 225.7, 229.1, 233.6, 241.8, 250.3, 254.1,
        ]
        self.cat.set_ctcss_dcs_mode("ctcss_enc")
        time.sleep(0.05)
        items = [f"{t:.1f} Hz" for t in tones]
        tx_str, ok = QInputDialog.getItem(
            self, "CTCSS TX", "Vyberte TX tón:", items, items.index("88.5 Hz"), False
        )
        if not ok:
            return
        tx = float(tx_str.split()[0])
        rx_str, ok = QInputDialog.getItem(
            self, "CTCSS RX", "Vyberte RX tón:", items, items.index(tx_str), False
        )
        if not ok:
            return
        rx = float(rx_str.split()[0])
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

    def handle_ptt_on(self):
        if not self.cat.is_connected:
            return
        self.cat.ptt_on()
        self.ptt_heartbeat.start()

    def handle_ptt_off(self):
        if not self.cat.is_connected:
            return
        self.ptt_heartbeat.stop()
        self.cat.ptt_off()

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
