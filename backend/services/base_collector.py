import asyncio
import logging
from typing import Optional

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import engine
from services.mqtt_client import AsyncMQTTClient

logger = logging.getLogger(__name__)


class BaseCollector:
    """
    The base class for all data collectors.
    Provides a common lifecycle, connection management, and basic infrastructure.
    """

    def __init__(
        self,
        mqtt_client: Optional[AsyncMQTTClient] = None,
        redis_client: Optional[redis.Redis] = None,
        db_session: Optional[AsyncSession] = None,
    ):
        """
        Initialization of the basic collector.

        :param mqtt_client: instance of AsyncMQTTClient (may be None)
        :param redis_client: a redis instance.Redis (maybe None)
        :param db_session: DB session AsyncSession (may be None)
        """
        self.mqtt_client = mqtt_client
        self.redis_client = redis_client
        self.db_session = db_session or AsyncSession(bind=engine)
        self._is_running = False

    async def collect(self):
        """
        The main method of data collection. Must be redefined in the heirs.
        Starts an endless data collection/processing cycle before calling stop().
        """
        raise NotImplementedError(
            "The collect() method must be implemented in a subclass"
        )

    def stop(self):
        """
        Stops data collection. Sets the _is_running flag to False,
        which should end the loop in collect().
        """
        self._is_running = False
        logger.debug(f"{self.__class__.__name__}: data collection stopped")

    async def _cleanup(self):
        """
        Safe shutdown of all resources: MQTT, Redis.
        Called when the mail importer is shutting down.
        """
        try:
            if self.mqtt_client:
                await self.mqtt_client.disconnect()
                logger.info(f"{self.__class__.__name__}: MQTT client disabled")
        except Exception as e:
            logger.error(f"{self.__class__.__name__}: error disabling MQTT: {e}")

        try:
            if self.redis_client:
                await self.redis_client.close()
                logger.info(f"{self.__class__.__name__}: Redis client is closed")
        except Exception as e:
            logger.error(f"{self.__class__.__name__}: error when closing Redis: {e}")

    async def _ensure_mqtt_connected(self) -> bool:
        """
        Verifies and ensures the connection of the MQTT client.
        Returns True if the connection is successful, otherwise False.

        :return: bool — connection status
        """
        if not self.mqtt_client:
            logger.warning("MQTT client is not initialized")
            return False

        if not self.mqtt_client.is_connected:
            logger.info("MQTT is not connected, we are trying to connect...")
            try:
                await self.mqtt_client.connect()
                if self.mqtt_client.is_connected:
                    logger.info("MQTT successfully connected")
                    return True
                else:
                    logger.error("Couldn't connect to the MQTT broker")
                    return False
            except Exception as e:
                logger.error(f"Error connecting to MQTT: {e}")
                return False

        return True

    async def _sleep_if_no_data(self, data_received: bool, delay: float = 1.0):
        """
        Falls asleep for a preset time if no data has been received.

        :param data_received: flag — whether data was received in the current cycle
        :param delay: waiting time in seconds
        """
        if not data_received:
            await asyncio.sleep(delay)

    def _log_exception(self, prefix: str, exc: Exception):
        """
        Unified exception logging.

        :param prefix: prefix for the message (for example, the name of the plug-in/device)
        :param exc: exception
        """
        logger.error(
            f"{self.__class__.__name__} [{prefix}]: {type(exc).__name__}: {exc}",
            exc_info=True,
        )
