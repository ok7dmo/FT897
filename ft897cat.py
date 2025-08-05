import os
import shutil
import subprocess
import logging
from typing import Dict, Optional


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
        # On older Python versions ``subprocess.Popen`` is not subscriptable, so
        # avoid using ``Popen[str]`` type hints to keep compatibility.
        self.proc: Optional[subprocess.Popen] = None

    def _find_rigctl_path(self) -> str:
        path = shutil.which("rigctl")
        if path:
            return path
        candidates = [
            r"C:\\Program Files\\hamlib-w64-4.6.3\\bin\\rigctl.exe",
            r"C:\\Program Files\\Hamlib\\bin\\rigctl.exe",
            r"C:\\Hamlib\\bin\\rigctl.exe",
            r"C:\\Program Files (x86)\\Hamlib\\bin\\rigctl.exe",
            r"C:\\Tools\\Hamlib\\bin\\rigctl.exe",
            r"C:\\rigctl\\rigctl.exe",
            r"D:\\Program Files\\Hamlib\\bin\\rigctl.exe",
        ]
        for cand in candidates:
            if os.path.isfile(cand):
                return cand
        raise FileNotFoundError("rigctl executable not found")

    def _start_rigctl(self) -> None:
        if self.proc:
            return
        if not self.rigctl_path:
            self.rigctl_path = self._find_rigctl_path()
        self.proc = subprocess.Popen(
            [self.rigctl_path, "-m", "1023", "-r", self.port or "", "-s", str(self.baudrate)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        # rigctl prints an initial banner/prompt when started; consume it so the
        # first command gets the expected response line.
        if self.proc.stdout:
            try:
                self.proc.stdout.readline()
            except Exception:
                pass

    def _send_command(self, command: str) -> Optional[str]:
        try:
            self._start_rigctl()
            assert self.proc and self.proc.stdin and self.proc.stdout
            self.proc.stdin.write(command + "\n")
            self.proc.stdin.flush()
            return self.proc.stdout.readline().strip()
        except Exception as e:
            self.last_error = str(e)
            logging.getLogger(__name__).warning("rigctl command failed: %s", e)
            return None

    def connect(self, port: str, baudrate: int = 9600) -> bool:
        self.port = port
        self.baudrate = baudrate
        res = self._send_command("get_freq")
        if res:
            self.is_connected = True
            logging.getLogger(__name__).info("Connected to %s at %d bps", port, baudrate)
            return True
        self.is_connected = False
        if not self.last_error:
            self.last_error = "Neznámá chyba"
        return False

    def disconnect(self) -> None:
        if self.proc:
            try:
                self.proc.terminate()
            except Exception:
                pass
            self.proc = None
        self.is_connected = False
        logging.getLogger(__name__).info("Disconnected")

    def get_frequency(self) -> Optional[int]:
        if not self.is_connected:
            return None
        res = self._send_command("get_freq")
        if res:
            try:
                hz = float(res)  # Hamlib returns frequency in Hz
                return int(hz)
            except ValueError:
                logging.getLogger(__name__).warning("Neplatná frekvence: %s", res)
        return None

    def set_frequency(self, freq_hz: int) -> bool:
        if not self.is_connected:
            return False
        return self._send_command(f"set_freq {freq_hz}") is not None

    def set_mode(self, mode: str) -> bool:
        if not self.is_connected or mode not in self.MODE_MAP:
            return False
        return self._send_command(f"set_mode {mode} 0") is not None

    def ptt_on(self) -> bool:
        if not self.is_connected:
            return False
        if self._send_command("set_ptt 1") is not None:
            self.ptt_active = True
            return True
        return False

    def ptt_off(self) -> bool:
        if not self.is_connected:
            return False
        if self._send_command("set_ptt 0") is not None:
            self.ptt_active = False
            return True
        return False

    def get_smeter(self) -> Optional[int]:
        if not self.is_connected:
            return None
        res = self._send_command("get_level RF")
        if res:
            try:
                return int(float(res))
            except ValueError:
                logging.getLogger(__name__).warning("Neplatná hodnota S-měru: %s", res)
        return None

    def read_tx_status(self) -> Optional[int]:
        if not self.is_connected:
            return None
        ptt_res = self._send_command("get_ptt")
        if not ptt_res:
            return None
        ptt_on = ptt_res.strip() == "1"
        if not ptt_on:
            return 0x80
        power_res = self._send_command("get_level TX_POWER")
        level = 0
        if power_res:
            try:
                level = int(round(float(power_res) / 6.667))
            except ValueError:
                logging.getLogger(__name__).warning("Neplatná hodnota výkonu: %s", power_res)
        return max(0, min(level, 15))

    def get_power_level(self) -> Optional[int]:
        status = self.read_tx_status()
        if status is None or status & 0x80:
            return None
        return status & 0x0F

    def get_swr(self, tx_status: Optional[int] = None) -> Optional[int]:
        if not self.is_connected:
            return None
        res = self._send_command("get_level SWR")
        if res:
            try:
                val = float(res)
                return 1 if val >= 3.0 else 0
            except ValueError:
                logging.getLogger(__name__).warning("Neplatné SWR: %s", res)
        return None

    def toggle_vfo(self) -> bool:
        if not self.is_connected:
            return False
        res = self._send_command("get_vfo")
        if not res:
            return False
        cur = res.upper()
        new = "VFOB" if cur == "VFOA" else "VFOA"
        return self._send_command(f"set_vfo {new}") is not None

    def split_on(self) -> bool:
        if not self.is_connected:
            return False
        return self._send_command("set_split 1") is not None

    def split_off(self) -> bool:
        if not self.is_connected:
            return False
        return self._send_command("set_split 0") is not None

    def lock_on(self) -> bool:
        if not self.is_connected:
            return False
        return self._send_command("set_lock 1") is not None

    def lock_off(self) -> bool:
        if not self.is_connected:
            return False
        return self._send_command("set_lock 0") is not None

    def clar_on(self) -> bool:
        if not self.is_connected:
            return False
        return self._send_command("set_rit 1") is not None

    def clar_off(self) -> bool:
        if not self.is_connected:
            return False
        return self._send_command("set_rit 0") is not None

    def set_clar_frequency(self, offset_hz: int, sign: int = 1) -> bool:
        if not self.is_connected:
            return False
        val = sign * offset_hz
        return self._send_command(f"set_rit {val}") is not None

    def set_repeater_offset_mode(self, mode: str) -> bool:
        if not self.is_connected:
            return False
        mapping = {"minus": "-", "plus": "+", "simplex": "0"}
        shift = mapping.get(mode)
        if shift is None:
            return False
        return self._send_command(f"set_rptr_shift {shift}") is not None

    def set_repeater_offset_frequency(self, freq_hz: int) -> bool:
        if not self.is_connected:
            return False
        return self._send_command(f"set_rptr_offs {freq_hz}") is not None

    def get_repeater_offset_mode(self) -> Optional[str]:
        if not self.is_connected:
            return None
        res = self._send_command("get_rptr_shift")
        if res:
            mapping = {"-": "minus", "+": "plus", "0": "simplex"}
            return mapping.get(res)
        return None

    def apply_repeater_settings(self, offset_hz: int, tone_hz: Optional[float] = None, tx_only: bool = False) -> None:
        if not self.is_connected:
            return
        shift = "-" if offset_hz < 0 else "+" if offset_hz > 0 else "0"
        self._send_command(f"set_rptr_shift {shift}")
        self._send_command(f"set_rptr_offs {abs(offset_hz)}")
        if tone_hz is not None:
            self._send_command(f"set_ctcss_mode {'TONE' if tx_only else 'TSQL'}")
            self._send_command(f"set_ctcss_tone {int(round(tone_hz))}")
        else:
            self._send_command("set_ctcss_mode OFF")

    def set_ctcss_dcs_mode(self, mode: str) -> bool:
        if not self.is_connected:
            return False
        mapping = {
            "dcs": "DCS",
            "ctcss": "TSQL",
            "ctcss_dec": "CTCSS",
            "ctcss_enc": "TONE",
            "off": "OFF",
        }
        arg = mapping.get(mode)
        if arg is None:
            return False
        return self._send_command(f"set_ctcss_mode {arg}") is not None

    def set_ctcss_tone(self, tone_hz: float) -> bool:
        if not self.is_connected:
            return False
        return self._send_command(f"set_ctcss_tone {int(round(tone_hz))}") is not None

    def set_dcs_code(self, tx_code: int, rx_code: int) -> bool:
        if not self.is_connected:
            return False
        ok1 = self._send_command(f"set_dcs_code {tx_code}") is not None
        ok2 = self._send_command(f"set_dcs_code {rx_code}") is not None
        return ok1 and ok2

