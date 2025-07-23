import io
from ft897_single import FT897Clone

class DummySerial:
    def __init__(self, data: bytes):
        self.buffer = io.BytesIO(data)
        self.written = bytearray()
        self.timeout = 1.0

    def read(self, n=1):
        return self.buffer.read(n)

    def write(self, data):
        self.written.extend(data)
        return len(data)

    def flush(self):
        pass


def test_recv_send_image(monkeypatch):
    dummy = DummySerial(b"abc")
    monkeypatch.setattr(FT897Clone, "__init__", lambda self, port, baudrate=9600, timeout=1.0: setattr(self, "serial", dummy))
    clone = FT897Clone("COM1")
    data = clone.recv_image()
    assert data == b"abc"
    clone.send_image(b"xyz")
    assert dummy.written == b"xyz"
