from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml


class ConfigError(ValueError):
    """Raised when daemon configuration is missing or invalid."""


TransportType = Literal["tcp", "serial"]


@dataclass(frozen=True)
class TlsConfig:
    enabled: bool = False
    ca_file: str | None = None
    cert_file: str | None = None
    key_file: str | None = None
    insecure: bool = False


@dataclass(frozen=True)
class MqttConfig:
    host: str
    port: int = 1883
    username: str | None = None
    username_env: str | None = None
    username_file: str | None = None
    password: str | None = None
    password_env: str | None = None
    password_file: str | None = None
    tls: TlsConfig = field(default_factory=TlsConfig)
    client_id: str = "arcam-rs232"
    daemon_topic: str = "arcam/daemon"
    retain: bool = True
    qos: int = 0


@dataclass(frozen=True)
class TransportConfig:
    type: TransportType
    timeout_seconds: float = 1.0
    host: str | None = None
    port: int | None = None
    serial_port: str | None = None
    baudrate: int = 38400


@dataclass(frozen=True)
class PollingConfig:
    heartbeat_seconds: float = 5
    missed_heartbeats_limit: int = 2
    offline_retry_seconds: float = 10
    offline_backoff_max_seconds: float = 60
    core_refresh_seconds: float = 30
    burst_collection_seconds: float = 5


@dataclass(frozen=True)
class CommandConfig:
    ack_timeout_seconds: float = 2
    reject_when_unavailable: bool = True
    update_state_from_ack: bool = False


@dataclass(frozen=True)
class ZoneConfig:
    enabled: bool = True
    control_requires_power_on: bool = True
    power_command_allowed_when_device_online: bool = True
    core: tuple[str, ...] = ("power", "source", "volume", "mute")
    extended: tuple[str, ...] = ()


@dataclass(frozen=True)
class DeviceConfig:
    id: str
    model: str
    topic: str
    transport: TransportConfig
    polling: PollingConfig = field(default_factory=PollingConfig)
    commands: CommandConfig = field(default_factory=CommandConfig)
    zones: dict[str, ZoneConfig] = field(default_factory=dict)


@dataclass(frozen=True)
class DaemonConfig:
    mqtt: MqttConfig
    devices: dict[str, DeviceConfig]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_config(path: str | Path) -> DaemonConfig:
    config_path = Path(path)
    try:
        raw = yaml.safe_load(config_path.read_text()) or {}
    except OSError as exc:
        raise ConfigError(f"cannot read config {config_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError("config root must be a mapping")
    return parse_config(raw)


def parse_config(raw: dict[str, Any]) -> DaemonConfig:
    mqtt = _parse_mqtt(_required_mapping(raw, "mqtt", "config"))
    devices_raw = _required_mapping(raw, "devices", "config")
    devices = {
        device_id: _parse_device(device_id, _ensure_mapping(device_raw, f"devices.{device_id}"))
        for device_id, device_raw in devices_raw.items()
    }
    if not devices:
        raise ConfigError("devices must contain at least one device")
    return DaemonConfig(mqtt=mqtt, devices=devices)


def _parse_mqtt(raw: dict[str, Any]) -> MqttConfig:
    tls_raw = _optional_mapping(raw, "tls", "mqtt")
    username, username_env, username_file = _secret(raw, "username", "mqtt")
    password, password_env, password_file = _secret(raw, "password", "mqtt")
    return MqttConfig(
        host=_required_str(raw, "host", "mqtt"),
        port=_int(raw, "port", 1883, "mqtt", minimum=1, maximum=65535),
        username=username,
        username_env=username_env,
        username_file=username_file,
        password=password,
        password_env=password_env,
        password_file=password_file,
        tls=TlsConfig(
            enabled=_bool(tls_raw, "enabled", False, "mqtt.tls"),
            ca_file=_optional_str(tls_raw, "ca_file", "mqtt.tls"),
            cert_file=_optional_str(tls_raw, "cert_file", "mqtt.tls"),
            key_file=_optional_str(tls_raw, "key_file", "mqtt.tls"),
            insecure=_bool(tls_raw, "insecure", False, "mqtt.tls"),
        ),
        client_id=_str(raw, "client_id", "arcam-rs232", "mqtt"),
        daemon_topic=_topic(raw, "daemon_topic", "arcam/daemon", "mqtt"),
        retain=_bool(raw, "retain", True, "mqtt"),
        qos=_int(raw, "qos", 0, "mqtt", minimum=0, maximum=2),
    )


def _parse_device(device_id: str, raw: dict[str, Any]) -> DeviceConfig:
    zones_raw = _required_mapping(raw, "zones", f"devices.{device_id}")
    zones = {
        zone_name: _parse_zone(zone_name, _ensure_mapping(zone_raw, f"devices.{device_id}.zones.{zone_name}"))
        for zone_name, zone_raw in zones_raw.items()
    }
    if not zones:
        raise ConfigError(f"devices.{device_id}.zones must contain at least one zone")
    return DeviceConfig(
        id=device_id,
        model=_str(raw, "model", "unknown", f"devices.{device_id}"),
        topic=_topic(raw, "topic", f"arcam/{device_id}", f"devices.{device_id}"),
        transport=_parse_transport(_required_mapping(raw, "transport", f"devices.{device_id}"), device_id),
        polling=_parse_polling(_optional_mapping(raw, "polling", f"devices.{device_id}"), device_id),
        commands=_parse_commands(_optional_mapping(raw, "commands", f"devices.{device_id}"), device_id),
        zones=zones,
    )


def _parse_transport(raw: dict[str, Any], device_id: str) -> TransportConfig:
    ctx = f"devices.{device_id}.transport"
    transport_type = _required_str(raw, "type", ctx)
    if transport_type == "tcp":
        return TransportConfig(
            type="tcp",
            host=_required_str(raw, "host", ctx),
            port=_int(raw, "port", None, ctx, minimum=1, maximum=65535),
            timeout_seconds=_float(raw, "timeout_seconds", 1.0, ctx, minimum=0.1),
        )
    if transport_type == "serial":
        return TransportConfig(
            type="serial",
            serial_port=_required_str(raw, "port", ctx),
            baudrate=_int(raw, "baudrate", 38400, ctx, minimum=1),
            timeout_seconds=_float(raw, "timeout_seconds", 1.0, ctx, minimum=0.1),
        )
    raise ConfigError(f"{ctx}.type must be tcp or serial")


def _parse_polling(raw: dict[str, Any], device_id: str) -> PollingConfig:
    ctx = f"devices.{device_id}.polling"
    return PollingConfig(
        heartbeat_seconds=_float(raw, "heartbeat_seconds", 5, ctx, minimum=1),
        missed_heartbeats_limit=_int(raw, "missed_heartbeats_limit", 2, ctx, minimum=1),
        offline_retry_seconds=_float(raw, "offline_retry_seconds", 10, ctx, minimum=1),
        offline_backoff_max_seconds=_float(raw, "offline_backoff_max_seconds", 60, ctx, minimum=1),
        core_refresh_seconds=_float(raw, "core_refresh_seconds", 30, ctx, minimum=1),
        burst_collection_seconds=_float(raw, "burst_collection_seconds", 5, ctx, minimum=0),
    )


def _parse_commands(raw: dict[str, Any], device_id: str) -> CommandConfig:
    ctx = f"devices.{device_id}.commands"
    return CommandConfig(
        ack_timeout_seconds=_float(raw, "ack_timeout_seconds", 2, ctx, minimum=0.1),
        reject_when_unavailable=_bool(raw, "reject_when_unavailable", True, ctx),
        update_state_from_ack=_bool(raw, "update_state_from_ack", False, ctx),
    )


def _parse_zone(zone_name: str, raw: dict[str, Any]) -> ZoneConfig:
    ctx = f"zone {zone_name}"
    core = _str_list(raw, "core", ["power", "source", "volume", "mute"], ctx)
    extended = _str_list(raw, "extended", [], ctx)
    _validate_spec_names(core, f"{ctx}.core")
    _validate_spec_names(extended, f"{ctx}.extended")
    return ZoneConfig(
        enabled=_bool(raw, "enabled", True, ctx),
        control_requires_power_on=_bool(raw, "control_requires_power_on", True, ctx),
        power_command_allowed_when_device_online=_bool(raw, "power_command_allowed_when_device_online", True, ctx),
        core=tuple(core),
        extended=tuple(extended),
    )


def _required_mapping(raw: dict[str, Any], key: str, ctx: str) -> dict[str, Any]:
    if key not in raw:
        raise ConfigError(f"{ctx}.{key} is required")
    return _ensure_mapping(raw[key], f"{ctx}.{key}")


def _str_list(raw: dict[str, Any], key: str, default: list[str], ctx: str) -> list[str]:
    value = raw.get(key, default)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigError(f"{ctx}.{key} must be a list of strings")
    return value


def _validate_spec_names(names: list[str], ctx: str):
    from .registry import spec_by_name

    unknown = [name for name in names if spec_by_name(name) is None]
    if unknown:
        raise ConfigError(f"{ctx} contains unknown MQTT spec(s): {', '.join(unknown)}")


def _optional_mapping(raw: dict[str, Any], key: str, ctx: str) -> dict[str, Any]:
    value = raw.get(key, {})
    if value is None:
        return {}
    return _ensure_mapping(value, f"{ctx}.{key}")


def _ensure_mapping(value: Any, ctx: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{ctx} must be a mapping")
    return value


def _required_str(raw: dict[str, Any], key: str, ctx: str) -> str:
    if key not in raw:
        raise ConfigError(f"{ctx}.{key} is required")
    return _str(raw, key, "", ctx)


def _optional_str(raw: dict[str, Any], key: str, ctx: str) -> str | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigError(f"{ctx}.{key} must be a string or null")
    return value


def _secret(raw: dict[str, Any], key: str, ctx: str) -> tuple[str | None, str | None, str | None]:
    value = _optional_str(raw, key, ctx)
    env_key = f"{key}_env"
    file_key = f"{key}_file"
    env_name = _optional_str(raw, env_key, ctx)
    file_name = _optional_str(raw, file_key, ctx)
    configured = [source is not None for source in (value, env_name, file_name)].count(True)
    if configured > 1:
        raise ConfigError(f"{ctx}.{key}, {ctx}.{env_key}, and {ctx}.{file_key} are mutually exclusive")
    if env_name:
        value = os.getenv(env_name)
        if value is None:
            raise ConfigError(f"environment variable {env_name} from {ctx}.{env_key} is not set")
    if file_name:
        secret_path = Path(file_name)
        try:
            value = secret_path.read_text().strip()
        except OSError as exc:
            raise ConfigError(f"cannot read {ctx}.{file_key} {secret_path}: {exc}") from exc
    return value, env_name, file_name


def _str(raw: dict[str, Any], key: str, default: str, ctx: str) -> str:
    value = raw.get(key, default)
    if not isinstance(value, str) or not value:
        raise ConfigError(f"{ctx}.{key} must be a non-empty string")
    return value


def _topic(raw: dict[str, Any], key: str, default: str, ctx: str) -> str:
    value = _str(raw, key, default, ctx).strip("/")
    if not value or "//" in value:
        raise ConfigError(f"{ctx}.{key} must be a valid MQTT topic prefix")
    return value


def _bool(raw: dict[str, Any], key: str, default: bool, ctx: str) -> bool:
    value = raw.get(key, default)
    if not isinstance(value, bool):
        raise ConfigError(f"{ctx}.{key} must be true or false")
    return value


def _int(
    raw: dict[str, Any],
    key: str,
    default: int | None,
    ctx: str,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    if key not in raw:
        if default is None:
            raise ConfigError(f"{ctx}.{key} is required")
        value = default
    else:
        value = raw[key]
    if not isinstance(value, int) or isinstance(value, bool):
        raise ConfigError(f"{ctx}.{key} must be an integer")
    if minimum is not None and value < minimum:
        raise ConfigError(f"{ctx}.{key} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ConfigError(f"{ctx}.{key} must be <= {maximum}")
    return value


def _float(raw: dict[str, Any], key: str, default: float, ctx: str, minimum: float | None = None) -> float:
    value = raw.get(key, default)
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ConfigError(f"{ctx}.{key} must be a number")
    result = float(value)
    if minimum is not None and result < minimum:
        raise ConfigError(f"{ctx}.{key} must be >= {minimum}")
    return result
