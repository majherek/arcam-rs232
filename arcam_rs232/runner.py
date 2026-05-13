from __future__ import annotations

import socket
import time
from dataclasses import dataclass, field

from .config import DeviceConfig
from .mqtt import OFFLINE, ONLINE, MqttBridge
from .protocol import FrameReader, SOURCE_MAP, request_frame
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
            self._refresh_core(transport, reader)

            while not self.stop_requested:
                got_response = self._poll_power(transport, reader)
                if got_response:
                    missed = 0
                else:
                    missed += 1
                    if missed >= self.device.polling.missed_heartbeats_limit:
                        raise TimeoutError("missed heartbeat responses")
                time.sleep(self.device.polling.heartbeat_seconds)
        finally:
            transport.close()
            self._publish_device_status(OFFLINE)
            self._publish_all_zone_control("stale")

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
