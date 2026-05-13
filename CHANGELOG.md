# Changelog

## v0.1.1

- Fixed MQTT device availability for RS232-to-Ethernet converters.
- `status/device=online` is now published only after a valid Arcam response/status frame is received.
- Avoided false `online` / `unknown` flapping when the TCP converter is reachable but the receiver is powered off.
- Deduplicated repeated retained `status/device` and `zoneX/status/control` publications.
- Updated openHAB examples to use switch channels for binary states.

## v0.1.0

- Initial MQTT daemon release.
- Added RS232/TCP CLI package layout.
- Added MQTT daemon with device runners, heartbeat polling, command topics, and retained state.
- Added Docker, systemd, GitHub Actions, and openHAB examples.
