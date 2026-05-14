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
from .protocol import FrameReader, hex_bytes, rc5_frame_from_alias, request_frame
from .registry import MqttSpec, command_spec_for_topic, normalize_spec_name, spec_by_name, spec_for_frame, specs_for_names
from .transport import make_config_transport

LOGGER = logging.getLogger(__name__)
DECODE_2CH_MODE_PRESS_DELAY_SECONDS = 0.5

DECODE_2CH_MODE_ORDER = (
    "Stereo",
    "Dolby Pro Logic Emulation",
    "Pro Logic II/x Movie",
    "Pro Logic II/x Music",
    "Pro Logic II Matrix",
    "Pro Logic II Game",
    "Neo:6 Cinema",
    "Neo:6 Music",
)

DECODE_2CH_MODE_ALIASES = {
    "0x01": "Stereo",
    "1": "Stereo",
    "stereo": "Stereo",
    "0x02": "Pro Logic II/x Movie",
    "2": "Pro Logic II/x Movie",
    "pro-logic-ii/x-movie": "Pro Logic II/x Movie",
    "pro-logic-ii-x-movie": "Pro Logic II/x Movie",
    "pro-logic-iix-movie": "Pro Logic II/x Movie",
    "plii-movie": "Pro Logic II/x Movie",
    "movie": "Pro Logic II/x Movie",
    "0x03": "Pro Logic II/x Music",
    "3": "Pro Logic II/x Music",
    "pro-logic-ii/x-music": "Pro Logic II/x Music",
    "pro-logic-ii-x-music": "Pro Logic II/x Music",
    "pro-logic-iix-music": "Pro Logic II/x Music",
    "plii-music": "Pro Logic II/x Music",
    "music": "Pro Logic II/x Music",
    "0x04": "Pro Logic II Matrix",
    "4": "Pro Logic II Matrix",
    "pro-logic-ii-matrix": "Pro Logic II Matrix",
    "matrix": "Pro Logic II Matrix",
    "0x05": "Pro Logic II Game",
    "5": "Pro Logic II Game",
    "pro-logic-ii-game": "Pro Logic II Game",
    "game": "Pro Logic II Game",
    "0x06": "Dolby Pro Logic Emulation",
    "6": "Dolby Pro Logic Emulation",
    "dolby-pro-logic-emulation": "Dolby Pro Logic Emulation",
    "pro-logic-emulation": "Dolby Pro Logic Emulation",
    "emulation": "Dolby Pro Logic Emulation",
    "0x07": "Neo:6 Cinema",
    "7": "Neo:6 Cinema",
    "neo:6-cinema": "Neo:6 Cinema",
    "neo-6-cinema": "Neo:6 Cinema",
    "neo6-cinema": "Neo:6 Cinema",
    "cinema": "Neo:6 Cinema",
    "0x08": "Neo:6 Music",
    "8": "Neo:6 Music",
    "neo:6-music": "Neo:6 Music",
    "neo-6-music": "Neo:6 Music",
    "neo6-music": "Neo:6 Music",
}


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
    last_activity: float = field(default_factory=time.monotonic)

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
            self._publish_unknown_control_for_missing_power()
            LOGGER.info("%s: bootstrap completed", self.device.id)
            self._complete_scan_requests(initial_scan_requests or [])

            next_heartbeat = self.last_activity + self.device.polling.heartbeat_seconds
            while not self.stop_requested:
                now = time.monotonic()
                command_timeout = min(0.2, max(0.0, next_heartbeat - now))
                try:
                    command = self.command_queue.get(timeout=command_timeout)
                except Empty:
                    command = None
                if command is not None:
                    self._execute_command(transport, reader, command)
                    next_heartbeat = self.last_activity + self.device.polling.heartbeat_seconds
                    continue
                if self.wake_event.is_set():
                    self.wake_event.clear()
                    scan_requests = self._drain_scan_requests()
                    LOGGER.info("%s: scan requested; refreshing configured state", self.device.id)
                    try:
                        self._refresh_configured_state(transport, reader)
                    finally:
                        self._complete_scan_requests(scan_requests)
                    next_heartbeat = self.last_activity + self.device.polling.heartbeat_seconds
                    continue
                if self._collect(transport, reader, 0.05):
                    missed = 0
                    next_heartbeat = self.last_activity + self.device.polling.heartbeat_seconds
                    continue
                if time.monotonic() < next_heartbeat:
                    continue
                got_response = self._poll_power(transport, reader)
                if got_response:
                    missed = 0
                    next_heartbeat = self.last_activity + self.device.polling.heartbeat_seconds
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
                self._execute_pending_commands(transport, reader)
        return seen

    def _poll_power(self, transport, reader: FrameReader) -> bool:
        seen = False
        for zone_name in self._heartbeat_zones():
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
                self._mark_activity()
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
        self._publish_device_status(ONLINE)
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
        if command.spec.name == "decode-2ch-mode":
            self._execute_decode_2ch_mode_command(transport, reader, command)
            return

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
        self._mark_activity()
        ack_seen = self._collect_command_response(transport, reader, frame, expected_rc5)
        if ack_seen:
            self._publish_command_event(command, f"accepted: tx {hex_bytes(frame)}")
        else:
            self._publish_command_event(command, f"ack timeout: tx {hex_bytes(frame)}")
        if command.spec.burst_after_command:
            self._collect(transport, reader, self.device.polling.burst_collection_seconds)

    def _execute_decode_2ch_mode_command(self, transport, reader: FrameReader, command: "MqttCommand"):
        try:
            zone_id = _zone_number(command.zone_name)
            if zone_id != 0x01:
                raise ValueError("decode-2ch-mode is only available for Zone 1")
            if not self._command_allowed(command):
                self._publish_command_event(command, "rejected: zone control unavailable")
                return
            target = _decode_2ch_target(command.payload)
            self._request_state(transport, reader, command.zone_name, "audio-input")
            audio_input = self.state.get(command.zone_name, {}).get("audio-input")
            if audio_input != "Analogue":
                raise ValueError(f"decode-2ch-mode requires audio-input Analogue, current={audio_input or 'unknown'}")
            self._request_state(transport, reader, command.zone_name, "decode-2ch")
            current = self.state.get(command.zone_name, {}).get("decode-2ch")
            if current not in DECODE_2CH_MODE_ORDER:
                raise ValueError(f"unknown current decode-2ch mode: {current or 'unknown'}")
        except ValueError as exc:
            self._publish_command_event(command, f"rejected: {exc}")
            return

        current_index = DECODE_2CH_MODE_ORDER.index(current)
        target_index = DECODE_2CH_MODE_ORDER.index(target)
        steps = (target_index - current_index) % len(DECODE_2CH_MODE_ORDER)
        if steps == 0:
            self._publish_command_event(command, f"accepted: already {target}")
            return
        presses = steps + 1

        frame = rc5_frame_from_alias(zone_id, "mode")
        LOGGER.info(
            "%s: cycling decode-2ch from %s to %s with %d RC5 mode step(s) and %d press(es)",
            self.device.id,
            current,
            target,
            steps,
            presses,
        )
        for press in range(presses):
            self._trace_tx(f"{command.zone_name}/decode-2ch-mode press {press + 1}/{presses}", frame)
            transport.write(frame)
            self._mark_activity()
            if press + 1 < presses:
                self._collect(transport, reader, DECODE_2CH_MODE_PRESS_DELAY_SECONDS)

        self._collect(transport, reader, min(1.0, self.device.polling.burst_collection_seconds))
        self._request_state(transport, reader, command.zone_name, "decode-2ch")
        final = self.state.get(command.zone_name, {}).get("decode-2ch", "unknown")
        self._publish_command_event(command, f"accepted: {current} -> {target}, steps={steps}, presses={presses}, final={final}")

    def _request_state(self, transport, reader: FrameReader, zone_name: str, spec_name: str) -> bool:
        spec = spec_by_name(spec_name)
        if spec is None or spec.request_command is None:
            return False
        zone_id = _zone_number(zone_name)
        frame = request_frame(zone_id, spec.request_command)
        self._trace_tx(f"{zone_name}/{spec.name} request", frame)
        transport.write(frame)
        LOGGER.debug("%s: requesting %s/%s", self.device.id, zone_name, spec.name)
        return self._collect(transport, reader, self.device.transport.timeout_seconds)

    def _execute_pending_commands(self, transport, reader: FrameReader):
        while True:
            try:
                command = self.command_queue.get_nowait()
            except Empty:
                return
            self._execute_command(transport, reader, command)

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
                self._mark_activity()
                self._trace_rx(raw)
                is_ack = _is_expected_ack(raw, frame, expected_rc5)
                if is_ack:
                    ack_seen = True
                    if not self.device.commands.update_state_from_ack:
                        continue
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

    def _heartbeat_zones(self) -> tuple[str, ...]:
        zone1 = self.device.zones.get("zone1")
        if zone1 is not None and zone1.enabled:
            return ("zone1",)
        for zone_name, zone in self.device.zones.items():
            if zone.enabled:
                return (zone_name,)
        return ()

    def _trace_tx(self, label: str, frame: bytes):
        if self.protocol_trace:
            LOGGER.info("%s: TX %s: %s", self.device.id, label, hex_bytes(frame))

    def _trace_rx(self, frame: bytes):
        if self.protocol_trace:
            LOGGER.info("%s: RX: %s", self.device.id, hex_bytes(frame))

    def _mark_activity(self):
        self.last_activity = time.monotonic()


def _zone_number(zone_name: str) -> int:
    normalized = zone_name.strip().lower()
    if normalized.startswith("zone"):
        normalized = normalized[4:]
    return int(normalized, 10)


def _decode_2ch_target(payload: str) -> str:
    key = normalize_spec_name(payload)
    target = DECODE_2CH_MODE_ALIASES.get(key)
    if target is None:
        choices = ", ".join(DECODE_2CH_MODE_ORDER)
        raise ValueError(f"decode-2ch-mode must be one of: {choices}")
    return target


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
