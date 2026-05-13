# Changelog

## Unreleased

- Fixed MQTT scan handling so the daemon does not block the Paho network loop
  while publishing scan switch state back to `OFF`.
- Added timestamped daemon logging with `--log-level`, including `DEBUG` logs
  for MQTT messages, reconnects, scans, heartbeats, commands, and state updates.
- Added `--protocol-trace` to log raw ARCAM RS232/TCP TX/RX frames as HEX.
- Changed scan switch state so `state/scan=OFF` is published after the scan
  attempt finishes instead of immediately when the command is accepted.
- Publish `status/device=online` after the first valid ARCAM status frame,
  without waiting for the full configured bootstrap scan to finish.
- Fixed command ACK handling so direct command acknowledgements do not update
  MQTT state when `update_state_from_ack` is disabled.
- Give queued MQTT commands priority between bootstrap/scan requests, so slow
  extended reads do not block user control for the full bootstrap duration.
- Limit heartbeat polling to Zone 1 power, with a fallback to the first enabled
  zone if Zone 1 is disabled.
- Added MQTT support for generic named RC5 commands through `cmd/rc5`, including
  the `mode` RC5 alias.
- Added MQTT and OpenHAB support for `sub-stereo-trim` / `sub_stereo_trim`.
- Added MQTT and OpenHAB support for `subwoofer-trim` / `subwoofer_trim`.
- Changed the OpenHAB volume control example to a slider capped at `50 dB`.
- Added Docker troubleshooting notes for `docker logs`.

## v0.2.0

- Added MQTT scan command topics to wake offline device runners immediately:
  `arcam/daemon/cmd/scan` and `arcam/<device_id>/cmd/scan`.
- Added scan state topics for OpenHAB switch controls:
  `arcam/daemon/state/scan` and `arcam/<device_id>/state/scan`.
- The daemon now interrupts offline retry backoff when a scan command is received.
- Online runners refresh configured state when a scan command is received.
- Updated OpenHAB examples and documentation for the scan switch.

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
