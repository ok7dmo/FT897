import sys
import logging
import time
from dataclasses import dataclass
from typing import Callable, Dict, Optional

from PyQt5 import QtCore, QtGui, QtWidgets
import serial
from serial.tools import list_ports

# Custom exception hierarchy
class CATError(Exception):
    """Base class for CAT application errors."""


class ConnectionError(CATError):
    """Raised when a serial connection fails."""


class CommandError(CATError):
    """Raised when a CAT command fails."""


@dataclass
class SerialConfig:
    port: Optional[str] = None
    baudrate: int = 4800
    timeout: float = 1.0


class SerialConnection:
    """Context manager for serial communication."""

    def __init__(self, config: SerialConfig) -> None:
        self.config = config
        self._serial: Optional[serial.Serial] = None

    def __enter__(self) -> "SerialConnection":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        self.close()

    # --- Serial port management -------------------------------------------------
    def open(self) -> None:
        if self._serial and self._serial.is_open:
            return
        port = self.config.port or self._detect_port()
        try:
            self._serial = serial.Serial(
                port,
                self.config.baudrate,
                timeout=self.config.timeout,
                write_timeout=self.config.timeout,
            )
        except serial.SerialException as exc:  # pragma: no cover - hardware specific
            raise ConnectionError(str(exc)) from exc
        logging.info("Připojeno k %s", port)

    def close(self) -> None:
        if self._serial and self._serial.is_open:
            self._serial.close()
            logging.info("Seriový port uzavřen")

    def _detect_port(self) -> str:
        ports = list(list_ports.comports())
        if not ports:
            raise ConnectionError("Nenalezen žádný seriový port")
        logging.info("Detekován port %s", ports[0].device)
        return ports[0].device

    # --- Communication helpers --------------------------------------------------
    def send_command(self, command: bytes, retries: int = 3) -> bytes:
        if not self._serial or not self._serial.is_open:
            raise ConnectionError("Seriový port není otevřen")
        for attempt in range(retries):
            try:
                self._serial.reset_input_buffer()
                self._serial.write(command)
                self._serial.flush()
                response = self._serial.read_until(b";")
                if not response:
                    raise CommandError("Prázdná odpověď")
                return response
            except serial.SerialException as exc:
                logging.warning("Chyba komunikace (pokus %s/3): %s", attempt + 1, exc)
                time.sleep(0.1)
                if attempt + 1 == retries:
                    raise ConnectionError(str(exc))
        return b""

    def is_healthy(self) -> bool:
        try:
            self.send_command(b"FA;")
            return True
        except CATError:
            return False


class StatusThread(QtCore.QThread):
    status = QtCore.pyqtSignal(dict)
    error = QtCore.pyqtSignal(str)

    def __init__(
        self,
        connection_factory: Callable[[], SerialConnection],
        parent: Optional[QtCore.QObject] = None,
    ) -> None:
        super().__init__(parent)
        self.connection_factory = connection_factory

    def run(self) -> None:  # pragma: no cover - thread behaviour
        conn: Optional[SerialConnection] = None
        while not self.isInterruptionRequested():
            try:
                if conn is None:
                    conn = self.connection_factory()
                    conn.open()
                if not conn.is_healthy():
                    raise ConnectionError("Test spojení selhal")
                freq = conn.send_command(b"FA;")
                self.status.emit({"frekvence": freq.decode(errors="ignore")})
            except Exception as exc:  # noqa: BLE001 - we want to capture all errors
                logging.error("Chyba ve status vláknu: %s", exc)
                self.error.emit(str(exc))
                if conn:
                    conn.close()
                    conn = None
                self.msleep(1000)  # pokus o reconnect po 1s
                continue
            self.msleep(500)
        if conn:
            conn.close()

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

        # Thread and serial
        self.status_thread: Optional[StatusThread] = None
        self.serial_config = SerialConfig()

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
        self.status_thread = StatusThread(self._create_connection)
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

    def _create_connection(self) -> SerialConnection:
        return SerialConnection(self.serial_config)

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
