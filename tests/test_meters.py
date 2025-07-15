import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from meters import format_smeter, format_power


def test_format_smeter():
    assert format_smeter(0) == "S0"
    assert format_smeter(16) == "S1"
    assert format_smeter(176) == "S9+10"


def test_format_power():
    assert format_power(255, "160 m") == "100 W"
    assert format_power(128, "2 m") == "25 W"
    assert format_power(0, "70 cm") == "0 W"
