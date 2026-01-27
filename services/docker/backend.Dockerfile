FROM --platform=$BUILDPLATFORM python:3.14-slim-bookworm AS base

LABEL maintainer="Ignat Vakorin https://vakorin.net"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Этап для системных зависимостей (универсальные пакеты)
FROM base AS system-deps
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Этап для i2c-tools (только для arm64)
FROM base AS i2c-deps
RUN if [ "$(dpkg --print-architecture)" = "arm64" ]; then \
        apt-get update && \
        apt-get install -y --no-install-recommends i2c-tools && \
        rm -rf /var/lib/apt/lists/*; \
    else \
        echo "Skipping i2c-tools for non-arm64"; \
    fi

FROM base AS poetry-install
COPY --from=system-deps / /
COPY --from=i2c-deps / /
RUN pip install --no-cache-dir poetry


FROM base AS python-deps
COPY --from=poetry-install /usr/local/ /usr/local/
COPY poetry.lock pyproject.toml ./
RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi --only main


FROM base AS rpi-deps
COPY --from=system-deps / /
COPY --from=i2c-deps / /
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

FROM base

# Промежуточный этап: проверяем и копируем i2c-инструменты, если они есть
RUN mkdir -p /usr/local/bin && \
    if [ -f /tmp/i2c-deps/usr/sbin/i2cdetect ]; then \
        cp /tmp/i2c-deps/usr/sbin/i2cdetect /usr/local/bin/i2cdetect && \
        echo "i2cdetect copied"; \
    else \
        echo "i2cdetect not found (non-arm64)"; \
    fi && \
    if [ -f /tmp/i2c-deps/usr/sbin/i2cset ]; then \
        cp /tmp/i2c-deps/usr/sbin/i2cset /usr/local/bin/i2cset && \
        echo "i2cset copied"; \
    else \
        echo "i2cset not found (non-arm64)"; \
    fi

# Копируем poetry и его зависимости
COPY --from=poetry-install /usr/local/ /usr/local/

# Копируем Python-пакеты
COPY --from=python-deps /usr/local/lib/python3.14/site-packages/ /usr/local/lib/python3.14/site-packages/
COPY --from=rpi-deps /usr/local/lib/python3.14/site-packages/RPi* /usr/local/lib/python3.14/site-packages/

# Проверка RPi.GPIO (только для arm64)
RUN if [ "$(dpkg --print-architecture)" = "arm64" ]; then \
        if [ -d "/usr/local/lib/python3.14/site-packages/RPi" ]; then \
            python -c "import RPi.GPIO; print('RPi.GPIO OK')" || \
            (echo "RPi.GPIO import failed" && exit 1); \
        else \
            echo "RPi directory not found in site-packages"; \
        fi; \
    else \
        echo "RPi.GPIO test skipped (not arm64)"; \
    fi

COPY backend/ /app/

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80", "--proxy-headers", "--forwarded-allow-ips=*"]
