import argparse
import json
from dataclasses import asdict

from .config import ConfigError, load_config


def build_parser():
    parser = argparse.ArgumentParser(description="Arcam RS232 MQTT daemon")
    parser.add_argument("--config", default="config.example.yaml", help="Path to daemon YAML configuration")
    parser.add_argument("--print-config", action="store_true", help="Load, validate, and print normalized config as JSON")
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

    raise SystemExit("Daemon runtime is not implemented yet. Use --print-config to validate configuration.")


if __name__ == "__main__":
    arcam_daemon()
