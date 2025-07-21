from __future__ import annotations

import sys
from typing import Tuple

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton,
    QComboBox, QMessageBox, QAction, QSizePolicy, QTabWidget, QMenu
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont

from .cat_controller import FT897CAT
from .memory_manager import MemoryManager

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
                mode = next((n for n,v in FT897CAT.MODE_MAP.items() if v==mode_code), "")
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

    def init_ui(self) -> None:
        self.setWindowTitle("FT-897 CAT Control")
        self.resize(800, 400)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        self.port_combo = QComboBox()
        from serial.tools import list_ports
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
        freq_tab = QWidget()
        v = QVBoxLayout(freq_tab)
        v.addWidget(self.freq_label)
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
        self.smeter_label.setText(f"S-metr: {sm}" if sm >=0 else "S-metr: ---")
        self.power_label.setText(f"Výkon: {power}" if power>=0 else "Výkon: ---")
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
