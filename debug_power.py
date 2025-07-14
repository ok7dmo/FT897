#!/usr/bin/env python3
"""Simple tool to log CAT traffic while polling power settings."""

import sys
import time
from cat_control import FT897CAT


def main():
    if len(sys.argv) < 2:
        print("Usage: debug_power.py <serial-port> [baudrate]")
        return
    port = sys.argv[1]
    baud = int(sys.argv[2]) if len(sys.argv) > 2 else 9600
    cat = FT897CAT(debug=True)
    if not cat.connect(port, baudrate=baud):
        print("Cannot connect to", port)
        return
    print("Connected. Press Ctrl-C to stop.")
    try:
        while True:
            block = cat.get_meter_block()
            if block is not None:
                hex_block = " ".join(f"{b:02X}" for b in block)
                print("Meter block:", hex_block)
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        cat.disconnect()


if __name__ == "__main__":
    main()
