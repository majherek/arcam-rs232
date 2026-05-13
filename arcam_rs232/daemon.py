import argparse
import json
import threading
import time
from dataclasses import asdict
from typing import Any

from .config import ConfigError, load_config
from .mqtt import MqttBridge
from .registry import MQTT_SPECS
from .runner import DeviceRunner


def build_parser():
    parser = argparse.ArgumentParser(description="Arcam RS232 MQTT daemon")
    parser.add_argument("--config", default="config.example.yaml", help="Path to daemon YAML configuration")
    parser.add_argument("--print-config", action="store_true", help="Load, validate, and print normalized config as JSON")
    parser.add_argument("--list-specs", action="store_true", help="List MQTT state/command specs usable in zone core/extended")
    parser.add_argument("--once", action="store_true", help="Connect to MQTT, publish daemon online/offline, then exit")
    return parser


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


def arcam_daemon():
    args = build_parser().parse_args()
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
    print(f"Published daemon status online to {config.mqtt.daemon_topic}")
    runners = [DeviceRunner(device=device, mqtt=bridge) for device in config.devices.values()]
    threads: list[threading.Thread] = []
    try:
        if args.once:
            time.sleep(0.2)
            return
        for runner in runners:
            thread = threading.Thread(target=runner.run_forever, name=f"arcam-{runner.device.id}", daemon=True)
            thread.start()
            threads.append(thread)
        print(f"Daemon is running with {len(threads)} device runner(s).")
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("Stopping daemon.")
    finally:
        for runner in runners:
            runner.stop()
        for thread in threads:
            thread.join(timeout=3)
        bridge.disconnect()


if __name__ == "__main__":
    arcam_daemon()
