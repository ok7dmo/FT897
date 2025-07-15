# FT897

Simple PyQt5 utility for controlling the Yaesu FT‑897 transceiver over
its CAT interface.  The code is organised into several small modules:

* `cat_control.py` – serial I/O and CAT command helpers
* `meters.py` – formatting utilities for S‑meter and power readings
* `resources.py` – shared constants such as mode codes and band lists
* `ui_main.py` – PyQt5 user interface
* `main.py` – application entry point
* `debug_power.py` – optional helper for logging raw CAT traffic
* `log_window.py` – dialog window for saving meter changes to a text file
* `meter_validator.py` – interactive script to compare observed meter
  readings with CAT responses

The UI polls the radio every 400 ms for the current frequency and only
queries meter values about once per second or when the frequency changes.
Power menus are populated dynamically based on the selected band.  Run the
application with `--debug` to print all bytes exchanged with the radio.  You
can optionally pass `--port` and `--baud` to open the serial connection
automatically.
Use the **Log** menu to open a window that records meter and power
changes to a chosen file for later analysis.  The helper script
`meter_validator.py` can be used to compare observed front-panel
readings with the CAT responses for troubleshooting.

This project is released under the MIT license.  See ``LICENSE`` for details.

