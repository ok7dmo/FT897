#!/usr/bin/env python3
import sys
import subprocess

required = ["pyserial", "PyQt5"]
for module in required:
    try:
        __import__(module)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", module])

from ft897control.ui import main

if __name__ == "__main__":
    main()
