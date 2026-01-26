import asyncio
import logging
from typing import Dict, Any

from plugins.template import ActuatorPlugin

logger = logging.getLogger(__name__)


class TestActuatorPlugin(ActuatorPlugin):
    """
    Тестовый актуатор для отладки на десктопе.
    Имитирует реле/светодиод без реального доступа к GPIO.
    """

    def __init__(
        self,
        device_id: str,
        initial_state: bool = False,
        pin: int | None = 4,
        inverted: bool = False,
    ):
        super().__init__(device_id, pin)
        self._state = initial_state  # Логическое состояние (True = включено)
        self.pin = pin
        self.inverted = inverted
        self._last_command: Dict[str, Any] = {}  # Для хранения последней команды
        logger.info(f"TestActuator '{self.device_id}' initialized (state={self._state})")

    async def init_hardware(self):
        """Имитация инициализации аппаратной части (для теста)."""
        logger.info(f"{self.device_id}: init_hardware() called (simulated)")

    async def handle_command(self, command: Dict[str, Any]) -> None:
        """
        Обрабатывает команды:
        - {"action": "set_state", "state": true/false}
        - Любые другие команды — логгируются как неизвестные
        """
        action = command.get("action")

        if action == "set_state":
            new_state = command.get("state")
            if new_state is None:
                logger.warning(f"{self.device_id}: 'state' missing in command: {command}")
                return

            self._state = bool(new_state)
            self._last_command = command
            logger.info(
                f"{self.device_id}: State set to {self._state} via command: {command}"
            )

        else:
            logger.warning(f"{self.device_id}: Unknown command received: {command}")
            self._last_command = command

    async def get_state(self) -> Dict[str, Any]:
        """Возвращает текущее состояние актуатора."""
        return {
            "device_id": self.device_id,
            "state": self._state,
            "last_command": self._last_command,
            "online": True,
            "simulated": True,  # Флаг, что это тестовый актуатор
            "timestamp": asyncio.get_event_loop().time(),  # Приблизительное время
        }

    async def cleanup(self):
        """Очистка — в тестовом режиме просто логируем."""
        logger.info(f"{self.device_id}: cleanup() called. Current state: {self._state}")
        # В реальном актуаторе тут было бы: выключить реле, освободить пин и т. п.
