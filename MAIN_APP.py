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
import threading
import time as _time
import telegram_connect



""" 

Основной файл переехал сюда

Задачи:
- Собрать все "Задачи" в проекте в одном месте. По большей части там будут устаревшие
- Разобрать логику роутов в app.py Как минимум - проставить #region для ориентирования. Можно также вынести доп. логику от туда в соседний файл, что бы не нагромождать app.py а то он сильно раздулся
- Пройтись ещё раз по логике создания и отправки скриншотов
- Надо отрефакторить логику отправки сообщений в Тг. Как минимум - прописать свои названия для функций, как максимум - распутать этот клубок, и разнести всё также по модулям в telegram_connect.py
- Надо сделать README.md - для людей, с описанием как работает проект, простым человеческим языком. А CLAUDE.md оставить для нейронок
- Опять же пройтись, посмотреть, возможно какие-то файлы и скрипты устарели, и больше не используются
- И потом ещё посидеть подумать, что нужно сделать по этому проекту

"""















# Загрузка .env перед импортом app.py
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


# Опциональные дефолты для переменных (если не заданы в .env или системно)
os.environ.setdefault("APSP_TELEGRAM_BOT_USERNAME", "auto_gen_parsers_info_bot")
os.environ.setdefault("APSP_BASE_URL", "http://127.0.0.1:5000")

# Прочие настройки (раскомментируйте при необходимости)
# os.environ.setdefault("APSP_TASK_TIMEOUT_SECONDS", "5")
# os.environ.setdefault("APSP_MAX_WORKERS", "1")

def _env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    v = v.strip().lower()
    return v in ("1", "true", "yes", "y", "on")


if __name__ == "__main__":
    # Импортируем app после загрузки .env
    from Apsp_front.app import run_dev_server

    host = os.environ.get("APSP_HOST", "127.0.0.1")
    port = int(os.environ.get("APSP_PORT", "5000"))
    debug = _env_bool("APSP_DEBUG", True)
    
    # def test_code():
    #     try:            
    #         _time.sleep(1.0)  # Дать серверу подняться

    #         """
    #         Вот тут можно написать код для теста. Он выполнится после поднятия сервера.
    #         Это параллельный поток.
    #         """

    #         telegram_connect.try_send_to_log_chat("Текст для отправки в Log chat")
    #         telegram_connect.try_send_to_info_chat("Текст для отправки в Info chat")
            
    #     except Exception as e:
    #         print(e)
    # threading.Thread(target=test_code, daemon=True).start()

    run_dev_server(host=host, port=port, debug=debug)

    # Установка аккаунта в куки реализована в Apsp_front/app.py
    # в роуте main_page_1() через response.set_cookie('user_account', '@GogikOrtey')
