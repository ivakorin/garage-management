FROM python:3.14-alpine AS base

LABEL maintainer="Ignat Vakorin https://vakorin.net"
RUN apk update && apk add --no-cache g++ python3-dev libgpiod-dev libgpiod curl
RUN pip install poetry

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
COPY poetry.lock pyproject.toml ./
RUN poetry config virtualenvs.create false
RUN poetry install --no-interaction --no-ansi --only main
COPY backend/ /app/
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80", "--proxy-headers", "--forwarded-allow-ips=*"]

