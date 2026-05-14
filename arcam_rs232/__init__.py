"""Arcam AVR500/AVR600/AV888 RS232 protocol helpers."""

from importlib.metadata import PackageNotFoundError, version

from .protocol import (
    END,
    REQUEST,
    START,
    ArcamDecoder,
    Frame,
    FrameReader,
    build_frame,
    build_rc5_frame,
    hex_bytes,
    request_frame,
)
from .config import ConfigError, DaemonConfig, DeviceConfig, MqttConfig, load_config


def package_version() -> str:
    try:
        return version("arcam-rs232")
    except PackageNotFoundError:
        return "unknown"


__version__ = package_version()


__all__ = [
    "__version__",
    "END",
    "REQUEST",
    "START",
    "ArcamDecoder",
    "Frame",
    "FrameReader",
    "build_frame",
    "build_rc5_frame",
    "hex_bytes",
    "request_frame",
    "ConfigError",
    "DaemonConfig",
    "DeviceConfig",
    "MqttConfig",
    "package_version",
    "load_config",
]
