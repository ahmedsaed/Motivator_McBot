FROM python:3.13-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install -r requirements.txt


FROM python:3.13-slim

LABEL org.opencontainers.image.title="Motivator McBot" \
      org.opencontainers.image.description="A bot that posts motivational quotes rendered over random photography" \
      org.opencontainers.image.source="https://github.com/ahmedsaed/Motivator_McBot" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    OUTPUT_PATH=/app/images/output_image.jpg

# DejaVu supplies the bold sans face the renderer falls back to, replacing the
# arial.ttf that setup.sh used to download at install time.
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 bot

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY bot.py ./
COPY data ./data
RUN mkdir -p /app/images /app/state && chown -R bot:bot /app

USER bot

ENTRYPOINT ["python", "bot.py"]
