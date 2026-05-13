from __future__ import annotations

import socket
import threading
import time
import logging
from dataclasses import dataclass, field
from queue import Empty, Queue
from typing import Callable

from .config import DeviceConfig
from .mqtt import OFFLINE, ONLINE, MqttBridge
from .protocol import FrameReader, hex_bytes, request_frame
from .registry import MqttSpec, command_spec_for_topic, spec_for_frame, specs_for_names
from .transport import make_config_transport

LOGGER = logging.getLogger(__name__)


@dataclass
class DeviceRunner:
    device: DeviceConfig
    mqtt: MqttBridge
    stop_requested: bool = False
    state: dict[str, dict[str, str]] = field(default_factory=dict)
    command_queue: Queue["MqttCommand"] = field(default_factory=Queue)
    scan_queue: Queue["ScanRequest"] = field(default_factory=Queue)
    subscribed: bool = False
    published: dict[str, str] = field(default_factory=dict)
    wake_event: threading.Event = field(default_factory=threading.Event)
    protocol_trace: bool = False

    def run_forever(self):
        retry_delay = self.device.polling.offline_retry_seconds
        while not self.stop_requested:
            scan_requests = self._drain_scan_requests()
            try:
                self._run_connected(scan_requests)
                retry_delay = self.device.polling.offline_retry_seconds
            except (OSError, TimeoutError, socket.timeout) as exc:
                self._publish_device_status(OFFLINE)
                self._publish_all_zone_control("stale")
                self._complete_scan_requests(scan_requests)
                LOGGER.warning(
                    "%s: connection failed: %s; retrying in %.1f seconds",
                    self.device.id,
                    exc,
                    retry_delay,
                )
                self.wake_event.wait(retry_delay)
                self.wake_event.clear()
                retry_delay = min(retry_delay * 2, self.device.polling.offline_backoff_max_seconds)

    def stop(self):
        self.stop_requested = True
        self.wake()

    def wake(self, on_scan_complete: Callable[[], None] | None = None):
        LOGGER.debug("%s: wake requested", self.device.id)
        if on_scan_complete is not None:
            self.scan_queue.put(ScanRequest(on_complete=on_scan_complete))
        self.wake_event.set()

    def _run_connected(self, initial_scan_requests: list["ScanRequest"] | None = None):
        transport = make_config_transport(self.device.transport)
        reader = FrameReader()
        missed = 0
        try:
            LOGGER.info("%s: connected to %s", self.device.id, transport.label)
            self._subscribe_commands()
            if not self._refresh_configured_state(transport, reader):
                raise TimeoutError("no bootstrap response from device")
            self._publish_device_status(ONLINE)
            self._publish_unknown_control_for_missing_power()
            LOGGER.info("%s: bootstrap completed", self.device.id)
            self._complete_scan_requests(initial_scan_requests or [])

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
                if self.wake_event.is_set():
                    self.wake_event.clear()
                    scan_requests = self._drain_scan_requests()
                    LOGGER.info("%s: scan requested; refreshing configured state", self.device.id)
                    try:
                        self._refresh_configured_state(transport, reader)
                    finally:
                        self._complete_scan_requests(scan_requests)
                    next_heartbeat = time.monotonic() + self.device.polling.heartbeat_seconds
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
            LOGGER.info("%s: disconnected", self.device.id)

    def _refresh_configured_state(self, transport, reader: FrameReader) -> bool:
        seen = False
        for zone_name, zone in self.device.zones.items():
            if not zone.enabled:
                continue
            zone_id = _zone_number(zone_name)
            for spec in specs_for_names((*zone.core, *zone.extended)):
                if not spec.can_read:
                    continue
                frame = request_frame(zone_id, spec.request_command)
                self._trace_tx(f"{zone_name}/{spec.name} request", frame)
                transport.write(frame)
                LOGGER.debug(
                    "%s: requesting %s/%s",
                    self.device.id,
                    zone_name,
                    spec.name,
                )
                seen = self._collect(transport, reader, self.device.transport.timeout_seconds) or seen
        return seen

    def _poll_power(self, transport, reader: FrameReader) -> bool:
        seen = False
        for zone_name, zone in self.device.zones.items():
            if not zone.enabled:
                continue
            zone_id = _zone_number(zone_name)
            frame = request_frame(zone_id, 0x00)
            self._trace_tx(f"{zone_name}/power heartbeat", frame)
            transport.write(frame)
            LOGGER.debug("%s: heartbeat power request for %s", self.device.id, zone_name)
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
                self._trace_rx(raw)
                seen = True
                self._handle_frame(raw)
        return seen

    def _handle_frame(self, raw: bytes):
        if len(raw) < 6 or raw[3] != 0x00:
            return
        zone_id = raw[1]
        command = raw[2]
        data = raw[5:-1]
        spec = spec_for_frame(command)
        if spec is None or spec.parse_state is None:
            return
        value = spec.parse_state(data)
        if value is None:
            return
        zone_topic = f"zone{zone_id}"
        self.state.setdefault(zone_topic, {})[spec.name] = value
        LOGGER.debug("%s: state %s/%s=%s", self.device.id, zone_topic, spec.topic, value)
        self.mqtt.publish(f"{self.device.topic}/{zone_topic}/state/{spec.topic}", value)
        if spec.name == "power":
            self._publish_zone_control(zone_topic, "available" if value == "on" else "unavailable")

    def _publish_device_status(self, payload: str):
        self._publish_retained(f"{self.device.topic}/status/device", payload)

    def _publish_all_zone_control(self, payload: str):
        for zone_name, zone in self.device.zones.items():
            if zone.enabled:
                self._publish_zone_control(zone_name, payload)

    def _publish_zone_control(self, zone_name: str, payload: str):
        self._publish_retained(f"{self.device.topic}/{zone_name}/status/control", payload)

    def _publish_unknown_control_for_missing_power(self):
        for zone_name, zone in self.device.zones.items():
            if not zone.enabled:
                continue
            if self.state.get(zone_name, {}).get("power") is None:
                self._publish_zone_control(zone_name, "unknown")

    def _publish_retained(self, topic: str, payload: str):
        if self.published.get(topic) == payload:
            return
        self.mqtt.publish(topic, payload)
        self.published[topic] = payload

    def _subscribe_commands(self):
        if self.subscribed:
            return

        def enqueue(message):
            if message.retain:
                return
            parsed = _parse_command_topic(self.device.topic, message.topic)
            if parsed is None:
                return
            zone_name, command_name, spec = parsed
            payload = message.payload.decode("utf-8", "replace").strip()
            self.command_queue.put(MqttCommand(zone_name=zone_name, command=command_name, payload=payload, spec=spec))

        self.mqtt.subscribe(f"{self.device.topic}/+/cmd/+", enqueue)
        self.subscribed = True
        LOGGER.info("%s: subscribed to command topics", self.device.id)

    def _execute_command(self, transport, reader: FrameReader, command: "MqttCommand"):
        try:
            zone_id = _zone_number(command.zone_name)
            if command.spec.build_command is None:
                raise ValueError(f"{command.command} is read-only")
            frame = command.spec.build_command(zone_id, command.payload)
            if not self._command_allowed(command):
                self._publish_command_event(command, "rejected: zone control unavailable")
                return
        except ValueError as exc:
            self._publish_command_event(command, f"rejected: {exc}")
            return

        expected_rc5 = frame[4:6] if len(frame) == 7 and frame[2] == 0x08 and frame[3] == 0x02 else None
        LOGGER.info(
            "%s: executing command %s/%s payload=%s",
            self.device.id,
            command.zone_name,
            command.command,
            command.payload,
        )
        self._trace_tx(f"{command.zone_name}/{command.command} command", frame)
        transport.write(frame)
        ack_seen = self._collect_command_response(transport, reader, frame, expected_rc5)
        if ack_seen:
            self._publish_command_event(command, f"accepted: tx {hex_bytes(frame)}")
        else:
            self._publish_command_event(command, f"ack timeout: tx {hex_bytes(frame)}")
        if command.spec.burst_after_command:
            self._collect(transport, reader, self.device.polling.burst_collection_seconds)

    def _command_allowed(self, command: "MqttCommand") -> bool:
        if not self.device.commands.reject_when_unavailable:
            return True
        if not command.spec.power_required:
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
                self._trace_rx(raw)
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

    def _drain_scan_requests(self) -> list["ScanRequest"]:
        requests = []
        while True:
            try:
                requests.append(self.scan_queue.get_nowait())
            except Empty:
                return requests

    def _complete_scan_requests(self, requests: list["ScanRequest"]):
        for request in requests:
            try:
                request.on_complete()
            except Exception:
                LOGGER.exception("%s: scan completion callback failed", self.device.id)

    def _trace_tx(self, label: str, frame: bytes):
        if self.protocol_trace:
            LOGGER.info("%s: TX %s: %s", self.device.id, label, hex_bytes(frame))

    def _trace_rx(self, frame: bytes):
        if self.protocol_trace:
            LOGGER.info("%s: RX: %s", self.device.id, hex_bytes(frame))


def _zone_number(zone_name: str) -> int:
    normalized = zone_name.strip().lower()
    if normalized.startswith("zone"):
        normalized = normalized[4:]
    return int(normalized, 10)


@dataclass(frozen=True)
class MqttCommand:
    zone_name: str
    command: str
    payload: str
    spec: MqttSpec


@dataclass(frozen=True)
class ScanRequest:
    on_complete: Callable[[], None]


def _parse_command_topic(device_topic: str, topic: str) -> tuple[str, str, MqttSpec] | None:
    prefix = device_topic.strip("/")
    parts = topic.strip("/").split("/")
    prefix_parts = prefix.split("/")
    if parts[: len(prefix_parts)] != prefix_parts:
        return None
    tail = parts[len(prefix_parts) :]
    if len(tail) != 3 or tail[1] != "cmd":
        return None
    spec = command_spec_for_topic(tail[2])
    if spec is None:
        return None
    return tail[0], tail[2], spec


def _is_expected_ack(raw: bytes, frame: bytes, expected_rc5: bytes | None) -> bool:
    if len(raw) < 6 or raw[3] != 0x00:
        return False
    if expected_rc5 is not None:
        return raw[2] == 0x08 and raw[4] == 0x02 and raw[5:7] == expected_rc5
    return raw[1] == frame[1] and raw[2] == frame[2]
