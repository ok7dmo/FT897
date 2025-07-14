"""Utility functions for formatting meter values."""

from typing import Iterable


def format_smeter(raw_s: int) -> str:
    """Convert raw S-meter value (0-255) to a human-readable string."""
    thresholds = [16 * i for i in range(1, 10)]
    if raw_s < thresholds[0]:
        return "S0"
    for i, t in enumerate(thresholds[1:], start=1):
        if raw_s < t:
            return f"S{i}"
    extra_db = ((raw_s - thresholds[-1]) // 32) * 10
    return f"S9+{extra_db}"


def format_power(raw_p: int, band_label: str) -> str:
    """Return power reading in watts for the given band label."""
    if band_label in {
        "160 m",
        "80 m",
        "60 m",
        "40 m",
        "30 m",
        "20 m",
        "17 m",
        "15 m",
        "12 m",
        "10 m",
        "6 m",
    }:
        pmax = 100
    elif band_label == "2 m":
        pmax = 50
    elif band_label == "70 cm":
        pmax = 20
    else:
        return "---"
    watts = round(pmax * raw_p / 255)
    return f"{watts} W"
