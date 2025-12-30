#!/bin/bash

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color


echo -e "${YELLOW}Установка Garage Management${NC}"

# Шаг 1. Запрос пути для работы
read -p "Введите путь для установки (пусто = текущая директория): " INSTALL_PATH

if [ -z "$INSTALL_PATH" ]; then
    INSTALL_PATH="."
    echo -e "${GREEN}→ Используем текущую директорию: $(pwd)${NC}"
else
    # Проверяем существование директории
    if [ ! -d "$INSTALL_PATH" ]; then
        echo -e "${RED}→ Директория $INSTALL_PATH не существует! Создаём...${NC}"
        mkdir -p "$INSTALL_PATH"
        if [ $? -ne 0 ]; then
            echo -e "${RED}Ошибка создания директории $INSTALL_PATH. Выход.${NC}"
            exit 1
        fi
    fi
    echo -e "${GREEN}→ Работаем в директории: $INSTALL_PATH${NC}"
fi

# Переходим в целевую директорию
cd "$INSTALL_PATH" || { echo -e "${RED}Не удалось перейти в $INSTALL_PATH. Выход.${NC}"; exit 1; }


# Шаг 2. Клонирование репозитория
REPO_URL="https://gitflic.ru/project/ivakorin/garage-management.git"
echo -e "${YELLOW}→ Клонируем репозиторий: $REPO_URL${NC}"


git clone "$REPO_URL" tmp_garage_management
if [ $? -ne 0 ]; then
    echo -e "${RED}Ошибка клонирования репозитория. Выход.${NC}"
    exit 1
fi

# Шаг 3. Копирование /services/docker/ (исключая любые файлы, содержащие "Dockerfile" в имени)
echo -e "${YELLOW}→ Копируем services/docker/... (исключая файлы с \"Dockerfile\" в имени)${NC}"


find tmp_garage_management/services/docker/ -mindepth 1 \
    -maxdepth 1 \
    ! -iregex '.*/.*Dockerfile.*' \
    -exec cp -r {} ./ \;


if [ $? -ne 0 ]; then
    echo -e "${RED}Ошибка копирования файлов из services/docker/. Выход.${NC}"
    rm -rf tmp_garage_management
    exit 1
fi

# Шаг 4. Копирование и переименование .env_example
echo -e "${YELLOW}→ Копируем .env_example → .env${NC}"
if [ -f "tmp_garage_management/.env_example" ]; then
    cp tmp_garage_management/.env_example ./.env
    if [ $? -ne 0 ]; then
        echo -e "${RED}Ошибка копирования .env_example. Выход.${NC}"
        rm -rf tmp_garage_management
        exit 1
    fi
else
    echo -e "${RED}.env_example не найден в репозитории. Пропускаем.${NC}"
fi

# Шаг 5. Создание директории plugins и копирование файлов из /backend/plugins
echo -e "${YELLOW}→ Создаём директорию plugins и копируем файлы из backend/plugins/${NC}"
mkdir -p plugins
if [ -d "tmp_garage_management/backend/plugins" ]; then
    cp -r tmp_garage_management/backend/plugins/* plugins/
    if [ $? -ne 0 ]; then
        echo -e "${RED}Ошибка копирования файлов из backend/plugins/. Выход.${NC}"
        rm -rf tmp_garage_management
        exit 1
    fi
else
    echo -e "${RED}Директория backend/plugins не найдена в репозитории. Пропускаем.${NC}"
fi

# Шаг 6. Удаление всех файлов .gitkeep в скопированных директориях
echo -e "${YELLOW}→ Удаляем все файлы .gitkeep в скопированных директориях...${NC}"
find . -name ".gitkeep" -type f -delete
if [ $? -ne 0 ]; then
    echo -e "${RED}Ошибка при удалении .gitkeep. Продолжаем...${NC}"
fi

# Шаг 7. Делаем файл init-mqtt.sh исполняемым в директории mosquitto
echo -e "${YELLOW}→ Проверяем и настраиваем права для init-mqtt.sh в директории mosquitto...${NC}"

if [ -f "mosquitto/init-mqtt.sh" ]; then
    chmod +x "mosquitto/init-mqtt.sh"
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}→ Файл mosquitto/init-mqtt.sh успешно сделан исполняемым.${NC}"
    else
        echo -e "${RED}→ Ошибка при установке прав для mosquitto/init-mqtt.sh.${NC}"
    fi
else
    echo -e "${YELLOW}→ Файл mosquitto/init-mqtt.sh не найден. Пропускаем.${NC}"
fi

# Шаг 8. Очистка временных файлов
echo -e "${YELLOW}→ Удаляем временные файлы...${NC}"
rm -rf tmp_garage_management


# Финальное сообщение
echo -e "${GREEN}"
echo "========================================="
echo "Установка завершена!"
echo "→ Файлы скопированы в: $(pwd)"
echo "→ Проверьте файл .env и настройте его при необходимости."
echo "→ Для запуска используйте: docker-compose up -d"
echo "→ Файлы с \"Dockerfile\" в имени не были скопированы."
echo "→ Плагины скопированы в директорию: $(pwd)/plugins"
echo "→ Все файлы .gitkeep удалены из скопированных директорий."
echo "→ Файл mosquitto/init-mqtt.sh сделан исполняемым (если присутствовал)."
echo "========================================="
echo -e "${NC}"

exit 0
