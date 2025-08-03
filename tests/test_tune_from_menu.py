import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QAction

app = QApplication.instance() or QApplication([])

import types
import pytest

from app import RadioControlApp


class DummyCAT:
    def __init__(self):
        self.calls = []
        self.is_connected = True

    def set_frequency(self, freq):
        self.calls.append(("freq", freq))
        return True

    def set_mode(self, mode):
        self.calls.append(("mode", mode))
        return True

    def set_repeater_offset_mode(self, mode):
        self.calls.append(("offset_mode", mode))
        return True

    def set_repeater_offset_frequency(self, freq):
        self.calls.append(("offset_freq", freq))
        return True

    def set_ctcss_dcs_mode(self, mode):
        self.calls.append(("ctcss_mode", mode))
        return True

    def set_ctcss_tone(self, tx, rx):
        self.calls.append(("ctcss_tone", tx, rx))
        return True

    def connect(self, port):
        self.calls.append(("connect", port))
        self.is_connected = True
        return True


def build_app():
    rc = RadioControlApp()
    rc.cat = DummyCAT()
    rc.status_thread = types.SimpleNamespace(isRunning=lambda: False, start=lambda: None,
                                             stop=lambda: None, wait=lambda: None)
    return rc


def trigger_action(rc, act):
    act.triggered.connect(rc.tune_from_menu)
    act.trigger()


def test_band_menu_tunes_frequency_and_mode():
    rc = build_app()
    act = QAction(rc)
    act.setData((145_500_000, "FM"))
    trigger_action(rc, act)
    assert ("freq", 145_500_000) in rc.cat.calls
    assert ("mode", "FM") in rc.cat.calls


def test_repeater_tx_only_ctcss_and_offset():
    rc = build_app()
    act = QAction(rc)
    act.setData({"freq": 145_587_500, "mode": "FM", "ctcss": 77.0, "offset": -600_000, "tx_only": True})
    act.setProperty("repeater", True)
    trigger_action(rc, act)
    assert ("offset_mode", "minus") in rc.cat.calls
    assert ("offset_freq", 600000) in rc.cat.calls
    assert ("ctcss_mode", "ctcss_enc") in rc.cat.calls
    assert ("ctcss_tone", 77.0, 0.0) in rc.cat.calls


def test_simplex_tx_only_ctcss():
    rc = build_app()
    act = QAction(rc)
    act.setData({"freq": 433_275_000, "mode": "FM", "ctcss": 88.5, "offset": 0, "tx_only": True})
    trigger_action(rc, act)
    assert ("offset_mode", "simplex") in rc.cat.calls
    assert ("offset_freq", 0) in rc.cat.calls
    assert ("ctcss_mode", "ctcss_enc") in rc.cat.calls
    assert ("ctcss_tone", 88.5, 0.0) in rc.cat.calls


def test_regular_memory_with_ctcss():
    rc = build_app()
    act = QAction(rc)
    act.setData({"freq": 145_500_000, "mode": "FM", "ctcss": 88.5})
    trigger_action(rc, act)
    assert ("ctcss_mode", "ctcss") in rc.cat.calls
    assert ("ctcss_tone", 88.5, 88.5) in rc.cat.calls
