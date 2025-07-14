from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QLabel, QFileDialog, QTextEdit, QMessageBox
)
import time


class LogWindow(QDialog):
    """Simple dialog for logging meter changes to a text file."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Logování")
        self._file = None

        layout = QVBoxLayout(self)

        file_layout = QHBoxLayout()
        file_layout.addWidget(QLabel("Soubor:"))
        self.path_edit = QLineEdit()
        file_layout.addWidget(self.path_edit)
        browse = QPushButton("Vybrat…")
        browse.clicked.connect(self.choose_file)
        file_layout.addWidget(browse)
        layout.addLayout(file_layout)

        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.start_btn.clicked.connect(self.start_logging)
        btn_layout.addWidget(self.start_btn)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_logging)
        btn_layout.addWidget(self.stop_btn)
        layout.addLayout(btn_layout)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view)

    def choose_file(self):
        path, _ = QFileDialog.getSaveFileName(self, "Vyberte soubor logu", "log.txt", "Text files (*.txt);;All files (*)")
        if path:
            self.path_edit.setText(path)

    def start_logging(self):
        if self._file:
            return
        path = self.path_edit.text()
        if not path:
            QMessageBox.warning(self, "Chyba", "Nejprve vyberte soubor")
            return
        try:
            self._file = open(path, "a", encoding="utf-8")
        except Exception as exc:
            QMessageBox.warning(self, "Chyba", f"Nelze otevřít soubor:\n{exc}")
            self._file = None
            return
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.log_view.append(f"== Logging started {time.ctime()} ==")
        self._file.write(f"# start {time.ctime()}\n")
        self._file.flush()

    def stop_logging(self):
        if not self._file:
            return
        self.log_view.append(f"== Logging stopped {time.ctime()} ==")
        try:
            self._file.write(f"# stop {time.ctime()}\n")
            self._file.close()
        except Exception:
            pass
        self._file = None
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def is_logging(self):
        return self._file is not None

    def log(self, message: str):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        line = f"{timestamp} {message}"
        self.log_view.append(line)
        if self._file:
            try:
                self._file.write(line + "\n")
                self._file.flush()
            except Exception:
                pass

    def closeEvent(self, event):
        self.stop_logging()
        event.accept()
