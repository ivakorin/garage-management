# services/docker/backend.Dockerfile
FROM python:3.14-slim-bookworm AS base


LABEL maintainer="Ignat Vakorin https://vakorin.net"

# Переменные окружения
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Для условной установки зависимостей
ARG TARGETPLATFORM
ARG BUILDPLATFORM

WORKDIR /app

# --- Этап 1: Установка общих системных зависимостей (для всех платформ)
FROM base AS common-system-deps

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        i2c-tools \
    && rm -rf /var/lib/apt/lists/*

# --- Этап 2: Установка Poetry
FROM base AS poetry-install

COPY --from=common-system-deps / /
RUN pip install --no-cache-dir poetry

# --- Этап 3: Установка Python-зависимостей (без RPi.GPIO)
FROM base AS python-deps


COPY poetry.lock pyproject.toml ./
RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi --only main

# --- Этап 4: Установка RPi.GPIO только для arm64
FROM base AS rpi-deps


# Проверяем архитектуру (arm64 = Raspberry Pi)
RUN if [ "$(dpkg --print-architecture)" = "arm64" ]; then \
        apt-get update && \
        apt-get install -y --no-install-recommends build-essential python3-dev libgpiod-dev libgpiod2 && \
        pip install --no-cache-dir RPi.GPIO && \
        apt-get remove -y build-essential python3-dev && \
        apt-get autoremove -y && \
        rm -rf /var/lib/apt/lists/*; \
    else \
        echo "Skipping RPi.GPIO setup (not arm64)"; \
    fi

# --- Финальный этап: Сборка образа
FROM base

# Копируем общие системные зависимости
COPY --from=common-system-deps /usr/bin/i2cdetect /usr/bin/i2cdetect
COPY --from=common-system-deps /usr/sbin/i2cset /usr/sbin/i2cset


# Копируем Poetry и Python-зависимости
COPY --from=poetry-install /usr/local/bin/poetry /usr/local/bin/poetry
COPY --from=python-deps /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/


# Копируем RPi.GPIO только если он был собран (для arm64)
COPY --from=rpi-deps /usr/local/lib/python3.11/site-packages/RPi /usr/local/lib/python3.11/site-packages/RPi
COPY --from=rpi-deps /usr/local/lib/python3.11/site-packages/RPi* /usr/local/lib/python3.11/site-packages/

# Очищаем кэш pip
RUN find /usr/local/lib/python3.11/site-packages/ -name "*.dist-info" -exec rm -rf {} +


# Копируем код приложения
COPY backend/ /app/


# Проверка: если arm64, убедимся, что RPi.GPIO доступен
RUN if [ "$(dpkg --print-architecture)" = "arm64" ]; then \
        python -c "import RPi.GPIO; print('RPi.GPIO OK')"; \
    else \
        echo "RPi.GPIO test skipped (not arm64)"; \
    fi

# Запуск
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80", "--proxy-headers", "--forwarded-allow-ips=*"]
