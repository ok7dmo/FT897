import io
from ft897_single import (
    MemoryChannel,
    parse_image,
    build_image,
    export_json,
    import_json,
    export_csv,
    import_csv,
)


def test_roundtrip_image():
    ch = MemoryChannel(index=0, rx_freq_hz=144300000, tx_freq_hz=144300000, mode="USB", name="TEST")
    img = build_image([ch])
    parsed = parse_image(img)
    assert parsed[0].rx_freq_hz == 144300000
    assert parsed[0].name.strip() == "TEST"


def test_json_csv_roundtrip():
    channels = [MemoryChannel(index=1, rx_freq_hz=145500000, tx_freq_hz=145500000, mode="FM", name="CHAN")]
    buf = io.StringIO()
    export_json(channels, buf)
    buf.seek(0)
    ch_from_json = import_json(buf)
    assert ch_from_json[0].mode == "FM"

    buf = io.StringIO()
    export_csv(channels, buf)
    buf.seek(0)
    ch_from_csv = import_csv(buf)
    assert ch_from_csv[0].rx_freq_hz == 145500000
