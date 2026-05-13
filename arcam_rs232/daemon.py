import argparse
import json
import threading
import time
from dataclasses import asdict

from .config import ConfigError, load_config
from .mqtt import MqttBridge
from .runner import DeviceRunner


def build_parser():
    parser = argparse.ArgumentParser(description="Arcam RS232 MQTT daemon")
    parser.add_argument("--config", default="config.example.yaml", help="Path to daemon YAML configuration")
    parser.add_argument("--print-config", action="store_true", help="Load, validate, and print normalized config as JSON")
    parser.add_argument("--once", action="store_true", help="Connect to MQTT, publish daemon online/offline, then exit")
    return parser


def arcam_daemon():
    args = build_parser().parse_args()
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        raise SystemExit(f"Configuration error: {exc}") from exc

    if args.print_config:
        print(json.dumps(asdict(config), indent=2, sort_keys=True))
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
