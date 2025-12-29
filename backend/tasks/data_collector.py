import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.settings import settings
from crud.sensor import DeviceDataCRUD
from models import DeviceData, Device
from plugins.template import DevicePlugin
from schemas.sensor import SensorMessage
from services.mqtt_client import AsyncMQTTClient

logger = logging.getLogger(__name__)


class DataCollector:
    def __init__(
        self,
        plugins: list[DevicePlugin],
        db_session: AsyncSession,
        redis_client: Optional[redis.Redis] = None,  # Может быть None
    ):
        self.plugins = plugins
        self.db_session = db_session
        self.redis_client = redis_client
        self.mqtt_client: Optional[AsyncMQTTClient] = None
        self._is_running = False

        # Логируем плагины
        for i, p in enumerate(self.plugins):
            if not isinstance(p, DevicePlugin):
                logger.error(
                    f"Plugin No.{i} is not an instance of DevicePlugin: {type(p)} = {p}"
                )
            else:
                logger.debug(f"Plugin No.{i}: {p.device_id}")

    async def collect(self):
        self._is_running = True
        logger.info("DataCollector started")

        if not self.plugins:
            logger.error("There are no poll plugins!")
            return

        # Инициализируем MQTT клиент (но не подключаемся сразу)
        self.mqtt_client = AsyncMQTTClient(
            broker=settings.mqtt.host,
            port=settings.mqtt.port,
            username=settings.mqtt.username,
            password=settings.mqtt.password,
        )

        # Сохраняем генераторы для каждого плагина
        plugin_generators = {}
        for plugin in self.plugins:
            try:
                plugin_generators[plugin.device_id] = plugin.start()
                logger.debug(f"The generator was created for {plugin.device_id}")
            except Exception as e:
                logger.error(f"Failed to create generator for {plugin.device_id}: {e}")

        try:
            while self._is_running:
                for plugin in self.plugins:
                    try:
                        generator = plugin_generators[plugin.device_id]

                        # Читаем одно сообщение
                        try:
                            message = await generator.__anext__()

                            # 1. Сохраняем в БД (всегда)
                            await self._save_to_db(message)

                        except StopAsyncIteration:
                            logger.warning(f"{plugin.device_id} generator completed")
                            plugin_generators[plugin.device_id] = plugin.start()
                            continue
                        except Exception as e:
                            logger.error(
                                f"Error when reading from the generator {plugin.device_id}: {type(e).__name__}: {e}",
                                exc_info=True,
                            )

                    except Exception as e:
                        logger.error(
                            f"Error working with the plugin {plugin.device_id}: {type(e).__name__}: {e}",
                            exc_info=True,
                        )
                        continue

                await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            logger.info("DataCollector cancelled")
        finally:
            await self._cleanup()
            logger.info("DataCollector stopped")

    async def _cleanup(self):
        """Отключаем клиенты при завершении."""
        if self.mqtt_client and self.mqtt_client._is_connected:
            await self.mqtt_client.disconnect()
        if self.redis_client:
            await self.redis_client.close()

    async def _save_to_db(self, message: SensorMessage):
        """Сохранение в SQLAlchemy только при изменении данных."""
        try:
            # Проверка существования устройства
            result = await self.db_session.execute(
                select(Device).where(Device.device_id == message.device_id)
            )
            device = result.scalars().first()

            if not device:
                device = Device(device_id=message.device_id, name=message.device_id)
                self.db_session.add(device)

            # Получаем последние данные
            last_data_result = await self.db_session.execute(
                select(DeviceData)
                .where(DeviceData.device_id == message.device_id)
                .order_by(DeviceData.timestamp.desc())
                .limit(1)
            )
            last_data = last_data_result.scalars().first()

            if self._is_data_changed(last_data, message.data):
                await DeviceDataCRUD.cleanup_old_data(
                    session=self.db_session,
                    device_id=message.device_id,
                    retention_days=settings.app_settings.keep_data,
                )
                message.value = self._extract_numeric_value(message.data)
                db_data = DeviceData(
                    device_id=message.device_id,
                    timestamp=datetime.fromisoformat(message.timestamp),
                    data=json.dumps(message.data),
                    value=message.value,
                    unit=message.unit,
                )
                self.db_session.add(db_data)
                await self.db_session.commit()
                logger.info(f"Data saved for device {message.device_id}")
                # 1. Пытаемся отправить в Redis
                await self._publish_to_redis(message)
                # 1. Пытаемся отправить в MQTT
                await self._publish_to_mqtt(message)
            else:
                logger.debug(
                    f"Data has not changed for device {message.device_id}, skipping saving"
                )

        except Exception as e:
            logger.error(f"Error saving to database: {e}")
            await self.db_session.rollback()

    def _is_data_changed(
        self, last_data: Optional[DeviceData], new_data: Dict[str, Any]
    ) -> bool:
        if last_data is None:
            return True
        last_data_dict = json.loads(last_data.data)
        return last_data_dict != new_data

    def _extract_numeric_value(self, data: Dict[str, Any]) -> Optional[float]:
        numeric = [v for v in data.values() if isinstance(v, (int, float))]
        return sum(numeric) / len(numeric) if numeric else None

    async def _publish_to_redis(self, message: SensorMessage):
        """Публикация в Redis с переподключением при ошибке."""
        if not self.redis_client:
            logger.warning("Redis client is not initialized, skipping publication")
            return

        try:
            # Проверяем подключение (ping)
            await self.redis_client.ping()
            await self.redis_client.publish("sensor_updates", message.model_dump_json())
            logger.info(f"Sent to Redis: sensor_updates → {message.device_id}")
        except (redis.ConnectionError, redis.TimeoutError) as e:
            logger.error(
                f"Error connecting to Redis: {e}. There will be a second attempt."
            )
            # Можно добавить retry с задержкой
        except Exception as e:
            logger.error(f"Unexpected Redis error: {e}")

    async def _publish_to_mqtt(self, message: SensorMessage):
        """Публикация в MQTT с автоматической переподключкой при потере соединения."""
        if not self.mqtt_client:
            logger.warning("MQTT client is not initialized, skipping publication")
            return

        try:
            # Проверяем подключение перед отправкой
            if not self.mqtt_client._is_connected:
                logger.info("MQTT is not connected, trying to connect...")
                try:
                    await self.mqtt_client.connect()
                    if self.mqtt_client._is_connected:
                        logger.info("MQTT connection restored")
                    else:
                        logger.error("Couldn't connect to the MQTT broker")
                        return
                except Exception as e:
                    logger.error(f"Error connecting to MQTT: {e}")
                    return

            # Отправляем сообщение
            topic = f"devices/{message.device_id}/data"
            payload = json.dumps(message.data)

            await self.mqtt_client.publish(topic, payload)
            logger.debug(f"Sent to MQTT: {topic} → {payload}")

        except (ConnectionError, OSError) as e:
            logger.error(
                f"Disconnection MQTT: {e}. There will be an attempt to reconnect"
            )
            # Клиент останется в состоянии "не подключён" — следующее сообщение вызовет reconnect
        except Exception as e:
            logger.error(
                f"Unexpected error when publishing in MQTT: {type(e).__name__}: {e}",
                exc_info=True,
            )
