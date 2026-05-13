from __future__ import annotations

import ssl
from dataclasses import dataclass
from typing import Callable

import paho.mqtt.client as mqtt

from .config import MqttConfig


ONLINE = "online"
OFFLINE = "offline"


@dataclass(frozen=True)
class PublishResult:
    topic: str
    payload: str


class MqttBridge:
    def __init__(self, config: MqttConfig):
        self.config = config
        self._subscriptions: dict[str, Callable[[mqtt.MQTTMessage], None]] = {}
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=config.client_id)
        self.client.on_message = self._on_message
        if config.username is not None:
            self.client.username_pw_set(config.username, config.password)
        if config.tls.enabled:
            self._configure_tls(config)
        self.client.will_set(config.daemon_topic, OFFLINE, qos=config.qos, retain=config.retain)

    def connect(self):
        self.client.connect(self.config.host, self.config.port)
        self.client.loop_start()
        self.publish_daemon_status(ONLINE)

    def disconnect(self):
        self.publish_daemon_status(OFFLINE)
        self.client.loop_stop()
        self.client.disconnect()

    def publish_daemon_status(self, payload: str) -> PublishResult:
        self.publish(self.config.daemon_topic, payload)
        return PublishResult(topic=self.config.daemon_topic, payload=payload)

    def publish(self, topic: str, payload: str, retain: bool | None = None) -> PublishResult:
        effective_retain = self.config.retain if retain is None else retain
        result = self.client.publish(topic, payload, qos=self.config.qos, retain=effective_retain)
        result.wait_for_publish()
        return PublishResult(topic=topic, payload=payload)

    def subscribe(self, topic: str, callback: Callable[[mqtt.MQTTMessage], None]):
        self._subscriptions[topic] = callback
        self.client.subscribe(topic, qos=self.config.qos)

    def _configure_tls(self, config: MqttConfig):
        self.client.tls_set(
            ca_certs=config.tls.ca_file,
            certfile=config.tls.cert_file,
            keyfile=config.tls.key_file,
            tls_version=ssl.PROTOCOL_TLS_CLIENT,
        )
        self.client.tls_insecure_set(config.tls.insecure)

    def _on_message(self, client, userdata, message: mqtt.MQTTMessage):
        for topic_filter, callback in self._subscriptions.items():
            if mqtt.topic_matches_sub(topic_filter, message.topic):
                callback(message)
