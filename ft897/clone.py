"""Clone mode support for the Yaesu FT-897."""

from __future__ import annotations

import serial
import time
from typing import Callable


class FT897Clone:
    """Handle CLONE mode transfers of complete memory images."""

    def __init__(self, port: str, baudrate: int = 9600, timeout: float = 1.0):
        self.serial = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=timeout,
            write_timeout=timeout,
        )

    @staticmethod
    def enter_clone_mode_instructions() -> str:
        return (
            "1. Turn off the FT-897.\n"
            "2. Hold [FAST] while powering on to enter CLONE mode.\n"
            "3. Press [SEND] on the radio to start transfer." 
        )

    def recv_image(self, progress: Callable[[int], None] | None = None) -> bytes:
        """Receive entire clone image. Returns bytes."""
        buf = bytearray()
        while True:
            data = self.serial.read(1024)
            if data:
                buf.extend(data)
                if progress:
                    progress(len(buf))
            else:
                break
        return bytes(buf)

    def send_image(self, image: bytes, progress: Callable[[int], None] | None = None) -> None:
        """Send clone image back to the radio."""
        sent = 0
        view = memoryview(image)
        while sent < len(image):
            n = self.serial.write(view[sent : sent + 1024])
            sent += n
            if progress:
                progress(sent)
            time.sleep(0.01)
        self.serial.flush()


