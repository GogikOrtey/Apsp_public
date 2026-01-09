"""
Точка входа для запуска Flask-фронта.

Запуск:
  python MAIN_APP.py

По умолчанию поднимает Flask на 127.0.0.1:5000 в debug, без reloader (чтобы логи/print не "переезжали" в дочерний процесс).
Параметры можно переопределить через переменные окружения:
  APSP_HOST, APSP_PORT, APSP_DEBUG
"""

import os

def _env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    v = v.strip().lower()
    return v in ("1", "true", "yes", "y", "on")

if __name__ == "__main__":
    # # Поменять переменную среды для теста можно так:
    # os.environ.setdefault("APSP_TASK_TIMEOUT_SECONDS", "5")
    
    # # ТЕСТ: ограничение в 1 задачу, чтобы проверить блокировку интерфейса
    # os.environ.setdefault("APSP_MAX_WORKERS", "1")

    from Apsp_front.app import run_dev_server

    host = os.environ.get("APSP_HOST", "127.0.0.1")
    port = int(os.environ.get("APSP_PORT", "5000"))
    debug = _env_bool("APSP_DEBUG", True)
    run_dev_server(host=host, port=port, debug=debug)


