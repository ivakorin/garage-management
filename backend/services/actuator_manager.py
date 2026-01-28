import importlib
import inspect
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from crud.actuators import ActuatorCRUD
from crud.plugins import Plugins
from mock.gpio_adapter import is_rpi, GPIO
from plugins.template import ActuatorPlugin
from schemas.actuators import ActuatorCreate, ActuatorUpdate
from schemas.plugins import PluginBaseSchema

logger = logging.getLogger(__name__)


class ActuatorManager:
    def __init__(self):
        self.actuators: Dict[str, ActuatorPlugin] = {}

    async def load_actuators(self, db_session) -> None:

        plugins_dir = Path(__file__).parent.parent / "plugins"

        if not plugins_dir.exists():
            logger.warning(f"Plugins directory not found: {plugins_dir}")
            return

        for filename in plugins_dir.iterdir():
            if not filename.is_file() or not filename.name.endswith(".py"):
                continue
            if filename.name in ("__init__.py", "template.py"):
                continue
            if str(filename).endswith("example.py"):
                logger.info(
                    f"Skip loading actuator plugin {filename}. Remove 'example' from filename to enable."
                )
                continue

            module_name = f"plugins.{filename.stem}"

            try:
                if is_rpi():  # Только на Raspberry Pi
                    current_mode = GPIO.gpio_function(pin)
                    if current_mode != GPIO.IN and current_mode != GPIO.OUT:
                        # Пин свободен
                        pass
                    else:
                        logger.warning(f"Pin {pin} already in use (mode={current_mode})")
                module = importlib.import_module(module_name)

                for attr_name in dir(module):
                    cls = getattr(module, attr_name)

                    if (
                        isinstance(cls, type)
                        and issubclass(cls, ActuatorPlugin)
                        and cls is not ActuatorPlugin
                    ):
                        registry = await Plugins.get(
                            module_name=module_name, session=db_session
                        )
                        if registry:
                            device_id = registry.device_id
                            if not await Plugins.is_running(device_id):
                                continue
                        else:
                            uid = uuid.uuid4().hex[:12]
                            device_id = f"{filename.stem}_{uid}"
                            registry = PluginBaseSchema(
                                module_name=module_name,
                                class_name=attr_name,
                                device_id=device_id,
                            )
                            await Plugins.add(plugin=registry, session=db_session)
                            logger.info(
                                f"Registered new actuator in PluginRegistry: {device_id}"
                            )

                        sig = inspect.signature(cls.__init__)
                        pin = 4
                        inverted = False

                        for param_name, param in sig.parameters.items():
                            if param_name == "pin" and param.default is not param.empty:
                                pin = param.default
                            elif (
                                param_name == "inverted"
                                and param.default is not param.empty
                            ):
                                inverted = param.default
                        check_actuator = await ActuatorCRUD.get(
                            device_id=device_id, session=db_session
                        )
                        if (
                            check_actuator
                            and check_actuator.device_id != device_id
                            and check_actuator.pin == pin
                        ):
                            logger.error(
                                f"Pin {pin} is already occupied by actuator {check_actuator.device_id} (Name: {check_actuator.name}). "
                                f"Cannot load {device_id}. Please change pin in plugin constructor."
                            )
                            continue
                        check_actuator.is_active = False
                        update_state = ActuatorUpdate(
                            device_id=device_id,
                            is_active=False,
                            updated_at=datetime.now(),
                        )
                        await ActuatorCRUD.update(
                            actuator=update_state, session=db_session
                        )
                        if not check_actuator:
                            actuator_db = ActuatorCreate(
                                device_id=device_id,
                                name=device_id,
                                pin=pin,
                                inverted=inverted,
                                is_active=False,  # Create non-active (switch off by default)
                            )
                            await ActuatorCRUD.add(actuator_db, db_session)
                            logger.info(
                                f"Created actuator metadata in DB: {device_id} (pin={pin})"
                            )
                        kwargs = {
                            "device_id": device_id,
                            "pin": pin,
                            "state": False,
                        }
                        if "inverted" in [p.name for p in sig.parameters.values()]:
                            kwargs["inverted"] = inverted

                        try:
                            actuator = cls(**kwargs)
                            await actuator.init_hardware()
                            self.actuators[device_id] = actuator
                            logger.info(
                                f"Loaded actuator: {device_id} "
                                f"(pin={pin}, inverted={inverted})"
                            )
                        except Exception as e:
                            logger.error(
                                f"Failed to initialize actuator {device_id}: {e}",
                                exc_info=True,
                            )

            except Exception as e:
                logger.error(f"Error loading module {module_name}: {e}", exc_info=True)

    async def send_command(self, device_id: str, command: Dict[str, Any]) -> None:
        actuator = self.actuators.get(device_id)
        if actuator:
            await actuator.handle_command(command)
        else:
            raise ValueError(f"Actuator {device_id} not found")

    async def get_state(self, device_id: str) -> Dict[str, Any]:
        actuator = self.actuators.get(device_id)
        if actuator:
            return await actuator.get_state()
        raise ValueError(f"Actuator {device_id} not found")
