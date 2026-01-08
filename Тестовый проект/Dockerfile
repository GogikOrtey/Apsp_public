FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
# ВАЖНО: не используем cache-mount для /ms-playwright.
# Иначе браузеры будут установлены в build-cache, но не попадут в слои образа (docker save/load на другой машине сломается).
RUN pip install -r requirements.txt && python -m playwright install --with-deps chromium

COPY . .

ENV PORT=8000
EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]

