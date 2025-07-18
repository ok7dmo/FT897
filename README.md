# FT897 CAT Control

This repository contains a simple PyQt5 application for controlling the Yaesu FT-897 via its CAT interface. The program can display the current frequency and S-meter, provide PTT control, and offers band presets for quick tuning.  A "Módy" menu lets you change the modulation mode (USB, LSB, CW, AM, FM, etc.) while the "CAT příkazy" menu exposes CAT commands including VFO switching, split mode control, lock and clarifier functions and CTCSS/DCS configuration.  The band menu now covers CB, PMR446, the airband, FM broadcast and several shortwave broadcast bands.

## Power control

According to the Yaesu CAT Operation Reference and the Hamlib implementation of the FT-897/857 protocol, the transceiver does **not** provide a command for setting the RF output power remotely. The output power must be adjusted manually on the radio. The application therefore only supports displaying power levels (when the radio reports them) but cannot change them. When the transceiver is keyed the program queries it using the TX status command (`0xF7`) and displays the returned power nibble as a percentage of the calibrated range for the current band.

## PMR446 frequencies

PMR446 channels are included from 446.00625 MHz to 446.19375 MHz in 12.5 kHz steps (16 channels in total) and are tuned using FM mode.
