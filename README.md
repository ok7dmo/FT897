# FT897

This project provides a simple PyQt5 application to control the Yaesu FT-897 transceiver over a serial CAT interface.

The application offers several preset memory channels for quick tuning, including 2 m, FM broadcast and a new 70 cm entry "Rink" on 433.275 MHz with a transmit‑only CTCSS 88.5 Hz tone.
An "OK0B" repeater preset at 145.5875 MHz sends a transmit-only 77 Hz CTCSS tone with a -600 kHz shift.

## Requirements
Install dependencies using pip:

```
pip install -r requirements.txt
```

## Running
Execute the application with Python 3:

```
python app.py
```


## License
This project is released under the MIT License. See [LICENSE](LICENSE) for details.
