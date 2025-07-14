"""PyQt5 GUI for FT-897 control."""

import serial.tools.list_ports
import time
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QFontMetrics
from PyQt5.QtWidgets import (
    QAction,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QRadioButton,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QFontDialog,
)

from cat_control import FT897CAT
from meters import format_power, format_smeter
from resources import MODE_CODES, MODE_NAMES, band_definitions, band_menu_items


class RadioControlApp(QMainWindow):
    """Main window class."""

    def __init__(self):
        super().__init__()
        self.cat = FT897CAT()

        self.status_timer = QTimer(self)
        # faster GUI response with moderate polling interval
        self.status_timer.setInterval(300)
        self.status_timer.timeout.connect(self.update_status)

        self.ptt_heartbeat = QTimer(self)
        self.ptt_heartbeat.setInterval(100)
        self.ptt_heartbeat.timeout.connect(self.cat.ptt_on)

        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.adjust_all_fonts)

        self.current_font_family = "Courier New"
        self.freq_text = "000,00000"
        self.current_theme = "dark"
        self.last_valid_frequency = None
        self.last_mode = None
        self._last_s = None
        self._last_p = None
        self._last_power_band = None
        self._last_meter_time = 0.0

        self.band_definitions = band_definitions
        self.band_menu_items = band_menu_items

        self.band_range_map = {label: rng for rng, label in self.band_definitions}
        self.band_mode_map = {label: mode for label, _freq, mode in self.band_menu_items}

        self.init_ui()
        self.apply_stylesheet(self.current_theme)

    # ------------------------ UI Setup ------------------------
    def init_ui(self):
        self.setWindowTitle("Ovl\u00e1d\u00e1n\u00ed r\u00e1dia")
        self.setGeometry(100, 100, 800, 400)

        self.central = QWidget()
        self.setCentralWidget(self.central)
        self.layout = QVBoxLayout(self.central)

        self.port_combo = QComboBox()
        for port in serial.tools.list_ports.comports():
            self.port_combo.addItem(port.device)
        self.layout.addWidget(self.port_combo)

        self.connect_btn = QPushButton("P\u0159ipojit")
        self.connect_btn.clicked.connect(self.toggle_connection)
        self.layout.addWidget(self.connect_btn)

        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        # Frequency tab
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

        self.mode_label = QLabel("M\u00f3d: ---")
        self.mode_label.setAlignment(Qt.AlignCenter)
        self.mode_label.setStyleSheet("font-size: 18px;")
        self.mode_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.freq_layout.addWidget(self.mode_label)

        self.tabs.addTab(self.freq_tab, "Frekvence")

        # S-meter tab
        self.smeter_tab = QWidget()
        self.smeter_layout = QVBoxLayout(self.smeter_tab)

        self.smeter_label = QLabel("S-metr: ---")
        self.smeter_label.setAlignment(Qt.AlignCenter)
        self.smeter_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.smeter_layout.addWidget(self.smeter_label)

        self.tabs.addTab(self.smeter_tab, "S-metr")

        # Power tab
        self.power_tab = QWidget()
        self.power_layout = QVBoxLayout(self.power_tab)

        self.power_label = QLabel("V\u00fdkon: ---")
        self.power_label.setAlignment(Qt.AlignCenter)
        self.power_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.power_layout.addWidget(self.power_label)

        self.tabs.addTab(self.power_tab, "V\u00fdkon")

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
        view_menu = menubar.addMenu("Zobrazen\u00ed")

        font_action = QAction("Nastavit p\u00edsmo…", self)
        font_action.triggered.connect(self.choose_font)
        view_menu.addAction(font_action)

        color_scheme_action = QAction("Nastavit barevn\u00e9 sch\u00e9ma…", self)
        color_scheme_action.triggered.connect(self.choose_color_scheme)
        view_menu.addAction(color_scheme_action)

        band_menu = menubar.addMenu("Pásmo")
        self.power_menu = menubar.addMenu("Výkon")
        for label, _freq, mode in self.band_menu_items:
            if label == "2 m":
                two_m = QMenu("2 m", self)
                self.add_freq_menu(two_m, "144 MHz", 144000, 145000, 25, MODE_CODES["USB"])
                self.add_freq_menu(two_m, "145 MHz", 145000, 146000, 25, MODE_CODES["FM"])
                band_menu.addMenu(two_m)
                continue
            if label == "6 m":
                menu6 = QMenu("6 m", self)
                self.add_freq_menu(menu6, "50-52 MHz", 50000, 52000, 5, MODE_CODES["USB"])
                self.add_freq_menu(menu6, "52-54 MHz", 52000, 54000, 25, MODE_CODES["FM"])
                band_menu.addMenu(menu6)
                continue
            if label == "70 cm":
                menu70 = QMenu("70 cm", self)
                self.add_freq_menu(menu70, "432-434 MHz", 432000, 434000, 25, MODE_CODES["USB"])
                self.add_freq_menu(menu70, "434-440 MHz", 434000, 440000, 25, MODE_CODES["FM"])
                band_menu.addMenu(menu70)
                continue
            rng = self.band_range_map.get(label)
            if label == "10 m" and rng:
                menu10 = QMenu("10 m", self)
                start_khz, end_khz = rng
                self.add_freq_menu(menu10, "10 m", start_khz, end_khz, 10, MODE_CODES["USB"])
                band_menu.addMenu(menu10)
                continue
            if label == "FM rozhlas" and rng:
                menu_fm = QMenu("FM rozhlas", self)
                start_khz, end_khz = rng
                self.add_freq_menu(menu_fm, "FM", start_khz, end_khz, 200, MODE_CODES["FM"])
                band_menu.addMenu(menu_fm)
                continue
            if label == "Letecké pásmo" and rng:
                menu_air = QMenu("Letecké pásmo", self)
                start_khz, end_khz = rng
                self.add_freq_menu(menu_air, "Air", start_khz, end_khz, 100, MODE_CODES["AM"])
                band_menu.addMenu(menu_air)
                continue
            if label in {"Rozšířený VHF RX", "UHF RX"} and rng:
                sub = QMenu(label, self)
                start_khz, end_khz = rng
                step = 100 if label == "Rozšířený VHF RX" else 200
                self.add_freq_menu(sub, label, start_khz, end_khz, step, MODE_CODES["FM"])
                band_menu.addMenu(sub)
                continue
            if rng:
                start_khz, end_khz = rng
                step = 3 if label in {"160 m", "80 m", "60 m", "40 m", "30 m", "20 m", "17 m", "15 m", "12 m"} else 5
                sub = QMenu(label, self)
                self.add_freq_menu(sub, label, start_khz, end_khz, step, mode)
                band_menu.addMenu(sub)

        cmd_menu = menubar.addMenu("P\u0159\u00edkazy")
        vfo_act = QAction("P\u0159epnout VFO A/B", self)
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

    def add_freq_menu(self, parent: QMenu, label: str, start_khz: int, end_khz: int, step: int, mode_code: int):
        """Populate a menu with frequency actions on demand."""
        def populate():
            parent.clear()
            for khz in range(start_khz, end_khz + 1, step):
                freq = khz * 1000
                act = QAction(f"{khz} kHz", self)
                act.triggered.connect(lambda _=False, f=freq, m=mode_code: self.goto_band(f, m))
                parent.addAction(act)

        parent.setTitle(label)
        parent.aboutToShow.connect(populate)

    # ------------------------ Settings dialogs ------------------------
    def choose_font(self):
        font, ok = QFontDialog.getFont(QFont(self.current_font_family, 10), self)
        if ok:
            self.current_font_family = font.family()
            self.adjust_all_fonts()

    def choose_color_scheme(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Vyberte barevn\u00e9 sch\u00e9ma")
        layout = QVBoxLayout()
        dark = QRadioButton("Tmav\u00fd re\u017eim")
        light = QRadioButton("Sv\u011bt\u00bd re\u017eim")
        contrast = QRadioButton("Vysok\u00fd kontrast")
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

    # ------------------------ Font autosizing ------------------------
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

    # ------------------------ Main logic ------------------------
    def toggle_connection(self):
        if not self.cat.is_connected:
            port = self.port_combo.currentText()
            if self.cat.connect(port):
                self.status_timer.start()
                self.ptt_btn.setEnabled(True)
                self.connect_btn.setText("Odpojit")
            else:
                QMessageBox.warning(self, "Chyba", "Nelze se p\u0159ipojit.")
        else:
            self.status_timer.stop()
            self.cat.disconnect()
            self.ptt_btn.setEnabled(False)
            self.connect_btn.setText("P\u0159ipojit")

    def update_status(self):
        if not self.cat.is_connected:
            return
        freq_hz, mode = self.cat.get_frequency_and_mode()
        if freq_hz is None:
            return
        freq_changed = freq_hz != self.last_valid_frequency
        self.last_valid_frequency = freq_hz
        self.last_mode = mode
        freq_mhz = freq_hz / 1_000_000.0
        formatted = f"{freq_mhz:.5f}".replace('.', ',')
        if formatted != self.freq_label.text():
            self.freq_label.setText(formatted)
        freq_khz = freq_hz / 1000.0
        band_label = self.get_band_label_from_khz(freq_khz)
        band_str = f"P\u00e1smo: {band_label}"
        if band_str != self.band_label.text():
            self.band_label.setText(band_str)
        mode_name = MODE_NAMES.get(mode, f"0x{mode:02X}")
        mode_str = f"M\u00f3d: {mode_name}"
        if mode_str != self.mode_label.text():
            self.mode_label.setText(mode_str)
        self.update_power_menu(band_label)

        now = time.time()
        if freq_changed or (now - self._last_meter_time) > 1.0:
            raw_s, raw_p = self.cat.get_s_and_power()
            self._last_meter_time = now
            if raw_s is not None and raw_s != self._last_s:
                self._last_s = raw_s
                self.smeter_label.setText(f"S-metr: {format_smeter(raw_s)}")
            elif raw_s is None and self._last_s is not None:
                self._last_s = None
                self.smeter_label.setText("S-metr: ---")
            if raw_p is not None and raw_p != self._last_p:
                self._last_p = raw_p
                self.power_label.setText(
                    f"V\u00fdkon: {format_power(raw_p, band_label)}"
                )

    def get_band_label_from_khz(self, freq_khz: float) -> str:
        for (start, end), label in self.band_definitions:
            if start <= freq_khz <= end:
                return label
        return f"Nezn\u00e1m\u00e9 p\u00e1smo ({freq_khz/1000:.5f} MHz)"

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

    def goto_band(self, freq_hz: int, mode_code: int):
        if not self.cat.is_connected:
            return
        self.cat.set_frequency(freq_hz)
        self.cat.set_mode(mode_code)

    def closeEvent(self, event):
        self.status_timer.stop()
        self.cat.disconnect()
        event.accept()

    # ------------------------ Power menu ------------------------
    def update_power_menu(self, band_label: str):
        if not hasattr(self, "power_menu"):
            return
        if band_label == self._last_power_band:
            return
        self._last_power_band = band_label
        self.power_menu.clear()
        band_map = {**{b: 100 for b in [
            "160 m", "80 m", "60 m", "40 m", "30 m", "20 m", "17 m", "15 m", "12 m", "10 m", "6 m"
        ]}, "2 m": 50, "70 cm": 20}
        pmax = band_map.get(band_label, 0)
        for w in range(5, pmax + 1, 5):
            act = QAction(f"{w} W", self)
            act.triggered.connect(lambda _=False, watt=w, band=band_label: self.set_power_level(band, watt))
            self.power_menu.addAction(act)

    def set_power_level(self, band_label: str, watts: int) -> None:
        """Apply transmit power change without altering frequency."""
        if self.cat.set_power(watts, band_label):
            self.power_label.setText(f"V\u00fdkon: {watts} W")

