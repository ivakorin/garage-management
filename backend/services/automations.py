from pathlib import Path

import yaml

from schemas.automations import Automation


def load_automation_from_yaml(file_path: str) -> Automation:
    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # Валидация и преобразование в модель
    return Automation(**data["automation"])


def load_all_automations(directory: str) -> list[Automation]:
    automations = []
    for file_path in Path(directory).glob("*.yaml"):
        try:
            automation = load_automation_from_yaml(file_path)
            automations.append(automation)
        except Exception as e:
            print(f"Ошибка при загрузке {file_path}: {e}")
    return automations
