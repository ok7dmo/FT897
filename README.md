# FT897 CAT Control

This repository contains a simple PyQt5 application for controlling the Yaesu FT-897 via its CAT interface. The program can display the current frequency and S-meter, provide PTT control, and offers band presets for quick tuning.  A "Módy" menu lets you change the modulation mode (USB, LSB, CW, AM, FM, etc.) while the "CAT příkazy" menu exposes common CAT commands including firmware version retrieval, VFO switching and split mode control.  Additional presets now include CB channels, PMR446, the airband and broadcast bands.

## Power control

According to the Yaesu CAT Operation Reference and the Hamlib implementation of the FT-897/857 protocol, the transceiver does **not** provide a command for setting the RF output power remotely. The output power must be adjusted manually on the radio. The application therefore only supports displaying power levels (when the radio reports them) but cannot change them.

The radio does accept CAT commands to power the transceiver off (`0x8F`) and back on (`0x0F`) as long as the CAT interface remains active. The "Zapnout rádio" and "Vypnout rádio" items in the "CAT příkazy" menu use these official commands. Ensure the CAT port stays powered after shutdown; otherwise the radio cannot be turned on remotely.

## PMR446 frequencies

PMR446 channels are included from 446.00625 MHz to 446.19375 MHz in 12.5 kHz steps (16 channels in total) and are tuned using FM mode.
