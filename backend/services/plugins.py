import asyncio
import importlib
import os
import uuid
from typing import get_type_hints

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import log
from models.plugins import PluginRegistry
from plugins.template import DevicePlugin
from services.mqtt_client import AsyncMQTTClient


async def load_plugins(db_session: AsyncSession, mqtt_client: AsyncMQTTClient):
    """Автозагрузка всех плагинов из каталога plugins/ с постоянными device_id."""
    plugins = {}
    plugins_dir = os.path.join(os.path.dirname(__file__),"..", "plugins")
    log.info(f"Loading plugins from {plugins_dir}")

    for filename in os.listdir(plugins_dir):
        if filename.endswith(".py") and filename not in ("__init__.py", "template.py"):
            module_name = f"plugins.{filename[:-3]}"
            try:
                module = importlib.import_module(module_name)
                log.debug(f"Imported module {module_name}")

                for attr in dir(module):
                    cls = getattr(module, attr)
                    if (
                            isinstance(cls, type)
                            and issubclass(cls, DevicePlugin)
                            and cls is not DevicePlugin
                    ):
                        # Генерируем ключ для поиска в реестре
                        registry_key = f"{module_name}.{attr}"

                        # Ищем существующий device_id в БД
                        result = await db_session.execute(
                            select(PluginRegistry).where(
                                PluginRegistry.module_name == module_name,
                                PluginRegistry.class_name == attr
                            )
                        )
                        registry = result.scalars().first()

                        if registry:
                            device_id = registry.device_id
                            log.debug(f"Found existing device_id: {device_id} for {registry_key}")
                        else:
                            # Генерируем новый уникальный device_id (один раз!)
                            device_id = f"{filename[:-3]}_{uuid.uuid4().hex[:8]}"

                            # Сохраняем в реестр
                            registry = PluginRegistry(
                                module_name=module_name,
                                class_name=attr,
                                device_id=device_id
                            )
                            db_session.add(registry)
                            await db_session.commit()
                            log.info(f"Registered new device_id: {device_id} for {registry_key}")

                        # Инициализируем init_hints заранее (чтобы избежать ошибки)
                        init_hints = {}  # <-- Гарантированная инициализация
                        try:
                            init_hints = get_type_hints(cls.__init__)
                        except (TypeError, AttributeError) as e:
                            log.debug(f"Could not get type hints for {cls.__name__}: {e}")


                        kwargs = {
                            "device_id": device_id,
                            "mqtt_client": mqtt_client,
                            "db_session": db_session
                        }

                        # Проверяем наличие параметра 'pin' в сигнатуре __init__
                        if "pin" in init_hints:
                            kwargs["pin"] = 4
                        else:
                            # Дополнительно проверяем через кодовый объект (на случай отсутствия аннотаций)
                            try:
                                if "pin" in cls.__init__.__code__.co_varnames:
                                    kwargs["pin"] = 4
                            except (AttributeError, TypeError):
                                pass  # Если __init__ не имеет __code__, пропускаем


                        try:
                            plugin = cls(**kwargs)
                            plugins[device_id] = plugin
                            asyncio.create_task(plugin.start())
                            log.info(f"Loaded plugin: {device_id}")
                        except TypeError as e:
                            log.error(f"Failed to instantiate plugin {device_id}: {e}")


            except Exception as e:
                log.error(f"Failed to load plugin {filename}: {e}")

    return plugins

