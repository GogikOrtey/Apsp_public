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



""" 

Основной файл переехал сюда


telegram_connect.try_send_to_log_chat("Текст для отправки в Log chat")
telegram_connect.try_send_to_info_chat("Текст для отправки в Info chat")

"""














# ============================================================================
# ВАЖНО: Загрузка .env ПЕРЕД импортом app.py
# ============================================================================
# Flask читает переменные окружения при импорте модуля app.py,
# поэтому нужно загрузить .env ДО импорта.
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    if env_path.is_file():
        load_dotenv(env_path)
        print(f"✓ Loaded .env from {env_path}")
    else:
        print(f"⚠ .env file not found at {env_path}")
        print("  Using system environment variables or defaults")
except ImportError:
    print("⚠ python-dotenv not installed")
    print("  Install with: pip install python-dotenv")
    print("  Using system environment variables or defaults")

# ============================================================================
# Опциональные дефолты для переменных (если не заданы в .env или системно)
# ============================================================================
os.environ.setdefault("APSP_TELEGRAM_BOT_USERNAME", "auto_gen_parsers_info_bot")
os.environ.setdefault("APSP_BASE_URL", "http://127.0.0.1:5000")

# Прочие настройки (раскомментируйте при необходимости)
# os.environ.setdefault("APSP_TASK_TIMEOUT_SECONDS", "5")
# os.environ.setdefault("APSP_MAX_WORKERS", "1")

# ============================================================================

def _env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    v = v.strip().lower()
    return v in ("1", "true", "yes", "y", "on")

if __name__ == "__main__":
    # Импортируем app ПОСЛЕ загрузки .env
    from Apsp_front.app import run_dev_server

    # Диагностика: показываем какие переменные загружены
    print("\n" + "="*70)
    print("Telegram Bot Configuration:")
    print("="*70)
    token = os.environ.get("APSP_TELEGRAM_BOT_TOKEN", "")
    print(f"APSP_TELEGRAM_BOT_TOKEN: {'✓ SET' if token else '✗ NOT SET'}")
    
    username = os.environ.get("APSP_TELEGRAM_BOT_USERNAME", "")
    print(f"APSP_TELEGRAM_BOT_USERNAME: {username or '✗ NOT SET'}")
    
    secret = os.environ.get("APSP_TELEGRAM_WEBHOOK_SECRET", "")
    print(f"APSP_TELEGRAM_WEBHOOK_SECRET: {'✓ SET' if secret else '✗ NOT SET'}")
    
    base_url = os.environ.get("APSP_BASE_URL", "")
    print(f"APSP_BASE_URL: {base_url or '✗ NOT SET'}")
    print("="*70 + "\n")

    host = os.environ.get("APSP_HOST", "127.0.0.1")
    port = int(os.environ.get("APSP_PORT", "5000"))
    debug = _env_bool("APSP_DEBUG", True)
    run_dev_server(host=host, port=port, debug=debug)

    # Установка аккаунта в куки реализована в Apsp_front/app.py
    # в роуте main_page_1() через response.set_cookie('user_account', '@GogikOrtey')
