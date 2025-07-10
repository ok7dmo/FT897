# FT-897 CAT Control

This PyQt5 application provides CAT control for the Yaesu FT-897 transceiver on Windows.

## Installation

Install the required Python packages:

```bash
pip install pyserial PyQt5
```

## Running

Run the application with:

```bash
python ft897_app.py
```

### Packaging with PyInstaller

To create a standalone Windows executable:

```bash
pyinstaller --onefile --windowed --add-data "<path_to_PyQt5>\\Qt5Core.dll;." ft897_app.py
```

Replace `<path_to_PyQt5>` with your local PyQt5 installation path.

By default the GUI lists available COM ports and common CAT baud rates (4800,
9600, 38400). Select the correct speed for your transceiver before connecting.

### PL2303 notes

The popular Prolific PL‑2303 USB‑to‑serial adapter works with the FT‑897 using
standard 8 data bits, no parity and **one** stop bit. Set the radio and the
software to the same baud rate (usually 9600) and ensure the Prolific drivers
are installed on Windows.
