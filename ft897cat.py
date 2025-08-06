#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import time
import threading
import logging
import subprocess
import shutil
import os
import serial
from pathlib import Path
from typing import Dict, Optional, Tuple

# Try to import Hamlib bindings for faster, in-process CAT control.
# Fall back to rigctl subprocess calls if the bindings are unavailable.
try:  # pragma: no cover - environment dependent
    import Hamlib  # type: ignore
except Exception:  # pragma: no cover - Hamlib may not be installed
    try:
        sys.path.append('/usr/lib/python3/dist-packages')
        import Hamlib  # type: ignore
    except Exception:  # pragma: no cover
        Hamlib = None  # type: ignore

from serial.tools import list_ports

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton,
    QComboBox, QAction, QSizePolicy, QFontDialog,
    QDialog, QRadioButton, QDialogButtonBox, QTabWidget, QFrame,
    QInputDialog, QMessageBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QFontMetrics


# Configure basic logging to a file in the user's home directory
LOG_PATH = Path.home() / ".ft897cat.log"
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def format_smeter(raw: Optional[int]) -> str:
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


class CATError(Exception):
    """Base exception for CAT control errors."""


class FT897CAT:
    """CAT control for the Yaesu FT-897 via the rigctl utility."""

    MODE_MAP: Dict[str, str] = {
        "LSB": "LSB",
        "USB": "USB",
        "CW": "CW",
        "CWR": "CWR",
        "AM": "AM",
        "FM": "FM",
        "DIG": "DIG",
    }

    def __init__(self) -> None:
        self.port: Optional[str] = None
        self.baudrate: int = 9600
        self.is_connected: bool = False
        self.ptt_active: bool = False
        self.rigctl_path: Optional[str] = None
        self.last_error: Optional[str] = None
        self._lock = threading.Lock()
        self.use_hamlib: bool = Hamlib is not None
        self._rig = None
        self._proc: Optional[subprocess.Popen] = None
        if self.use_hamlib:
            try:  # pragma: no cover - depends on Hamlib availability
                Hamlib.rig_set_debug(Hamlib.RIG_DEBUG_NONE)
                self._rig = Hamlib.Rig(1023)
            except Exception as e:  # pragma: no cover
                logging.getLogger(__name__).warning('Hamlib init failed: %s', e)
                self.use_hamlib = False

    def _find_rigctl_path(self) -> str:
        path = shutil.which("rigctl")
        if path:
            return path
        cand = r"C:\Program Files\hamlib-w64-4.6.3\bin\rigctl.exe"
        if os.path.isfile(cand):
            return cand
        raise FileNotFoundError(
            "rigctl executable not found; expected at C:\\Program Files\\hamlib-w64-4.6.3\\bin\\rigctl.exe"
        )

    def _run(self, *args: str):
        if self._proc is None or self._proc.poll() is not None:
            self.last_error = 'rigctl process not running'
            return None
        try:
            cmd = ' '.join(args) + '\n'
            assert self._proc.stdin and self._proc.stdout
            self._proc.stdin.write(cmd)
            self._proc.stdin.flush()
            out = self._proc.stdout.readline()
            self.last_error = None
            class _Res:
                def __init__(self, s: str):
                    self.stdout = s
            return _Res(out)
        except Exception as e:
            self.last_error = str(e)
            logging.getLogger(__name__).warning('rigctl command failed: %s', self.last_error)
            return None

    def _clear_buffers(self) -> None:
        """Flush serial port buffers to improve responsiveness."""
        if not self.port:
            return
        try:
            with serial.Serial(self.port, self.baudrate, timeout=0) as sp:
                sp.reset_input_buffer()
                sp.reset_output_buffer()
        except Exception as e:
            logging.getLogger(__name__).warning('Buffer clear failed: %s', e)

    def connect(self, port: str, baudrate: int = 9600) -> bool:
        """Connect to ``port`` using a fixed 9600 bps CAT speed."""
        self.port = port
        self.baudrate = 9600
        if self.use_hamlib and self._rig is not None:
            try:  # pragma: no cover - depends on Hamlib
                self._rig.set_conf("rig_pathname", port)
                self._rig.set_conf("serial_speed", str(self.baudrate))
                self._rig.open()
                self.is_connected = True
                logging.getLogger(__name__).info(
                    'Connected via Hamlib to %s at %d bps', port, self.baudrate
                )
                return True
            except Exception as e:  # pragma: no cover
                self.last_error = str(e)
                logging.getLogger(__name__).warning('Hamlib connect failed: %s', e)
                self.is_connected = False
        try:
            if not self.rigctl_path:
                self.rigctl_path = self._find_rigctl_path()
            cmd = [self.rigctl_path, '-m', '1023', '-n']
            if self.port:
                cmd += ['-r', self.port]
            if self.baudrate:
                cmd += ['-s', str(self.baudrate)]
            self._proc = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            self.is_connected = True
            logging.getLogger(__name__).info('Connected to %s at %d bps', port, self.baudrate)
            return True
        except Exception as e:
            self.last_error = str(e)
            logging.getLogger(__name__).warning('rigctl start failed: %s', e)
            self.is_connected = False
            return False

    def disconnect(self) -> None:
        if self.use_hamlib and self._rig is not None:
            try:  # pragma: no cover
                self._rig.close()
            except Exception:
                pass
        if self._proc is not None:
            try:
                self._proc.terminate()
            except Exception:
                pass
            self._proc = None
        self.is_connected = False
        logging.getLogger(__name__).info('Disconnected')

    def get_frequency(self) -> Optional[int]:
        if not self.is_connected:
            return None
        if self.use_hamlib and self._rig is not None:
            try:  # pragma: no cover
                return int(self._rig.get_freq())
            except Exception as e:
                logging.getLogger(__name__).warning('Neplatná frekvence: %s', e)
                return None
        res = self._run('get_freq')
        if res and res.stdout.strip():
            try:
                return int(float(res.stdout.strip()))
            except ValueError:
                logging.getLogger(__name__).warning('Neplatná frekvence: %s', res.stdout.strip())
        return None

    def set_frequency(self, freq_hz: int) -> bool:
        if not self.is_connected:
            return False
        if self.use_hamlib and self._rig is not None:
            try:  # pragma: no cover
                self._rig.set_freq(freq_hz)
                return True
            except Exception as e:
                logging.getLogger(__name__).warning('Hamlib set_freq failed: %s', e)
                return False
        self._clear_buffers()
        return self._run('set_freq', str(freq_hz)) is not None

    def set_mode(self, mode: str) -> bool:
        if not self.is_connected:
            return False
        if self.use_hamlib and self._rig is not None:
            try:  # pragma: no cover
                ham_mode = getattr(Hamlib, f'RIG_MODE_{mode}')
            except AttributeError:
                return False
            try:
                self._rig.set_mode(ham_mode)
                return True
            except Exception as e:
                logging.getLogger(__name__).warning('Hamlib set_mode failed: %s', e)
                return False
        if mode not in self.MODE_MAP:
            return False
        return self._run('set_mode', mode, '0') is not None

    def ptt_on(self) -> bool:
        if not self.is_connected:
            return False
        if self.use_hamlib and self._rig is not None:
            try:  # pragma: no cover
                self._rig.set_ptt(1)
                self.ptt_active = True
                return True
            except Exception as e:
                logging.getLogger(__name__).warning('Hamlib set_ptt failed: %s', e)
        if self._run('set_ptt', '1'):
            self.ptt_active = True
            return True
        return False

    def ptt_off(self) -> bool:
        if not self.is_connected:
            return False
        if self.use_hamlib and self._rig is not None:
            try:  # pragma: no cover
                self._rig.set_ptt(0)
                self.ptt_active = False
                return True
            except Exception as e:
                logging.getLogger(__name__).warning('Hamlib set_ptt failed: %s', e)
        if self._run('set_ptt', '0'):
            self.ptt_active = False
            return True
        return False

    def get_smeter(self) -> Optional[int]:
        if not self.is_connected:
            return None
        if self.use_hamlib and self._rig is not None:
            try:  # pragma: no cover
                val = self._rig.get_level(Hamlib.RIG_LEVEL_STRENGTH)
                if val is not None:
                    return int(round(float(val)))
            except Exception as e:
                logging.getLogger(__name__).warning('Neplatná hodnota S-měru: %s', e)
                return None
        res = self._run('get_level', 'RF')
        if res and res.stdout.strip():
            try:
                return int(float(res.stdout.strip()))
            except ValueError:
                logging.getLogger(__name__).warning('Neplatná hodnota S-měru: %s', res.stdout.strip())
        return None

    def read_tx_status(self) -> Optional[int]:
        if not self.is_connected:
            return None
        if self.use_hamlib and self._rig is not None:
            try:  # pragma: no cover
                ptt_on = bool(self._rig.get_ptt())
                if not ptt_on:
                    return 0x80
                level = self._rig.get_level(Hamlib.RIG_LEVEL_RFPOWER_METER_WATTS)
                lvl = 0
                if level is not None:
                    try:
                        lvl = int(round(float(level) / 6.667))
                    except Exception:
                        lvl = 0
                return max(0, min(lvl, 15))
            except Exception as e:
                logging.getLogger(__name__).warning('Hamlib read_tx_status failed: %s', e)
                return None
        ptt_res = self._run('get_ptt')
        if not ptt_res or not ptt_res.stdout.strip():
            return None
        ptt_on = ptt_res.stdout.strip() == '1'
        if not ptt_on:
            return 0x80
        power_res = self._run('get_level', 'TX_POWER')
        level = 0
        if power_res and power_res.stdout.strip():
            try:
                level = int(round(float(power_res.stdout.strip()) / 6.667))
            except ValueError:
                logging.getLogger(__name__).warning('Neplatná hodnota výkonu: %s', power_res.stdout.strip())
        return max(0, min(level, 15))

    def get_power_level(self) -> Optional[int]:
        status = self.read_tx_status()
        if status is None or status & 0x80:
            return None
        return status & 0x0F

    def get_swr(self, tx_status: Optional[int] = None) -> Optional[int]:
        if not self.is_connected:
            return None
        if self.use_hamlib and self._rig is not None:
            try:  # pragma: no cover
                val = self._rig.get_level(Hamlib.RIG_LEVEL_SWR)
                if val is not None:
                    try:
                        return 1 if float(val) >= 3.0 else 0
                    except Exception:
                        pass
            except Exception as e:
                logging.getLogger(__name__).warning('Neplatné SWR: %s', e)
                return None
        res = self._run('get_level', 'SWR')
        if res and res.stdout.strip():
            try:
                val = float(res.stdout.strip())
                return 1 if val >= 3.0 else 0
            except ValueError:
                logging.getLogger(__name__).warning('Neplatné SWR: %s', res.stdout.strip())
        return None

    def toggle_vfo(self) -> bool:
        if not self.is_connected:
            return False
        res = self._run('get_vfo')
        if not res or not res.stdout.strip():
            return False
        cur = res.stdout.strip().upper()
        new = 'VFOB' if cur == 'VFOA' else 'VFOA'
        return self._run('set_vfo', new) is not None

    def split_on(self) -> bool:
        if not self.is_connected:
            return False
        return self._run('set_split', '1') is not None

    def split_off(self) -> bool:
        if not self.is_connected:
            return False
        return self._run('set_split', '0') is not None

    def lock_on(self) -> bool:
        if not self.is_connected:
            return False
        return self._run('set_lock', '1') is not None

    def lock_off(self) -> bool:
        if not self.is_connected:
            return False
        return self._run('set_lock', '0') is not None

    def clar_on(self) -> bool:
        if not self.is_connected:
            return False
        return self._run('set_rit', '1') is not None

    def clar_off(self) -> bool:
        if not self.is_connected:
            return False
        return self._run('set_rit', '0') is not None

    def set_clar_frequency(self, offset_hz: int, sign: int = 1) -> bool:
        if not self.is_connected:
            return False
        val = sign * offset_hz
        return self._run('set_rit', str(val)) is not None

    def set_repeater_offset_mode(self, mode: str) -> bool:
        if not self.is_connected:
            return False
        mapping = {'minus': '-', 'plus': '+', 'simplex': '0'}
        shift = mapping.get(mode)
        if shift is None:
            return False
        return self._run('set_rptr_shift', shift) is not None

    def set_repeater_offset_frequency(self, freq_hz: int) -> bool:
        if not self.is_connected:
            return False
        return self._run('set_rptr_offs', str(freq_hz)) is not None

    def get_repeater_offset_mode(self) -> Optional[str]:
        if not self.is_connected:
            return None
        res = self._run('get_rptr_shift')
        if res and res.stdout.strip():
            mapping = {'-': 'minus', '+': 'plus', '0': 'simplex'}
            return mapping.get(res.stdout.strip())
        return None

    def apply_repeater_settings(self, offset_hz: int, tone_hz: Optional[float] = None, tx_only: bool = False) -> None:
        if not self.is_connected:
            return
        shift = '-' if offset_hz < 0 else '+' if offset_hz > 0 else '0'
        self._run('set_rptr_shift', shift)
        self._run('set_rptr_offs', str(abs(offset_hz)))
        if tone_hz is not None:
            self._run('set_ctcss_mode', 'TONE' if tx_only else 'TSQL')
            self._run('set_ctcss_tone', str(int(round(tone_hz))))
        else:
            self._run('set_ctcss_mode', 'OFF')

    def set_ctcss_dcs_mode(self, mode: str) -> bool:
        if not self.is_connected:
            return False
        mapping = {
            'dcs': 'DCS',
            'ctcss': 'TSQL',
            'ctcss_dec': 'CTCSS',
            'ctcss_enc': 'TONE',
            'off': 'OFF',
        }
        arg = mapping.get(mode)
        if arg is None:
            return False
        return self._run('set_ctcss_mode', arg) is not None

    def set_ctcss_tone(self, tone_hz: float) -> bool:
        if not self.is_connected:
            return False
        return self._run('set_ctcss_tone', str(int(round(tone_hz)))) is not None

    def set_dcs_code(self, tx_code: int, rx_code: int) -> bool:
        if not self.is_connected:
            return False
        ok1 = self._run('set_dcs_code', str(tx_code)) is not None
        ok2 = self._run('set_dcs_code', str(rx_code)) is not None
        return ok1 and ok2

class StatusThread(QThread):
    status_updated = pyqtSignal(int, int, int, int)

    def __init__(self, cat: FT897CAT):
        super().__init__()
        self.cat = cat
        self._fails = 0

    def run(self):
        while not self.isInterruptionRequested():
            try:
                freq = -1
                sm = -1
                power = -1
                swr_val = -1
                if self.cat.is_connected:
                    f = self.cat.get_frequency()
                    if f is not None:
                        freq = f
                    s = self.cat.get_smeter()
                    if s is not None:
                        sm = s
                    status = self.cat.read_tx_status()
                    if status is not None and (status & 0x80) == 0:
                        power = status & 0x0F
                        swr = self.cat.get_swr(status)
                        if swr is not None:
                            swr_val = swr
                    self._fails = 0
                else:
                    self._fails += 1
                if self._fails >= 3 and self.cat.port:
                    self.cat.disconnect()
                    self.cat.connect(self.cat.port)
                    self._fails = 0
                self.status_updated.emit(freq, sm, power, swr_val)
            except Exception as e:
                logger.error("Status thread error: %s", e)
                self._fails += 1
                if self._fails >= 3 and self.cat.port:
                    self.cat.disconnect()
                    self.cat.connect(self.cat.port)
                    self._fails = 0
            self.msleep(1000)

    def stop(self):
        self.requestInterruption()


class RadioControlApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cat = FT897CAT()
        self.status_thread = StatusThread(self.cat)
        self.status_thread.status_updated.connect(self.update_status)
        self.status_thread.finished.connect(lambda: self.update_connection_indicator(False))

        self.ptt_heartbeat = QTimer(self)
        self.ptt_heartbeat.setInterval(100)
        self.ptt_heartbeat.timeout.connect(self.cat.ptt_on)

        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.setInterval(200)
        self.resize_timer.timeout.connect(self.adjust_all_fonts)

        self._font_cache: Dict[Tuple[str, int, int, str], QFont] = {}

        self.current_font_family = "Courier New"
        self.freq_text = "---"
        self.current_theme = "dark"
        self.last_valid_frequency = None

        # Define frequency ranges and default modes
        self.band_configs = {
            "160 m": {"range": (1_800_000, 2_000_000), "step": 1000, "mode": "LSB"},
            "80 m": {"range": (3_500_000, 3_799_000), "step": 1000, "mode": "LSB"},
            "60 m": {"list": [5_357_000, 5_371_500], "mode": "USB"},
            "40 m": {"range": (7_000_000, 7_200_000), "step": 1000, "mode": "LSB"},
            "30 m": {"range": (10_100_000, 10_150_000), "step": 1000, "mode": "USB"},
            "20 m": {"range": (14_000_000, 14_350_000), "step": 1000, "mode": "USB"},
            "17 m": {"range": (18_068_000, 18_168_000), "step": 1000, "mode": "USB"},
            "15 m": {"range": (21_000_000, 21_450_000), "step": 1000, "mode": "USB"},
            "12 m": {"range": (24_890_000, 24_990_000), "step": 1000, "mode": "USB"},
            "10 m": {"list": [28_070_000, 28_074_000, 28_400_000], "mode": "USB"},
            "6 m": {"range": (50_000_000, 54_000_000), "step": 5000, "mode": "USB"},
            "FM rozhlas": {"range": (87_500_000, 108_000_000), "step": 100_000, "mode": "FM"},
            "2 m": {"submenus": {
                "144 MHz": {"range": (144_000_000, 144_400_000), "step": 1000, "mode": "USB"},
                "145 MHz": {"range": (145_000_000, 145_800_000), "step": 12500, "mode": "FM"}
            }},
            "70 cm": {"submenus": {
                "432 MHz": {"range": (432_000_000, 434_000_000), "step": 1000, "mode": "USB"},
                "438 MHz": {"range": (438_000_000, 440_000_000), "step": 12500, "mode": "FM"}
            }},
            "CB": {"range": (26_965_000, 27_405_000), "step": 10000, "mode": "AM"},
            "Letecké": {"range": (118_000_000, 137_000_000), "step": 25000, "mode": "AM"},
            "AM rozhlas": {"range": (500_000, 1_700_000), "step": 10000, "mode": "AM"},
            "PMR446": {"range": (446_006_250, 446_193_750), "step": 12500, "mode": "FM"},
            "SW 120 m": {"range": (2_300_000, 2_495_000), "step": 5000, "mode": "AM"},
            "SW 90 m": {"range": (3_200_000, 3_400_000), "step": 5000, "mode": "AM"},
            "SW 75 m": {"range": (3_900_000, 4_000_000), "step": 5000, "mode": "AM"},
            "SW 60 m": {"range": (4_750_000, 5_000_000), "step": 5000, "mode": "AM"},
            "SW 49 m": {"range": (5_900_000, 6_200_000), "step": 5000, "mode": "AM"},
            "SW 41 m": {"range": (7_200_000, 7_600_000), "step": 5000, "mode": "AM"},
            "SW 31 m": {"range": (9_400_000, 10_000_000), "step": 5000, "mode": "AM"},
            "SW 25 m": {"range": (11_600_000, 12_100_000), "step": 5000, "mode": "AM"},
            "SW 22 m": {"range": (13_570_000, 13_870_000), "step": 5000, "mode": "AM"},
            "SW 19 m": {"range": (15_100_000, 15_800_000), "step": 5000, "mode": "AM"},
            "SW 16 m": {"range": (17_480_000, 17_900_000), "step": 5000, "mode": "AM"},
            "SW 13 m": {"range": (21_450_000, 21_850_000), "step": 5000, "mode": "AM"},
            "SW 11 m": {"range": (25_670_000, 26_100_000), "step": 5000, "mode": "AM"},
        }

        self.memory_presets = {
            "FM rozhlas": [
                ("Evropa 2 – Kleť", 105_500_000, "FM"),
                ("ČRo Radiožurnál – Kleť", 91_100_000, "FM"),
                ("Frekvence 1 – Kleť", 94_100_000, "FM"),
                ("Rock Radio – Kleť", 99_700_000, "FM"),
                ("Rádio Beat – Kleť", 101_000_000, "FM"),
                ("Rádio Impuls – Kleť", 102_900_000, "FM"),
                ("Hitrádio Faktor – Kleť", 104_300_000, "FM"),
                ("ČRo Dvojka", 103_200_000, "FM"),
                ("Radio Niederösterreich", 95_700_000, "FM"),
                ("Ö1", 92_700_000, "FM"),
                ("FM4", 101_400_000, "FM"),
                ("Metro Life Radio", 100_800_000, "FM"),
                ("Ö1 – Jauerling", 97_500_000, "FM"),
                ("ČRo Plus", 95_400_000, "FM"),
                ("Frekvence 1 – Jihlava Strážník", 93_400_000, "FM"),
                ("Rádio Kiss", 97_700_000, "FM"),
                ("ČRo České Budějovice – Kleť", 106_400_000, "FM"),
                ("ČRo Radiožurnál – Votice Mezivrata", 93_100_000, "FM"),
                ("Country Radio", 92_000_000, "FM"),
            ],
            "CB kanály": [
                (f"CB {i}", 26_965_000 + (i - 1) * 10_000, "AM")
                for i in range(1, 81)
            ],
            "PMR446": [
                (f"Kanál {i+1}", 446_006_250 + i * 12_500, "FM") for i in range(16)
            ],
            "2 m": [
                ("145.500 FM", 145_500_000, "FM"),
                ("JČ direkt", 145_400_000, "FM"),
                ("144.300 USB", 144_300_000, "USB"),
            ],
            "70 cm": [
                # Rink simplex channel with TX-only CTCSS 88.5 Hz and no offset
                ("Rink", 433_275_000, "FM", 88.5, None, True),
            ],
            "Převaděče": [
                # OK0G repeater with fixed -600 kHz shift and TX-only CTCSS
                ("OK0G", 145_587_500, "FM", 77.0, -600_000, True),
            ],
        }

        self.band_max_power = {
            "160 m": 100,
            "80 m": 100,
            "60 m": 100,
            "40 m": 100,
            "30 m": 100,
            "20 m": 100,
            "17 m": 100,
            "15 m": 100,
            "12 m": 100,
            "10 m": 100,
            "6 m": 100,
            "2 m": 50,
            "70 cm": 20,
        }

        self.band_min_power = {
            band: 5 for band in self.band_max_power
        }

        self.band_power_calibration = {
            "160 m": {"min_raw": 1, "max_raw": 15},
            "80 m": {"min_raw": 1, "max_raw": 15},
            "60 m": {"min_raw": 1, "max_raw": 15},
            "40 m": {"min_raw": 1, "max_raw": 15},
            "30 m": {"min_raw": 1, "max_raw": 15},
            "20 m": {"min_raw": 1, "max_raw": 15},
            "17 m": {"min_raw": 1, "max_raw": 15},
            "15 m": {"min_raw": 1, "max_raw": 15},
            "12 m": {"min_raw": 1, "max_raw": 15},
            "10 m": {"min_raw": 1, "max_raw": 15},
            "6 m": {"min_raw": 1, "max_raw": 15},
            "2 m": {"min_raw": 2, "max_raw": 7},
            "70 cm": {"min_raw": 2, "max_raw": 7},
        }

        self.band_power_curve = {
            "2 m": {
                2: 5,
                3: 14,
                4: 23,
                5: 34,
                6: 43,
                7: 50,
            },
        }

        self.band_definitions = [
            ((87500, 108000), "FM rozhlas"),
            ((108000, 137000), "Letecké pásmo"),
            ((446000, 446200), "PMR446"),
            ((148, 283), "DLF/Morze"),
        ]
        for band, cfg in self.band_configs.items():
            if "range" in cfg:
                start, end = cfg["range"]
            elif "list" in cfg:
                start, end = min(cfg["list"]), max(cfg["list"])
            elif "submenus" in cfg:
                ranges = []
                for subcfg in cfg["submenus"].values():
                    if "range" in subcfg:
                        ranges.append(subcfg["range"])
                    elif "list" in subcfg:
                        ranges.append((min(subcfg["list"]), max(subcfg["list"])) )
                if ranges:
                    start = min(r[0] for r in ranges)
                    end = max(r[1] for r in ranges)
                else:
                    continue
            else:
                continue
            self.band_definitions.append(((start / 1000, end / 1000), band))

        self.init_ui()
        self.apply_stylesheet(self.current_theme)

    def init_ui(self):
        self.setWindowTitle("FT-897 CAT Control")
        self.setGeometry(100, 100, 800, 400)

        self.central = QWidget()
        self.setCentralWidget(self.central)
        self.layout = QVBoxLayout(self.central)

        self.port_combo = QComboBox()
        ports = list_ports.comports()
        for port in ports:
            self.port_combo.addItem(port.device)
        self.layout.addWidget(self.port_combo)

        self.connect_btn = QPushButton("Připojit")
        self.connect_btn.clicked.connect(self.toggle_connection)
        self.connect_btn.setShortcut("Ctrl+K")
        self.layout.addWidget(self.connect_btn)

        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        self.freq_tab = QWidget()
        self.freq_layout = QVBoxLayout(self.freq_tab)

        self.freq_label = QLabel(self.freq_text)
        self.freq_label.setAlignment(Qt.AlignCenter)
        self.freq_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.freq_label.setFont(QFont(self.current_font_family, 10, QFont.Bold))
        self.freq_layout.addWidget(self.freq_label)

        self.band_label = QLabel("")
        self.band_label.setAlignment(Qt.AlignCenter)
        self.band_label.setStyleSheet("font-size: 18px;")
        self.freq_layout.addWidget(self.band_label)

        self.tabs.addTab(self.freq_tab, "Frekvence")

        self.smeter_tab = QWidget()
        self.smeter_layout = QVBoxLayout(self.smeter_tab)

        self.smeter_desc_label = QLabel("S-metr:")
        self.smeter_desc_label.setAlignment(Qt.AlignCenter)
        self.smeter_layout.addWidget(self.smeter_desc_label)

        self.smeter_value_label = QLabel("---")
        self.smeter_value_label.setAlignment(Qt.AlignCenter)
        self.smeter_value_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.smeter_value_label.setFont(QFont(self.current_font_family, 10, QFont.Bold))
        self.smeter_layout.addWidget(self.smeter_value_label)

        self.tabs.addTab(self.smeter_tab, "S-metr")

        self.swr_tab = QWidget()
        self.swr_layout = QVBoxLayout(self.swr_tab)

        self.swr_label = QLabel("SWR: ---")
        self.swr_label.setAlignment(Qt.AlignCenter)
        self.swr_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.swr_layout.addWidget(self.swr_label)

        self.tabs.addTab(self.swr_tab, "SWR")

        self.power_tab = QWidget()
        self.power_layout = QVBoxLayout(self.power_tab)
        self.power_label = QLabel("Výkon: ---")
        self.power_label.setAlignment(Qt.AlignCenter)
        self.power_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.power_label.setFont(QFont(self.current_font_family, 10, QFont.Bold))
        self.power_layout.addWidget(self.power_label)

        self.tabs.addTab(self.power_tab, "Výkon")


        self.ptt_container = QFrame()
        self.ptt_layout = QVBoxLayout(self.ptt_container)
        self.ptt_btn = QPushButton("PTT")
        self.ptt_btn.setFont(QFont("Arial", 20, QFont.Bold))
        self.ptt_btn.setCheckable(True)
        self.ptt_btn.pressed.connect(self.handle_ptt_on)
        self.ptt_btn.released.connect(self.handle_ptt_off)
        self.ptt_btn.setEnabled(False)
        self.ptt_btn.setShortcut("Space")
        self.ptt_layout.addWidget(self.ptt_btn)
        self.layout.addWidget(self.ptt_container)

        self.init_menu()

        self.status_led = QLabel()
        self.status_led.setFixedSize(12, 12)
        self.status_led.setStyleSheet("background-color: #800; border-radius: 6px;")
        self.status_text = QLabel("Odpojeno")
        bar = self.statusBar()
        bar.addPermanentWidget(self.status_led)
        bar.addPermanentWidget(self.status_text)

        if self.port_combo.count() == 1:
            QTimer.singleShot(0, self.toggle_connection)

        self.resize_timer.start()

    def init_menu(self):
        menubar = self.menuBar()
        menubar.setStyleSheet(
            """
            QMenuBar {
                background-color: #333;
                color: white;
                font-weight: bold;
                font-size: 16px;
            }
            QMenuBar::item {
                background: transparent;
                padding: 6px 20px;
            }
            QMenuBar::item:selected {
                background: #555;
                color: yellow;
            }
            QMenu {
                background-color: #222;
                color: white;
                font-size: 15px;
            }
            QMenu::item {
                padding: 6px 24px;
            }
            QMenu::item:selected {
                background-color: #444;
                color: yellow;
            }
        """
        )
        view_menu = menubar.addMenu("Zobrazení")

        band_menu = menubar.addMenu("Pásma")
        for band, cfg in self.band_configs.items():
            if "submenus" in cfg:
                parent = band_menu.addMenu(band)
                for subname, subcfg in cfg["submenus"].items():
                    sub = parent.addMenu(subname)
                    if "list" in subcfg:
                        freqs = subcfg["list"]
                    else:
                        start, end = subcfg["range"]
                        step = subcfg.get("step", 1000)
                        freqs = list(range(start, end + 1, step))
                    for f in freqs:
                        label = f"{f/1_000_000:.3f} MHz"
                        act = QAction(label, self)
                        act.setData((int(f), subcfg["mode"]))
                        act.triggered.connect(self.tune_from_menu)
                        sub.addAction(act)
            else:
                sub = band_menu.addMenu(band)
                if "list" in cfg:
                    freqs = cfg["list"]
                else:
                    start, end = cfg["range"]
                    step = cfg.get("step", 1000)
                    freqs = list(range(start, end + 1, step))
                for f in freqs:
                    label = f"{f/1_000_000:.3f} MHz"
                    act = QAction(label, self)
                    act.setData((int(f), cfg["mode"]))
                    act.triggered.connect(self.tune_from_menu)
                    sub.addAction(act)

        self.memory_menu = menubar.addMenu("Paměti")
        for group, memories in self.memory_presets.items():
            sub = self.memory_menu.addMenu(group)
            for mem in memories:
                if len(mem) < 3:
                    continue
                label, freq, mode = mem[:3]
                ctcss = mem[3] if len(mem) >= 4 else None
                offset = mem[4] if len(mem) >= 5 else None
                tx_only = bool(mem[5]) if len(mem) >= 6 else False
                act = QAction(f"{label} ({freq/1_000_000:.3f} MHz)", self)
                payload = {"freq": int(freq), "mode": mode}
                if ctcss is not None:
                    payload["ctcss"] = ctcss
                if offset is not None:
                    payload["offset"] = offset
                if tx_only:
                    payload["tx_only"] = True
                act.setData(payload)
                if group == "Převaděče":
                    act.setProperty("repeater", True)
                act.triggered.connect(self.tune_from_menu)
                sub.addAction(act)
        font_action = QAction("Nastavit písmo…", self)
        font_action.triggered.connect(self.choose_font)
        view_menu.addAction(font_action)

        color_scheme_action = QAction("Nastavit barevné schéma…", self)
        color_scheme_action.triggered.connect(self.choose_color_scheme)
        view_menu.addAction(color_scheme_action)

        self.verbose_action = QAction("Verbose log", self, checkable=True)
        self.verbose_action.toggled.connect(self.toggle_verbose)
        view_menu.addAction(self.verbose_action)

        mode_menu = menubar.addMenu("Módy")
        for mode in ["LSB", "USB", "CW", "CWR", "AM", "FM", "DIG"]:
            act = QAction(mode, self)
            act.triggered.connect(lambda _, m=mode: self.cat.set_mode(m))
            mode_menu.addAction(act)

        cat_menu = menubar.addMenu("CAT příkazy")

        vfo_action = QAction("Přepnout VFO A/B", self)
        vfo_action.triggered.connect(self.cat.toggle_vfo)
        cat_menu.addAction(vfo_action)

        split_on = QAction("Split ON", self)
        split_on.triggered.connect(self.cat.split_on)
        cat_menu.addAction(split_on)

        split_off = QAction("Split OFF", self)
        split_off.triggered.connect(self.cat.split_off)
        cat_menu.addAction(split_off)

        cat_menu.addSeparator()

        lock_on = QAction("LOCK ON", self)
        lock_on.triggered.connect(self.cat.lock_on)
        cat_menu.addAction(lock_on)

        lock_off = QAction("LOCK OFF", self)
        lock_off.triggered.connect(self.cat.lock_off)
        cat_menu.addAction(lock_off)

        clar_on = QAction("CLAR ON", self)
        clar_on.triggered.connect(self.cat.clar_on)
        cat_menu.addAction(clar_on)

        clar_off = QAction("CLAR OFF", self)
        clar_off.triggered.connect(self.cat.clar_off)
        cat_menu.addAction(clar_off)

        clar_freq = QAction("Nastavit CLAR offset…", self)
        clar_freq.triggered.connect(self.prompt_clar_offset)
        cat_menu.addAction(clar_freq)

        rpt_minus = QAction("Opakovač -", self)
        rpt_minus.triggered.connect(lambda: self.cat.set_repeater_offset_mode("minus"))
        cat_menu.addAction(rpt_minus)

        rpt_plus = QAction("Opakovač +", self)
        rpt_plus.triggered.connect(lambda: self.cat.set_repeater_offset_mode("plus"))
        cat_menu.addAction(rpt_plus)

        rpt_simplex = QAction("Opakovač simplex", self)
        rpt_simplex.triggered.connect(lambda: self.cat.set_repeater_offset_mode("simplex"))
        cat_menu.addAction(rpt_simplex)

        rpt_freq = QAction("Nastavit offset…", self)
        rpt_freq.triggered.connect(self.prompt_offset_frequency)
        cat_menu.addAction(rpt_freq)

        ctcss_mode = QAction("CTCSS/DCS režim…", self)
        ctcss_mode.triggered.connect(self.prompt_ctcss_mode)
        cat_menu.addAction(ctcss_mode)

        ctcss_tone = QAction("Nastavit CTCSS tón…", self)
        ctcss_tone.triggered.connect(self.prompt_ctcss_tone)
        cat_menu.addAction(ctcss_tone)

        dcs_code = QAction("Nastavit DCS kód…", self)
        dcs_code.triggered.connect(self.prompt_dcs_code)
        cat_menu.addAction(dcs_code)


    def choose_font(self):
        font, ok = QFontDialog.getFont(QFont(self.current_font_family, 10), self)
        if ok:
            self.current_font_family = font.family()
            self._font_cache.clear()
            self.resize_timer.start()

    def choose_color_scheme(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Vyberte barevné schéma")
        layout = QVBoxLayout()
        dark = QRadioButton("Tmavý režim")
        light = QRadioButton("Světlý režim")
        contrast = QRadioButton("Vysoký kontrast")
        if self.current_theme == "dark":
            dark.setChecked(True)
        elif self.current_theme == "light":
            light.setChecked(True)
        else:
            contrast.setChecked(True)
        layout.addWidget(dark)
        layout.addWidget(light)
        layout.addWidget(contrast)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.setLayout(layout)
        if dialog.exec_() == QDialog.Accepted:
            if dark.isChecked():
                self.apply_stylesheet("dark")
            elif light.isChecked():
                self.apply_stylesheet("light")
            else:
                self.apply_stylesheet("contrast")

    def toggle_verbose(self, checked: bool):
        level = logging.DEBUG if checked else logging.INFO
        logger.setLevel(level)
        logging.getLogger().setLevel(level)

    def show_toast(self, message: str, timeout: int = 2000) -> None:
        toast = QLabel(message, self)
        toast.setStyleSheet(
            "background-color: #444; color: white; padding: 5px; border-radius: 3px;"
        )
        toast.setWindowFlags(Qt.ToolTip)
        toast.adjustSize()
        toast.move((self.width() - toast.width()) // 2, 30)
        QTimer.singleShot(timeout, toast.close)
        toast.show()

    def prompt_clar_offset(self):
        if not self.cat.is_connected:
            self.show_toast("Rádio není připojeno.")
            return
        val, ok = QInputDialog.getInt(self, "CLAR offset", "Zadejte offset v Hz:", 0, -9999, 9999)
        if ok:
            sign = 1 if val >= 0 else -1
            self.cat.set_clar_frequency(abs(val), sign)

    def prompt_offset_frequency(self):
        if not self.cat.is_connected:
            self.show_toast("Rádio není připojeno.")
            return
        val, ok = QInputDialog.getInt(self, "Offset", "Zadejte offset v Hz:", 0, 0, 9999999)
        if ok:
            self.cat.set_repeater_offset_frequency(val)

    def prompt_ctcss_mode(self):
        if not self.cat.is_connected:
            self.show_toast("Rádio není připojeno.")
            return
        modes = {
            "DCS": "dcs",
            "CTCSS": "ctcss",
            "CTCSS dekód": "ctcss_dec",
            "CTCSS enkód": "ctcss_enc",
            "Vypnuto": "off",
        }
        item, ok = QInputDialog.getItem(self, "CTCSS/DCS", "Režim:", list(modes.keys()), 0, False)
        if ok:
            self.cat.set_ctcss_dcs_mode(modes[item])

    def prompt_ctcss_tone(self):
        if not self.cat.is_connected:
            self.show_toast("Rádio není připojeno.")
            return
        tone, ok = QInputDialog.getDouble(
            self,
            "CTCSS",
            "Frekvence v Hz:",
            88.5,
            60.0,
            300.0,
            1,
        )
        if ok:
            self.cat.set_ctcss_tone(tone)

    def prompt_dcs_code(self):
        if not self.cat.is_connected:
            self.show_toast("Rádio není připojeno.")
            return
        tx, ok = QInputDialog.getInt(self, "DCS TX", "Kód:", 23, 0, 511)
        if not ok:
            return
        rx, ok = QInputDialog.getInt(self, "DCS RX", "Kód:", tx, 0, 511)
        if ok:
            self.cat.set_dcs_code(tx, rx)

    def apply_stylesheet(self, theme):
        self.current_theme = theme
        base_style = (
            "QWidget { font-family: 'Segoe UI'; }"
            " QPushButton { padding: 6px; border-radius: 3px; }"
            " QPushButton:checked { font-weight: bold; }"
        )
        if theme == "dark":
            extra = "QWidget { background-color: #1e1e1e; color: white; }"
        elif theme == "light":
            extra = "QWidget { background-color: #ffffff; color: black; }"
        else:
            extra = "QWidget { background-color: #000; color: yellow; }"
        self.setStyleSheet(base_style + extra)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._font_cache.clear()
        self.resize_timer.start()

    def adjust_all_fonts(self):
        self.adjust_label_font(self.freq_label)
        self.adjust_label_font(self.smeter_value_label)
        self.adjust_label_font(self.swr_label)
        self.adjust_label_font(self.power_label)

    def adjust_label_font(self, label: QLabel):
        text = label.text()
        if not text:
            return
        key = (text, label.width(), label.height(), self.current_font_family)
        cached = self._font_cache.get(key)
        if cached:
            label.setFont(cached)
            return
        width = label.width()
        height = label.height()
        orig_weight = label.font().weight()
        font = QFont(self.current_font_family, 10)
        min_size, max_size = 10, 300
        while min_size <= max_size:
            mid = (min_size + max_size) // 2
            font.setPointSize(mid)
            metrics = QFontMetrics(font)
            rect = metrics.boundingRect(text)
            if rect.width() <= width and rect.height() <= height:
                min_size = mid + 1
            else:
                max_size = mid - 1
        font.setPointSize(max_size)
        font.setWeight(orig_weight)
        self._font_cache[key] = font
        label.setFont(font)

    def update_connection_indicator(self, connected: bool) -> None:
        color = "#0a0" if connected else "#800"
        self.status_led.setStyleSheet(
            f"background-color: {color}; border-radius: 6px;"
        )
        self.status_text.setText("Připojeno" if connected else "Odpojeno")

    def toggle_connection(self) -> None:
        if not self.cat.is_connected:
            port = self.port_combo.currentText()
            if self.cat.connect(port):
                self.status_thread.start()
                self.ptt_btn.setEnabled(True)
                self.connect_btn.setText("Odpojit")
                self.update_connection_indicator(True)
            else:
                msg = self.cat.last_error or "Nelze se připojit."
                QMessageBox.critical(self, "Chyba připojení", msg)
        else:
            self.status_thread.stop()
            self.status_thread.wait()
            self.cat.disconnect()
            self.ptt_btn.setEnabled(False)
            self.connect_btn.setText("Připojit")
            self.update_connection_indicator(False)

    def update_status(self, freq_hz, sm_level, power_level, swr_flag):
        """Refresh GUI with latest values.

        Hamlet would ask "Být či nebýt" – here we choose to show
        meters whenever data exists and fall back gracefully otherwise.
        """
        self.update_connection_indicator(self.cat.is_connected)
        if freq_hz >= 0:
            self.last_valid_frequency = freq_hz
            formatted = f"{freq_hz / 1e6:09.5f}"
            if formatted != self.freq_label.text():
                self.freq_label.setText(formatted)
                self.adjust_label_font(self.freq_label)
            freq_khz = freq_hz / 1000.0
            self.band_label.setText(f"Pásmo: {self.get_band_label_from_khz(freq_khz)}")
        else:
            if "---" != self.freq_label.text():
                self.freq_label.setText("---")
                self.adjust_label_font(self.freq_label)
            self.band_label.setText("")
            freq_khz = (self.last_valid_frequency or 0) / 1000.0
        if sm_level >= 0:
            new_sm_text = self.format_smeter(sm_level)
        else:
            new_sm_text = "---"
        if new_sm_text != self.smeter_value_label.text():
            self.smeter_value_label.setText(new_sm_text)
            self.adjust_label_font(self.smeter_value_label)

        if power_level >= 0:
            band = self.get_band_label_from_khz(freq_khz)
            calib = self.band_power_calibration.get(band, {"min_raw": 0, "max_raw": 15})
            raw_min = calib.get("min_raw", 0)
            raw_max = calib.get("max_raw", 15)
            if raw_max == raw_min:
                percent = 0
            else:
                level = max(raw_min, min(power_level, raw_max))
                percent = int(round(100 * (level - raw_min) / (raw_max - raw_min)))
            text = f"Výkon: {percent} %"
        else:
            text = "Výkon: ---"
        if text != self.power_label.text():
            self.power_label.setText(text)
            self.adjust_label_font(self.power_label)
        if swr_flag == 1:
            new_swr_text = "SWR: High"
        elif swr_flag == 0:
            new_swr_text = "SWR: Normal"
        else:
            new_swr_text = "SWR: ---"
        if new_swr_text != self.swr_label.text():
            self.swr_label.setText(new_swr_text)
            self.adjust_label_font(self.swr_label)

    def get_band_label_from_khz(self, freq_khz):
        return band_label_from_khz(freq_khz, self.band_definitions)

    def format_smeter(self, raw):
        return format_smeter(raw)

    def tune_from_menu(self):
        action = self.sender()
        data = action.data()

        if isinstance(data, tuple):
            freq, mode = data
            ctcss = None
            offset = None
            tx_only = False
        elif isinstance(data, dict):
            freq = data.get("freq")
            mode = data.get("mode")
            ctcss = data.get("ctcss")
            offset = data.get("offset")
            tx_only = bool(data.get("tx_only"))
        else:
            return

        if not self.cat.is_connected:
            port = self.port_combo.currentText()
            if not self.cat.connect(port):
                self.show_toast("Rádio není připojeno.")
                return
            if not self.status_thread.isRunning():
                self.status_thread.start()
            self.ptt_btn.setEnabled(True)
            self.connect_btn.setText("Odpojit")
            self.update_connection_indicator(True)

        self.cat.set_frequency(freq)
        self.cat.set_mode(mode)
        repeater = bool(action.property("repeater"))
        if repeater:
            if action.text().startswith("OK0G"):
                self.cat.apply_repeater_settings(-600_000, 77.0, True)
            else:
                if offset is None:
                    if 145_000_000 <= freq <= 146_000_000:
                        offset = -600_000
                    elif 430_000_000 <= freq <= 440_000_000:
                        offset = -7_600_000
                    else:
                        offset = 0
                self.cat.apply_repeater_settings(offset, ctcss, tx_only)
        else:
            if offset is not None:
                if offset == 0:
                    self.cat.set_repeater_offset_frequency(0)
                    self.cat.set_repeater_offset_mode("simplex")
                else:
                    self.cat.set_repeater_offset_frequency(abs(int(offset)))
                    self.cat.set_repeater_offset_mode("minus" if offset < 0 else "plus")
            else:
                self.cat.set_repeater_offset_frequency(0)
                self.cat.set_repeater_offset_mode("simplex")

            # ensure simplex or custom offset applies immediately
            self.cat.set_frequency(freq)

            if ctcss is not None:
                mode = "ctcss_enc" if tx_only else "ctcss"
                self.cat.set_ctcss_dcs_mode(mode)
                self.cat.set_ctcss_tone(ctcss)
            else:
                self.cat.set_ctcss_dcs_mode("off")

    def handle_ptt_on(self):
        if not self.cat.is_connected:
            self.show_toast("Rádio není připojeno.")
            return
        self.cat.ptt_on()
        self.ptt_heartbeat.start()
        self.ptt_container.setStyleSheet("background-color: #600;")

    def handle_ptt_off(self):
        if not self.cat.is_connected:
            self.show_toast("Rádio není připojeno.")
            return
        self.ptt_heartbeat.stop()
        self.cat.ptt_off()
        self.ptt_container.setStyleSheet("")

    def closeEvent(self, event):
        self.status_thread.stop()
        self.status_thread.wait()
        self.ptt_heartbeat.stop()
        self.resize_timer.stop()
        self.cat.disconnect()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = RadioControlApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
