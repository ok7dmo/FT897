# FT897

This project provides a simple PyQt5 application to control the Yaesu FT-897 transceiver over a serial CAT interface.

The app can download the radio's memory channels via Clone Mode or from a
saved clone image file. Use **Paměti → Load memories from radio…** to read
directly from the transceiver, or **Paměti → Load memories from file…** to
open a `.img`/`.bin` file exported by other software. Parsed channels appear
under **Paměti → Radio**.

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
