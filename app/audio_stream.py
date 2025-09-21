"""Audio streaming utilities."""
from __future__ import annotations

import asyncio
import logging
import struct
from dataclasses import dataclass
from typing import AsyncIterator, Optional

try:
    import sounddevice  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    sounddevice = None  # type: ignore

LOGGER = logging.getLogger(__name__)


@dataclass
class AudioConfig:
    """Configuration for capturing audio from the host sound card."""

    samplerate: int = 16000
    channels: int = 1
    blocksize: int = 1024
    subtype: str = "int16"
    device: Optional[int] = None
    enabled: bool = True


class AudioStreamer:
    """Stream audio from the system's sound card as linear PCM WAV data."""

    def __init__(self, config: AudioConfig):
        self._config = config
        self._queue: "asyncio.Queue[bytes]" = asyncio.Queue(maxsize=10)
        self._stream: Optional["sounddevice.RawInputStream"] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._running = False

    def _audio_callback(self, indata, frames, time, status) -> None:  # pragma: no cover - callback
        if status:
            LOGGER.warning("Audio callback status: %s", status)
        if not self._running:
            return
        data = bytes(indata)
        try:
            self._queue.put_nowait(data)
        except asyncio.QueueFull:
            LOGGER.debug("Audio queue full; dropping frame")

    def _wav_header(self) -> bytes:
        byte_rate = self._config.samplerate * self._config.channels * 2
        block_align = self._config.channels * 2
        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",
            36 + 0x7FFFFFFF,  # huge placeholder size for streaming
            b"WAVE",
            b"fmt ",
            16,
            1,
            self._config.channels,
            self._config.samplerate,
            byte_rate,
            block_align,
            16,
            b"data",
            0x7FFFFFFF,
        )
        return header

    async def audio_generator(self) -> AsyncIterator[bytes]:
        if not self._config.enabled:
            LOGGER.info("Audio streaming is disabled via configuration")
            raise RuntimeError("Audio streaming disabled")

        if sounddevice is None:
            raise RuntimeError(
                "sounddevice is not available. Install it with 'pip install sounddevice'."
            )

        self._loop = asyncio.get_running_loop()
        self._running = True
        LOGGER.info(
            "Starting audio capture: %d Hz, %d channel(s)",
            self._config.samplerate,
            self._config.channels,
        )
        try:
            self._stream = sounddevice.RawInputStream(  # type: ignore[call-arg]
                samplerate=self._config.samplerate,
                channels=self._config.channels,
                dtype=self._config.subtype,
                blocksize=self._config.blocksize,
                device=self._config.device,
                callback=self._audio_callback,
            )
            self._stream.start()
        except Exception as exc:  # pragma: no cover - hardware dependent
            LOGGER.error("Unable to start audio stream: %s", exc)
            raise

        yield self._wav_header()

        try:
            while self._running:
                chunk = await self._queue.get()
                yield chunk
        finally:
            await self.stop()

    async def stop(self) -> None:
        if self._stream is not None:
            LOGGER.info("Stopping audio capture")
            try:
                self._stream.stop()
                self._stream.close()
            finally:
                self._stream = None
        self._running = False
        while not self._queue.empty():
            self._queue.get_nowait()


__all__ = ["AudioConfig", "AudioStreamer"]
