# FT897

This repository provides a PyQt5 application to control the Yaesu FT‑897 transceiver via CAT commands. The band menu sets an appropriate mode (USB, LSB or FM) for each band automatically.

The 2 m and 70 cm bands include separate submenus so 144 MHz uses USB and 145 MHz uses FM. On the 10 m band, frequencies below 29 MHz default to USB while 29–29.7 MHz tune in FM.

## Recommended modes by band

| Band | Typical voice mode |
|------|--------------------|
|160 m|LSB|
|80 m|LSB|
|60 m|USB|
|40 m|LSB|
|30 m|CW/digital|
|20 m|USB|
|17 m|USB|
|15 m|USB|
|12 m|USB|
|10 m (<29 MHz)|USB|
|10 m (>=29 MHz)|FM|
|6 m (50–52 MHz)|USB|
|6 m (52–54 MHz)|FM|
|2 m 144 MHz|USB|
|2 m 145 MHz|FM|
|70 cm 432–434 MHz|USB|
|70 cm 434–440 MHz|FM|

Run the app with:

```bash
python3 main.py
```

The "Výkon" tab displays transmit power based on the radio's meter
reading. When the radio is idle the label shows ``0 W``. The S‑meter tab
continuously reflects the meter value so it updates during both
reception and transmission.
