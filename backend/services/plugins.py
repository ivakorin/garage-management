import importlib
import os
import uuid
from typing import get_type_hints

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import log
from crud.plugins import Plugins
from models.plugins import PluginRegistry
from plugins.template import DevicePlugin, ActuatorPlugin  # Добавлен ActuatorPlugin


async def load_plugins(db_session: AsyncSession) -> dict:
    """Автозагрузка плагинов (только датчиков) с корректным управлением жизненным циклом."""
    plugins = {}
    plugins_dir = os.path.join(os.path.dirname(__file__), "..", "plugins")
    log.info(f"Loading plugins (sensors only) from {plugins_dir}")

    for filename in os.listdir(plugins_dir):
        # Пропускаем example-файлы
        if filename.endswith("example.py"):
            log.info(
                f"Skip loading plugin {filename}. Remove 'example' from filename to enable."
            )
            continue
        # Обрабатываем только .py-файлы, кроме __init__.py и template.py
        if not (
            filename.endswith(".py") and filename not in ("__init__.py", "template.py")
        ):
            continue

        prefix = filename.split("_")[0]
        module_name = f"plugins.{filename[:-3]}"

        try:
            module = importlib.import_module(module_name)
            log.debug(f"Imported module {module_name}")

            for attr in dir(module):
                cls = getattr(module, attr)
                # Проверяем:
                # - это класс
                # - наследуется от DevicePlugin
                # - не является самим DevicePlugin
                # - НЕ является наследником ActuatorPlugin (исключаем актуаторы)
                if (
                    isinstance(cls, type)
                    and issubclass(cls, DevicePlugin)
                    and cls is not DevicePlugin
                    and not issubclass(cls, ActuatorPlugin)
                ):
                    registry_key = f"{module_name}.{attr}"
                    # Ищем запись в БД
                    result = await db_session.execute(
                        select(PluginRegistry).where(
                            PluginRegistry.module_name == module_name,
                            PluginRegistry.class_name == attr,
                        )
                    )
                    registry = result.scalars().first()

                    if registry:
                        device_id = registry.device_id
                        log.debug(
                            f"Found existing device_id: {device_id} for {registry_key}"
                        )
                        # Пропускаем, если плагин помечен как остановленный
                        if not await Plugins.is_running(device_id):
                            continue
                    else:
                        # Создаём новую запись в БД
                        uid = uuid.uuid4().hex[:12]
                        device_id = f"{prefix}_{uid}"
                        registry = PluginRegistry(
                            module_name=module_name,
                            class_name=attr,
                            device_id=device_id,
                            is_running=True,
                        )
                        db_session.add(registry)
                        await db_session.commit()
                        log.info(
                            f"Registered new device_id: {device_id} for {registry_key}"
                        )

                    # Собираем аргументы для инициализации
                    kwargs = {"device_id": device_id}

                    # Если плагин ожидает `pin` в __init__, добавляем дефолт
                    try:
                        init_hints = get_type_hints(cls.__init__)
                        if "pin" in init_hints:
                            kwargs["pin"] = 4  # Дефолтный пин
                    except (TypeError, AttributeError):
                        pass

                    # Создаём экземпляр плагина
                    try:
                        plugin = cls(**kwargs)
                        plugins[device_id] = plugin
                        log.info(f"Loaded plugin: {device_id} ({registry_key})")
                    except TypeError as e:
                        log.error(f"Failed to instantiate plugin {device_id}: {e}")

        except Exception as e:
            log.error(f"Failed to load plugin {filename}: {e}")

    return plugins
