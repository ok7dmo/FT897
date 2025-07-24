from __future__ import annotations


def format_smeter(raw: int | None) -> str:
    """Return textual representation from raw S-meter value (0-15)."""
    if raw is None:
        return "---"
    if raw <= 9:
        return f"S{raw}"
    db = (raw - 9) * 10
    return f"S9+{db}"


def band_label_from_khz(freq_khz: float, definitions) -> str:
    """Return label for frequency from band definition list."""
    for (start, end), label in definitions:
        if start <= freq_khz <= end:
            return label
    return f"Neznámé pásmo ({freq_khz/1000:.5f} MHz)"
