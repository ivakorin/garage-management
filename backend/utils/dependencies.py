import importlib.util
import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional

from utils.automations import AutomationEngine

logger = logging.getLogger(__name__)


def setup_plugin_dependencies():
    lib_path = Path(__file__).parent / "plugins" / "lib"  # Унифицированный путь
    lib_path.mkdir(exist_ok=True)
    lib_path_str = str(lib_path.resolve())

    if lib_path_str not in sys.path:
        sys.path.insert(0, lib_path_str)
        logger.info(f"[DEP] Added to sys.path: {lib_path_str}")

    REQUIRED_PACKAGES = ["RPi.GPIO"]

    for package in REQUIRED_PACKAGES:
        try:
            if package in sys.modules:
                logger.info(f"[DEP] {package} has already been downloaded")
                module = sys.modules[package]
            else:
                importlib.invalidate_caches()  # Очищаем кеш
                spec = importlib.util.find_spec(package)
                if spec is not None:
                    logger.info(f"[DEP] {package} found via find_spec")
                    module = importlib.import_module(package)
                else:
                    logger.info(f"[DEP] Installing {package} in {lib_path_str}")
                    subprocess.check_call(
                        [
                            sys.executable,
                            "-m",
                            "pip",
                            "install",
                            "--target",
                            lib_path_str,
                            package,
                        ]
                    )

                    importlib.invalidate_caches()  # Повторно очищаем
                    spec = importlib.util.find_spec(package)
                    if spec is None:
                        # Пробуем прямой импорт как запасной вариант
                        try:
                            module = __import__(package)
                            logger.info(f"[DEP] {package} imported via __import__")
                        except ImportError:
                            raise ImportError(f"{package} not found after installation")
                    else:
                        module = importlib.import_module(package)
                        logger.info(f"[DEP] {package} installed and imported")

            # Сохраняем в globals
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
