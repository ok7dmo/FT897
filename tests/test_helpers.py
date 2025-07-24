import pytest
from helpers import format_smeter, band_label_from_khz

BANDS = [((1000, 2000), 'A'), ((2000, 3000), 'B')]

def test_format_smeter_range():
    assert format_smeter(0) == 'S0'
    assert format_smeter(9) == 'S9'
    assert format_smeter(10) == 'S9+10'
    assert format_smeter(None) == '---'

def test_band_label():
    assert band_label_from_khz(1500, BANDS) == 'A'
    assert band_label_from_khz(2500, BANDS) == 'B'
    assert 'Neznámé pásmo' in band_label_from_khz(5000, BANDS)
