import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import time
from cat_control import FT897CAT

class FakeSerial:
    def __init__(self, data: bytes):
        self.read_buffer = bytearray(data)
        self.written = bytearray()
        self.timeout = 0.01
        self.is_open = True
    def write(self, data: bytes):
        self.written.extend(data)
    def flush(self):
        pass
    def read(self, size: int = 1):
        if not self.read_buffer:
            time.sleep(self.timeout)
            return b''
        data = self.read_buffer[:size]
        del self.read_buffer[:size]
        return bytes(data)
    def reset_input_buffer(self):
        pass
    def reset_output_buffer(self):
        pass
    def close(self):
        self.is_open = False

def test_get_meter_block_with_echo():
    # command echo plus filler byte before meter block
    response = b'\x00\x00\x00\x00\xE7' + b'\x00' + b'\x10\x20\x30\x40\x50'
    fake = FakeSerial(response)
    cat = FT897CAT()
    cat.serial_port = fake
    cat.is_connected = True
    block = cat.get_meter_block()
    assert block == b'\x10\x20\x30\x40\x50'
    assert fake.written == b'\x00\x00\x00\x00\xE7'

def test_get_meter_block_short():
    response = b'\x01\x02\x03\x04\x05'
    fake = FakeSerial(response)
    cat = FT897CAT()
    cat.serial_port = fake
    cat.is_connected = True
    block = cat.get_meter_block()
    assert block == b'\x01\x02\x03\x04\x05'

def test_get_s_and_power():
    response = b'\x00\x00\x00\x00\xE7' + b'\xAA\xBB\xCC\xDD\xEE'
    fake = FakeSerial(response)
    cat = FT897CAT()
    cat.serial_port = fake
    cat.is_connected = True
    s_val, p_val = cat.get_s_and_power()
    assert s_val == 0xAA
    assert p_val == 0xBB
