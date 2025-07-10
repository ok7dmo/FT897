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
