FROM python:3.14-slim-bookworm


LABEL maintainer="Ignat Vakorin https://vakorin.net"

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        python3-dev \
        libgpiod-dev \
        libgpiod2 \
        curl \
        i2c-tools \
    && rm -rf /var/lib/apt/lists/*


# Установка Poetry
RUN pip install poetry


WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1


COPY poetry.lock pyproject.toml ./
RUN poetry config virtualenvs.create false
RUN poetry install --no-interaction --no-ansi --only main


COPY backend/ /app/


CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80", "--proxy-headers", "--forwarded-allow-ips=*"]
