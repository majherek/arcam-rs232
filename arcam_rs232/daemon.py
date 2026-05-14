import argparse
import json
import logging
import threading
import time
from dataclasses import asdict
from typing import Any

from . import package_version
from .config import ConfigError, load_config
from .mqtt import MqttBridge
from .registry import MQTT_SPECS
from .runner import DeviceRunner

LOGGER = logging.getLogger(__name__)


def build_parser():
    parser = argparse.ArgumentParser(description="Arcam RS232 MQTT daemon")
    parser.add_argument("--version", action="version", version=f"arcam-daemon {package_version()}")
    parser.add_argument("--config", default="config.example.yaml", help="Path to daemon YAML configuration")
    parser.add_argument("--print-config", action="store_true", help="Load, validate, and print normalized config as JSON")
    parser.add_argument("--list-specs", action="store_true", help="List MQTT state/command specs usable in zone core/extended")
    parser.add_argument("--once", action="store_true", help="Connect to MQTT, publish daemon online/offline, then exit")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        help="Daemon log verbosity",
    )
    parser.add_argument(
        "--protocol-trace",
        action="store_true",
        help="Log ARCAM RS232/TCP TX/RX frames as HEX",
    )
    return parser


def configure_logging(level: str):
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s %(levelname)s [%(threadName)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )


def print_specs():
    headers = ("name", "topic", "read", "write", "values")
    rows = [
        (
            spec.name,
            spec.topic,
            "yes" if spec.can_read else "no",
            "yes" if spec.can_write else "no",
            spec.values,
        )
        for spec in MQTT_SPECS
    ]
    widths = [max(len(str(row[index])) for row in (headers, *rows)) for index in range(len(headers))]
    print("  ".join(value.ljust(widths[index]) for index, value in enumerate(headers)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)))


def redacted_config(config) -> dict[str, Any]:
    data = asdict(config)
    mqtt = data.get("mqtt")
    if isinstance(mqtt, dict):
        mqtt["username"] = "<set>" if mqtt.get("username") else None
        mqtt["password"] = "<set>" if mqtt.get("password") else None
    return data


def daemon_topic_prefix(daemon_topic: str) -> str:
    topic = daemon_topic.strip("/")
    if "/" not in topic:
        return ""
    return topic.rsplit("/", 1)[0]


def subscribe_scan_commands(bridge: MqttBridge, config, runners: list[DeviceRunner]):
    by_id = {runner.device.id: runner for runner in runners}
    daemon_prefix = daemon_topic_prefix(config.mqtt.daemon_topic)
    daemon_scan_state_topic = f"{config.mqtt.daemon_topic}/state/scan"

    def publish_scan_off(topic: str):
        def complete():
            LOGGER.info("Scan completed for %s.", topic)
            bridge.publish_async(topic, "OFF")

        return complete

    def publish_scan_off_after_all(topic: str, count: int):
        remaining = count
        lock = threading.Lock()

        def complete():
            nonlocal remaining
            with lock:
                remaining -= 1
                if remaining > 0:
                    return
            LOGGER.info("Scan completed for %s.", topic)
            bridge.publish_async(topic, "OFF")

        return complete

    def valid_scan_payload(message) -> bool:
        if message.retain:
            return False
        payload = message.payload.decode("utf-8", "replace").strip().lower()
        return payload in ("", "scan", "now", "1", "true", "on")

    def scan_all(message):
        if not valid_scan_payload(message):
            return
        LOGGER.info("Received daemon scan request.")
        complete = publish_scan_off_after_all(daemon_scan_state_topic, len(runners))
        for runner in runners:
            runner.wake(complete)

    def scan_device(message):
        if not valid_scan_payload(message):
            return
        topic = message.topic.strip("/")
        suffix = "/cmd/scan"
        if not daemon_prefix or not topic.endswith(suffix):
            return
        device_id = topic[len(daemon_prefix) + 1 : -len(suffix)]
        runner = by_id.get(device_id)
        if runner is None:
            return
        LOGGER.info("Received scan request for %s.", device_id)
        runner.wake(publish_scan_off(f"{daemon_prefix}/{device_id}/state/scan"))

    bridge.subscribe(f"{config.mqtt.daemon_topic}/cmd/scan", scan_all)
    bridge.publish(daemon_scan_state_topic, "OFF")
    if daemon_prefix:
        bridge.subscribe(f"{daemon_prefix}/+/cmd/scan", scan_device)
        for runner in runners:
            bridge.publish(f"{daemon_prefix}/{runner.device.id}/state/scan", "OFF")


def arcam_daemon():
    args = build_parser().parse_args()
    configure_logging(args.log_level)
    if args.list_specs:
        print_specs()
        return

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        raise SystemExit(f"Configuration error: {exc}") from exc

    if args.print_config:
        print(json.dumps(redacted_config(config), indent=2, sort_keys=True))
        return

    bridge = MqttBridge(config.mqtt)
    bridge.connect()
    LOGGER.info("MQTT bridge started; daemon status topic is %s", config.mqtt.daemon_topic)
    runners = [
        DeviceRunner(device=device, mqtt=bridge, protocol_trace=args.protocol_trace)
        for device in config.devices.values()
    ]
    subscribe_scan_commands(bridge, config, runners)
    threads: list[threading.Thread] = []
    try:
        if args.once:
            time.sleep(0.2)
            return
        for runner in runners:
            thread = threading.Thread(target=runner.run_forever, name=f"arcam-{runner.device.id}", daemon=True)
            thread.start()
            threads.append(thread)
        LOGGER.info("Daemon is running with %d device runner(s).", len(threads))
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        LOGGER.info("Stopping daemon.")
    finally:
        for runner in runners:
            runner.stop()
        for thread in threads:
            thread.join(timeout=3)
        bridge.disconnect()


if __name__ == "__main__":
    arcam_daemon()
