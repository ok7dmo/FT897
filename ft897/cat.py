"""CAT control module for the Yaesu FT-897."""
import serial
import time
import threading

class FT897CAT:
    """Minimal CAT control for the Yaesu FT-897 using direct serial commands."""

    MODE_MAP = {
        "LSB": 0x00,
        "USB": 0x01,
        "CW": 0x02,
        "CWR": 0x03,
        "AM": 0x04,
        "FM": 0x08,
        "DIG": 0x06,
    }

    def __init__(self):
        self.port = None
        self.baudrate = 9600
        self.is_connected = False
        self.ptt_active = False
        self.serial_port = None
        self._lock = threading.Lock()

    def _send(self, data: bytes):
        with self._lock:
            try:
                self.serial_port.reset_input_buffer()
                self.serial_port.reset_output_buffer()
                self.serial_port.write(data)
                self.serial_port.flush()
                time.sleep(0.05)
                return True
            except Exception as e:
                print(f"Chyba serial write: {e}")
                return False

    def _read(self, length=5):
        with self._lock:
            try:
                return self.serial_port.read(length)
            except Exception as e:
                print(f"Chyba serial read: {e}")
                return None

    def connect(self, port, baudrate=9600):
        self.port = port
        self.baudrate = baudrate
        try:
            self.serial_port = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.2,
                write_timeout=0.2,
            )
            self.is_connected = True
            return True
        except Exception as e:
            print(f"Chyba připojení: {e}")
            return False

    def disconnect(self):
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.close()
            except Exception:
                pass
        self.is_connected = False

    def get_frequency(self):
        if not self.is_connected:
            return None
        if not self._send(b"\x00\x00\x00\x00\x03"):
            return None
        resp = self._read(5)
        if not resp or len(resp) != 5:
            return None
        units_10hz = 0
        for b in resp[:4]:
            units_10hz = units_10hz * 100 + ((b >> 4) & 0x0F) * 10 + (b & 0x0F)
        return units_10hz * 10

    def get_smeter(self):
        """Return raw S-meter value (0-15) using RX status command."""
        if not self.is_connected:
            return None
        with self._lock:
            try:
                self.serial_port.reset_input_buffer()
                self.serial_port.reset_output_buffer()
                self.serial_port.write(b'\x00\x00\x00\x00\xe7')
                time.sleep(0.1)
                resp = self.serial_port.read(1)
            except Exception as e:
                print(f"Chyba při čtení S-metu: {e}")
                return None

        if not resp:
            return None
        return resp[0] & 0x0F

    def get_swr(self, tx_status: int | None = None) -> int | None:
        """Return 1 if high VSWR, 0 if normal, None if not transmitting."""
        if not self.is_connected:
            return None
        if tx_status is None:
            tx_status = self.read_tx_status()
            if tx_status is None:
                return None
        # Bit 7 is 0 when transmitting. VSWR information only valid then.
        if tx_status & 0x80:
            return None
        return 1 if (tx_status & 0x40) else 0

    def get_power_level(self):
        """Return raw power meter level (0-15) from the TX status byte."""
        status = self.read_tx_status()
        if status is None:
            return None
        # Bit 7 indicates PTT: 0 = transmit, 1 = receive.
        if status & 0x80:
            return None
        return status & 0x0F


    def ptt_on(self):
        if not self.is_connected:
            return False
        self.ptt_active = True
        return self._send(b"\x00\x00\x00\x00\x08")

    def ptt_off(self):
        if not self.is_connected:
            return False
        self.ptt_active = False
        return self._send(b"\x00\x00\x00\x00\x88")

    def set_frequency(self, freq_hz: int):
        """Tune the radio to the specified frequency in Hz."""
        if not self.is_connected:
            return False
        units_10hz = int(freq_hz // 10)
        digits = f"{units_10hz:08d}"
        bcd = bytearray()
        for i in range(0, 8, 2):
            bcd.append((int(digits[i]) << 4) | int(digits[i + 1]))
        return self._send(bytes(bcd) + b"\x01")

    def set_mode(self, mode: str):
        if not self.is_connected:
            return False
        code = self.MODE_MAP.get(mode)
        if code is None:
            return False
        # Mode codes go in the first byte of the 5-byte CAT command.
        # The remaining bytes are zeros followed by 0x07.
        cmd = bytes([code, 0x00, 0x00, 0x00, 0x07])
        return self._send(cmd)

    def toggle_vfo(self):
        if not self.is_connected:
            return False
        return self._send(b"\x00\x00\x00\x00\x81")

    def split_on(self):
        if not self.is_connected:
            return False
        return self._send(b"\x00\x00\x00\x00\x02")

    def split_off(self):
        if not self.is_connected:
            return False
        return self._send(b"\x00\x00\x00\x00\x82")

    def lock_on(self):
        if not self.is_connected:
            return False
        return self._send(b"\x00\x00\x00\x00\x00")

    def lock_off(self):
        if not self.is_connected:
            return False
        return self._send(b"\x00\x00\x00\x00\x80")

    def clar_on(self):
        if not self.is_connected:
            return False
        return self._send(b"\x00\x00\x00\x00\x05")

    def clar_off(self):
        if not self.is_connected:
            return False
        return self._send(b"\x00\x00\x00\x00\x85")

    def set_clar_frequency(self, offset_hz: int, sign: int = 1):
        if not self.is_connected:
            return False
        sign_byte = 0x00 if sign >= 0 else 0xFF
        units_10hz = int(abs(offset_hz) // 10)
        digits = f"{units_10hz:04d}"
        bcd = bytearray([sign_byte, 0x00])
        for i in range(0, 4, 2):
            bcd.append((int(digits[i]) << 4) | int(digits[i + 1]))
        bcd.append(0xF5)
        return self._send(bytes(bcd))

    def set_repeater_offset_mode(self, mode: str):
        if not self.is_connected:
            return False
        mapping = {
            "minus": 0x09,
            "plus": 0x49,
            "simplex": 0x89,
        }
        code = mapping.get(mode)
        if code is None:
            return False
        cmd = bytes([code, 0x00, 0x00, 0x00, 0x09])
        return self._send(cmd)

    def set_repeater_offset_frequency(self, freq_hz: int):
        if not self.is_connected:
            return False
        units_10hz = int(freq_hz // 10)
        digits = f"{units_10hz:08d}"
        bcd = bytearray()
        for i in range(0, 8, 2):
            bcd.append((int(digits[i]) << 4) | int(digits[i + 1]))
        bcd.append(0xF9)
        return self._send(bytes(bcd))

    def set_ctcss_dcs_mode(self, mode: str):
        if not self.is_connected:
            return False
        mapping = {
            "dcs": 0x0A,
            "ctcss": 0x2A,
            "ctcss_dec": 0x3A,
            "ctcss_enc": 0x4A,
            "off": 0x8A,
        }
        code = mapping.get(mode)
        if code is None:
            return False
        cmd = bytes([code, 0x00, 0x00, 0x00, 0x0A])
        return self._send(cmd)

    def set_ctcss_tone(self, tx_hz: float, rx_hz: float):
        if not self.is_connected:
            return False
        tx = int(round(tx_hz * 10))
        rx = int(round(rx_hz * 10))
        digits_tx = f"{tx:04d}"
        digits_rx = f"{rx:04d}"
        data = bytearray()
        for i in range(0, 4, 2):
            data.append((int(digits_tx[i]) << 4) | int(digits_tx[i + 1]))
        for i in range(0, 4, 2):
            data.append((int(digits_rx[i]) << 4) | int(digits_rx[i + 1]))
        data.append(0x0B)
        return self._send(bytes(data))

    def set_dcs_code(self, tx_code: int, rx_code: int):
        if not self.is_connected:
            return False
        digits_tx = f"{tx_code:03d}".rjust(3, '0')
        digits_rx = f"{rx_code:03d}".rjust(3, '0')
        data = bytearray()
        for digits in (digits_tx, digits_rx):
            if len(digits) == 3:
                digits = '0' + digits
            for i in range(0, 4, 2):
                data.append((int(digits[i]) << 4) | int(digits[i + 1]))
        data.append(0x0C)
        return self._send(bytes(data))

    def read_tx_status(self):
        if not self.is_connected:
            return None
        if not self._send(b"\x00\x00\x00\x00\xf7"):
            return None
        resp = self._read(1)
        if not resp:
            return None
        return resp[0]



