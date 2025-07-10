"""Application logic for FT-897 CAT GUI."""

import sys
import threading
import time
from typing import Optional

from PyQt5 import QtCore, QtWidgets
import serial
from serial.tools import list_ports

from ft897_cat import FT897CAT
from ui_mainwindow import MainWindow


class PollThread(QtCore.QThread):
    """Thread to poll radio status."""

    frequency_updated = QtCore.pyqtSignal(float)
    smeter_updated = QtCore.pyqtSignal(int)
    swr_updated = QtCore.pyqtSignal(float)
    error_occurred = QtCore.pyqtSignal(str)

    def __init__(self, cat: FT897CAT, parent: Optional[QtCore.QObject] = None) -> None:
        super().__init__(parent)
        self.cat = cat
        self._running = threading.Event()
        self._running.set()

    def run(self) -> None:  # noqa: D401
        """Thread loop."""
        while self._running.is_set():
            try:
                freq = self.cat.get_frequency()
                if freq is not None:
                    self.frequency_updated.emit(freq)
                s = self.cat.get_smeter()
                if s is not None:
                    self.smeter_updated.emit(s)
                swr = self.cat.get_swr()
                if swr is not None:
                    self.swr_updated.emit(swr)
            except Exception as exc:  # noqa: BLE001
                self.error_occurred.emit(str(exc))
            # Sleep using QThread.msleep for accurate timing without busy wait
            self.msleep(300)

    def stop(self) -> None:
        self._running.clear()
        self.wait(1000)


class App(QtWidgets.QApplication):
    """Main application controller."""

    def __init__(self, argv: list[str]) -> None:
        super().__init__(argv)
        self.cat = FT897CAT()
        self.window = MainWindow()
        self.window.connect_clicked.connect(self.connect_port)
        self.window.disconnect_clicked.connect(self.disconnect_port)
        self.window.ptt_pressed.connect(self.handle_ptt)
        self.poll_thread: Optional[PollThread] = None
        self.ptt_timer = QtCore.QTimer()
        self.ptt_timer.setInterval(100)
        self.ptt_timer.timeout.connect(self.cat.ptt_on)
        self.refresh_ports()
        self.port_timer = QtCore.QTimer()
        self.port_timer.setInterval(5000)
        self.port_timer.timeout.connect(self.refresh_ports)
        self.port_timer.start()
        self.window.show()
        self.aboutToQuit.connect(self.cleanup)

    def refresh_ports(self) -> None:
        current = self.window.com_combo.currentText()
        ports = [p.device for p in list_ports.comports()]
        self.window.com_combo.blockSignals(True)
        self.window.com_combo.clear()
        for p in ports:
            self.window.com_combo.addItem(p)
        idx = self.window.com_combo.findText(current)
        if idx >= 0:
            self.window.com_combo.setCurrentIndex(idx)
        self.window.com_combo.blockSignals(False)

    def connect_port(self, port: str, baud: int) -> None:
        try:
            self.cat.open(port, baud)
        except Exception as exc:  # noqa: BLE001
            QtWidgets.QMessageBox.critical(self.window, "Error", str(exc))
            return
        self.window.set_connected(True)
        self.poll_thread = PollThread(self.cat)
        self.poll_thread.frequency_updated.connect(self.on_frequency)
        self.poll_thread.smeter_updated.connect(self.on_smeter)
        self.poll_thread.swr_updated.connect(self.on_swr)
        self.poll_thread.error_occurred.connect(self.on_error)
        self.poll_thread.start()

    def disconnect_port(self) -> None:
        if self.poll_thread and self.poll_thread.isRunning():
            self.poll_thread.stop()
        self.poll_thread = None
        self.cat.close()
        self.window.set_connected(False)
        self.ptt_timer.stop()
        self.window.ptt_btn.setChecked(False)

    def handle_ptt(self, pressed: bool) -> None:
        if pressed:
            self.ptt_timer.start()
        else:
            self.ptt_timer.stop()
            self.cat.ptt_off()

    def on_frequency(self, freq_mhz: float) -> None:
        band = self.cat.band_from_frequency(freq_mhz)
        self.window.update_frequency(freq_mhz, band)

    def on_smeter(self, level: int) -> None:
        self.window.update_smeter(level)

    def on_swr(self, value: float) -> None:
        self.window.update_swr(value)

    def on_error(self, message: str) -> None:
        QtWidgets.QMessageBox.warning(self.window, "Serial Error", message)
        self.disconnect_port()

    def cleanup(self) -> None:
        """Handle application exit."""
        if self.poll_thread and self.poll_thread.isRunning():
            self.poll_thread.stop()
        self.cat.close()



def main() -> None:
    """Entry point."""
    app = App(sys.argv)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
