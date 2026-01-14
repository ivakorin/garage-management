import asyncio
import logging
from typing import Optional

import redis.asyncio as redis

from schemas.sensor import SensorMessage

logger = logging.getLogger(__name__)


async def publish_to_redis(
    redis_client: Optional[redis.Redis],
    message: SensorMessage,
    channel: str = "sensor_updates",
    max_retries: int = 2,
    retry_delay: float = 0.5,
    ping_interval: float = 10.0,
) -> bool:
    """
    Publishes a message to Redis with repeated attempts and connection verification.

    :param redis_client: Redis client instance (may be None)
    :param message: message to publish (SensorMessage)
    :param channel: Redis channel to publish
    :param max_retries: maximum number of retries in case of error
    :param retry_delay: delay between retries (in seconds)
    :param ping_interval: Redis connection verification interval (in seconds)
    :return: True if publication is successful, otherwise False
    """
    if not redis_client:
        logger.warning("Redis client not initialized, publication skipped")
        return False
    now = asyncio.get_event_loop().time()
    last_ping = getattr(redis_client, "_last_redis_ping", 0.0)
    if now - last_ping >= ping_interval:
        try:
            await redis_client.ping()
            redis_client._last_redis_ping = now
            logger.debug("Redis connection checked (ping)")
        except (redis.ConnectionError, redis.TimeoutError) as e:
            logger.error(f"Connection verification with Redis failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error when checking Redis: {type(e).__name__}: {e}")
            return False
    try:
        payload = message.model_dump_json()
    except Exception as e:
        logger.error(f"Failed to serialize message for Redis: {e}")
        return False
    for attempt in range(max_retries + 1):
        try:
            await redis_client.publish(channel, payload)
            logger.info(f"Sent to Redis: {channel} → {message.device_id}")
            return True

        except (redis.ConnectionError, redis.TimeoutError) as e:
            if attempt < max_retries:
                logger.warning(
                    f"Redis error (attempt {attempt + 1}/{max_retries}): {e}. "
                    f" Will be repeated after {retry_delay} with."
                )
                await asyncio.sleep(retry_delay)
            else:
                logger.error("Exceeded the number of attempts to publish in Redis")
                return False

        except Exception as e:
            logger.error(
                f"Unexpected error when publishing in Redis: {type(e).__name__}: {e}",
                exc_info=True,
            )
            return False

    return False


async def is_redis_connected(
    redis_client: Optional[redis.Redis], ping_timeout: float = 5.0
) -> bool:
    """
    Checks the availability of the Redis server.

    :param redis_client: Redis client instance
    :param ping_timeout: waiting time for a response from the server (in seconds)
    :return: True if the connection is active, otherwise False
    """
    if not redis_client:
        return False

    try:
        await asyncio.wait_for(redis_client.ping(), timeout=ping_timeout)
        return True
    except (redis.ConnectionError, redis.TimeoutError, asyncio.TimeoutError):
        return False
    except Exception as e:
        logger.error(f"Error checking connection with Redis: {e}")
        return False


async def close_redis_client(redis_client: Optional[redis.Redis]) -> None:
    """
    Secure closure of the Redis client.

    :param redis_client: instance of the Redis client
    """
    if redis_client:
        try:
            await redis_client.close()
            logger.info("Redis client is closed")
        except Exception as e:
            logger.error(f"Error when closing the Redis client: {e}")
