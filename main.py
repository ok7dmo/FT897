"""Application entry point."""

import sys
from PyQt5.QtWidgets import QApplication

from ui_main import RadioControlApp


def main():
    app = QApplication(sys.argv)
    window = RadioControlApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
