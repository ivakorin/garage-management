import asyncio
import json
import logging
from typing import Callable, Optional

from core.settings import settings
from services.mqtt_client import AsyncMQTTClient

logger = logging.getLogger(__name__)


def create_mqtt_client(
    broker: Optional[str] = None,
    port: Optional[int] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    client_id: Optional[str] = None,
) -> AsyncMQTTClient:
    """
    Factory for creating an instance of AsyncMQTTClient with default settings from the config.

    :param broker: address of the MQTT broker (if None, taken from settings.mqtt.host)
    :param port: port of the MQTT broker (if None, from settings.mqtt.port)
    :param username: login (if None— from settings.mqtt.username)
    :param password: password (if None— from settings.mqtt.password)
    :param client_id: client ID (if None is 'gm—gateway')
    :return: AsyncMQTTClient instance
    """
    return AsyncMQTTClient(
        broker=broker or settings.mqtt.host,
        port=port or settings.mqtt.port,
        username=username or settings.mqtt.username,
        password=password or settings.mqtt.password,
        client_id=client_id or "gm-gateway",
    )


async def safe_subscribe(
    mqtt_client: AsyncMQTTClient,
    topic: str,
    callback: Callable,
    max_retries: int = 3,
    retry_delay: float = 1.0,
) -> bool:
    """Secure subscription to the MQTT topic with repeated attempts."""
    for attempt in range(max_retries + 1):
        try:
            await mqtt_client.subscribe(topic, callback)
            logger.info(f"Subscribed to the MQTT topic: {topic}")
            return True

        except Exception as e:
            if attempt < max_retries:
                logger.warning(
                    f"Error subscribing to {topic} (attempt {attempt + 1}/{max_retries}): {e}. "
                    f"Retrying after {retry_delay} s."
                )
                await asyncio.sleep(retry_delay)
            else:
                logger.error(
                    f"Failed to subscribe to {topic} after {max_retries} attempts: {e}"
                )
                return False
    return False


async def safe_unsubscribe(
    mqtt_client: AsyncMQTTClient,
    topic: str,
    max_retries: int = 3,
    retry_delay: float = 1.0,
) -> bool:
    """
    Secure unsubscription from the MQTT topic with repeated attempts.

    :param mqtt_client: instance of AsyncMQTTClient
    :param topic: unsubscribe topic
    :param max_retries: maximum number of attempts
    :param retry_delay: delay between attempts (in seconds)
    :return: True if unsubscription is successful, otherwise False
    """
    for attempt in range(max_retries + 1):
        try:
            await mqtt_client.unsubscribe(topic)
            logger.info(f"Unsubscribed from the MQTT topic: {topic}")
            return True

        except Exception as e:
            if attempt < max_retries:
                logger.warning(
                    f"Error unsubscribing from {topic} (attempt {attempt + 1}/{max_retries}): {e}. "
                    f" Will be repeated after {retry_delay} with."
                )
                await asyncio.sleep(retry_delay)
            else:
                logger.error(
                    f"Couldn't unsubscribe from {topic} after {max_retries} attempts: {e}"
                )
                return False

    return False


async def wait_for_mqtt_connection(
    mqtt_client: AsyncMQTTClient,
    timeout: float = 30.0,
    check_interval: float = 1.0,
) -> bool:
    """
    Waits for a connection to be established with the MQTT broker within the specified time.

    :param mqtt_client: instance of AsyncMQTTClient
    :param timeout: maximum waiting time (in seconds)
    :param check_interval: status check interval (in seconds)
    :return: True if connection is established, otherwise False
    """
    start_time = asyncio.get_event_loop().time()

    while (asyncio.get_event_loop().time() - start_time) < timeout:
        if mqtt_client.is_connected:
            logger.info("MQTT client is connected")
            return True
        await asyncio.sleep(check_interval)

    logger.error(
        f"The waiting time for the MQTT connection has been exceeded (>{timeout} s)"
    )
    return False


def is_topic_match(pattern: str, topic: str) -> bool:
    """
    Checks whether the topic matches the specified template with MQTT‑wildcard (#, +).

    :param pattern: topic template (for example, 'devices/+/data')
    :param topic: actual topic (for example, 'devices/sensor1/data')
    :return: True if the topic matches the template
    """
    import fnmatch

    # Replacing MQTT-wildcard with fnmatch templates
    pattern = pattern.replace("#", "**").replace("+", "*")

    if pattern.endswith("**"):
        prefix = pattern[:-2]
        return topic.startswith(prefix)

    return fnmatch.fnmatch(topic, pattern)


async def publish_with_retry(
    mqtt_client: AsyncMQTTClient,
    topic: str,
    payload: dict,
    qos: int = 0,
    retain: bool = False,
    max_retries: int = 2,
    retry_delay: float = 1.0,
) -> bool:
    """
    Publishes a message to MQTT with repeated attempts.

    :param mqtt_client: instance of AsyncMQTTClient
    :param topic: topic for publication
    :param payload: data (dictionary, to be serialized in JSON)
    :param qos: QoS level (0, 1, 2)
    :param retain: retain message flag
    :param max_retries: number of retries
    :param retry_delay: delay between attempts (in seconds)
    :return: True if the publication is successful, otherwise False
    """
    if not mqtt_client.is_connected:
        logger.warning(f"MQTT is not connected. Skipping the publication: {topic}")
        return False

    payload_str = None
    try:
        payload_str = json.dumps(payload)
    except (TypeError, ValueError) as e:
        logger.error(f"Unable to serialize payload for {topic}: {e}")
        return False

    for attempt in range(max_retries + 1):
        try:
            await mqtt_client.publish(topic, payload_str, qos=qos, retain=retain)
            logger.debug(f"Published in MQTT: {topic} → {payload_str}")
            return True

        except Exception as e:
            if attempt < max_retries:
                logger.warning(
                    f"Error publishing in {topic} (attempt {attempt + 1}/{max_retries}): {e}. "
                    f" Will be repeated after {retry_delay} with."
                )
                await asyncio.sleep(retry_delay)
            else:
                logger.error(
                    f"Failed to publish in {topic} after {max_retries} attempts: {e}"
                )
                return False

    return False
