"""FastAPI application for remote control of the Yaesu FT-897."""
from __future__ import annotations

import logging
from functools import lru_cache
import sys
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

if __package__ in {None, ""}:  # pragma: no cover - runtime safety for script execution
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from app.audio_stream import AudioConfig, AudioStreamer  # type: ignore
    from app.cat_control import CATConfig, FT897Controller  # type: ignore
else:  # pragma: no cover - exercised indirectly
    from .audio_stream import AudioConfig, AudioStreamer
    from .cat_control import CATConfig, FT897Controller

LOGGER = logging.getLogger(__name__)


class Settings(BaseSettings):
    serial_port: str = Field("/dev/ttyUSB0", alias="FT897_SERIAL_PORT")
    baudrate: int = Field(9600, alias="FT897_BAUDRATE")
    serial_timeout: float = Field(1.0, alias="FT897_SERIAL_TIMEOUT")
    simulate_radio: bool = Field(False, alias="FT897_SIMULATE")

    audio_samplerate: int = Field(16000, alias="FT897_AUDIO_SAMPLERATE")
    audio_channels: int = Field(1, alias="FT897_AUDIO_CHANNELS")
    audio_blocksize: int = Field(1024, alias="FT897_AUDIO_BLOCKSIZE")
    audio_enabled: bool = Field(True, alias="FT897_AUDIO_ENABLED")
    audio_device: Optional[int] = Field(None, alias="FT897_AUDIO_DEVICE")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @field_validator("baudrate")
    @classmethod
    def validate_baudrate(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Baudrate must be positive")
        return value


class CommandRequest(BaseModel):
    command: str


class FrequencyRequest(BaseModel):
    frequency_hz: int


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()


def get_controller(settings: Settings = Depends(get_settings)) -> FT897Controller:
    return FT897Controller(
        CATConfig(
            port=settings.serial_port,
            baudrate=settings.baudrate,
            timeout=settings.serial_timeout,
            simulate=settings.simulate_radio,
        )
    )


def get_audio_streamer(settings: Settings = Depends(get_settings)) -> AudioStreamer:
    return AudioStreamer(
        AudioConfig(
            samplerate=settings.audio_samplerate,
            channels=settings.audio_channels,
            blocksize=settings.audio_blocksize,
            enabled=settings.audio_enabled,
            device=settings.audio_device,
        )
    )


app = FastAPI(title="FT-897 Remote Control", version="1.0.0")

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse("index.html", {"request": request})


@app.post("/api/command", response_class=JSONResponse)
async def send_command(data: CommandRequest, controller: FT897Controller = Depends(get_controller)) -> JSONResponse:
    try:
        response = controller.send_raw_command(data.command)
    except Exception as exc:  # pragma: no cover - depends on hardware
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return JSONResponse({"command": data.command, "response": response})


@app.post("/api/frequency", response_class=JSONResponse)
async def set_frequency(data: FrequencyRequest, controller: FT897Controller = Depends(get_controller)) -> JSONResponse:
    try:
        controller.set_vfo_a_frequency(data.frequency_hz)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return JSONResponse({"frequency_hz": data.frequency_hz})


@app.get("/api/frequency", response_class=JSONResponse)
async def get_frequency(controller: FT897Controller = Depends(get_controller)) -> JSONResponse:
    try:
        frequency = controller.get_vfo_a_frequency()
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if frequency is None:
        raise HTTPException(status_code=502, detail="No response from radio")
    return JSONResponse({"frequency_hz": frequency})


@app.post("/api/ptt", response_class=JSONResponse)
async def set_ptt(active: bool = Form(...), controller: FT897Controller = Depends(get_controller)) -> JSONResponse:
    try:
        controller.set_ptt(active)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return JSONResponse({"ptt": active})


@app.get("/api/ptt", response_class=JSONResponse)
async def get_ptt(controller: FT897Controller = Depends(get_controller)) -> JSONResponse:
    try:
        status = controller.get_ptt_status()
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if status is None:
        raise HTTPException(status_code=502, detail="No response from radio")
    return JSONResponse({"ptt": status})


@app.get("/audio/stream")
async def audio_stream(streamer: AudioStreamer = Depends(get_audio_streamer)) -> StreamingResponse:
    try:
        generator = streamer.audio_generator()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return StreamingResponse(generator, media_type="audio/wav")


@app.on_event("startup")
async def on_startup() -> None:
    logging.basicConfig(level=logging.INFO)
    LOGGER.info("FT-897 remote control server starting up")


@app.on_event("shutdown")
async def on_shutdown() -> None:
    LOGGER.info("FT-897 remote control server shutting down")


def main() -> None:  # pragma: no cover - convenience wrapper
    """Run the FastAPI application via uvicorn."""

    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise RuntimeError(
            "Uvicorn is required to run the development server. "
            "Install dependencies from requirements.txt first."
        ) from exc

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":  # pragma: no cover - manual execution path
    main()
