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

Adjust the MQTT broker bridge in `arcam-av888.things` before using it:

```text
Bridge mqtt:broker:mosquitto "Mosquitto MQTT Broker" [
    host="mosquitto",
    port=1883,
    secure=false
]
```

If you already have an MQTT Broker Thing in openHAB, either reuse its bridge id
in the channel links or remove the bridge block and move the topic Thing under
your existing broker.

The sitemap uses `visibility=[... AND ...]` for daemon/device readiness and
`zoneX/status/control` for zone-specific controls. Zone power controls stay
visible whenever the daemon and device are online; other Zone 1 controls are
visible only when `zone1/status/control` is `available`.

Reference: https://www.openhab.org/docs/ui/sitemaps
