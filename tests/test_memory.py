import io
from ft897_single import (
    MemoryChannel,
    parse_image,
    build_image,
    verify_image,
    export_json,
    import_json,
    export_csv,
    import_csv,
)


def test_roundtrip_image():
    ch = MemoryChannel(
        index=0,
        rx_freq_hz=144300000,
        tx_freq_hz=144900000,
        mode="USB",
        offset_dir="+",
        offset_hz=600000,
        ctcss=5.3,
        step_hz=12500,
        name="TEST",
    )
    img = build_image([ch])
    ok, _ = verify_image(img)
    assert ok
    parsed = parse_image(img)
    p = parsed[0]
    assert p.tx_freq_hz == 144900000
    assert p.ctcss == 5.3
    assert p.offset_dir == "+"
    assert p.name.strip() == "TEST"


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
