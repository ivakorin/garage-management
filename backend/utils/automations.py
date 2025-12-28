import asyncio
from datetime import datetime

from schemas.automations import Automation, TriggerType, Trigger, Action, ActionType
from services.automations import load_all_automations


class AutomationEngine:
    def __init__(self, automations: list[Automation]):
        self.automations = {a.id: a for a in automations}
        self.running = True

    async def run(self):
        while self.running:
            for automation in self.automations.values():
                if not automation.enabled:
                    continue

                if self._check_trigger(automation.trigger):
                    await self._execute_action(automation.action)

            await asyncio.sleep(1)  # Проверка каждую секунду

    def _check_trigger(self, trigger: Trigger) -> bool:
        if trigger.type == TriggerType.sensor_change:
            # Здесь логика проверки состояния сенсора
            pass

        elif trigger.type == TriggerType.time:
            now = datetime.now().strftime("%H:%M")
            return now == trigger.time
        return False

    async def _execute_action(self, action: Action):
        if action.type == ActionType.send_notification:
            pass
        elif action.type == ActionType.toggle_device:
            pass


async def automations_loader(path: str):
    automations = load_all_automations(path)
    engine = AutomationEngine(automations)
    asyncio.create_task(engine.run())
