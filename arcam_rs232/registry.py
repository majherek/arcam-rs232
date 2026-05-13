from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .protocol import (
    AUDIO_FORMAT,
    AUDIO_CHANNEL_CONFIG,
    AUDIO_INPUT_TYPE,
    DECODE_2CH,
    DECODE_MCH,
    DIRECT_MODE,
    DOLBY_VOLUME,
    ROOM_EQ,
    SAMPLE_RATE_MAP,
    SOURCE_MAP,
    VIDEO_INPUT_TYPE,
    build_frame,
    rc5_frame_from_alias,
    source_to_rc5_alias,
    sub_stereo_trim_to_byte,
    volume_to_byte,
    zone_rc5_alias,
)


StateParser = Callable[[bytes], str | None]
FrameBuilder = Callable[[int, str], bytes]


@dataclass(frozen=True)
class MqttSpec:
    name: str
    topic: str
    values: str = ""
    request_command: int | None = None
    state_command: int | None = None
    parse_state: StateParser | None = None
    build_command: FrameBuilder | None = None
    power_required: bool = True
    burst_after_command: bool = False

    def matches_command(self, command: int) -> bool:
        return self.state_command == command

    @property
    def can_read(self) -> bool:
        return self.request_command is not None and self.parse_state is not None

    @property
    def can_write(self) -> bool:
        return self.build_command is not None


def normalize_spec_name(value: str) -> str:
    return value.strip().lower().replace("_", "-").replace(" ", "-")


def spec_by_name(name: str) -> MqttSpec | None:
    return SPECS_BY_NAME.get(normalize_spec_name(name))


def specs_for_names(names: tuple[str, ...] | list[str]) -> list[MqttSpec]:
    specs: list[MqttSpec] = []
    for name in names:
        spec = spec_by_name(name)
        if spec is not None:
            specs.append(spec)
    return specs


def spec_for_frame(command: int) -> MqttSpec | None:
    return SPECS_BY_COMMAND.get(command)


def command_spec_for_topic(topic_name: str) -> MqttSpec | None:
    normalized = normalize_spec_name(topic_name)
    return SPECS_BY_NAME.get(normalized) or SPECS_BY_TOPIC.get(topic_name.strip().lower())


def _power_value(data: bytes) -> str | None:
    if len(data) != 1:
        return None
    return "on" if data[0] == 0x01 else "standby"


def _source_value(data: bytes) -> str | None:
    if len(data) != 1:
        return None
    return SOURCE_MAP.get(data[0], f"0x{data[0]:02X}")


def _volume_value(data: bytes) -> str | None:
    if len(data) != 2:
        return None
    return str(data[0] + 0.5 if data[1] == 0x05 else data[0])


def _sub_stereo_trim_value(data: bytes) -> str | None:
    if len(data) != 1:
        return None
    value = data[0]
    if value == 0x00:
        return "0"
    if 0x80 <= value <= 0xA7:
        return str(-((value - 0x7F) * 0.25))
    return f"0x{value:02X}"


def _mute_value(data: bytes) -> str | None:
    if len(data) != 1:
        return None
    return "muted" if data[0] == 0x00 else "unmuted"


def _mapped_value(mapping: dict[int, str]) -> StateParser:
    def parse(data: bytes) -> str | None:
        if len(data) != 1:
            return None
        return mapping.get(data[0], f"0x{data[0]:02X}")

    return parse


def _incoming_audio_value(data: bytes) -> str | None:
    if len(data) != 2:
        return None
    audio_format = AUDIO_FORMAT.get(data[0], f"0x{data[0]:02X}")
    channel_config = AUDIO_CHANNEL_CONFIG.get(data[1], f"0x{data[1]:02X}")
    return f"{audio_format}, {channel_config}"


def _build_power(zone: int, payload: str) -> bytes:
    value = payload.strip().lower()
    if value not in ("on", "standby"):
        raise ValueError("power must be on or standby")
    alias = zone_rc5_alias(zone, "power-on" if value == "on" else "power-off")
    return rc5_frame_from_alias(zone, alias)


def _build_source(zone: int, payload: str) -> bytes:
    return rc5_frame_from_alias(zone, source_to_rc5_alias(zone, payload))


def _build_volume(zone: int, payload: str) -> bytes:
    return build_frame(zone, 0x0D, [volume_to_byte(zone, payload)])


def _build_mute(zone: int, payload: str) -> bytes:
    value = payload.strip().lower()
    aliases = {"muted": "on", "unmuted": "off"}
    value = aliases.get(value, value)
    if value not in ("on", "off"):
        raise ValueError("mute must be on, off, muted, or unmuted")
    return rc5_frame_from_alias(zone, zone_rc5_alias(zone, f"mute-{value}"))


def _build_room_eq(zone: int, payload: str) -> bytes:
    values = {"on": 0xF1, "off": 0xF2}
    value = payload.strip().lower()
    if value not in values:
        raise ValueError("room-eq must be on or off")
    return build_frame(zone, 0x37, [values[value]])


def _build_dolby_volume(zone: int, payload: str) -> bytes:
    values = {"off": 0x00, "music": 0x01, "movie": 0x02}
    value = payload.strip().lower()
    if value not in values:
        raise ValueError("dolby-volume must be off, music, or movie")
    return build_frame(zone, 0x38, [values[value]])


def _build_direct(zone: int, payload: str) -> bytes:
    value = payload.strip().lower()
    if value not in ("on", "off"):
        raise ValueError("direct must be on or off")
    return rc5_frame_from_alias(zone, zone_rc5_alias(zone, f"direct-{value}"))


def _build_sub_stereo_trim(zone: int, payload: str) -> bytes:
    return build_frame(zone, 0x45, [sub_stereo_trim_to_byte(payload)])


def _build_rc5(zone: int, payload: str) -> bytes:
    return rc5_frame_from_alias(zone, payload)


MQTT_SPECS = (
    MqttSpec("power", "power", "on|standby", 0x00, 0x00, _power_value, _build_power, power_required=False, burst_after_command=True),
    MqttSpec("source", "source", "source name, e.g. AV|PVR|SAT", 0x1D, 0x1D, _source_value, _build_source),
    MqttSpec("volume", "volume", "numeric dB value", 0x0D, 0x0D, _volume_value, _build_volume),
    MqttSpec("mute", "mute", "on|off command, muted|unmuted state", 0x0E, 0x0E, _mute_value, _build_mute),
    MqttSpec("room-eq", "room_eq", "on|off", 0x37, 0x37, _mapped_value(ROOM_EQ), _build_room_eq),
    MqttSpec("dolby-volume", "dolby_volume", "off|music|movie", 0x38, 0x38, _mapped_value(DOLBY_VOLUME), _build_dolby_volume),
    MqttSpec("direct", "direct", "on|off", 0x0F, 0x0F, _mapped_value(DIRECT_MODE), _build_direct),
    MqttSpec("sub-stereo-trim", "sub_stereo_trim", "numeric dB value in 0.25 dB steps, -10.0..0.0", 0x45, 0x45, _sub_stereo_trim_value, _build_sub_stereo_trim),
    MqttSpec("rc5", "rc5", "named RC5 alias, e.g. mode|display-off|volume-up", None, None, None, _build_rc5),
    MqttSpec("decode-2ch", "decode_2ch", "read-only decode mode", 0x10, 0x10, _mapped_value(DECODE_2CH), None),
    MqttSpec("decode-mch", "decode_mch", "read-only decode mode", 0x11, 0x11, _mapped_value(DECODE_MCH), None),
    MqttSpec("incoming-audio", "incoming_audio", "read-only audio format", 0x43, 0x43, _incoming_audio_value, None),
    MqttSpec("sample-rate", "sample_rate", "read-only sample rate", 0x44, 0x44, _mapped_value(SAMPLE_RATE_MAP), None),
    MqttSpec("audio-input", "audio_input", "read-only audio input type", 0x0B, 0x0B, _mapped_value(AUDIO_INPUT_TYPE), None),
    MqttSpec("video-input", "video_input", "read-only video input type", 0x0C, 0x0C, _mapped_value(VIDEO_INPUT_TYPE), None),
)

SPECS_BY_NAME = {spec.name: spec for spec in MQTT_SPECS}
SPECS_BY_TOPIC = {spec.topic: spec for spec in MQTT_SPECS}
SPECS_BY_COMMAND = {spec.state_command: spec for spec in MQTT_SPECS if spec.state_command is not None}
