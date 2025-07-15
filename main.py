"""Application entry point."""

import sys
import argparse
from PyQt5.QtWidgets import QApplication

from ui_main import RadioControlApp


def main():
    parser = argparse.ArgumentParser(description="FT-897 control GUI")
    parser.add_argument("--debug", action="store_true", help="log CAT bytes")
    parser.add_argument("--port", help="serial port, e.g. /dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=9600, help="baud rate")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    window = RadioControlApp(debug=args.debug, port=args.port, baudrate=args.baud)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
