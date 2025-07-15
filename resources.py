"""Resource constants for FT-897 control UI."""

# Mode codes as per Yaesu CAT manual
MODE_CODES = {
    "LSB": 0x00,
    "USB": 0x01,
    "CW": 0x02,
    "CWR": 0x03,
    "AM": 0x04,
    "FM": 0x08,
    "DIG": 0x0A,
    "PKT": 0x0C,
    "FMN": 0x88,
}

# Reverse lookup from CAT mode codes to human readable names
MODE_NAMES = {v: k for k, v in MODE_CODES.items()}

# Frequency ranges in kHz mapped to band labels
band_definitions = [
    ((1800, 2000), "160 m"),
    ((3500, 3800), "80 m"),
    ((5250, 5450), "60 m"),
    ((7000, 7200), "40 m"),
    ((10100, 10150), "30 m"),
    ((14000, 14350), "20 m"),
    ((18068, 18168), "17 m"),
    ((21000, 21450), "15 m"),
    ((24890, 24990), "12 m"),
    ((28000, 29700), "10 m"),
    ((50000, 52000), "6 m"),
    ((70000, 70500), "4 m"),
    ((144000, 146000), "2 m"),
    ((430000, 440000), "70 cm"),
    ((76000, 108000), "FM rozhlas"),
    ((118000, 136975), "Letecké pásmo"),
    ((137000, 174000), "Rozšířený VHF RX"),
    ((420000, 470000), "UHF RX"),
]

# Default tuning points for the band selection menu
band_menu_items = [
    ("160 m", 1_850_000, MODE_CODES["LSB"]),
    ("80 m", 3_700_000, MODE_CODES["LSB"]),
    ("60 m", 5_357_000, MODE_CODES["USB"]),
    ("40 m", 7_100_000, MODE_CODES["LSB"]),
    ("30 m", 10_130_000, MODE_CODES["CW"]),
    ("20 m", 14_200_000, MODE_CODES["USB"]),
    ("17 m", 18_100_000, MODE_CODES["USB"]),
    ("15 m", 21_250_000, MODE_CODES["USB"]),
    ("12 m", 24_950_000, MODE_CODES["USB"]),
    ("10 m", 28_500_000, MODE_CODES["USB"]),
    ("6 m", 50_150_000, MODE_CODES["USB"]),
    ("4 m", 70_200_000, MODE_CODES["FM"]),
    ("2 m", 145_500_000, MODE_CODES["FM"]),
    ("70 cm", 433_500_000, MODE_CODES["FM"]),
    ("FM rozhlas", 100_000_000, MODE_CODES["FM"]),
    ("Letecké pásmo", 125_000_000, MODE_CODES["AM"]),
    ("Rozšířený VHF RX", 150_000_000, MODE_CODES["FM"]),
    ("UHF RX", 440_000_000, MODE_CODES["FM"]),
]
