# openHAB MQTT Example

Example files for openHAB Generic MQTT integration:

```text
openhab/arcam-av888.things
openhab/arcam-av888.items
openhab/arcam-av888.sitemap
```

Install them under your openHAB config directory:

```text
$OPENHAB_CONF/things/arcam-av888.things
$OPENHAB_CONF/items/arcam-av888.items
$OPENHAB_CONF/sitemaps/arcam-av888.sitemap
```

The Thing file assumes that your MQTT broker already exists in openHAB as:

```text
mqtt:broker:mybroker
```

Change the bridge UID in `arcam-av888.things` if your broker uses another id.

The file defines two Things:

```text
Thing mqtt:topic:arcamDaemon
Thing mqtt:topic:arcamAV888
```

`arcamDaemon` availability follows the daemon LWT/status topic:

```text
arcam/daemon = online | offline
```

It also exposes a manual scan command:

```text
arcam/daemon/cmd/scan = ON
arcam/daemon/state/scan = OFF
```

The scan channel is a `Switch`: OpenHAB sends `ON`, and the daemon publishes
`OFF` after accepting the scan request.

`arcamAV888` availability follows the physical receiver status:

```text
arcam/av888/status/device = online | offline
```

The sitemap uses `visibility=[... AND ...]` for daemon/device readiness and
`zoneX/status/control` for zone-specific controls. Zone power controls stay
visible whenever the daemon and device are online; other Zone 1 controls are
visible only when `zone1/status/control` is `available`.

Logical on/off fields use MQTT `switch` channels:

```text
power: on <-> standby
mute: muted <-> unmuted
room_eq: On <-> Off
direct: On <-> Off
```

`zoneX/status/control` stays a string because it can be `available`,
`unavailable`, `stale`, or `unknown`.

Reference: https://www.openhab.org/docs/ui/sitemaps
