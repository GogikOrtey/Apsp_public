#!/usr/bin/env sh
set -eu

HOST="${APSP_HOST:-0.0.0.0}"
PORT="${APSP_PORT:-5000}"

# ВАЖНО для этого проекта:
# - запускаем 1 worker, чтобы не плодить несколько TaskRegistry/Playwright-pool одновременно
# - используем threads для параллельных HTTP-запросов UI
WORKERS="${GUNICORN_WORKERS:-1}"
THREADS="${GUNICORN_THREADS:-8}"
TIMEOUT="${GUNICORN_TIMEOUT:-300}"

exec gunicorn \
  --bind "${HOST}:${PORT}" \
  --workers "${WORKERS}" \
  --threads "${THREADS}" \
  --timeout "${TIMEOUT}" \
  "wsgi:app"


