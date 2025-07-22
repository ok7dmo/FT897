# FT897 CAT Control

This project provides CAT control utilities and a PyQt5 GUI for the Yaesu FT-897 transceiver.

## Clone mode

To transfer memories using CLONE:

1. Turn off the transceiver.
2. Hold **FAST** while powering on to enter CLONE mode.
3. Choose *Načíst z rádia…* in the application and press **SEND** on the radio.
4. To write an image back, choose *Nahrát do rádia…* and press **RCV** on the radio.

A simple CLI is also available:

```bash
python -m ft897.cli backup COM3 backup.img
python -m ft897.cli restore COM3 backup.img
python -m ft897.cli export backup.img memories.csv
```
