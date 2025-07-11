# FT897

Simple PyQt5 CAT control for the Yaesu FT-897.

## Requirements

- Python 3
- PyQt5
- pyserial

## Usage

Run `python3 ft897_gui.py` and choose your serial port from the drop down.
The frequency and S-meter labels always use the largest possible font. The
window calculates a generous minimum size on startup so these labels remain
large and stable even when the tabs change. All tabs share that same minimum
size to avoid any flicker while switching.
