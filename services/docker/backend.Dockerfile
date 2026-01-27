FROM python:3.14-slim-bookworm AS base


LABEL maintainer="Ignat Vakorin https://vakorin.net"


ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

FROM base AS system-deps
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        i2c-tools \
    && rm -rf /var/lib/apt/lists/*


FROM base AS poetry-install
COPY --from=system-deps / /
RUN pip install --no-cache-dir poetry


FROM base AS python-deps
COPY --from=poetry-install /usr/local/bin/poetry /usr/local/bin/poetry
COPY poetry.lock pyproject.toml ./
RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi --only main


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

FROM base
COPY --from=system-deps /usr/sbin/i2cdetect /usr/local/bin/i2cdetect
COPY --from=system-deps /usr/sbin/i2cset /usr/local/bin/i2cset

COPY --from=poetry-install /usr/local/bin/poetry /usr/local/bin/poetry
COPY --from=python-deps /usr/local/lib/python3.14/site-packages/ /usr/local/lib/python3.14/site-packages/

RUN mkdir -p /tmp/rpi-check && \
    if [ -d "/usr/local/lib/python3.14/site-packages/RPi" ]; then \
        cp -r /usr/local/lib/python3.14/site-packages/RPi /tmp/rpi-check/; \
    fi

COPY --from=rpi-deps --chown=0:0 /usr/local/lib/python3.14/site-packages/RPi* /tmp/rpi-check/


RUN if [ -d "/tmp/rpi-check/RPi" ]; then \
        cp -r /tmp/rpi-check/RPi* /usr/local/lib/python3.14/site-packages/; \
        rm -rf /tmp/rpi-check; \
    else \
        rm -rf /tmp/rpi-check; \
        echo "RPi packages not found (skipping copy)"; \
    fi

RUN find /usr/local/lib/python3.14/site-packages/ -name "*.dist-info" -exec rm -rf {} +


COPY backend/ /app/


RUN if [ "$(dpkg --print-architecture)" = "arm64" ]; then \
        python -c "import RPi.GPIO; print('RPi.GPIO OK')"; \
    else \
        echo "RPi.GPIO test skipped (not arm64)"; \
    fi

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80", "--proxy-headers", "--forwarded-allow-ips=*"]
