# **Руководство по созданию автоматизаций**

## **1. Основные понятия**

****Автоматизация**** — правило, которое выполняет действие при наступлении заданного
условия.  
****Триггер**** — событие, запускающее автоматизацию.  
****Действие**** — команда, выполняемая при срабатывании триггера.

## **2. Структура автоматизации**

```yaml

automation:
  id: <уникальный_идентификатор>
  name: <название>
  trigger: <блок_триггера>
  action: <блок_действия>
  enabled: <true/false> # по умолчанию true
  description: <описание> # опционально
```

## **3. Триггеры (trigger)**

### **Типы триггеров**

- sensor_change — изменение значения датчика.
- time — точное время (по расписанию).
- manual — ручной запуск.
- multi_condition — комбинация нескольких условий.

### **Параметры по типам**

#### **sensor_change**

```yaml
trigger:
  type: sensor_change
  sensor_id: <id_датчика>
  # condition: <старое_условие> (не рекомендуется)
```

#### **time**

```yaml
trigger:
  type: time
  time: "ЧЧ:ММ" # например "08:00"
```

#### **multi_condition**

```yaml

trigger:
  type: multi_condition
  conditions:
    - sensor_id: <id_датчика_1>
      operator: <оператор>
      value: <пороговое_значение>
      hysteresis: # опционально
        low: <нижний_порог>
        high: <верхний_порог>
    - sensor_id: <id_датчика_2>
        ...
  combine_logic: "AND|OR" # как объединять условия
```

## **4. Условия (conditions)**

### **Операторы сравнения**

| **Оператор** | **Значение**     | **Пример**   |
|--------------|------------------|--------------|
| \==          | Равно            | value == 100 |
| !=           | Не равно         | value != 0   |
| \>           | Больше           | value > 50   |
| <            | Меньше           | value < 30   |
| \>=          | Больше или равно | value >= 25  |
| <=           | Меньше или равно | value <= 75  |

### **Гистерезис (hysteresis)**

Используется для предотвращения частых срабатываний.

```yaml
hysteresis:
  low: 450 # нижний порог
  high: 550 # верхний порог
```

****Как работает:****

- Условие считается выполненным, если value находится в диапазоне \[low, high\].
- Пример: при value > 500 и гистерезисе \[450, 550\] автоматизация сработает при value ≥
  550 и отключится при value ≤ 450.

## **5. Действия (action)**

### **Типы действий**

- send_notification — отправить уведомление.
- turn_on — включить устройство.
- turn_off — выключить устройство.
- toggle_device — переключить устройство (устаревшее).
- set_value — установить значение (например, яркость).
- group_action — выполнить группу команд.

### **Параметры по типам**

#### **send_notification**

```yaml
action:
  type: send_notification
  recipient: <email_или_id>
  message: <текст_сообщения>
```

#### **turn_on / turn_off**

```yaml
action:
  type: turn_on
  device_id: <id_устройства>
```

#### **set_value**

```yaml
action:
  type: set_value
  device_id: <id_устройства>
  value: <числовое_значение>
```

#### **group_action**

```yaml
action:
  type: group_action
  commands:
    - device_id: <id_устройства_1>
      action: <turn_on|turn_off|set_value>
      value: <если_set_value> # опционально
      delay: <секунды> # задержка перед выполнением, опционально
    - device_id: <id_устройства_2>
      ...
```

## **6. Примеры автоматизаций**

### **Пример 1: Оповещение при открытии двери**

```yaml
automation:
  id: door-alert
  name: "Оповещение о открытии двери"
  trigger:
    type: sensor_change
    sensor_id: garage_door
  action:
    type: send_notification
    recipient: admin@example.com
    message: "Дверь гаража открыта!"
  enabled: true
```

### **Пример 2: Управление вытяжкой по TVOC и CO₂**

```yaml
automation:
    id: air-control
    name: "Контроль качества воздуха"
    trigger:
      type: multi_condition
      conditions:
        - sensor_id: living_room_tvoc
          operator: ">"
          value: 500
          hysteresis:
            low: 450
            high: 550
        - sensor_id: living_room_co2
          operator: ">"
          value: 800
      combine_logic: "AND"
    action:
      type: turn_on
      device_id: exhaust_fan
    enabled: true
```

### **Пример 3: Групповое действие**

```yaml
automation:
  id: complex-action
  name: "Комплексное управление"
  trigger:
    type: multi_condition
    conditions:
      - sensor_id: temp_sensor
        operator: "<"
        value: 18
  action:
    type: group_action
    commands:
      - device_id: heater
        action: turn_on
        delay: 0
      - device_id: lights
        action: set_value
        value: 50
        delay: 3
      - device_id: fan
        action: turn_off
        delay: 5
        enabled: true
```

## **7. Рекомендации**

1. ****Уникальность ID****: Каждый id автоматизации должен быть уникальным.
2. ****Проверка sensor_id****: Убедитесь, что sensor_id и device_id существуют в системе.
3. ****Гистерезис****: Используйте для датчиков с плавающими значениями (температура,
   TVOC).
4. ****Логика AND/OR****: В multi_condition:
    - AND — все условия должны быть выполнены.
    - OR — достаточно одного выполненного условия.
5. ****Задержки в group_action****: Используйте delay для последовательного выполнения
   команд.

## **8. Ошибки и отладка**

- ****Нет данных в Redis/БД****: Проверьте, что датчик передаёт данные.
- ****Не срабатывает триггер****: Убедитесь, что enabled: true и условия корректны.
- ****Устройство не реагирует****: Проверьте device_id и доступность устройства.
- ****Ошибки в логах****: Смотрите логи движка автоматизаций для деталей.