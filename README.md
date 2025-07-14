# FT897

Simple PyQt5 utility for controlling the Yaesu FT‑897 transceiver over
its CAT interface.  The code is organised into several small modules:

* `cat_control.py` – serial I/O and CAT command helpers
* `meters.py` – formatting utilities for S‑meter and power readings
* `resources.py` – shared constants such as mode codes and band lists
* `ui_main.py` – PyQt5 user interface
* `main.py` – application entry point

The UI polls the radio every 400 ms for the current frequency and only
queries meter values about once per second or when the frequency changes.
Power menus are populated dynamically based on the selected band.

