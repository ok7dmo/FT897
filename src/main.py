import sys
import logging
import time
import threading
from typing import Dict, Optional

from PyQt5 import QtCore, QtGui, QtWidgets
import serial
from serial.tools import list_ports


logger = logging.getLogger(__name__)


class FT897CAT:
    """Minimal CAT control using original serial protocol."""

    def __init__(self) -> None:
        self.port: Optional[str] = None
        self.baudrate: int = 9600
        self.is_connected: bool = False
        self.serial_port: Optional[serial.Serial] = None
        self._lock = threading.Lock()

    def connect(self, port: str, baudrate: int = 9600) -> bool:
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
                rtscts=False,
                dsrdtr=False,
            )
            self.is_connected = True
            logger.info("Connected to %s at %d bps", port, baudrate)
            return True
        except Exception as exc:  # pragma: no cover - hardware specific
            logger.error("Chyba připojení: %s", exc)
            self.is_connected = False
            return False

    def disconnect(self) -> None:
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.close()
            except Exception:  # pragma: no cover - hardware specific
                pass
        self.is_connected = False
        logger.info("Disconnected")

    def send_command(self, cmd: bytes, resp_len: int = 0):
        """Send raw CAT command and optionally read response."""
        with self._lock:
            try:
                if not self.serial_port:
                    return None
                self.serial_port.reset_input_buffer()
                logger.debug("SEND: %s", cmd.hex())
                self.serial_port.write(cmd)
                self.serial_port.flush()
                if resp_len:
                    time.sleep(0.05)
                    resp = self.serial_port.read(resp_len)
                    if resp:
                        logger.debug("RECV: %s", resp.hex())
                    return resp
                return True
            except Exception as exc:  # pragma: no cover - hardware specific
                logger.error("Serial command failed: %s", exc)
                return None

    def get_frequency(self) -> Optional[int]:
        if not self.is_connected:
            return None
        resp = self.send_command(b"\x00\x00\x00\x00\x03", resp_len=5)
        if not resp or len(resp) != 5:
            return None
        units_10hz = 0
        for b in resp[:4]:
            units_10hz = units_10hz * 100 + ((b >> 4) & 0x0F) * 10 + (b & 0x0F)
        return units_10hz * 10


class StatusThread(QtCore.QThread):
    """Polling thread for radio status."""

    status = QtCore.pyqtSignal(dict)
    error = QtCore.pyqtSignal(str)

    def __init__(self, cat: FT897CAT, parent: Optional[QtCore.QObject] = None) -> None:
        super().__init__(parent)
        self.cat = cat

    def run(self) -> None:  # pragma: no cover - thread behaviour
        while not self.isInterruptionRequested():
            try:
                freq = self.cat.get_frequency() if self.cat.is_connected else None
                if freq is not None:
                    self.status.emit({"frekvence": f"{freq/1_000_000:.5f}"})
                self.msleep(500)
            except Exception as exc:  # noqa: BLE001 - broad exception to keep thread alive
                logger.error("Chyba ve status vláknu: %s", exc)
                self.error.emit(str(exc))
                self.cat.disconnect()
                self.msleep(1000)
        self.cat.disconnect()

    def stop(self) -> None:
        self.requestInterruption()


class LedIndicator(QtWidgets.QWidget):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._on = False
        self.setFixedSize(16, 16)

    def set_on(self, state: bool) -> None:
        self._on = state
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # pragma: no cover - GUI code
        painter = QtGui.QPainter(self)
        color = QtGui.QColor("green" if self._on else "red")
        painter.setBrush(QtGui.QBrush(color))
        painter.setPen(QtCore.Qt.NoPen)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.drawEllipse(0, 0, self.width(), self.height())


class Toast(QtWidgets.QWidget):
    """Jednoduchá toast notifikace."""

    def __init__(self, message: str, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent, QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
        layout = QtWidgets.QHBoxLayout(self)
        label = QtWidgets.QLabel(message)
        layout.addWidget(label)
        self.timer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)

    def show_(self, timeout: int = 3000) -> None:
        self.timer.start(timeout)
        self.show()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("FT-897 CAT")
        self.resize(400, 200)
        self._font_cache: Dict[int, QtGui.QFont] = {}

        self.cat = FT897CAT()
        self.status_thread: Optional[StatusThread] = None

        # UI elements
        central = QtWidgets.QWidget()
        vbox = QtWidgets.QVBoxLayout(central)

        self.freq_label = QtWidgets.QLabel("-")
        vbox.addWidget(self.freq_label)

        self.connect_btn = QtWidgets.QPushButton("Připojit")
        self.connect_btn.clicked.connect(self.start_thread)
        vbox.addWidget(self.connect_btn)

        self.disconnect_btn = QtWidgets.QPushButton("Odpojit")
        self.disconnect_btn.clicked.connect(self.stop_thread)
        self.disconnect_btn.setEnabled(False)
        vbox.addWidget(self.disconnect_btn)

        self.setCentralWidget(central)

        # Status bar
        self.status_indicator = LedIndicator()
        self.statusBar().addPermanentWidget(self.status_indicator)
        self.status_label = QtWidgets.QLabel("Odpojeno")
        self.statusBar().addWidget(self.status_label)

        # Timers
        self.resize_timer = QtCore.QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.update_fonts)

        # Shortcuts
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+R"), self, self.start_thread)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+D"), self, self.stop_thread)

    # --- Font management -------------------------------------------------------
    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # pragma: no cover - GUI
        self.resize_timer.start(200)
        super().resizeEvent(event)

    def update_fonts(self) -> None:
        size = max(10, self.width() // 20)
        if size not in self._font_cache:
            font = QtGui.QFont()
            font.setPointSize(size)
            self._font_cache[size] = font
        self.freq_label.setFont(self._font_cache[size])

    # --- Thread control --------------------------------------------------------
    def start_thread(self) -> None:
        if self.status_thread and self.status_thread.isRunning():
            return
        ports = list(list_ports.comports())
        if not ports:
            self.on_error("Nenalezen žádný port")
            return
        if not self.cat.connect(ports[0].device):
            self.on_error("Nelze se připojit")
            return
        self.status_thread = StatusThread(self.cat)
        self.status_thread.status.connect(self.on_status)
        self.status_thread.error.connect(self.on_error)
        self.status_thread.finished.connect(self.on_thread_finished)
        self.status_thread.start()
        self.status_label.setText("Připojování...")
        self.connect_btn.setEnabled(False)
        self.disconnect_btn.setEnabled(True)

    def stop_thread(self) -> None:
        if self.status_thread:
            self.status_thread.stop()
            self.status_thread.wait(2000)
            self.status_thread = None
        self.cat.disconnect()

    def on_thread_finished(self) -> None:
        self.status_thread = None
        self.status_indicator.set_on(False)
        self.status_label.setText("Odpojeno")
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)

    def on_status(self, data: Dict[str, str]) -> None:
        self.freq_label.setText(data.get("frekvence", "-"))
        self.status_indicator.set_on(True)
        self.status_label.setText("Připojeno")

    def on_error(self, message: str) -> None:
        self.status_indicator.set_on(False)
        self.status_label.setText("Chyba")
        toast = Toast(message, self)
        toast.move(self.geometry().center() - toast.rect().center())
        toast.show_()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # pragma: no cover - GUI
        self.resize_timer.stop()
        self.stop_thread()
        super().closeEvent(event)


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

