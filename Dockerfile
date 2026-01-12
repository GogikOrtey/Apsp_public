FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Node.js deps (нужны для инструментов в `new_program/html_toolkit.py`, которые запускают `node -e ...` и `require('cheerio')`)
# NOTE: берем nodejs из репозитория Debian (для bookworm это Node 18.x, что достаточно для cheerio ^1.1.x).
RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# NPM deps (cheerio и др.) — ставим до копирования всего репозитория, чтобы Docker-cache работал лучше
COPY package.json package-lock.json ./
RUN npm ci --omit=dev \
    && npm cache clean --force

# Python deps
COPY requirements.txt .

# Playwright browsers location inside image
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# ВАЖНО: не используем cache-mount для /ms-playwright.
# Иначе браузеры будут установлены в build-cache, но не попадут в слои образа (docker save/load на другой машине сломается).
RUN pip install --no-cache-dir -r requirements.txt && python -m playwright install --with-deps chromium

# App code
COPY . .

# Runtime defaults for container (can be overridden via docker-compose / env)
ENV APSP_HOST=0.0.0.0
ENV APSP_PORT=5000
ENV APSP_DEBUG=false

# Result tasks folder (Linux/container path used by Apsp_front/app.py)
RUN mkdir -p /RESULT_TASKS

RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 5000

CMD ["/app/docker-entrypoint.sh"]


