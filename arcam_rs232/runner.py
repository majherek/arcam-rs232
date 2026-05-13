from __future__ import annotations

import socket
import time
from dataclasses import dataclass, field
from queue import Empty, Queue

from .config import DeviceConfig
from .mqtt import OFFLINE, ONLINE, MqttBridge
from .protocol import (
    FrameReader,
    SOURCE_MAP,
    build_frame,
    hex_bytes,
    rc5_frame_from_alias,
    request_frame,
    source_to_rc5_alias,
    volume_to_byte,
    zone_rc5_alias,
)
from .transport import make_config_transport


COMMAND_TO_STATE = {
    0x00: "power",
    0x0D: "volume",
    0x0E: "mute",
    0x1D: "source",
}
CORE_COMMANDS = {
    "power": 0x00,
    "volume": 0x0D,
    "mute": 0x0E,
    "source": 0x1D,
}


@dataclass
class DeviceRunner:
    device: DeviceConfig
    mqtt: MqttBridge
    stop_requested: bool = False
    state: dict[str, dict[str, str]] = field(default_factory=dict)
    command_queue: Queue["MqttCommand"] = field(default_factory=Queue)
    subscribed: bool = False

    def run_forever(self):
        retry_delay = self.device.polling.offline_retry_seconds
        while not self.stop_requested:
            try:
                self._run_connected()
                retry_delay = self.device.polling.offline_retry_seconds
            except (OSError, TimeoutError, socket.timeout) as exc:
                self._publish_device_status(OFFLINE)
                self._publish_all_zone_control("stale")
                print(f"{self.device.id}: connection failed: {exc}")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, self.device.polling.offline_backoff_max_seconds)

    def stop(self):
        self.stop_requested = True

    def _run_connected(self):
        transport = make_config_transport(self.device.transport)
        reader = FrameReader()
        missed = 0
        try:
            print(f"{self.device.id}: connected to {transport.label}")
            self._publish_device_status(ONLINE)
            self._publish_all_zone_control("unknown")
            self._subscribe_commands()
            self._refresh_core(transport, reader)

            next_heartbeat = time.monotonic()
            while not self.stop_requested:
                now = time.monotonic()
                command_timeout = min(0.2, max(0.0, next_heartbeat - now))
                try:
                    command = self.command_queue.get(timeout=command_timeout)
                except Empty:
                    command = None
                if command is not None:
                    self._execute_command(transport, reader, command)
                    continue
                self._collect(transport, reader, 0.05)
                if time.monotonic() < next_heartbeat:
                    continue
                got_response = self._poll_power(transport, reader)
                if got_response:
                    missed = 0
                else:
                    missed += 1
                    if missed >= self.device.polling.missed_heartbeats_limit:
                        raise TimeoutError("missed heartbeat responses")
                next_heartbeat = time.monotonic() + self.device.polling.heartbeat_seconds
        finally:
            transport.close()
            self._publish_device_status(OFFLINE)
            self._publish_all_zone_control("stale")
            self._discard_pending_commands()

    def _refresh_core(self, transport, reader: FrameReader):
        for zone_name, zone in self.device.zones.items():
            if not zone.enabled:
                continue
            zone_id = _zone_number(zone_name)
            for item in zone.core:
                command = CORE_COMMANDS.get(item)
                if command is None:
                    continue
                transport.write(request_frame(zone_id, command))
                self._collect(transport, reader, self.device.transport.timeout_seconds)

    def _poll_power(self, transport, reader: FrameReader) -> bool:
        seen = False
        for zone_name, zone in self.device.zones.items():
            if not zone.enabled:
                continue
            zone_id = _zone_number(zone_name)
            transport.write(request_frame(zone_id, 0x00))
            seen = self._collect(transport, reader, self.device.transport.timeout_seconds) or seen
        return seen

    def _collect(self, transport, reader: FrameReader, wait_seconds: float) -> bool:
        deadline = time.monotonic() + wait_seconds
        seen = False
        while time.monotonic() < deadline:
            try:
                chunk = transport.read(4096)
            except (TimeoutError, socket.timeout):
                continue
            if not chunk:
                continue
            for raw in reader.feed(chunk):
                seen = True
                self._handle_frame(raw)
        return seen

    def _handle_frame(self, raw: bytes):
        if len(raw) < 6 or raw[3] != 0x00:
            return
        zone_id = raw[1]
        command = raw[2]
        data = raw[5:-1]
        state_name = COMMAND_TO_STATE.get(command)
        if state_name is None:
            return
        value = _state_value(command, data)
        if value is None:
            return
        zone_topic = f"zone{zone_id}"
        self.state.setdefault(zone_topic, {})[state_name] = value
        self.mqtt.publish(f"{self.device.topic}/{zone_topic}/state/{state_name}", value)
        if state_name == "power":
            self._publish_zone_control(zone_topic, "available" if value == "on" else "unavailable")

    def _publish_device_status(self, payload: str):
        self.mqtt.publish(f"{self.device.topic}/status/device", payload)

    def _publish_all_zone_control(self, payload: str):
        for zone_name, zone in self.device.zones.items():
            if zone.enabled:
                self._publish_zone_control(zone_name, payload)

    def _publish_zone_control(self, zone_name: str, payload: str):
        self.mqtt.publish(f"{self.device.topic}/{zone_name}/status/control", payload)

    def _subscribe_commands(self):
        if self.subscribed:
            return

        def enqueue(message):
            if message.retain:
                return
            parsed = _parse_command_topic(self.device.topic, message.topic)
            if parsed is None:
                return
            zone_name, command_name = parsed
            payload = message.payload.decode("utf-8", "replace").strip()
            self.command_queue.put(MqttCommand(zone_name=zone_name, command=command_name, payload=payload))

        self.mqtt.subscribe(f"{self.device.topic}/+/cmd/+", enqueue)
        self.subscribed = True

    def _execute_command(self, transport, reader: FrameReader, command: "MqttCommand"):
        try:
            zone_id = _zone_number(command.zone_name)
            frame = self._build_command_frame(zone_id, command)
            if not self._command_allowed(command):
                self._publish_command_event(command, "rejected: zone control unavailable")
                return
        except ValueError as exc:
            self._publish_command_event(command, f"rejected: {exc}")
            return

        expected_rc5 = frame[4:6] if len(frame) == 7 and frame[2] == 0x08 and frame[3] == 0x02 else None
        transport.write(frame)
        ack_seen = self._collect_command_response(transport, reader, frame, expected_rc5)
        if ack_seen:
            self._publish_command_event(command, f"accepted: tx {hex_bytes(frame)}")
        else:
            self._publish_command_event(command, f"ack timeout: tx {hex_bytes(frame)}")
        if command.command == "power":
            self._collect(transport, reader, self.device.polling.burst_collection_seconds)

    def _build_command_frame(self, zone_id: int, command: "MqttCommand") -> bytes:
        payload = command.payload.strip()
        if command.command == "power":
            value = payload.lower()
            if value not in ("on", "standby"):
                raise ValueError("power must be on or standby")
            alias = zone_rc5_alias(zone_id, "power-on" if value == "on" else "power-off")
            return rc5_frame_from_alias(zone_id, alias)
        if command.command == "source":
            return rc5_frame_from_alias(zone_id, source_to_rc5_alias(zone_id, payload))
        if command.command == "volume":
            return build_frame(zone_id, 0x0D, [volume_to_byte(zone_id, payload)])
        if command.command == "mute":
            value = payload.lower()
            if value not in ("on", "off"):
                raise ValueError("mute must be on or off")
            alias = zone_rc5_alias(zone_id, f"mute-{value}")
            return rc5_frame_from_alias(zone_id, alias)
        raise ValueError(f"unsupported command {command.command}")

    def _command_allowed(self, command: "MqttCommand") -> bool:
        if not self.device.commands.reject_when_unavailable:
            return True
        if command.command == "power":
            return True
        zone_state = self.state.get(command.zone_name, {})
        return zone_state.get("power") == "on"

    def _collect_command_response(self, transport, reader: FrameReader, frame: bytes, expected_rc5: bytes | None) -> bool:
        deadline = time.monotonic() + self.device.commands.ack_timeout_seconds
        ack_seen = False
        while time.monotonic() < deadline:
            try:
                chunk = transport.read(4096)
            except (TimeoutError, socket.timeout):
                continue
            if not chunk:
                continue
            for raw in reader.feed(chunk):
                if _is_expected_ack(raw, frame, expected_rc5):
                    ack_seen = True
                self._handle_frame(raw)
        return ack_seen

    def _publish_command_event(self, command: "MqttCommand", payload: str):
        self.mqtt.publish(
            f"{self.device.topic}/{command.zone_name}/event/{command.command}",
            payload,
            retain=False,
        )

    def _discard_pending_commands(self):
        while True:
            try:
                self.command_queue.get_nowait()
            except Empty:
                return


def _zone_number(zone_name: str) -> int:
    normalized = zone_name.strip().lower()
    if normalized.startswith("zone"):
        normalized = normalized[4:]
    return int(normalized, 10)


def _state_value(command: int, data: bytes) -> str | None:
    if command == 0x00 and len(data) == 1:
        return "on" if data[0] == 0x01 else "standby"
    if command == 0x0D and len(data) == 2:
        return str(data[0] + 0.5 if data[1] == 0x05 else data[0])
    if command == 0x0E and len(data) == 1:
        return "muted" if data[0] == 0x00 else "unmuted"
    if command == 0x1D and len(data) == 1:
        return SOURCE_MAP.get(data[0], f"0x{data[0]:02X}")
    return None


@dataclass(frozen=True)
class MqttCommand:
    zone_name: str
    command: str
    payload: str


def _parse_command_topic(device_topic: str, topic: str) -> tuple[str, str] | None:
    prefix = device_topic.strip("/")
    parts = topic.strip("/").split("/")
    prefix_parts = prefix.split("/")
    if parts[: len(prefix_parts)] != prefix_parts:
        return None
    tail = parts[len(prefix_parts) :]
    if len(tail) != 3 or tail[1] != "cmd":
        return None
    return tail[0], tail[2]


def _is_expected_ack(raw: bytes, frame: bytes, expected_rc5: bytes | None) -> bool:
    if len(raw) < 6 or raw[3] != 0x00:
        return False
    if expected_rc5 is not None:
        return raw[2] == 0x08 and raw[4] == 0x02 and raw[5:7] == expected_rc5
    return raw[1] == frame[1] and raw[2] == frame[2]
