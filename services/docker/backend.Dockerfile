# services/docker/backend.Dockerfile
FROM python:3.14-slim-bookworm AS base

LABEL maintainer="Ignat Vakorin https://vakorin.net"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# --- Этап 1: Установка системных зависимостей
FROM base AS system-deps
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        i2c-tools \
    && rm -rf /var/lib/apt/lists/*

# Проверяем реальные пути к утилитам (на случай нестандартного расположения)
RUN which i2cdetect || echo "i2cdetect not found" && \
    which i2cset || echo "i2cset not found"


# --- Этап 2: Установка Poetry
FROM base AS poetry-install
COPY --from=system-deps / /
RUN pip install --no-cache-dir poetry


# --- Этап 3: Установка Python-зависимостей
FROM base AS python-deps
COPY --from=poetry-install /usr/local/bin/poetry /usr/local/bin/poetry
COPY poetry.lock pyproject.toml ./
RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi --only main


# --- Этап 4: Установка RPi.GPIO только для arm64
FROM base AS rpi-deps
COPY --from=system-deps / /
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

# Копируем системные зависимости (используем which для точного пути)
RUN mkdir -p /usr/local/bin && \
    cp $(which i2cdetect) /usr/local/bin/i2cdetect && \
    cp $(which i2cset) /usr/local/bin/i2cset


# Альтернатива: копируем напрямую из system-deps, если уверены в путях
# COPY --from=system-deps /usr/sbin/i2cdetect /usr/local/bin/i2cdetect
# COPY --from=system-deps /usr/sbin/i2cset /usr/local/bin/i2cset


# Копируем Poetry и Python-зависимости
COPY --from=poetry-install /usr/local/bin/poetry /usr/local/bin/poetry
COPY --from=python-deps /usr/local/lib/python3.14/site-packages/ /usr/local/lib/python3.14/site-packages/


# Копируем RPi.GPIO (если установлен)
COPY --from=rpi-deps /usr/local/lib/python3.14/site-packages/RPi /usr/local/lib/python3.14/site-packages/RPi
COPY --from=rpi-deps /usr/local/lib/python3.14/site-packages/RPi* /usr/local/lib/python3.14/site-packages/


# Очищаем кэш pip
RUN find /usr/local/lib/python3.14/site-packages/ -name "*.dist-info" -exec rm -rf {} +


# Копируем код приложения
COPY backend/ /app/


# Проверка RPi.GPIO для arm64
RUN if [ "$(dpkg --print-architecture)" = "arm64" ]; then \
        python -c "import RPi.GPIO; print('RPi.GPIO OK')"; \
    else \
        echo "RPi.GPIO test skipped (not arm64)"; \
    fi

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80", "--proxy-headers", "--forwarded-allow-ips=*"]
