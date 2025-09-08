# syntax=docker/dockerfile:1

# --- Build stage ---
FROM python:3.11-slim AS builder
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends build-essential gcc libpq-dev curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --upgrade pip wheel setuptools \
    && pip install -r requirements.txt

# --- Runtime stage ---
FROM python:3.11-slim
WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app
USER app

COPY --from=builder /usr/local /usr/local
COPY . .

EXPOSE 8080
HEALTHCHECK CMD curl --fail http://localhost:8080/healthz || exit 1

CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "main:app", \
     "-b", "0.0.0.0:8080", "-w", "4", "--log-level", "info"]