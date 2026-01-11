FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

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

EXPOSE 5000

CMD ["python", "MAIN_APP.py"]


