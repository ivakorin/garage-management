import logging
from typing import Dict, Any

from mock.gpio_adapter import GPIO
from plugins.template import ActuatorPlugin

logger = logging.getLogger(__name__)


class MockActuatorPlugin(ActuatorPlugin):
    """
    Mock plugin for testing without actual GPIO access.
    Simulates relay behavior by logging actions to console.
    """

    def __init__(
        self,
        device_id: str,
        pin: int = 26,
        inverted: bool = True,
        initial_state: bool = False,
    ):
        super().__init__(device_id, pin, inverted)
        self._current_state = initial_state
        self._simulated_pin_state = (
            GPIO.HIGH if inverted else GPIO.LOW
        )  # Имитация начального состояния

    async def init_hardware(self):
        """Имитирует инициализацию GPIO."""
        if self._initialized:
            return

        logger.info(
            f"[{self.device_id}] MOCK: Simulated GPIO initialized on pin {self.pin} "
            f"(inverted={self.inverted}, initial_state={self._current_state})"
        )
        self._initialized = True

    async def handle_command(self, command: Dict[str, Any]) -> None:
        """
        Обрабатывает команду в формате:
        {"action": "set_state", "state": True}  → имитирует включение реле
        {"action": "set_state", "state": False} → имитирует выключение реле
        """
        action = command.get("action")
        state = command.get("state")
        logger.debug(f"MOCK Plugin {self.device_id}, received command: {command}")

        if action == "set_state" and isinstance(state, bool):
            if state:
                await self._mock_turn_on()
            else:
                await self._mock_turn_off()
        else:
            logger.warning(
                f"[{self.device_id}] MOCK: Invalid command: {command}. "
                "Expected {'action': 'set_state', 'state': True/False}"
            )

    async def get_state(self) -> Dict[str, Any]:
        """Возвращает текущее состояние реле (симулированное)."""
        return {
            "device_id": self.device_id,
            "state": self._current_state,
            "pin": self.pin,
            "inverted": self.inverted,
            "simulated": True,
        }

    async def _mock_turn_on(self):
        """Имитирует включение реле с учётом инверсии."""
        self._simulated_pin_state = GPIO.LOW if self.inverted else GPIO.HIGH
        self._current_state = True
        print("Turned ON")
        logger.info(
            f"[{self.device_id}] MOCK: Relay turned ON "
            f"(pin {self.pin}, inverted={self.inverted}, simulated_pin={self._simulated_pin_state})"
        )

    async def _mock_turn_off(self):
        """Имитирует выключение реле с учётом инверсии."""
        self._simulated_pin_state = GPIO.HIGH if self.inverted else GPIO.LOW
        self._current_state = False
        print("Turned OFF")
        logger.info(
            f"[{self.device_id}] MOCK: Relay turned OFF "
            f"(pin {self.pin}, inverted={self.inverted}, simulated_pin={self._simulated_pin_state})"
        )

    async def cleanup(self):
        """Имитирует освобождение пина GPIO."""
        if not self._initialized:
            return

        logger.info(f"[{self.device_id}] MOCK: GPIO cleaned up (pin {self.pin})")
        self._initialized = False
        self._current_state = False
        self._simulated_pin_state = GPIO.HIGH  # Возвращаем к "выключенному" состоянию
