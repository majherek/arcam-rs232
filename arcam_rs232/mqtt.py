from __future__ import annotations

import ssl
import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable

import paho.mqtt.client as mqtt

from .config import MqttConfig


ONLINE = "online"
OFFLINE = "offline"
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class PublishResult:
    topic: str
    payload: str


class MqttBridge:
    def __init__(self, config: MqttConfig):
        self.config = config
        self._subscriptions: dict[str, Callable[[mqtt.MQTTMessage], None]] = {}
        self._subscriptions_lock = threading.RLock()
        self._disconnect_times: list[float] = []
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=config.client_id)
        self.client.on_message = self._on_message
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.enable_logger(LOGGER)
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        if config.username is not None:
            self.client.username_pw_set(config.username, config.password)
        if config.tls.enabled:
            self._configure_tls(config)
        self.client.will_set(config.daemon_topic, OFFLINE, qos=config.qos, retain=config.retain)

    def connect(self):
        LOGGER.info("Connecting to MQTT %s:%s", self.config.host, self.config.port)
        self.client.connect(self.config.host, self.config.port)
        self.client.loop_start()

    def disconnect(self):
        LOGGER.info("Disconnecting from MQTT")
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
        LOGGER.debug("MQTT publish topic=%s retain=%s payload=%s", topic, effective_retain, payload)
        return PublishResult(topic=topic, payload=payload)

    def publish_async(self, topic: str, payload: str, retain: bool | None = None) -> PublishResult:
        effective_retain = self.config.retain if retain is None else retain
        self.client.publish(topic, payload, qos=self.config.qos, retain=effective_retain)
        LOGGER.debug("MQTT publish async topic=%s retain=%s payload=%s", topic, effective_retain, payload)
        return PublishResult(topic=topic, payload=payload)

    def subscribe(self, topic: str, callback: Callable[[mqtt.MQTTMessage], None]):
        with self._subscriptions_lock:
            self._subscriptions[topic] = callback
        self.client.subscribe(topic, qos=self.config.qos)
        LOGGER.info("MQTT subscribe topic=%s", topic)

    def _configure_tls(self, config: MqttConfig):
        self.client.tls_set(
            ca_certs=config.tls.ca_file,
            certfile=config.tls.cert_file,
            keyfile=config.tls.key_file,
            tls_version=ssl.PROTOCOL_TLS_CLIENT,
        )
        self.client.tls_insecure_set(config.tls.insecure)

    def _on_message(self, client, userdata, message: mqtt.MQTTMessage):
        with self._subscriptions_lock:
            subscriptions = tuple(self._subscriptions.items())
        for topic_filter, callback in subscriptions:
            if mqtt.topic_matches_sub(topic_filter, message.topic):
                try:
                    LOGGER.debug(
                        "MQTT message topic=%s retain=%s payload=%r",
                        message.topic,
                        message.retain,
                        message.payload,
                    )
                    callback(message)
                except Exception:
                    LOGGER.exception("MQTT callback failed for topic=%s", message.topic)

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        LOGGER.info("MQTT connected reason=%s", reason_code)
        with self._subscriptions_lock:
            topics = tuple(self._subscriptions)
        for topic in topics:
            client.subscribe(topic, qos=self.config.qos)
            LOGGER.info("MQTT resubscribe topic=%s", topic)
        self.publish_async(self.config.daemon_topic, ONLINE)

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        LOGGER.warning("MQTT disconnected flags=%s reason=%s", disconnect_flags, reason_code)
        now = time.monotonic()
        self._disconnect_times = [value for value in self._disconnect_times if now - value <= 15]
        self._disconnect_times.append(now)
        if len(self._disconnect_times) >= 3:
            LOGGER.warning(
                "MQTT disconnected %d times in %.0f seconds. Check for another daemon/client using the same "
                "MQTT client_id=%r; duplicate client IDs cause broker-side disconnect/reconnect loops and LWT "
                "offline flapping.",
                len(self._disconnect_times),
                now - self._disconnect_times[0],
                self.config.client_id,
            )
