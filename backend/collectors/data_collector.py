import asyncio
import logging
from typing import List, Dict, Optional

import redis.asyncio as redis

from core.settings import settings
from plugins.template import DevicePlugin
from schemas.sensor import SensorMessage
from services.base_collector import BaseCollector
from services.batch_saver import save_batch_to_db, extract_numeric_value
from services.mqtt_client import AsyncMQTTClient
from services.mqtt_helper import publish_with_retry, create_mqtt_client
from services.redis_publisher import publish_to_redis

logger = logging.getLogger(__name__)


class DataCollector(BaseCollector):
    """
    Collector of data from internal plugins of devices.
    Collects data, stores it in a database (batch), and publishes it to Redis and MQTT.
    """

    def __init__(
        self,
        plugins: List[DevicePlugin],
        redis_client: Optional[redis.Redis] = None,
        mqtt_client: Optional[AsyncMQTTClient] = None,
    ):
        """
        :param plugins: список плагинов устройств
        :param db_session: сессия БД
        :param redis_client: клиент Redis (может быть None)
        :param mqtt_client: клиент MQTT (может быть None)
        """
        super().__init__(mqtt_client=mqtt_client, redis_client=redis_client)
        self.plugins = plugins
        self._last_data_cache: Dict[str, Dict] = {}
        self._batch: List[SensorMessage] = []
        self._last_batch_check: float = 0.0
        self._last_redis_check: float = 0.0
        self._last_mqtt_check: float = 0.0
        for i, plugin in enumerate(self.plugins):
            if not isinstance(plugin, DevicePlugin):
                logger.error(f"Plugin # {i} is not DevicePlugin: {type(plugin)}")
            else:
                logger.debug(f"Plugin # {i}: {plugin.device_id}")

    async def collect(self):
        self._is_running = True
        logger.info("DataCollector is running")

        if not self.plugins:
            logger.warning("No poll plugins!")
            return
        if not self.mqtt_client:
            self.mqtt_client = create_mqtt_client()
        plugin_generators = {}
        for plugin in self.plugins:
            try:
                plugin_generators[plugin.device_id] = plugin.start()
                logger.debug(f"The generator was created for {plugin.device_id}")
            except Exception as e:
                logger.error(f"Failed to create generator for {plugin.device_id}: {e}")

        try:
            while self._is_running:
                data_received = False

                for plugin in self.plugins:
                    try:
                        generator = plugin_generators[plugin.device_id]
                        try:
                            message = await generator.__anext__()
                            if message.value is None:
                                message.value = await extract_numeric_value(message.data)
                            self._batch.append(message)
                            await asyncio.gather(
                                publish_to_redis(self.redis_client, message),
                                publish_with_retry(
                                    self.mqtt_client,
                                    f"gm/{message.device_id}/data",
                                    message.data,
                                    qos=1,
                                ),
                                publish_with_retry(
                                    self.mqtt_client,
                                    f"gm/{message.device_id}/online",
                                    {"online": message.online},
                                    qos=1,
                                ),
                                return_exceptions=True,
                            )
                            data_received = True

                        except StopAsyncIteration:
                            logger.warning(f"{plugin.device_id} generator completed")
                            plugin_generators[plugin.device_id] = plugin.start()
                            continue
                        except Exception as e:
                            logger.error(
                                f"Error when reading from the generator {plugin.device_id}: "
                                f"{type(e).__name__}: {e}",
                                exc_info=True,
                            )

                    except Exception as e:
                        logger.error(
                            f"Error working with the plugin {plugin.device_id}: "
                            f"{type(e).__name__}: {e}",
                            exc_info=True,
                        )
                        continue
                if not data_received:
                    await self._sleep_if_no_data(data_received, delay=1.0)
                now = asyncio.get_event_loop().time()
                batch_ready = len(self._batch) >= 5 or (
                    self._batch and (now - self._last_batch_check) >= 2.0
                )

                if batch_ready:
                    count = await save_batch_to_db(
                        self.db_session,
                        self._batch,
                        retention_days=settings.app_settings.keep_data,
                    )
                    self._batch = []
                    self._last_batch_check = now
                    logger.debug(f"Batch saved: {count} records")

        except asyncio.CancelledError:
            logger.info("DataCollector cancelled")
        except Exception as e:
            logger.error(f"Unexpected error in DataCollector: {e}", exc_info=True)
        finally:
            if self._batch:
                await save_batch_to_db(
                    self.db_session, self._batch, settings.app_settings.keep_data
                )
            await self._cleanup()
            logger.info("DataCollector stopped")

    async def _cleanup(self):
        await super()._cleanup()
        self._last_data_cache.clear()
