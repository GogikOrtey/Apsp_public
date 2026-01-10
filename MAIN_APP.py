"""
Точка входа для запуска Flask-фронта.

Запуск:
  python MAIN_APP.py

По умолчанию поднимает Flask на 127.0.0.1:5000 в debug, без reloader (чтобы логи/print не "переезжали" в дочерний процесс).
Параметры можно переопределить через переменные окружения:
  APSP_HOST, APSP_PORT, APSP_DEBUG
"""

import os
from pathlib import Path

def _env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    v = v.strip().lower()
    return v in ("1", "true", "yes", "y", "on")

if __name__ == "__main__":
    # ============================================================================
    # Загрузка .env файла (если есть)
    # ============================================================================
    # Для локальной разработки можно использовать .env файл.
    # Для Docker/продакшена переменные задаются через docker-compose / env контейнера.
    try:
        from dotenv import load_dotenv
        env_path = Path(__file__).parent / '.env'
        if env_path.is_file():
            load_dotenv(env_path)
            print(f"Loaded .env from {env_path}")
    except ImportError:
        # python-dotenv не установлен - ничего страшного, переменные могут быть заданы системно
        pass
    
    # ============================================================================
    # Telegram бот: настройки авторизации и уведомлений
    # ============================================================================
    # Переменные читаются из окружения (из .env файла или системных env).
    # Если переменная не задана - используется дефолтное значение.
    
    # Токен бота от @BotFather
    os.environ.setdefault(
        "APSP_TELEGRAM_BOT_TOKEN",
        os.getenv("APSP_TELEGRAM_BOT_TOKEN", "")
    )
    
    # Username бота без @ (например: auto_gen_parsers_info_bot)
    os.environ.setdefault(
        "APSP_TELEGRAM_BOT_USERNAME",
        os.getenv("APSP_TELEGRAM_BOT_USERNAME", "auto_gen_parsers_info_bot")
    )
    
    # Секрет для webhook URL (любая строка, которую знаете только вы)
    os.environ.setdefault(
        "APSP_TELEGRAM_WEBHOOK_SECRET",
        os.getenv("APSP_TELEGRAM_WEBHOOK_SECRET", "")
    )
    
    # Базовый URL сервиса
    os.environ.setdefault(
        "APSP_BASE_URL",
        os.getenv("APSP_BASE_URL", "http://127.0.0.1:5000")
    )
    
    # ============================================================================
    # Прочие настройки (опциональные)
    # ============================================================================
    # # Поменять переменную среды для теста можно так:
    # os.environ.setdefault("APSP_TASK_TIMEOUT_SECONDS", "5")    
    # # Ограничение в 1 задачу, чтобы проверить блокировку интерфейса
    # os.environ.setdefault("APSP_MAX_WORKERS", "1")
    
    # ============================================================================

    from Apsp_front.app import run_dev_server

    host = os.environ.get("APSP_HOST", "127.0.0.1")
    port = int(os.environ.get("APSP_PORT", "5000"))
    debug = _env_bool("APSP_DEBUG", True)
    run_dev_server(host=host, port=port, debug=debug)

    # Установка аккаунта в куки реализована в Apsp_front/app.py
    # в роуте main_page_1() через response.set_cookie('user_account', '@GogikOrtey')



