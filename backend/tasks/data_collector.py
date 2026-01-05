import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

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
        self._last_data_cache = {}  # Кеш для parsed data по device_id
        self._last_redis_ping = 0.0  # Время последнего успешного ping Redis
        self._last_mqtt_check = 0.0  # Время последней проверки соединения MQTT

        # Буфер для batch-записи в БД
        self._batch: List[SensorMessage] = []
        self._last_batch_check = 0.0

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
                data_received = False  # Флаг: получили ли хоть одно сообщение

                for plugin in self.plugins:
                    try:
                        generator = plugin_generators[plugin.device_id]

                        # Читаем одно сообщение
                        try:
                            message = await generator.__anext__()
                            if not message.value:
                                message.value = self._extract_numeric_value(message.data)
                            # 1. Добавляем в буфер для batch-записи
                            self._batch.append(message)

                            # 2. Мгновенно отправляем в Redis и MQTT (параллельно)
                            await asyncio.gather(
                                self._publish_to_redis(message),
                                self._publish_to_mqtt(message),
                                return_exceptions=True,
                            )
                            data_received = True

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

                # Спать только если данных не было
                if not data_received:
                    await asyncio.sleep(0.1)

                # Проверяем, пора ли записать batch в БД
                now = asyncio.get_event_loop().time()
                if (len(self._batch) >= 5) or (
                    self._batch and (now - self._last_batch_check) >= 2.0
                ):
                    await self._save_batch_to_db(self._batch)
                    self._batch = []
                    self._last_batch_check = now

        except asyncio.CancelledError:
            logger.info("DataCollector cancelled")
        finally:
            # Сохраняем оставшиеся данные в БД
            if self._batch:
                await self._save_batch_to_db(self._batch)
            await self._cleanup()
            logger.info("DataCollector stopped")

    async def _cleanup(self):
        """Отключаем клиенты при завершении."""
        if self.mqtt_client and self.mqtt_client._is_connected:
            await self.mqtt_client.disconnect()
        if self.redis_client:
            await self.redis_client.close()

    async def _save_batch_to_db(self, messages: List[SensorMessage]):
        """Batch-сохранение в БД с проверкой изменений."""
        if not messages:
            return

        try:
            # Получаем все устройства из БД
            device_ids = {msg.device_id for msg in messages}
            result = await self.db_session.execute(
                select(Device).where(Device.device_id.in_(device_ids))
            )
            devices = {dev.device_id: dev for dev in result.scalars().all()}

            # Получаем последние данные для всех устройств
            last_data_result = await self.db_session.execute(
                select(DeviceData)
                .where(DeviceData.device_id.in_(device_ids))
                .order_by(DeviceData.timestamp.desc())
            )
            last_data_list = last_data_result.scalars().all()
            last_data_map = {item.device_id: item for item in last_data_list}

            to_insert: List[DeviceData] = []
            to_cleanup: set = (
                set()
            )  # Устройства, для которых нужно почистить старые записи

            for msg in messages:
                # Создаём устройство, если его нет
                if msg.device_id not in devices:
                    device = Device(device_id=msg.device_id, name=msg.device_id)
                    self.db_session.add(device)
                    devices[msg.device_id] = device

                # Проверяем изменение данных
                last_data = last_data_map.get(msg.device_id)
                if self._is_data_changed(last_data, msg.data):
                    to_cleanup.add(msg.device_id)  # Помечаем для очистки
                    db_data = DeviceData(
                        device_id=msg.device_id,
                        timestamp=datetime.fromisoformat(msg.timestamp),
                        data=json.dumps(msg.data),
                        value=msg.value,
                        unit=msg.unit,
                    )
                    to_insert.append(db_data)

            # Очищаем старые записи один раз для всех затронутых устройств
            if to_cleanup:
                for dev_id in to_cleanup:
                    await DeviceDataCRUD.cleanup_old_data(
                        session=self.db_session,
                        device_id=dev_id,
                        retention_days=settings.app_settings.keep_data,
                    )

            if to_insert:
                self.db_session.add_all(to_insert)
                await self.db_session.commit()
                logger.info(f"Batch saved to DB: {len(to_insert)} records")

        except Exception as e:
            logger.error(f"Error saving batch to database: {e}")
            await self.db_session.rollback()

    def _is_data_changed(
        self, last_data: Optional[DeviceData], new_data: Dict[str, Any]
    ) -> bool:
        if last_data is None:
            return True

        # Получаем кешированный dict для этого device_id
        cached = self._last_data_cache.get(last_data.device_id)
        if cached is None:
            try:
                cached = json.loads(last_data.data)
                self._last_data_cache[last_data.device_id] = cached
            except (json.JSONDecodeError, TypeError) as e:
                logger.error(f"Error parsing last_data.data: {e}")
                return True  # При ошибке считаем, что данные изменились

        return cached != new_data

    def _extract_numeric_value(self, data: Dict[str, Any]) -> Optional[float]:
        numeric = [v for v in data.values() if isinstance(v, (int, float))]
        return sum(numeric) / len(numeric) if numeric else None

    async def _publish_to_redis(self, message: SensorMessage):
        """Публикация в Redis с повторной попыткой и разумной задержкой."""
        if not self.redis_client:
            logger.warning("Redis client is not initialized, skipping publication")
            return

        now = asyncio.get_event_loop().time()
        # Проверяем соединение раз в 10 секунд
        if not hasattr(self, "_last_redis_ping") or now - self._last_redis_ping >= 10.0:
            try:
                await self.redis_client.ping()
                self._last_redis_ping = now
            except (redis.ConnectionError, redis.TimeoutError) as e:
                logger.error(f"Redis ping failed: {e}")
                return  # Не отправляем, пока не восстановим соединение

        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                await self.redis_client.publish(
                    "sensor_updates", message.model_dump_json()
                )
                logger.info(f"Sent to Redis: sensor_updates → {message.device_id}")
                return  # Успешно отправили — выходим

            except (redis.ConnectionError, redis.TimeoutError) as e:
                logger.warning(f"Redis error (attempt {attempt + 1}): {e}")
                if attempt < max_retries:
                    await asyncio.sleep(0.5)  # Задержка перед повторной попыткой
                else:
                    logger.error("Max retries exceeded for Redis publication")
            except Exception as e:
                logger.error(f"Unexpected Redis error: {type(e).__name__}: {e}")
                break

    async def _publish_to_mqtt(self, message: SensorMessage):
        """Публикация в MQTT с переподключением и задержками."""
        if not self.mqtt_client:
            logger.warning("MQTT client is not initialized, skipping publication")
            return

        now = asyncio.get_event_loop().time()
        # Проверяем соединение раз в 5 секунд
        if not hasattr(self, "_last_mqtt_check") or now - self._last_mqtt_check >= 5.0:
            if not self.mqtt_client._is_connected:
                logger.info("MQTT not connected, attempting reconnect...")
                try:
                    await self.mqtt_client.connect()
                    if self.mqtt_client._is_connected:
                        logger.info("MQTT reconnected successfully")
                        self._last_mqtt_check = now
                    else:
                        logger.error("Failed to reconnect to MQTT broker")
                        return
                except Exception as conn_err:
                    logger.error(f"MQTT reconnect failed: {conn_err}")
                    return

        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                topic = f"devices/{message.device_id}/data"
                payload = json.dumps(message.data)

                await self.mqtt_client.publish(topic, payload, qos=1)
                logger.debug(f"Sent to MQTT: {topic} → {payload}")
                return  # Успешно отправили — выходим

            except (ConnectionError, OSError) as e:
                logger.warning(f"MQTT error (attempt {attempt + 1}): {e}")
                if attempt < max_retries:
                    await asyncio.sleep(1.0)
                else:
                    logger.error("Max MQTT publish retries exceeded")
            except Exception as e:
                logger.error(
                    f"Unexpected MQTT error: {type(e).__name__}: {e}", exc_info=True
                )
                break
