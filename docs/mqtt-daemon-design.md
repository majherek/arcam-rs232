# MQTT Daemon Design

This document defines the MQTT daemon for `arcam-rs232`.

The daemon is a long-running bridge between one or more Arcam AVR500/AVR600/AV888 devices and a plain MQTT broker such as Mosquitto. It is intended to integrate cleanly with openHAB through Generic MQTT Things, without requiring a custom openHAB binding.

## Goals

- Support multiple Arcam devices from one daemon process.
- Support TCP and serial transports per device.
- Publish device and zone states to MQTT.
- Subscribe to MQTT command topics and translate them to RS232/RC5 commands.
- Keep the existing CLI working independently.
- Detect when the daemon is alive.
- Detect when each Arcam device is reachable.
- Handle devices that are physically disconnected from power most of the time.
- Treat ACK as command acceptance, not as proof of final state.
- Update state only from Arcam status frames or explicit responses.
- Run in Docker, with systemd as an alternative.

## Non-Goals For The First Daemon Version

- Native openHAB binding.
- Homie auto-discovery.
- Automatic openHAB item creation.
- Full support for tuner/RDS/DAB features on AV888 profiles without tuner hardware.
- Optimistic state updates based only on RC5 ACK.

## Process And Devices

There is one daemon process and one MQTT connection.

The daemon may manage multiple configured Arcam devices:

```text
arcam-rs232-daemon
  mqtt client
  device runner: av888
  device runner: avr600-office
  device runner: ...
```

Each device runner owns:

- One transport connection.
- One command queue.
- One frame reader.
- One state store.
- One heartbeat loop.
- One MQTT topic prefix.

## MQTT Topic Layout

The daemon has one global status topic:

```text
arcam/daemon
```

Payloads:

```text
online
offline
```

This topic is also the MQTT Last Will and Testament (LWT). It represents daemon availability, not receiver power.

Each configured device has a topic prefix:

```text
arcam/<device_id>
```

Example:

```text
arcam/av888
arcam/avr600-office
```

## Device Topics

Device availability:

```text
arcam/<device_id>/status/device
arcam/<device_id>/status/last_seen
arcam/<device_id>/status/last_error
```

Payloads:

```text
status/device = online | offline
status/last_seen = ISO-8601 timestamp
status/last_error = text
```

`status/device` means whether the Arcam device is reachable and responding. It is not the same as Zone 1 power. For TCP RS232-to-Ethernet converters, a successful TCP connection is not enough to publish `online`; the daemon publishes `online` only after it receives a valid Arcam response/status frame.
`status/last_seen` and `status/last_error` are planned diagnostics topics.

## Zone Topics

Each zone has state and command topics.

Zone 1 example:

```text
arcam/av888/zone1/status/control

arcam/av888/zone1/state/power
arcam/av888/zone1/state/source
arcam/av888/zone1/state/volume
arcam/av888/zone1/state/mute

arcam/av888/zone1/cmd/power
arcam/av888/zone1/cmd/source
arcam/av888/zone1/cmd/volume
arcam/av888/zone1/cmd/mute
```

Zone 2 and Zone 3 use the same shape:

```text
arcam/av888/zone2/...
arcam/av888/zone3/...
```

## Payloads

Power:

```text
state/power = on | standby | unknown
cmd/power = on | standby
```

Source:

```text
state/source = CD | DVD | AV | SAT | PVR | VCR | Tape | Aux | Phono | Tuner AM | Tuner FM | Tuner Digital | MCH | NET | iPod | unknown
cmd/source = one of the supported source names
```

Volume:

```text
state/volume = numeric value, for example 11.5
cmd/volume = numeric value
```

Mute:

```text
state/mute = muted | unmuted | unknown
cmd/mute = on | off
```

Control availability:

```text
status/control = available | unavailable | stale | unknown
```

Meaning:

- `available`: normal controls for the zone should be shown/enabled.
- `unavailable`: device is reachable, but normal zone controls should not be used in the current state.
- `stale`: last known state exists, but the device is currently unreachable or heartbeat failed.
- `unknown`: daemon has not yet discovered enough state.

Power is special: zone power commands are allowed when the device is online, even if `status/control` is `unavailable`.

## Availability Rules

Global daemon:

```text
arcam/daemon = online
```

Device:

```text
arcam/<device_id>/status/device = online
```

Zone control:

For AV888 defaults:

```text
zone1/status/control = available when zone1 power is on
zone1/status/control = unavailable when zone1 power is standby

zone2/status/control = available when zone2 power is on
zone2/status/control = unavailable when zone2 power is standby

zone3/status/control = available when zone3 power is on
zone3/status/control = unavailable when zone3 power is standby
```

Zone power commands remain valid when:

```text
status/device = online
```

This matters for installations where Zone 2 or Zone 3 power controls external hardware such as a power amplifier trigger or speaker lift, even when Zone 1 is in standby.

## ACK And State Updates

RC5 ACK means the Arcam accepted the simulated RC5 command. It does not prove that the final user-visible state changed.

Example observed on AV888:

```text
Zone 1 standby
send source PVR
receive RC5 ACK
get source still returns AV
```

Therefore:

- The daemon publishes command ACK events separately.
- The daemon does not update `state/*` from RC5 ACK alone.
- `state/*` changes only when a matching status frame or explicit `get` response is received.

Suggested event topics:

```text
arcam/<device_id>/event/command_ack
arcam/<device_id>/event/command_error
```

Example payloads:

```text
zone1 source PVR ack
zone1 source PVR rejected: zone control unavailable
zone3 power on ack
```

## Command Handling

The daemon uses a command/state registry. Configured zone `core` and `extended`
lists select which values are requested during bootstrap, and the same registry
defines which MQTT command topics are writable.

The current daemon subscribes to command topics in this shape:

```text
arcam/<device_id>/zoneX/cmd/power
arcam/<device_id>/zoneX/cmd/source
arcam/<device_id>/zoneX/cmd/volume
arcam/<device_id>/zoneX/cmd/mute
arcam/<device_id>/zoneX/cmd/room_eq
arcam/<device_id>/zoneX/cmd/dolby_volume
arcam/<device_id>/zoneX/cmd/direct
```

Retained MQTT command messages are ignored to avoid replaying old commands when
the daemon reconnects.

The current read-only extended state allowlist is:

```text
decode_2ch
decode_mch
incoming_audio
sample_rate
audio_input
video_input
```

For every MQTT command:

1. Check `status/device`.
2. Check zone command rules.
3. Send the RS232 or RC5 frame.
4. Wait for direct response or RC5 ACK.
5. Publish command event.
6. Collect all status frames received after the command.
7. Update state store from all decoded frames, regardless of which command caused them.

The daemon should not filter incoming frames to only the command being executed. Arcam devices often emit bursts of related state after a single command.

## Power-On Burst Handling

Observed AV888 behavior: after `power on` or some zone power commands, the receiver emits a burst containing many states, including Zone 1 video/audio settings and Zone 2/3 source, volume, mute, and power.

Daemon behavior:

1. Enter a short `burst_collection` window after power-related commands.
2. Collect and apply all received status frames.
3. Avoid aggressive polling during this window.
4. After the window, poll only missing core fields.

Default burst collection window:

```text
5 seconds
```

Configurable per device.

## Core State

Minimal core state per zone:

```text
power
source
volume
mute
```

The daemon should try to know these values for each enabled zone.

If a zone field is unknown after bootstrap, it may remain `unknown` until the device reports it. This should not block other zones from operating.

## Extended State

Extended state is opt-in per zone through config. Example:

```yaml
zones:
  zone1:
    core:
      - power
      - source
      - volume
      - mute
    extended:
      - room-eq
      - dolby-volume
      - direct
      - decode-2ch
      - decode-mch
      - incoming-audio
      - sample-rate
      - audio-input
      - video-input
```

## Polling

All polling intervals are configurable.

Recommended defaults:

```text
heartbeat_seconds = 5
missed_heartbeats_limit = 2
offline_retry_seconds = 10
offline_backoff_max_seconds = 60
core_refresh_seconds = 30
burst_collection_seconds = 5
```

The current runner sends `get power` to every enabled zone on each heartbeat, so
zone power states stay fresh even when Zone 1 is in standby. A future profile may
choose another harmless request if needed.

When heartbeat fails repeatedly:

- Publish `status/device = offline`.
- Publish zone `status/control = stale`.
- Keep retained last known states, but mark them stale through zone status.

`offline_retry_seconds` is the first retry delay after a failed connection or
bootstrap. `offline_backoff_max_seconds` is the maximum delay after exponential
backoff. For example, `10` and `60` produce retry delays of roughly `10`, `20`,
`40`, `60`, `60` seconds.

The daemon also supports explicit scan wake-up commands:

```text
arcam/daemon/cmd/scan = now
arcam/<device_id>/cmd/scan = now
```

The global command wakes all configured device runners. The per-device command
wakes only the selected runner. If a runner is offline, the command interrupts
the current backoff sleep and starts a retry immediately. If a runner is already
online, it refreshes the configured state. Retained scan commands are ignored.

For OpenHAB switch controls, the daemon publishes scan state back to `OFF`
after accepting a scan command:

```text
arcam/daemon/state/scan = OFF
arcam/<device_id>/state/scan = OFF
```

## Retain Policy

Retain should be configurable.

Recommended retained topics:

```text
arcam/daemon
arcam/<device_id>/status/device
arcam/<device_id>/status/last_seen
arcam/<device_id>/zoneX/status/control
arcam/<device_id>/zoneX/state/*
```

Recommended non-retained topics:

```text
arcam/<device_id>/event/*
arcam/<device_id>/diagnostics/last_rx
arcam/<device_id>/diagnostics/last_tx
```

## Docker And systemd

The daemon supports both:

```text
Docker / docker compose
systemd service
```

The same YAML config file should be usable in both modes.

Daemon command:

```bash
arcam-daemon --config /etc/arcam-rs232/config.yaml
```

MQTT username and password can be provided directly, through environment
variables, or through files. Only one source may be configured per field.

```yaml
mqtt:
  username: arcam
  # username_env: ARCAM_MQTT_USERNAME
  # username_file: /run/secrets/arcam_mqtt_username

  password_env: ARCAM_MQTT_PASSWORD
  # password: change-me
  # password_file: /run/secrets/arcam_mqtt_password
```

Example deployment files:

```text
Dockerfile
docker-compose.example.yml
config.av888.example.yaml
packaging/arcam-rs232.service
packaging/arcam-rs232.env.example
```

## openHAB Integration

Use openHAB Generic MQTT Things.

Each Item can use:

- state topic: `.../state/...`
- command topic: `.../cmd/...`

Rules are not required for normal widgets such as:

- source dropdown
- volume slider
- mute switch
- power switch

Rules remain useful for scenes and automations.

MainUI or sitemap visibility can use:

```text
status/device == online
zoneX/status/control == available
```

Zone power controls should use only:

```text
status/device == online
```
