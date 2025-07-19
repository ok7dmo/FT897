# FT897 CAT Control

This repository contains a simple PyQt5 application for controlling the Yaesu FT-897 via its CAT interface. The program can display the current frequency, S-meter and power, provide PTT control, and offers band presets for quick tuning.  A "Módy" menu lets you change the modulation mode (USB, LSB, CW, AM, FM, etc.) while the "CAT příkazy" menu exposes CAT commands including VFO switching, split mode control, lock and clarifier functions and CTCSS/DCS configuration.  The band menu now covers CB, PMR446, the airband, FM broadcast and several shortwave broadcast bands.  The 15 m band spans the full 21.000–21.450 MHz range in USB mode, and the 70 cm band is split into a 432–434 MHz USB submenu and a 438–440 MHz FM submenu.  The SWR tab shows "High" only during transmission when the radio reports a VSWR alarm via the TX status byte.  A "Paměti" menu provides quick access to stored channels, including FM broadcast stations from the Kleť transmitter (Radiožurnál, Frekvence 1, Rock Radio, Rádio Beat, Rádio Impuls, Hitádio Faktor, Evropa 2 and ČRo České Budějovice).

## Power control

According to the Yaesu CAT Operation Reference and the Hamlib implementation of the FT‑897/857 protocol, the transceiver does **not** provide a command for setting the RF output power remotely. The output power must be adjusted manually on the radio. The application therefore only displays power levels. It continuously polls the radio’s TX status byte (`0xF7`) and when transmission is detected it converts the returned power nibble to a percentage of the calibrated range for the current band.

## PMR446 frequencies

PMR446 channels are included from 446.00625 MHz to 446.19375 MHz in 12.5 kHz steps (16 channels in total) and are tuned using FM mode.
