import importlib
import inspect
import logging
import uuid
from pathlib import Path
from typing import Dict, Any

from sqlalchemy import select

from crud.plugins import Plugins
from models import Actuator
from models.plugins import PluginRegistry
from plugins.template import ActuatorPlugin

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
                module = importlib.import_module(module_name)

                for attr_name in dir(module):
                    cls = getattr(module, attr_name)

                    if (
                        isinstance(cls, type)
                        and issubclass(cls, ActuatorPlugin)
                        and cls is not ActuatorPlugin
                    ):
                        result = await db_session.execute(
                            select(PluginRegistry).where(
                                PluginRegistry.module_name == module_name,
                                PluginRegistry.class_name == attr_name,
                            )
                        )
                        registry = result.scalars().first()

                        if registry:
                            device_id = registry.device_id
                            if not await Plugins.is_running(device_id):
                                continue
                        else:
                            uid = uuid.uuid4().hex[:12]
                            device_id = f"{filename.stem}_{uid}"
                            registry = PluginRegistry(
                                module_name=module_name,
                                class_name=attr_name,
                                device_id=device_id,
                                is_running=True,
                            )
                            db_session.add(registry)
                            await db_session.commit()
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
                        conflict_result = await db_session.execute(
                            select(Actuator).where(
                                Actuator.pin == pin, Actuator.device_id != device_id
                            )
                        )
                        conflicting_actuator = conflict_result.scalars().first()

                        if conflicting_actuator:
                            logger.error(
                                f"Pin {pin} is already occupied by actuator {conflicting_actuator.device_id}. "
                                f"Cannot load {device_id}. Please change pin in plugin constructor."
                            )
                            continue
                        actuator_result = await db_session.execute(
                            select(Actuator).where(Actuator.device_id == device_id)
                        )
                        actuator_db = actuator_result.scalars().first()

                        if not actuator_db:
                            actuator_db = Actuator(
                                device_id=device_id,
                                name=filename.stem,
                                description=f"Auto-generated for {module_name}.{attr_name}",
                                pin=pin,
                                inverted=inverted,
                                is_active=True,
                            )
                            db_session.add(actuator_db)
                            await db_session.commit()
                            logger.info(
                                f"Created actuator metadata in DB: {device_id} (pin={pin})"
                            )
                        else:
                            if actuator_db.pin != pin or actuator_db.inverted != inverted:
                                actuator_db.pin = pin
                                actuator_db.inverted = inverted
                                await db_session.commit()
                                logger.info(
                                    f"Updated actuator {device_id}: pin={pin}, inverted={inverted}"
                                )
                        kwargs = {
                            "device_id": device_id,
                            "pin": pin,
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
