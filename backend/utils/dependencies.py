import importlib.util
import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional

from utils.automations import AutomationEngine

logger = logging.getLogger(__name__)


def setup_plugin_dependencies():
    lib_path = Path(__file__).parent.parent / "plugins" / "lib"
    lib_path.mkdir(exist_ok=True)
    lib_path_str = str(lib_path.resolve())

    if lib_path_str not in sys.path:
        sys.path.insert(0, lib_path_str)
        logger.info(f"[DEP] Added to sys.path: {lib_path_str}")


    REQUIRED_PACKAGES = ["RPi.GPIO"]

    for package in REQUIRED_PACKAGES:
        try:
            # 1. Проверяем, загружен ли модуль уже
            if package in sys.modules:
                logger.info(f"[DEP] {package} already in sys.modules")
                module = sys.modules[package]
            else:
                # 2. Пробуем прямой импорт (обходит кеши find_spec)
                try:
                    module = __import__(package)
                    logger.info(f"[DEP] {package} imported via __import__")
                except ImportError:
                    # 3. Если не получилось — устанавливаем
                    logger.info(f"[DEP] Installing {package} to {lib_path_str}")
                    subprocess.check_call([
                        sys.executable,
                        "-m",
                        "pip",
                        "install",
                        "--target",
                        lib_path_str,
                        package
                    ])

                    # 4. После установки — принудительно перезагружаем модуль
                    importlib.invalidate_caches()
                    try:
                        module = __import__(package)  # Прямой импорт
                        logger.info(f"[DEP] {package} installed and imported")
                    except ImportError as e:
                        # 5. Если всё равно не работает — проверяем структуру
                        logger.error(f"[DEP] Failed to import {package} after install: {e}")
                        # Выводим содержимое lib для отладки
                        logger.debug(f"[DEP] Contents of {lib_path}: {list(lib_path.iterdir())}")
                        raise

            # 6. Сохраняем в globals
            if package == "RPi.GPIO":
                globals()["GPIO"] = module
                logger.info("[DEP] RPi.GPIO imported as GPIO")
            else:
                globals()[package] = module

        except Exception as e:
            logger.error(f"[DEP] Error with {package}: {e}", exc_info=True)



_automation_engine: Optional[AutomationEngine] = None


def set_automation_engine(engine: AutomationEngine):
    """Устанавливает экземпляр AutomationEngine (вызывается в lifespan)."""
    global _automation_engine
    _automation_engine = engine


def get_automation_engine() -> AutomationEngine:
    """Зависимость для доступа к запущенному AutomationEngine."""
    if _automation_engine is None:
        raise RuntimeError("AutomationEngine not initialized")
    return _automation_engine
