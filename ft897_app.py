"""FT-897 CAT control GUI application.

Requirements:
    pip install pyserial PyQt5

PyInstaller packaging example:
    pyinstaller --onefile --windowed --add-data "<path_to_PyQt5>\\Qt5Core.dll;." ft897_app.py
"""

from main import main


if __name__ == "__main__":
    main()
