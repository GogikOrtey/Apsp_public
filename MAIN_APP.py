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
    # # Ограничение в 1 задачу, чтобы проверить блокировку интерфейса
    # os.environ.setdefault("APSP_MAX_WORKERS", "1")

    # ============================================================================
    # Telegram бот: настройки авторизации и уведомлений
    # ============================================================================
    # ВАЖНО: Для продакшена замените значения ниже на реальные или задайте через env.
    # Эти дефолты нужны для локальной разработки и тестирования.
    
    # Токен бота от @BotFather
    os.environ.setdefault("APSP_TELEGRAM_BOT_TOKEN", _) # auto_gen_parsers_info_bot_access_token из env 
    
    # Username бота без @ (например: auto_gen_parsers_info_bot)
    os.environ.setdefault("APSP_TELEGRAM_BOT_USERNAME", "auto_gen_parsers_info_bot")
    
    # Секрет для webhook URL (любая строка, которую знаете только вы)
    os.environ.setdefault("APSP_TELEGRAM_WEBHOOK_SECRET", _) # auto_gen_parsers_info_bot_secret_keyphrase из env
    
    # Базовый URL сервиса (для локальной разработки http://127.0.0.1:5000, 
    # для ngrok - замените на https://xxxx.ngrok-free.app,
    # для продакшена - ваш реальный домен)
    os.environ.setdefault("APSP_BASE_URL", "http://127.0.0.1:5000")
    
    # ============================================================================

    from Apsp_front.app import run_dev_server

    host = os.environ.get("APSP_HOST", "127.0.0.1")
    port = int(os.environ.get("APSP_PORT", "5000"))
    debug = _env_bool("APSP_DEBUG", True)
    run_dev_server(host=host, port=port, debug=debug)

    # Установка аккаунта в куки реализована в Apsp_front/app.py
    # в роуте main_page_1() через response.set_cookie('user_account', '@GogikOrtey')



