#!/usr/bin/env python3
"""
Test script to verify imports and basic functionality
"""

print("Testing imports...")

try:
    import sys
    print("✓ sys module imported")
except ImportError as e:
    print(f"✗ Failed to import sys: {e}")
    sys.exit(1)

try:
    import vlc
    print("✓ vlc module imported")
    print(f"  VLC version: {vlc.__version__}")
except ImportError as e:
    print(f"✗ Failed to import vlc: {e}")
    sys.exit(1)

try:
    from PyQt5.QtWidgets import QApplication
    print("✓ PyQt5.QtWidgets imported")
except ImportError as e:
    print(f"✗ Failed to import PyQt5: {e}")
    sys.exit(1)

try:
    from PyQt5.QtCore import Qt
    print("✓ PyQt5.QtCore imported")
except ImportError as e:
    print(f"✗ Failed to import PyQt5.QtCore: {e}")
    sys.exit(1)

try:
    from PyQt5.QtGui import QIcon
    print("✓ PyQt5.QtGui imported")
except ImportError as e:
    print(f"✗ Failed to import PyQt5.QtGui: {e}")
    sys.exit(1)

print("\nTesting VLC instance creation...")
try:
    instance = vlc.Instance()
    print("✓ VLC instance created successfully")
    player = instance.media_player_new()
    print("✓ VLC media player created successfully")
except Exception as e:
    print(f"✗ Failed to create VLC instance/player: {e}")
    sys.exit(1)

print("\nTesting radio station data structure...")
try:
    stations = {
        "Test Station": "https://example.com/stream.mp3"
    }
    print(f"✓ Station data structure works: {list(stations.keys())}")
except Exception as e:
    print(f"✗ Failed to create station structure: {e}")
    sys.exit(1)

print("\n" + "="*50)
print("All basic tests passed! ✓")
print("="*50)
print("\nNote: GUI testing requires a display environment.")
print("On Windows, run: python radio_player.py")
