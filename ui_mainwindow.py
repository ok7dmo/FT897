"""PyQt5 GUI for FT-897 CAT control."""

from PyQt5 import QtCore, QtGui, QtWidgets


class MainWindow(QtWidgets.QMainWindow):
    """Main application window."""

    frequency_changed = QtCore.pyqtSignal(float, str)
    smeter_changed = QtCore.pyqtSignal(int)
    swr_changed = QtCore.pyqtSignal(float)
    connect_clicked = QtCore.pyqtSignal(str)
    disconnect_clicked = QtCore.pyqtSignal()
    ptt_pressed = QtCore.pyqtSignal(bool)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("FT-897 CAT")
        self.resize(500, 300)
        self._central_font = QtGui.QFont("Consolas", 24)

        self._create_menu()
        self._create_widgets()
        self._apply_theme("light")

    def _create_menu(self) -> None:
        menu = self.menuBar().addMenu("Settings")
        font_act = menu.addAction("Font...")
        font_act.triggered.connect(self._choose_font)

        theme_menu = menu.addMenu("Theme")
        for name in ("light", "dark", "high-contrast"):
            act = theme_menu.addAction(name.capitalize())
            act.triggered.connect(lambda _, n=name: self._apply_theme(n))

    def _choose_font(self) -> None:
        font, ok = QtWidgets.QFontDialog.getFont(self._central_font, self)
        if ok:
            self._central_font = font
            self._resize_fonts()

    def _apply_theme(self, name: str) -> None:
        palette = QtGui.QPalette()
        if name == "dark":
            palette.setColor(QtGui.QPalette.Window, QtGui.QColor(53, 53, 53))
            palette.setColor(QtGui.QPalette.WindowText, QtCore.Qt.white)
        elif name == "high-contrast":
            palette.setColor(QtGui.QPalette.Window, QtCore.Qt.black)
            palette.setColor(QtGui.QPalette.WindowText, QtCore.Qt.yellow)
        self.setPalette(palette)

    def _create_widgets(self) -> None:
        central = QtWidgets.QWidget()
        vbox = QtWidgets.QVBoxLayout(central)

        hbox = QtWidgets.QHBoxLayout()
        self.com_combo = QtWidgets.QComboBox()
        self.connect_btn = QtWidgets.QPushButton("Connect")
        self.connect_btn.clicked.connect(self._on_connect)
        hbox.addWidget(self.com_combo)
        hbox.addWidget(self.connect_btn)
        vbox.addLayout(hbox)

        self.tabs = QtWidgets.QTabWidget()
        self.freq_tab = QtWidgets.QWidget()
        self.s_tab = QtWidgets.QWidget()
        self.swr_tab = QtWidgets.QWidget()
        self.tabs.addTab(self.freq_tab, "Frequency")
        self.tabs.addTab(self.s_tab, "S-meter")
        self.tabs.addTab(self.swr_tab, "SWR")
        vbox.addWidget(self.tabs)

        self.freq_label = QtWidgets.QLabel("000.00000 MHz")
        self.freq_label.setAlignment(QtCore.Qt.AlignCenter)
        self.band_label = QtWidgets.QLabel("")
        self.band_label.setAlignment(QtCore.Qt.AlignCenter)
        freq_layout = QtWidgets.QVBoxLayout(self.freq_tab)
        freq_layout.addWidget(self.freq_label)
        freq_layout.addWidget(self.band_label)

        self.s_label = QtWidgets.QLabel("S: 0")
        self.s_label.setAlignment(QtCore.Qt.AlignCenter)
        s_layout = QtWidgets.QVBoxLayout(self.s_tab)
        s_layout.addWidget(self.s_label)

        self.swr_label = QtWidgets.QLabel("SWR: 1.0")
        self.swr_label.setAlignment(QtCore.Qt.AlignCenter)
        swr_layout = QtWidgets.QVBoxLayout(self.swr_tab)
        swr_layout.addWidget(self.swr_label)

        self.ptt_btn = QtWidgets.QPushButton("PTT")
        self.ptt_btn.setCheckable(True)
        self.ptt_btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                   QtWidgets.QSizePolicy.Preferred)
        self.ptt_btn.toggled.connect(lambda s: self.ptt_pressed.emit(s))
        vbox.addWidget(self.ptt_btn)

        self.setCentralWidget(central)

    def _on_connect(self) -> None:
        if self.connect_btn.text() == "Connect":
            port = self.com_combo.currentText()
            self.connect_clicked.emit(port)
        else:
            self.disconnect_clicked.emit()

    def set_connected(self, connected: bool) -> None:
        self.connect_btn.setText("Disconnect" if connected else "Connect")

    def update_frequency(self, freq_mhz: float, band: str) -> None:
        text = f"{freq_mhz:07.5f} MHz"
        if self.freq_label.text() != text:
            self.freq_label.setText(text)
        if self.band_label.text() != band:
            self.band_label.setText(band)

    def update_smeter(self, level: int) -> None:
        text = f"S: {level}"
        if self.s_label.text() != text:
            self.s_label.setText(text)

    def update_swr(self, value: float) -> None:
        text = f"SWR: {value:.1f}"
        if self.swr_label.text() != text:
            self.swr_label.setText(text)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._resize_fonts()

    def _resize_fonts(self) -> None:
        height = self.height() // 10
        if height > 0:
            self._central_font.setPointSize(max(10, height))
            for w in [self.freq_label, self.band_label, self.s_label,
                      self.swr_label, self.ptt_btn]:
                w.setFont(self._central_font)
