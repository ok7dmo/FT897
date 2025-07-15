#!/usr/bin/env python3
"""Interactive tool for verifying S-meter and power readings."""

import sys

from cat_control import FT897CAT


def main():
    if len(sys.argv) < 2:
        print("Usage: meter_validator.py <serial-port> [baudrate]")
        return
    port = sys.argv[1]
    baud = int(sys.argv[2]) if len(sys.argv) > 2 else 9600
    cat = FT897CAT()
    if not cat.connect(port, baudrate=baud):
        print("Cannot connect to", port)
        return
    try:
        while True:
            try:
                s_input = input("Enter observed S-meter value (0-255 or q to quit): ")
            except EOFError:
                break
            if s_input.lower().startswith('q'):
                break
            try:
                expected_s = int(s_input)
            except ValueError:
                print("Invalid S-meter value")
                continue
            try:
                p_input = input("Enter observed power value (0-255 or q to quit): ")
            except EOFError:
                break
            if p_input.lower().startswith('q'):
                break
            try:
                expected_p = int(p_input)
            except ValueError:
                print("Invalid power value")
                continue
            s_val, p_val = cat.get_s_and_power()
            if s_val is None or p_val is None:
                print("Failed to read meters from radio")
                continue
            print(f"Radio: S={s_val} Power={p_val} | Entered: S={expected_s} Power={expected_p}")
            if s_val != expected_s or p_val != expected_p:
                print("Mismatch detected!")
            else:
                print("Values match.")
    finally:
        cat.disconnect()


if __name__ == "__main__":
    main()
