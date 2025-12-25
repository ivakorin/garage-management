import importlib
import os
import uuid
from typing import get_type_hints

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import log
from models.plugins import PluginRegistry
from plugins.template import DevicePlugin


async def load_plugins(db_session: AsyncSession) -> dict:
    """Автозагрузка плагинов с корректным управлением жизненным циклом."""
    plugins = {}
    plugins_dir = os.path.join(os.path.dirname(__file__), "..", "plugins")
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
                        registry_key = f"{module_name}.{attr}"
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
                            device_id = f"{filename[:-3]}_{uuid.uuid4().hex[:8]}"
                            registry = PluginRegistry(
                                module_name=module_name,
                                class_name=attr,
                                device_id=device_id
                            )
                            db_session.add(registry)
                            await db_session.commit()
                            log.info(f"Registered new device_id: {device_id} for {registry_key}")

                        # Собираем аргументы для инициализации
                        kwargs = {"device_id": device_id}
                        try:
                            init_hints = get_type_hints(cls.__init__)
                            if "pin" in init_hints:
                                kwargs["pin"] = 4
                        except (TypeError, AttributeError):
                            pass

                        try:
                            plugin = cls(**kwargs)
                            plugins[device_id] = plugin
                        except TypeError as e:
                            log.error(f"Failed to instantiate plugin {device_id}: {e}")

            except Exception as e:
                log.error(f"Failed to load plugin {filename}: {e}")

    return plugins


async def _run_plugin(plugin: DevicePlugin):
    """Обёртка для запуска плагина с обработкой исключений."""
    try:
        # Используем async for для перебора значений генератора
        async for _ in plugin.start():
            pass  # Данные обрабатываются в DataCollector, здесь просто ждём
    except Exception as e:
        log.error(f"Plugin {plugin.device_id} crashed: {e}")

