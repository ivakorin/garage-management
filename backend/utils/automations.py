import asyncio
import importlib
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from crud.actuators import ActuatorCRUD
from crud.sensors import SensorDataCRUD
from db.database import engine
from models import PluginRegistry
from schemas.actuators import ActuatorUpdate, ActuatorCommandCreate
from schemas.automations import (
    Automation,
    TriggerType,
    Trigger,
    Action,
    ActionType,
    ConditionOperator,
    Condition,
)
from schemas.sensors import SensorMessage
from services.actuator_manager import ActuatorManager
from services.automations import load_all_automations
from services.redis_publisher import publish_to_redis

logger = logging.getLogger(__name__)


class AutomationEngine:
    def __init__(
        self,
        redis_client: redis.Redis = None,
        actuator_manager: ActuatorManager = None,
        automations: list[Automation] = None,
        db_session: Optional[AsyncSession] = None,
    ):
        self.db_session = db_session or AsyncSession(bind=engine)
        self.redis_client = redis_client
        self.actuator_manager = actuator_manager
        self.automations = {a.id: a for a in automations} if automations else None
        self.running = True
        self._plugin_cache: Dict[str, Any] = {}

    async def run(self):
        while self.running:
            for automation in self.automations.values():
                if not automation.enabled:
                    continue

                if await self._check_trigger(automation.trigger):
                    await self._execute_action(automation.action)

            await asyncio.sleep(1)

    async def _check_trigger(self, trigger: Trigger) -> bool:
        if trigger.type == TriggerType.sensor_change:
            return await self._check_sensor_change(trigger)
        elif trigger.type == TriggerType.time:
            return self._check_time(trigger)
        elif trigger.type == TriggerType.multi_condition:
            return await self._check_multi_condition(trigger)
        return False

    async def _check_sensor_change(self, trigger: Trigger) -> bool:
        sensor_id = trigger.sensor_id
        if not sensor_id:
            return False

        current_value = await self._get_sensor_value_from_db(sensor_id)
        if current_value is not None:
            await self._update_redis_cache(sensor_id, current_value)

        if current_value is None:
            return False

        # Сравниваем с предыдущим значением из Redis
        prev_value = await self._get_prev_value_from_redis(sensor_id)
        await self._update_prev_value_in_redis(sensor_id, current_value)

        return prev_value is None or current_value != prev_value

    def _check_time(self, trigger: Trigger) -> bool:
        now = datetime.now().strftime("%H:%M")
        return now == trigger.time

    async def _check_multi_condition(self, trigger: Trigger) -> bool:
        if not trigger.conditions:
            return False

        results = []
        for cond in trigger.conditions:
            sensor_value = await self._get_sensor_value(cond.sensor_id)
            if sensor_value is None:
                results.append(False)
                continue

            # Применяем оператор
            result = self._evaluate_condition(sensor_value, cond)
            results.append(result)

        # Объединяем по логике AND/OR
        if trigger.combine_logic == "AND":
            return all(results)
        else:
            return any(results)

    def _evaluate_condition(self, value: float, condition: Condition) -> bool:
        if condition.operator == ConditionOperator.EQ:
            result = value == condition.value
        elif condition.operator == ConditionOperator.NE:
            result = value != condition.value
        elif condition.operator == ConditionOperator.GT:
            result = value > condition.value
        elif condition.operator == ConditionOperator.LT:
            result = value < condition.value
        elif condition.operator == ConditionOperator.GTE:
            result = value >= condition.value
        elif condition.operator == ConditionOperator.LTE:
            result = value <= condition.value

        # Учитываем гистерезис
        if condition.hysteresis and result:
            result = (
                value >= condition.hysteresis.low and value <= condition.hysteresis.high
            )
        return result

    async def _execute_action(self, action: Action):
        if action.type == ActionType.send_notification:
            await self._send_notification(action.recipient, action.message)
        elif action.type == ActionType.turn_on:
            await self._control_device(action.device_id, True)
        elif action.type == ActionType.turn_off:
            await self._control_device(action.device_id, False)
        elif action.type == ActionType.toggle_device:
            command = {"action": "set_state", "state": action.state}
            await self.actuator_manager.send_command(action.device_id, command)
        elif action.type == ActionType.set_value:
            command = {"action": "set_value", "value": action.value}
            await self.actuator_manager.send_command(action.device_id, command)
        elif action.type == ActionType.group_action:
            if action.commands:
                await self._execute_group_action(action.commands)
        else:
            logger.warning(f"Unknown action type: {action.type}")

    async def _execute_group_action(self, commands: List[Dict[str, Any]]):
        """Выполняет список команд с задержками."""
        for cmd in commands:
            device_id = cmd.get("device_id")
            action = cmd.get("action")
            delay = cmd.get("delay", 0)

            if not device_id or not action:
                logger.error(f"Invalid command in group_action: {cmd}")
                continue

            # Ждём заданную задержку
            if delay > 0:
                await asyncio.sleep(delay)

            try:
                if action == "turn_on":
                    await self._control_device(device_id, True)
                elif action == "turn_off":
                    await self._control_device(device_id, False)
                elif action == "set_value":
                    value = cmd.get("value")
                    if value is not None:
                        command = {"action": "set_value", "value": value}
                        await self.actuator_manager.send_command(device_id, command)
                else:
                    logger.warning(f"Unsupported action in group: {action}")
            except Exception as e:
                logger.error(
                    f"Failed to execute command for {device_id}: {e}", exc_info=True
                )

    async def _get_sensor_value(self, sensor_id: str) -> Optional[float]:
        # Сначала пробуем Redis
        value = await self._get_sensor_value_from_redis(sensor_id)
        if value is not None:
            return value
        # Если нет — берём из БД и кэшируем
        value = await self._get_sensor_value_from_db(sensor_id)
        if value is not None:
            await self._update_redis_cache(sensor_id, value)
        return value

    async def _get_sensor_value_from_redis(self, sensor_id: str) -> Optional[float]:
        value_str = await self.redis_client.get(f"sensor:{sensor_id}:value")
        if value_str:
            return float(value_str)
        return None

    async def _get_prev_value_from_redis(self, sensor_id: str) -> Optional[float]:
        value_str = await self.redis_client.get(f"sensor:{sensor_id}:prev_value")
        if value_str:
            return float(value_str)
        return None

    async def _update_redis_cache(self, sensor_id: str, value: float):
        await self.redis_client.set(f"sensor:{sensor_id}:value", str(value))

    async def _update_prev_value_in_redis(self, sensor_id: str, value: float):
        await self.redis_client.set(f"sensor:{sensor_id}:prev_value", str(value))

    async def _get_sensor_value_from_db(self, sensor_id: str) -> Optional[float]:
        return await SensorDataCRUD.get_value(sensor_id, self.db_session)

    async def _send_notification(self, recipient: str, message: str):
        """Отправляет уведомление (реализацию можно расширить)."""
        logger.info(f"Notification to {recipient}: {message}")
        # Здесь можно добавить отправку email/push/SMS

    async def _control_device(self, device_id: str, state: bool):
        """
        Управляет устройством через его плагин.
        :param device_id: ID устройства из БД
        :param state: True — включить, False — выключить
        """
        device = await ActuatorCRUD.get(device_id=device_id, session=self.db_session)
        command = {"action": "set_state", "state": state}
        redis_message = SensorMessage(
            device_id=device_id,
            timestamp=datetime.now().isoformat(),
            data=command,
            value="on" if state else "off",
            unit="state",
        )
        if not device:
            logger.error(f"Device not found: {device_id}")
            return
        if device.is_active == state:
            logger.debug(f"Device {device_id} already turned {state}")
            await publish_to_redis(
                redis_client=self.redis_client,
                message=redis_message,
            )
            return
        try:
            plugin = self._plugin_cache.get(device_id)
            if not plugin:
                plugin = await self._load_plugin_by_device_id(device_id)
                if not plugin:
                    logger.error(f"Plugin not found for device_id={device_id}")
                    return

            await plugin.handle_command(command)
            await publish_to_redis(
                redis_client=self.redis_client,
                message=redis_message,
            )
            actuator = ActuatorUpdate(
                device_id=device_id,
                is_active=state,
                updated_at=datetime.now(),
            )
            await ActuatorCRUD.update(actuator=actuator, session=self.db_session)
            commands = ActuatorCommandCreate(
                device_id=device_id,
                command=str(command),
                success=True,
            )
            await ActuatorCRUD.add_command(commands=commands, session=self.db_session)
            logger.info(
                f"Device {device_id} turned {'on' if state else 'off'} via plugin"
            )

        except Exception as e:
            commands = ActuatorCommandCreate(
                device_id=device_id,
                command=str(command),
                success=False,
                error_message=str(e),
            )
            await ActuatorCRUD.add_command(commands=commands, session=self.db_session)
            if plugin and plugin._initialized:
                await plugin.cleanup()
            logger.error(f"Failed to control device {device_id}: {e}", exc_info=True)

    async def _load_plugin_by_device_id(self, device_id: str) -> Optional[Any]:
        """
        Загружает плагин по device_id из БД.
        :return: экземпляр плагина или None
        """
        # Получаем запись из plugins_registry
        result = await self.db_session.execute(
            select(PluginRegistry).where(PluginRegistry.device_id == device_id)
        )
        registry = result.scalars().first()

        if not registry:
            logger.warning(f"No plugin registry entry for device_id={device_id}")
            return None

        module_name = registry.module_name
        class_name = registry.class_name

        try:
            # Импортируем модуль
            module = importlib.import_module(module_name)
            # Получаем класс плагина
            plugin_class = getattr(module, class_name)

            # Создаём экземпляр
            plugin = plugin_class(
                device_id=device_id,
                # Здесь можно передать дополнительные параметры из registry,
                # например, pin, inverted, если они хранятся в БД
            )
            # Инициализируем аппаратную часть
            await plugin.init_hardware()

            # Сохраняем в кэш
            self._plugin_cache[device_id] = plugin
            logger.info(f"Loaded plugin {class_name} for {device_id} from {module_name}")
            return plugin

        except ImportError as e:
            logger.error(f"Failed to import module {module_name}: {e}")
        except AttributeError as e:
            logger.error(f"Class {class_name} not found in {module_name}: {e}")
        except Exception as e:
            logger.error(
                f"Failed to initialize plugin for {device_id}: {e}", exc_info=True
            )

        return None

    async def cleanup(self):
        """Очистка ресурсов при остановке движка."""
        # 1. Очищаем все плагины
        for plugin in self._plugin_cache.values():
            try:
                await plugin.cleanup()
            except Exception as e:
                logger.error(f"Error when clearing the plugin {plugin.device_id}: {e}")

        # 2. Очищаем кэш плагинов
        self._plugin_cache.clear()

        # 3. Закрываем Redis-соединение
        try:
            await self.redis_client.close()
            logger.info("Redis client is closed")
        except Exception as e:
            logger.error(f"Error when closing the Redis client: {e}")

        logger.info("AutomationEngine is completed and cleared")


async def automations_loader(path: str):
    automations = load_all_automations(path)
    engine = AutomationEngine(
        redis_client=redis.Redis.from_url("redis://localhost:6379"),
        actuator_manager=ActuatorManager(),
        automations=automations,
    )
    asyncio.create_task(engine.run())
    return automations
