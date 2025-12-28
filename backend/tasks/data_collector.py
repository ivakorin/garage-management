import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.settings import settings
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
                logger.error(f"Плагин №{i} — не экземпляр DevicePlugin: {type(p)} = {p}")
            else:
                logger.info(f"Плагин №{i}: {p.device_id}")

    async def collect(self):
        self._is_running = True
        logger.info("DataCollector started")

        if not self.plugins:
            logger.error("Нет плагинов для опроса!")
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
                logger.debug(f"Генератор создан для {plugin.device_id}")
            except Exception as e:
                logger.error(f"Не удалось создать генератор для {plugin.device_id}: {e}")

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
                            logger.warning(f"Генератор {plugin.device_id} завершён")
                            plugin_generators[plugin.device_id] = plugin.start()
                            continue
                        except Exception as e:
                            logger.error(
                                f"Ошибка при чтении из генератора {plugin.device_id}: {type(e).__name__}: {e}",
                                exc_info=True,
                            )

                    except Exception as e:
                        logger.error(
                            f"Ошибка работы с плагином {plugin.device_id}: {type(e).__name__}: {e}",
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
                numeric_value = self._extract_numeric_value(message.data)
                db_data = DeviceData(
                    device_id=message.device_id,
                    timestamp=datetime.fromisoformat(message.timestamp),
                    data=json.dumps(message.data),
                    value=numeric_value,
                )
                self.db_session.add(db_data)
                await self.db_session.commit()
                logger.info(f"Данные сохранены для устройства {message.device_id}")
                message.value = numeric_value
                # 1. Пытаемся отправить в Redis
                await self._publish_to_redis(message)
                # 1. Пытаемся отправить в MQTT
                await self._publish_to_mqtt(message)
            else:
                logger.debug(
                    f"Данные не изменились для устройства {message.device_id}, пропуск сохранения"
                )

        except Exception as e:
            logger.error(f"Ошибка сохранения в БД: {e}")
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
            logger.warning("Redis клиент не инициализирован, пропуск публикации")
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
            logger.warning("MQTT клиент не инициализирован, пропуск публикации")
            return

        try:
            # Проверяем подключение перед отправкой
            if not self.mqtt_client._is_connected:
                logger.info("MQTT не подключён, пытаемся подключиться...")
                try:
                    await self.mqtt_client.connect()
                    if self.mqtt_client._is_connected:
                        logger.info("MQTT подключение восстановлено")
                    else:
                        logger.error("Не удалось подключиться к MQTT брокеру")
                        return
                except Exception as e:
                    logger.error(f"Ошибка при подключении к MQTT: {e}")
                    return

            # Отправляем сообщение
            topic = f"devices/{message.device_id}/data"
            payload = json.dumps(message.data)

            await self.mqtt_client.publish(topic, payload)
            logger.debug(f"Отправлено в MQTT: {topic} → {payload}")

        except (ConnectionError, OSError) as e:
            logger.error(f"Разрыв соединения MQTT: {e}. Будет попытка переподключения.")
            # Клиент останется в состоянии "не подключён" — следующее сообщение вызовет reconnect
        except Exception as e:
            logger.error(
                f"Неожиданная ошибка при публикации в MQTT: {type(e).__name__}: {e}",
                exc_info=True,
            )
