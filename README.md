# FT897 CAT Control

This repository contains a simple PyQt5 application for controlling the Yaesu FT‑897 via its CAT interface. The program can display the current frequency and S‑meter, provide PTT control, and offers band presets for quick tuning.  A "CAT příkazy" menu exposes common CAT commands, such as switching modes or querying the radio firmware version.

## Power control

According to the Yaesu CAT Operation Reference and the Hamlib implementation of the FT‑897/857 protocol, the transceiver does **not** provide a command for setting the RF output power remotely. The output power must be adjusted manually on the radio. The application therefore only supports displaying power levels (when the radio reports them) but cannot change them.
