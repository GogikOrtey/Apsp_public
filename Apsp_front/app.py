"""
Flask-фронт APSP.

Назначение:
- UI страницы `main_page_1/main_page_2/main_page_3` (см. `Apsp_front/templates/*`)
- API-эндпоинты для UI: лог, состояние прогресса, выдача результата, скриншоты

Важно:
- В этом файле НЕТ Flask `session`/`secret_key` (старый многошаговый флоу удалён).
- Часть состояния/файлов используется как "простой IPC" между Flask и `MAIN.py`/Playwright.
"""

from flask import Flask, render_template, request, redirect, url_for, send_from_directory, send_file, make_response
import json
import sys
import os
import threading
import zipfile
from pathlib import Path
from io import BytesIO
from datetime import datetime
import time
import shutil
import stat
from urllib.parse import urlparse
import re

import telegram_connect

# Корень репозитория (нужно для импорта модулей из верхнего уровня проекта).
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Проект исторически использует "агрегатор" импортов.
# Да, это не идеально (может переопределять имена), но так устроен текущий проект.
from import_all_libraries import *
from new_program.main_processer import *
from task_runtime.task_registry import TaskRegistry, TaskInfo
from task_runtime.stop_store import request_stop, USER_STOP_MESSAGE
from task_runtime.task_context import set_current_task, clear_current_task
from task_runtime.screenshot_store import TASK_SCREENSHOTS_STATE, TASK_SCREENSHOTS_LOCK
from task_runtime.print_router import install_print_router, register_thread_io, unregister_thread_io
# Скриншот текущей Playwright-страницы (если браузер запущен)
from playwright_tool.shared_page import get_cached_screenshot_png, clear_shared_page, set_shared_page
# Важно: `import *` выше может перетереть имя `Response` не-flask'овским классом.
# Явно фиксируем, что в этом файле под Response для HTTP-ответов используется именно flask.Response.
from flask import Response as FlaskResponse
import atexit

app = Flask(__name__) 

# Время старта текущего экземпляра приложения
APP_START_TIME = time.time() 


@app.errorhandler(404)
def page_not_found(e):
    """
    Стандартная страница 404 для любых неправильных URL.
    Для /api/* оставляем машинный JSON-ответ.
    """
    try:
        if request.path.startswith("/api/"):
            return FlaskResponse(
                '{"ok":false,"error":"not_found"}',
                mimetype='application/json; charset=utf-8',
                status=404
            )
    except Exception:
        # best-effort: если request недоступен по какой-то причине — покажем HTML
        pass
    return render_template("page_404.html"), 404


def run_dev_server(host: str = "127.0.0.1", port: int = 5000, debug: bool = True) -> None:
    """
    Запуск dev-сервера Flask.

    Важно: отключаем reloader, чтобы весь вывод стабильно попадал в одно окно/процесс
    (особенно при запуске из IDE/DebugPy).
    """
    app.run(debug=debug, host=host, port=port, use_reloader=False)

# Абсолютные пути: не зависят от текущей рабочей директории.
FRONT_DIR = Path(__file__).resolve().parent              # .../APSP_public/Apsp_front
PROJECT_ROOT = FRONT_DIR.parent                          # .../APSP_public

# Добавляем корень проекта в sys.path, чтобы можно было импортировать MainFuncAgent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))
 
# Выходные файлы генерации (лежат в корне проекта).
# Эти файлы пишет "бэк"/пайплайн генерации (например, `MAIN.py` и связанные модули),
# а Flask только отдаёт их UI как текст/скачивание.
RESULT_OUTPUT_DIR = PROJECT_ROOT / 'result_code_gen' / 'result'
RESULT_CODE_FILE_PATH = RESULT_OUTPUT_DIR / 'result_code.ts'
MESSAGE_GLOBAL_FILE_PATH = RESULT_OUTPUT_DIR / 'message_global.txt'
LOG_FILE_PATH = PROJECT_ROOT / 'output.log'
USEFUL_LOG_FILE_PATH = PROJECT_ROOT / 'useful_log.log'
NEW_PAGE_2_STATE_FILE_PATH = RESULT_OUTPUT_DIR / 'new_page_2_state.json'


def _resolve_result_tasks_dir() -> Path:
    """
    На Linux (контейнер) складываем результаты в /RESULT_TASKS.
    На Windows — на уровень выше папки проекта (рядом с репозиторием).
    """
    if os.name == "nt":
        return PROJECT_ROOT.parent / "RESULT_TASKS"
    return Path("/RESULT_TASKS")


RESULT_TASKS_DIR = _resolve_result_tasks_dir()

# ============================================================================
# Telegram connect config (bot auth + messaging)
# ============================================================================

TELEGRAM_BOT_TOKEN = os.environ.get("APSP_TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_BOT_USERNAME = os.environ.get("APSP_TELEGRAM_BOT_USERNAME", "").strip().lstrip("@")
TELEGRAM_WEBHOOK_SECRET = os.environ.get("APSP_TELEGRAM_WEBHOOK_SECRET", "").strip()
APSP_BASE_URL = os.environ.get("APSP_BASE_URL", "http://127.0.0.1:5000").strip()

TELEGRAM_AUTH_DIR = PROJECT_ROOT / "Apsp_front" / "_telegram_auth"
TELEGRAM_USERS_DIR = PROJECT_ROOT / "Apsp_front" / "_telegram_users"


# ============================================================================
# Централизованные функции для работы с кукой аккаунта
# ============================================================================

def set_user_account_cookie(response, username: str, max_age_days: int = 365):
    """
    Устанавливает куку user_account в переданный response.
    
    Args:
        response: Flask response объект
        username: имя пользователя для сохранения в куке
        max_age_days: срок жизни куки в днях (по умолчанию 365)
    
    Returns:
        response с установленной кукой
    """
    response.set_cookie(
        'user_account',
        username,
        max_age=max_age_days * 24 * 60 * 60,
        httponly=False,  # должна быть доступна из JavaScript
        secure=False,    # установить True для HTTPS в продакшене
        samesite='Lax'
    )
    return response


def get_user_account_from_cookie() -> str | None:
    """
    Получает имя пользователя из куки user_account.
    
    Returns:
        Имя пользователя или None, если кука не установлена
    """
    return request.cookies.get('user_account')


def clear_user_account_cookie(response):
    """
    Удаляет куку user_account из переданного response.
    
    Args:
        response: Flask response объект
    
    Returns:
        response с удалённой кукой
    """
    response.set_cookie('user_account', '', max_age=0)
    return response


# ============================================================================
# Telegram user cookie helpers
# ============================================================================

def set_user_telegram_id_cookie(response, tg_id: int, max_age_days: int = 365):
    """
    Сохраняем Telegram ID в отдельной куке.

    Примечание по безопасности:
    - Для продакшена лучше хранить сессии/привязки на сервере и/или подписывать cookie.
    - Здесь кука используется в основном для UX и уведомлений.
    """
    try:
        tg_id_str = str(int(tg_id))
    except Exception:
        tg_id_str = ""

    response.set_cookie(
        'user_telegram_id',
        tg_id_str,
        max_age=max_age_days * 24 * 60 * 60,
        httponly=True,   # JS не нужен доступ к tg_id
        secure=False,    # установить True для HTTPS в продакшене
        samesite='Lax'
    )
    return response


def get_user_telegram_id_from_cookie() -> int | None:
    v = request.cookies.get('user_telegram_id')
    if not v:
        return None
    try:
        return int(v)
    except Exception:
        return None


def clear_user_telegram_id_cookie(response):
    response.set_cookie('user_telegram_id', '', max_age=0)
    return response


# ============================================================================


def _on_rm_error(func, path, exc_info):
    # Best-effort handling for Windows read-only files.
    try:
        os.chmod(path, stat.S_IWRITE)
    except Exception:
        pass
    try:
        func(path)
    except Exception:
        raise


def _cleanup_result_tasks_older_than(days: int = 7) -> int:
    """
    Удаляет подпапки в RESULT_TASKS, у которых в meta.json указано,
    что они созданы старше N дней (по полю created_at_ts).

    Возвращает количество успешно удалённых папок.
    """
    root = RESULT_TASKS_DIR
    if not root.exists() or not root.is_dir():
        return 0

    cutoff_ts = time.time() - float(days) * 24.0 * 60.0 * 60.0
    deleted = 0

    for child in root.iterdir():
        if not child.is_dir():
            continue

        meta_path = child / "meta.json"
        if not meta_path.is_file():
            continue

        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        created_at_ts = (meta or {}).get("created_at_ts")
        try:
            created_at_ts_f = float(created_at_ts)
        except Exception:
            continue

        if created_at_ts_f >= cutoff_ts:
            continue

        try:
            shutil.rmtree(child, onerror=_on_rm_error)
            deleted += 1
        except Exception:
            # best-effort: не блокируем старт фронта из-за одной плохой папки
            pass

    return deleted
NEW_PAGE_2_ALLOWED_FIELDS = {
    "reflection_text",
    "goal_text",
    "action_text",
    "update_result_text",
    "current_step_title",
    "last_phase_result_text",
    "timer_reset_seq",
}

# Статус выполнения `main_funk_start_on_front()` (см. `MAIN.py`).
# UI (`templates/main_page_2.html`) опрашивает `/api/front_main_status`, чтобы понять,
# когда фоновая задача завершилась и можно перейти на main_page_3.
FRONT_MAIN_STATE = {
    "running": False,
    "done": False,
    "error": None,
}
FRONT_MAIN_STATE_LOCK = threading.Lock()

# Последний скриншот браузера.
# Два режима:
# - Playwright в ЭТОМ же процессе: можно снимать через `shared_page` (`get_cached_screenshot_png`)
# - Playwright в ДРУГОМ процессе (часто `MAIN.py`): тогда процесс-генератор "пушит" кадры в Flask
#   через `/api/browser_screenshot_push`, а UI читает через `/api/browser_screenshot`.
PUSHED_SCREENSHOT_STATE = {
    "png": None,   # bytes | None
    "ts": None,    # float | None (time.time())
}
PUSHED_SCREENSHOT_LOCK = threading.Lock()

# --- Task registry (до 10 параллельных заданий) ---
install_print_router()
try:
    deleted_old = _cleanup_result_tasks_older_than(days=7)
    if deleted_old > 0:
        print(f"RESULT_TASKS cleanup: deleted {deleted_old} folder(s) older than 7 days")
except Exception:
    # best-effort: не блокируем старт фронта из-за очистки
    pass

def _get_max_workers():
    try:
        return int(os.environ.get("APSP_MAX_WORKERS", "10"))
    except:
        return 10

TASKS = TaskRegistry(result_tasks_dir=RESULT_TASKS_DIR, max_workers=_get_max_workers(), headless=True)
TASKS.warmup()
atexit.register(TASKS.shutdown)

 # TASK_SCREENSHOTS_STATE / TASK_SCREENSHOTS_LOCK are imported from task_runtime.screenshot_store


def _run_task(browser, info: TaskInfo):
    """
    Запускает генерацию в контексте выделенного браузера/таба.
    """
    # Берём стартовый ts из meta (если есть) или из info.started_at (datetime).
    started_at_ts = None
    try:
        meta_path = info.task_dir / "meta.json"
        if meta_path.is_file():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            started_at_ts = meta.get("started_at_ts")
    except Exception:
        started_at_ts = None
    if started_at_ts is None:
        try:
            started_at_ts = info.started_at.timestamp() if info.started_at else None
        except Exception:
            started_at_ts = None

    set_current_task(info.uid, info.task_dir, started_at_ts=started_at_ts)
    info.task_dir.mkdir(parents=True, exist_ok=True)

    # Важно для повторных попыток: не затираем логи на следующем запуске по тому же uid.
    attempt_n = 1
    try:
        meta_path = info.task_dir / "meta.json"
        if meta_path.is_file():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            attempt_n = int((meta or {}).get("attempts") or 1)
    except Exception:
        attempt_n = 1

    out_mode = "w" if attempt_n <= 1 else "a"
    out_file = open(info.task_dir / "output.log", out_mode, encoding="utf-8")
    if attempt_n > 1:
        try:
            out_file.write(f"\n\n--- RETRY attempt {attempt_n}/{TASKS.max_attempts} ---\n")
            out_file.flush()
        except Exception:
            pass
    register_thread_io(out_file, out_file)

    # Create/truncate per-task logs at start (best-effort).
    try:
        from useful_log import init_useful_log
        init_useful_log(truncate=(attempt_n <= 1))
    except Exception:
        pass
    try:
        from reasoning_agent.chat_terminal import init_chat_channel
        init_chat_channel(truncate=(attempt_n <= 1))
    except Exception:
        pass

    context = browser.new_context()
    page = context.new_page()
    set_shared_page(page)
    # Важно:
    # `playwright_tool/screenshot_pusher.py` делает ОС-скриншот (ImageGrab) и поэтому
    # на `main_page_2` может отображаться "рабочий стол" вместо страницы Playwright.
    # Кроме того, при внешнем домене (например, ngrok) это может сильно грузить сеть.
    #
    # По умолчанию desktop-screenshot pusher ВЫКЛЮЧЕН. Включить можно только явно:
    #   APSP_ENABLE_DESKTOP_SCREENSHOT_PUSHER=1
    # Интервал (сек): APSP_DESKTOP_SCREENSHOT_PUSHER_INTERVAL_S (по умолчанию 5.0)
    _enable_desktop_pusher = str(os.environ.get("APSP_ENABLE_DESKTOP_SCREENSHOT_PUSHER", "")).strip() == "1"
    _desktop_pusher_interval_s = 5.0
    try:
        if os.environ.get("APSP_DESKTOP_SCREENSHOT_PUSHER_INTERVAL_S") is not None:
            _desktop_pusher_interval_s = float(os.environ.get("APSP_DESKTOP_SCREENSHOT_PUSHER_INTERVAL_S") or 5.0)
    except Exception:
        _desktop_pusher_interval_s = 5.0
    if _enable_desktop_pusher:
        try:
            from playwright_tool.screenshot_pusher import start_screenshot_pusher  # noqa: WPS433
            start_screenshot_pusher(interval_s=_desktop_pusher_interval_s, uid=info.uid)
        except Exception:
            pass
    try:
        main_processer(
            info.url,
            uid=info.uid,
            task_dir=info.task_dir,
            page=page,
            started_at_ts=started_at_ts,
        )
    finally:
        if _enable_desktop_pusher:
            try:
                from playwright_tool.screenshot_pusher import stop_screenshot_pusher  # noqa: WPS433
                stop_screenshot_pusher(uid=info.uid)
            except Exception:
                pass
        clear_shared_page()
        try:
            context.close()
        except Exception:
            pass
        unregister_thread_io()
        try:
            out_file.close()
        except Exception:
            pass
        clear_current_task()

def sanitize_text(value):
    """
    Небольшая обработка текстовых полей перед сохранением:
    1) Убрать пробелы/табы/переносы строк с концов
    2) Экранировать двойные кавычки: " -> \"

    Используется только для полей форм (URL/regions).
    Для отображения в UI используем отдельную функцию `normalize_display_text()`,
    чтобы не "засорять" экран лишними обратными слешами.
    """
    if value is None:
        return ''
    if not isinstance(value, str):
        return value
    value = value.strip()
    return value.replace('"', r'\"')


def normalize_display_text(value, *, max_len: int = 200_000) -> str:
    """
    Нормализация текста для отображения на фронте.
    - без экранирования кавычек (иначе на экране будут лишние '\\')
    - ограничение длины, чтобы случайно не положить сервер мегабайтами
    """
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    if len(value) > max_len:
        return value[:max_len]
    return value


def load_new_page_2_state() -> dict:
    default_state = {k: "" for k in NEW_PAGE_2_ALLOWED_FIELDS}
    try:
        if not NEW_PAGE_2_STATE_FILE_PATH.is_file():
            return default_state
        with open(NEW_PAGE_2_STATE_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return default_state
        # подмешиваем только разрешённые ключи
        for k in NEW_PAGE_2_ALLOWED_FIELDS:
            if k in data:
                default_state[k] = normalize_display_text(data.get(k))
        return default_state
    except Exception:
        return default_state


def save_new_page_2_state(state: dict) -> None:
    RESULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_state = {k: normalize_display_text(state.get(k, "")) for k in NEW_PAGE_2_ALLOWED_FIELDS}
    with open(NEW_PAGE_2_STATE_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(safe_state, f, ensure_ascii=False, indent=2, sort_keys=True)


def set_front_main_state(running=False, done=False, error=None):
    """Атомарно обновляет состояние выполнения main_funk_start_on_front()."""
    with FRONT_MAIN_STATE_LOCK:
        FRONT_MAIN_STATE["running"] = running
        FRONT_MAIN_STATE["done"] = done
        FRONT_MAIN_STATE["error"] = error


def get_front_main_state():
    """Возвращает копию текущего состояния выполнения main_funk_start_on_front()."""
    with FRONT_MAIN_STATE_LOCK:
        return dict(FRONT_MAIN_STATE)

def _normalize_url_for_check(url: str) -> str:
    """
    Нормализует URL так же, как это делает html_toolkit.normalize_url.
    Используется для проверки наличия готовых результатов.
    """
    url = url.strip()
    
    # Если схема не указана — добавляем https
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    
    # Убираем www.
    if domain.startswith("www."):
        domain = domain[4:]
    
    return f"https://{domain}"

def _is_valid_site_url_input(value: str) -> bool:
    """
    Строгая валидация ввода для main_page_1:
    - разрешаем http/https URL
    - разрешаем домен без схемы (пример: makitaclub.ru)
    Ограничение: требуем точку в hostname (чтобы "777" не считался доменом).
    """
    try:
        v = (value or "").strip()
        if not v:
            return False
        if any(ch.isspace() for ch in v):
            return False

        # Если схемы нет — трактуем как домен и добавляем https://
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", v):
            v = "https://" + v

        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https"):
            return False

        hostname = (parsed.hostname or "").strip()
        if not hostname:
            return False

        # Минимальный барьер от мусора: домен должен содержать точку (example.com)
        if "." not in hostname:
            return False

        return True
    except Exception:
        return False


def _find_existing_completed_task(normalized_url: str):
    """
    Ищет существующую задачу с данным URL и статусом COMPLETED.
    Возвращает UID последней (по времени) такой задачи, либо None.
    """
    if not RESULT_TASKS_DIR.exists() or not RESULT_TASKS_DIR.is_dir():
        return None
    
    matching_tasks = []
    
    for child in RESULT_TASKS_DIR.iterdir():
        if not child.is_dir():
            continue
        
        meta_path = child / "meta.json"
        if not meta_path.is_file():
            continue
        
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta_url = meta.get("url", "")
            meta_status = meta.get("status", "")
            
            # Нормализуем URL из мета-файла
            try:
                normalized_meta_url = _normalize_url_for_check(meta_url)
            except Exception:
                continue
            
            # Если URL совпадает и статус COMPLETED
            if normalized_meta_url == normalized_url and meta_status == "COMPLETED":
                created_at_ts = meta.get("created_at_ts", 0)
                matching_tasks.append({
                    "uid": child.name,
                    "created_at_ts": created_at_ts
                })
        except Exception:
            continue
    
    # Если нашли совпадения — возвращаем последний по времени
    if matching_tasks:
        matching_tasks.sort(key=lambda x: x["created_at_ts"], reverse=True)
        return matching_tasks[0]["uid"]
    
    return None


@app.route('/')
def index():
    """Главная страница"""
    return redirect(url_for('main_page_1'))


@app.route('/start_page_1', methods=['GET'])
@app.route('/start_page_1/', methods=['GET'])
def start_page_1():
    """Стартовая страница: выбор раздела."""
    return render_template('start_page_1.html')


@app.route('/before_starting_autogen_info', methods=['GET'])
@app.route('/before_starting_autogen_info/', methods=['GET'])
def before_starting_autogen_info():
    """Инфо-страница перед входом в автогенератор."""
    return render_template('before_starting_autogen_info.html')

@app.route('/login_page', methods=['GET'])
def login_page():
    """Страница входа в аккаунт"""
    return render_template('login_page.html')

@app.route('/main_page_1', methods=['GET', 'POST'])
def main_page_1():
    """
    Простая отдельная форма (без шагов и без зависимостей от многошагового флоу).
    Теперь поддерживает ввод UID для проверки существующих задач.
    """
    site_url = ''
    uid_not_found = request.args.get('uid_not_found', 'false') == 'true'
    invalid_format = request.args.get('invalid_format', 'false') == 'true'
    
    if request.method == 'POST':
        site_url = sanitize_text(request.form.get('site_url', ''))

        # Если пусто — ничего не делаем (остаёмся на странице).
        if site_url.strip():
            # Проверяем, не является ли введённое значение UID (12 hex символов)
            uid_pattern = re.compile(r'^[a-f0-9]{12}$', re.IGNORECASE)
            if uid_pattern.match(site_url.strip()):
                # Это UID — проверяем существование задачи
                uid = site_url.strip().lower()
                
                if TASKS.exists(uid):
                    # Задача найдена — проверяем её статус
                    task_info = TASKS.get(uid)
                    if task_info and task_info.status:
                        status = task_info.status.upper()
                        if status == 'WORK' or status == 'RUNNING':
                            # Задача в работе — открываем страницу 2
                            return redirect(url_for('main_page_2_uid', uid=uid))
                        elif status == 'COMPLETED' or status == 'FAILED':
                            # Задача завершена — открываем страницу 3
                            return redirect(url_for('main_page_3_uid', uid=uid))
                        else:
                            # Неизвестный статус — открываем страницу 2
                            return redirect(url_for('main_page_2_uid', uid=uid))
                    else:
                        # Не удалось получить информацию — всё равно пытаемся открыть
                        return redirect(url_for('main_page_2_uid', uid=uid))
                else:
                    # UID не найден — редиректим на GET с параметром ошибки
                    return redirect(url_for('main_page_1', uid_not_found='true'))
            else:
                # Строгая валидация URL/домена: если не похоже на ссылку — НЕ создаём задачу
                if not _is_valid_site_url_input(site_url):
                    invalid_format = True
                else:
                    # Это обычный URL — проверяем наличие готовых результатов
                    try:
                        normalized_url = _normalize_url_for_check(site_url)
                        existing_uid = _find_existing_completed_task(normalized_url)
                        
                        if existing_uid:
                            # Есть готовый результат — показываем страницу выбора
                            return redirect(url_for('parser_exists', url=site_url, existing_uid=existing_uid))
                    except Exception as e:
                        # Если проверка не удалась — продолжаем как обычно
                        print(f"Ошибка при проверке существующих результатов: {e}")
                    
                    # Нет готовых результатов или ошибка проверки — создаём новую задачу
                    tg_id = None
                    try:
                        tg_id = get_user_telegram_id_from_cookie()
                    except Exception:
                        tg_id = None
                    user_account = None
                    try:
                        user_account = get_user_account_from_cookie()
                    except Exception:
                        user_account = None

                    task = TASKS.create(site_url, user_telegram_id=tg_id, user_account=user_account)
                    TASKS.start(task.uid, _run_task)

                    return redirect(url_for('main_page_2_uid', uid=task.uid))

    # Создаём response
    response = make_response(render_template('main_page_1.html', site_url=site_url, uid_not_found=uid_not_found, invalid_format=invalid_format))

    # # Устанавливаем тестовый аккаунт в куку (для демонстрации)
    # # В продакшене это должно устанавливаться после авторизации пользователя
    # set_user_account_cookie(response, '@GogikOrtey')
    
    return response


@app.route('/parser_exists', methods=['GET'])
def parser_exists():
    """
    Страница, показывающая что парсер для данного URL уже существует.
    Предлагает открыть существующий результат или запустить генерацию заново.
    """
    site_url = request.args.get('url', '')
    existing_uid = request.args.get('existing_uid', '')
    
    if not site_url or not existing_uid:
        # Если параметры не указаны — редирект на главную
        return redirect(url_for('index'))
    
    # Извлекаем красивое отображение домена (domo-terra.ru вместо https://domo-terra.ru/)
    site_domain = _extract_site_domain(site_url)
    
    return render_template('parser_exists.html', 
                         site_url=site_url, 
                         site_domain=site_domain,
                         existing_uid=existing_uid)


@app.route('/parser_exists/new_generation', methods=['POST'])
def parser_exists_new_generation():
    """
    Обработчик для запуска новой генерации с страницы parser_exists.
    """
    site_url = sanitize_text(request.form.get('site_url', ''))
    
    if not site_url.strip():
        return redirect(url_for('index'))
    
    # Создаём новую задачу без проверки на существующие результаты
    tg_id = None
    try:
        tg_id = get_user_telegram_id_from_cookie()
    except Exception:
        tg_id = None
    user_account = None
    try:
        user_account = get_user_account_from_cookie()
    except Exception:
        user_account = None

    task = TASKS.create(site_url, user_telegram_id=tg_id, user_account=user_account)
    TASKS.start(task.uid, _run_task)

    return redirect(url_for('main_page_2_uid', uid=task.uid))


@app.route('/all_tasks')
def all_tasks():
    """
    Страница обзора всех задач из папки RESULT_TASKS.
    """
    tasks_data = _load_all_tasks_data()
    
    # Разделяем на активные (WORK) и завершенные (COMPLETED/FAILED/PAUSED)
    active_tasks = [t for t in tasks_data if t['status'] == 'WORK']
    completed_tasks = [t for t in tasks_data if t['status'] != 'WORK']
    
    # Ограничиваем до 70 задач
    total_tasks = len(active_tasks) + len(completed_tasks)
    max_tasks = 70
    
    # Берем первые задачи с учетом лимита
    if len(active_tasks) >= max_tasks:
        active_tasks = active_tasks[:max_tasks]
        completed_tasks = []
    else:
        remaining = max_tasks - len(active_tasks)
        completed_tasks = completed_tasks[:remaining]
        completed_tasks = completed_tasks[:remaining]
    
    return render_template('all_tasks.html',
                         active_tasks=active_tasks,
                         completed_tasks=completed_tasks,
                         total_tasks=total_tasks)


def _load_all_tasks_data():
    """
    Читает все задачи из RESULT_TASKS и возвращает список с данными для таблицы.
    """
    if not RESULT_TASKS_DIR.exists() or not RESULT_TASKS_DIR.is_dir():
        return []
    
    tasks = []
    
    for child in RESULT_TASKS_DIR.iterdir():
        if not child.is_dir():
            continue
        
        meta_path = child / "meta.json"
        if not meta_path.is_file():
            continue
        
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            uid = child.name
            url = meta.get("url", "")
            status = meta.get("status", "WORK")
            created_at_ts = meta.get("created_at_ts", 0)
            started_at_ts = meta.get("started_at_ts", 0)
            finished_at_ts = meta.get("finished_at_ts")
            
            # Определяем реальный статус задачи
            # Если задача в статусе WORK, но была запущена до старта текущего App - это PAUSED
            last_started_at_ts = meta.get("last_started_at_ts", 0)
            is_paused = False
            if status == "WORK" and last_started_at_ts > 0 and last_started_at_ts < APP_START_TIME:
                is_paused = True
            
            # Извлекаем домен
            domain = _extract_site_domain(url)
            
            # Время начала генерации (HH:MM или DD.MM.YYYY HH:MM для не сегодняшних)
            start_time = ""
            if started_at_ts:
                try:
                    dt = datetime.fromtimestamp(started_at_ts)
                    today = datetime.now().date()
                    task_date = dt.date()
                    
                    if task_date == today:
                        # Сегодняшняя задача - только время
                        start_time = dt.strftime("%H:%M")
                    else:
                        # Задача из прошлого - дата и время
                        start_time = dt.strftime("%d.%m.%Y %H:%M")
                except Exception:
                    pass
            
            # Время в процессе генерации (в минутах)
            duration = ""
            if is_paused:
                # Для приостановленных задач - прочерк
                duration = "—"
            elif started_at_ts:
                end_ts = finished_at_ts if finished_at_ts else time.time()
                duration_seconds = end_ts - started_at_ts
                duration_minutes = int(duration_seconds / 60)
                duration = f"{duration_minutes} мин."
            
            # Текущий шаг (из new_page_2_state.json)
            current_step = ""
            state_path = child / "new_page_2_state.json"
            if state_path.is_file():
                try:
                    state = json.loads(state_path.read_text(encoding="utf-8"))
                    current_step_title = state.get("current_step_title", "")
                    if current_step_title:
                        # Извлекаем "Шаг 3/10" из "Шаг 3/10: Описание"
                        match = re.match(r'(Шаг \d+/\d+)', current_step_title)
                        if match:
                            current_step = match.group(1)
                except Exception:
                    pass
            
            # Статус с эмодзи
            status_display = ""
            error_message = ""
            display_status = "PAUSED" if is_paused else status
            
            if display_status == "COMPLETED":
                status_display = "✅ COMPLETED"
            elif display_status == "WORK":
                status_display = "📘 IN WORK"
            elif display_status == "PAUSED":
                status_display = "⬛ PAUSED"
            elif display_status == "FAILED":
                status_display = "🟠 FAILED"
                # Загружаем сообщение об ошибке из result_code.ts для tooltip
                result_code_path = child / "result_code.ts"
                if result_code_path.is_file():
                    try:
                        result_code = result_code_path.read_text(encoding="utf-8")
                        lines = result_code.strip().split('\n')
                        
                        # Ищем последнюю строку с исключением (ValueError:, Exception:, и т.д.)
                        exception_index = -1
                        for i in range(len(lines) - 1, -1, -1):
                            line = lines[i].strip()
                            # Ищем строки с типичными исключениями Python
                            if line and any(exc in line for exc in ['Error:', 'Exception:', 'ValueError:', 'TypeError:', 'KeyError:', 'AttributeError:']):
                                exception_index = i
                                break
                        
                        if exception_index >= 0:
                            # Берём строку с исключением и всё что после неё
                            error_lines = []
                            for i in range(exception_index, len(lines)):
                                if lines[i].strip():
                                    error_lines.append(lines[i].strip())
                            error_message = '\n'.join(error_lines) if error_lines else ''
                        else:
                            # Если не нашли traceback, берём последнюю непустую строку
                            for line in reversed(lines):
                                if line.strip():
                                    error_message = line.strip()
                                    break
                    except Exception:
                        pass
            else:
                status_display = display_status
            
            tasks.append({
                'uid': uid,
                'domain': domain,
                'start_time': start_time,
                'duration': duration,
                'current_step': current_step,
                'status': display_status,  # Используем display_status вместо status
                'status_display': status_display,
                'error_message': error_message,
                'created_at_ts': created_at_ts
            })
        except Exception:
            continue
    
    # Сортируем по времени создания (новые сначала)
    tasks.sort(key=lambda x: x['created_at_ts'], reverse=True)
    
    return tasks


def _render_invalid_uid_page(uid_state: str):
    uid_phrase = "не указан" if uid_state == "missing" else "указан неверно"
    return render_template('invalid_uid.html', uid_phrase=uid_phrase)


def _extract_site_domain(raw_url: str) -> str:
    """
    Превращает URL/хост в домен для отображения в UI.
    Примеры:
      - https://domo-terra.ru/ -> domo-terra.ru
      - domo-terra.ru/catalog -> domo-terra.ru
    """
    if not raw_url:
        return ""
    u = str(raw_url).strip()
    if not u:
        return ""

    # urlparse плохо работает без схемы — добавим.
    if "://" not in u:
        u = "http://" + u

    try:
        p = urlparse(u)
    except Exception:
        return ""

    host = (p.netloc or "").strip()
    if not host:
        # Иногда urlparse складывает всё в path (особенно для странных строк)
        host = (p.path or "").split("/")[0].strip()

    # user:pass@host:port -> host
    if "@" in host:
        host = host.split("@", 1)[1]
    if ":" in host:
        host = host.split(":", 1)[0]

    if host.startswith("www."):
        host = host[4:]

    return host


@app.route('/main_page_2', methods=['GET'])
@app.route('/main_page_2/', methods=['GET'])
def main_page_2_no_uid():
    return _render_invalid_uid_page("missing")


@app.route('/main_page_2/<uid>/', methods=['GET'])
def main_page_2_uid(uid):
    """Дашборд конкретной задачи."""
    info = _get_task_info(uid)
    if info is None:
        return _render_invalid_uid_page("invalid")

    # Заголовок страницы: берём URL из meta.json текущей задачи (best-effort).
    meta_url = ""
    try:
        meta_path = info.task_dir / "meta.json"
        if meta_path.is_file():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta_url = (meta or {}).get("url") or ""
    except Exception:
        meta_url = ""

    site_domain = _extract_site_domain(meta_url)
    page_heading = f"Генерируем парсер для сайта {site_domain}" if site_domain else "Генерируем парсер"

    return render_template('main_page_2.html', uid=uid, page_heading=page_heading, site_domain=site_domain)

@app.route('/main_page_3', methods=['GET'])
@app.route('/main_page_3/', methods=['GET'])
def main_page_3_no_uid():
    return _render_invalid_uid_page("missing")


@app.route('/main_page_3/<uid>/', methods=['GET'])
def main_page_3_uid(uid):
    """
    Страница результатов конкретной задачи.
    """
    if _get_task_info(uid) is None:
        return _render_invalid_uid_page("invalid")
    info = TASKS.get(uid)
    if info and info.status in {"running", "created"}:
        return redirect(url_for('main_page_2_uid', uid=uid))

    meta = {}
    try:
        meta_path = info.task_dir / "meta.json"
        if meta_path.is_file():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))

        # Format date for display: DD.MM.YYYY HH:MM
        ts = meta.get("started_at_ts")
        if ts:
            try:
                dt = datetime.fromtimestamp(float(ts))
                meta["started_at_display"] = dt.strftime("%d.%m.%Y %H:%M")
            except Exception:
                meta["started_at_display"] = "—"
        else:
            # Fallback to parsing human string if ts missing
            human = meta.get("started_at_human", "")
            if human:
                try:
                    # Expecting "YYYY-MM-DD HH:MM:SS"
                    dt = datetime.strptime(human, "%Y-%m-%d %H:%M:%S")
                    meta["started_at_display"] = dt.strftime("%d.%m.%Y %H:%M")
                except Exception:
                    meta["started_at_display"] = human
            else:
                meta["started_at_display"] = "—"

    except Exception:
        pass

    return render_template('main_page_3.html', uid=uid, meta=meta)


# --- Service / debug endpoints ---
@app.route('/check_task_status/<uid>/', methods=['GET'])
def check_task_status(uid):
    """
    Служебный эндпоинт: отдаёт meta.json по UID.

    Использовать для быстрой проверки статуса задачи после рестарта сервера.
    """
    info = _get_task_info(uid)
    if info is None:
        return FlaskResponse('{"ok":false,"error":"task_not_found"}', mimetype='application/json; charset=utf-8', status=404)

    meta_path = info.task_dir / "meta.json"
    if not meta_path.is_file():
        return FlaskResponse('{"ok":false,"error":"meta_not_found"}', mimetype='application/json; charset=utf-8', status=404)

    try:
        payload = meta_path.read_text(encoding="utf-8")
    except Exception:
        return FlaskResponse('{"ok":false,"error":"meta_read_failed"}', mimetype='application/json; charset=utf-8', status=500)

    resp = FlaskResponse(payload, mimetype='application/json; charset=utf-8')
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    return resp

@app.route('/example2', methods=['GET', 'POST'])
def example2():
    """
    Простая отдельная форма на /example2 (без шагов и без зависимостей от многошагового флоу).
    """
    site_url = ''
    regions = ''
    if request.method == 'POST':
        site_url = sanitize_text(request.form.get('site_url', ''))
        regions = sanitize_text(request.form.get('regions', ''))
        # Редирект на GET для избежания предупреждения о повторной отправке формы
        return redirect(url_for('example2', site_url=site_url, regions=regions))
    
    # GET: берём параметры из query string
    site_url = request.args.get('site_url', '')
    regions = request.args.get('regions', '')
    
    return render_template('example2.html', site_url=site_url, regions=regions)

@app.route('/content/<path:filename>')
def content(filename):
    """Обслуживание статических файлов из папки content"""
    return send_from_directory(str(FRONT_DIR / 'content'), filename)

# Многие браузеры (и некоторые боты) по умолчанию запрашивают /favicon.ico,
# даже если в HTML указан <link rel="icon">. Чтобы на всех страницах стабильно
# использовалась ваша фавиконка, отдаём favicon_2.png по этому пути.
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(str(FRONT_DIR / 'content'), 'favicon_2.png')


def _get_task_info(uid: str) -> TaskInfo | None:
    # `TaskRegistry.get()` умеет best-effort восстанавливать задачу по папке RESULT_TASKS/<uid>,
    # поэтому после рестарта Flask можно открывать старые UID и читать их артефакты.
    return TASKS.get(uid)


def _read_text_file(path: Path, tail_bytes: int | None = None) -> FlaskResponse:
    if not path.is_file():
        resp = FlaskResponse('', mimetype='text/plain; charset=utf-8')
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        return resp

    if tail_bytes is None:
        content = path.read_text(encoding="utf-8")
        resp = FlaskResponse(content, mimetype='text/plain; charset=utf-8')
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        return resp

    if tail_bytes < 0:
        tail_bytes = 0
    if tail_bytes > 10_000_000:
        tail_bytes = 10_000_000

    truncated = False
    with open(path, "rb") as f:
        f.seek(0, 2)
        size = f.tell()
        if size and tail_bytes:
            start = max(0, size - tail_bytes)
            truncated = start > 0
            f.seek(start)
            chunk = f.read()
            if truncated:
                nl = chunk.find(b"\n")
                if nl != -1:
                    chunk = chunk[nl + 1:]
        else:
            chunk = b""
    content = chunk.decode("utf-8", errors="replace")
    resp = FlaskResponse(content, mimetype='text/plain; charset=utf-8')
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    try:
        resp.headers["X-Log-Tail-Bytes"] = str(tail_bytes)
        resp.headers["X-Log-Truncated"] = "1" if truncated else "0"
    except Exception:
        pass
    return resp


@app.route('/api/task/<uid>/status')
def api_task_status(uid):
    info = _get_task_info(uid)
    if info is None:
        return FlaskResponse('{"ok":false,"error":"not_found"}', mimetype='application/json; charset=utf-8', status=404)
    return FlaskResponse(
        json.dumps(
            {
                "uid": info.uid,
                "url": info.url,
                "status": info.status,
                "error": info.error,
            },
            ensure_ascii=False,
        ),
        mimetype='application/json; charset=utf-8',
    )


@app.route('/api/tasks/active_count')
def api_tasks_active_count():
    active = TASKS.get_active_count()
    max_w = TASKS.max_workers
    return FlaskResponse(
        json.dumps({"ok": True, "active": active, "max": max_w}, ensure_ascii=False),
        mimetype='application/json; charset=utf-8'
    )


@app.route('/api/account/logout', methods=['POST'])
def api_account_logout():
    """
    API эндпоинт для выхода из аккаунта.
    Удаляет куку user_account.
    """
    response = FlaskResponse(
        json.dumps({"ok": True}, ensure_ascii=False),
        mimetype='application/json; charset=utf-8'
    )
    clear_user_account_cookie(response)
    clear_user_telegram_id_cookie(response)
    return response


@app.route('/api/telegram/auth/start', methods=['POST'])
def api_telegram_auth_start():
    """
    Старт Telegram-авторизации:
    - генерируем временный token
    - отдаём deep-link на бота: https://t.me/<bot>?start=<token>
    """
    if not TELEGRAM_BOT_USERNAME:
        return FlaskResponse(
            json.dumps({"ok": False, "error": "bot_username_not_configured"}, ensure_ascii=False),
            mimetype='application/json; charset=utf-8',
            status=500,
        )

    token = telegram_connect.create_auth_token()
    telegram_connect.create_pending_auth(TELEGRAM_AUTH_DIR, token)
    telegram_url = f"https://t.me/{TELEGRAM_BOT_USERNAME}?start={token}"

    return FlaskResponse(
        json.dumps({"ok": True, "token": token, "telegram_url": telegram_url}, ensure_ascii=False),
        mimetype='application/json; charset=utf-8',
    )


@app.route('/api/telegram/auth/status', methods=['GET'])
def api_telegram_auth_status():
    token = (request.args.get("token") or "").strip()
    payload = telegram_connect.get_auth_status(TELEGRAM_AUTH_DIR, token)
    return FlaskResponse(json.dumps(payload, ensure_ascii=False), mimetype='application/json; charset=utf-8')


@app.route('/api/telegram/auth/finish', methods=['POST'])
def api_telegram_auth_finish():
    payload = request.get_json(silent=True) or {}
    token = (payload.get("token") or "").strip()

    status = telegram_connect.get_auth_status(TELEGRAM_AUTH_DIR, token)
    if not status.get("ok") or status.get("status") != "authorized":
        return FlaskResponse(
            json.dumps({"ok": False, "error": "not_authorized", "status": status.get("status")}, ensure_ascii=False),
            mimetype='application/json; charset=utf-8',
            status=400,
        )

    user = status.get("user") or {}
    tg_id = user.get("id")
    tg_username = user.get("username")
    try:
        tg_id_int = int(tg_id)
    except Exception:
        return FlaskResponse(
            json.dumps({"ok": False, "error": "bad_user_id"}, ensure_ascii=False),
            mimetype='application/json; charset=utf-8',
            status=500,
        )

    # UI ожидает "username" строкой в user_account cookie (как сейчас в main_page_1.html)
    if isinstance(tg_username, str) and tg_username.strip():
        display_username = "@" + tg_username.strip().lstrip("@")
    else:
        display_username = f"tg_{tg_id_int}"

    resp = FlaskResponse(
        json.dumps({"ok": True, "username": display_username, "tg_id": tg_id_int}, ensure_ascii=False),
        mimetype='application/json; charset=utf-8',
    )
    set_user_account_cookie(resp, display_username)
    set_user_telegram_id_cookie(resp, tg_id_int)

    # Одноразовый токен больше не нужен
    telegram_connect.consume_auth_token(TELEGRAM_AUTH_DIR, token)
    return resp


@app.route('/api/telegram/webhook/<secret>', methods=['POST'])
def api_telegram_webhook(secret: str):
    """
    Webhook для Telegram Bot API.

    Секрет в URL нужен как простая защита от "случайных" запросов.
    """
    if not TELEGRAM_WEBHOOK_SECRET:
        return FlaskResponse(
            '{"ok":false,"error":"webhook_not_configured"}',
            mimetype='application/json; charset=utf-8',
            status=404,
        )
    if secret != TELEGRAM_WEBHOOK_SECRET:
        return FlaskResponse('{"ok":false,"error":"forbidden"}', mimetype='application/json; charset=utf-8', status=403)

    update = request.get_json(silent=True) or {}
    try:
        result = telegram_connect.handle_telegram_update(
            update,
            auth_dir=TELEGRAM_AUTH_DIR,
            users_dir=TELEGRAM_USERS_DIR,
            bot_token=TELEGRAM_BOT_TOKEN,
            base_url=APSP_BASE_URL,
        )
    except Exception:
        # Telegram ожидает 200; ошибки лучше не эскалировать
        result = {"ok": True, "handled": False, "error": "exception"}

    return FlaskResponse(json.dumps(result, ensure_ascii=False), mimetype='application/json; charset=utf-8')


@app.route('/api/task/<uid>/stop', methods=['POST'])
def api_task_stop(uid):
    info = _get_task_info(uid)
    if info is None:
        return FlaskResponse('{"ok":false,"error":"not_found"}', mimetype='application/json; charset=utf-8', status=404)

    try:
        request_stop(uid, reason=USER_STOP_MESSAGE)
    except Exception:
        return FlaskResponse('{"ok":false,"error":"stop_failed"}', mimetype='application/json; charset=utf-8', status=500)

    # best-effort лог в output.log, чтобы видно было в UI.
    try:
        log_path = info.task_dir / "output.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] stop requested by user\n")
    except Exception:
        pass

    return FlaskResponse('{"ok":true}', mimetype='application/json; charset=utf-8')


def _task_state_path(info: TaskInfo) -> Path:
    return info.task_dir / "new_page_2_state.json"


def _load_task_state(info: TaskInfo) -> dict:
    default_state = {k: "" for k in NEW_PAGE_2_ALLOWED_FIELDS}
    path = _task_state_path(info)
    try:
        if not path.is_file():
            return default_state
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return default_state
        for k in NEW_PAGE_2_ALLOWED_FIELDS:
            if k in data:
                default_state[k] = normalize_display_text(data.get(k))
        return default_state
    except Exception:
        return default_state


def _save_task_state(info: TaskInfo, state: dict) -> None:
    path = _task_state_path(info)
    safe_state = {k: normalize_display_text(state.get(k, "")) for k in NEW_PAGE_2_ALLOWED_FIELDS}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(safe_state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


@app.route('/api/task/<uid>/new_page_2_state', methods=['GET'])
def api_task_new_page_2_state_get(uid):
    info = _get_task_info(uid)
    if info is None:
        return FlaskResponse('{"ok":false,"error":"not_found"}', mimetype='application/json; charset=utf-8', status=404)
    state = _load_task_state(info)
    return FlaskResponse(json.dumps(state, ensure_ascii=False), mimetype='application/json; charset=utf-8')


@app.route('/api/task/<uid>/new_page_2_state', methods=['POST'])
def api_task_new_page_2_state_post(uid):
    info = _get_task_info(uid)
    if info is None:
        return FlaskResponse('{"ok":false,"error":"not_found"}', mimetype='application/json; charset=utf-8', status=404)
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return FlaskResponse('{"ok":false,"error":"invalid_json"}', mimetype='application/json; charset=utf-8', status=400)

    state = _load_task_state(info)
    if "field" in payload:
        field = payload.get("field")
        value = payload.get("value", "")
        if field not in NEW_PAGE_2_ALLOWED_FIELDS:
            return FlaskResponse('{"ok":false,"error":"unknown_field"}', mimetype='application/json; charset=utf-8', status=400)
        state[field] = normalize_display_text(value)
    else:
        updated_any = False
        for k in NEW_PAGE_2_ALLOWED_FIELDS:
            if k in payload:
                state[k] = normalize_display_text(payload.get(k))
                updated_any = True
        if not updated_any:
            return FlaskResponse('{"ok":false,"error":"no_allowed_fields"}', mimetype='application/json; charset=utf-8', status=400)

    try:
        _save_task_state(info, state)
    except Exception:
        return FlaskResponse('{"ok":false,"error":"save_failed"}', mimetype='application/json; charset=utf-8', status=500)
    return FlaskResponse('{"ok":true}', mimetype='application/json; charset=utf-8')


@app.route('/api/task/<uid>/browser_screenshot', methods=['GET'])
def api_task_browser_screenshot(uid):
    if not TASKS.exists(uid):
        return FlaskResponse("task_not_found", mimetype='text/plain; charset=utf-8', status=404)
    with TASK_SCREENSHOTS_LOCK:
        entry = TASK_SCREENSHOTS_STATE.get(uid) or {}
        png = entry.get("png")
        ts = entry.get("ts")
    if png is None:
        return FlaskResponse("screenshot_not_available", mimetype='text/plain; charset=utf-8', status=404)
    resp = FlaskResponse(png, mimetype="image/png")
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    try:
        resp.headers["X-Screenshot-Ts"] = str(ts or "")
    except Exception:
        pass
    return resp


@app.route('/api/task/<uid>/browser_screenshot_push', methods=['POST'])
def api_task_browser_screenshot_push(uid):
    if not TASKS.exists(uid):
        return FlaskResponse('{"ok":false,"error":"task_not_found"}', mimetype='application/json; charset=utf-8', status=404)
    try:
        raw = request.get_data(cache=False) or b""
    except Exception:
        raw = b""
    if not raw:
        return FlaskResponse('{"ok":false,"error":"empty_body"}', mimetype='application/json; charset=utf-8', status=400)
    if not (len(raw) >= 8 and raw[:8] == b"\x89PNG\r\n\x1a\n"):
        return FlaskResponse('{"ok":false,"error":"not_png"}', mimetype='application/json; charset=utf-8', status=400)
    if len(raw) > 8_000_000:
        return FlaskResponse('{"ok":false,"error":"too_large"}', mimetype='application/json; charset=utf-8', status=413)
    with TASK_SCREENSHOTS_LOCK:
        TASK_SCREENSHOTS_STATE[uid] = {"png": raw, "ts": datetime.now().timestamp()}
    return FlaskResponse('{"ok":true}', mimetype='application/json; charset=utf-8')


@app.route('/api/task/<uid>/logs/output')
def api_task_output_log(uid):
    info = _get_task_info(uid)
    if info is None:
        return FlaskResponse('{"ok":false,"error":"not_found"}', mimetype='application/json; charset=utf-8', status=404)
    tail_bytes = request.args.get('tail_bytes', default=None, type=int)
    return _read_text_file(info.task_dir / "output.log", tail_bytes=tail_bytes)


@app.route('/api/task/<uid>/logs/useful')
def api_task_useful_log(uid):
    info = _get_task_info(uid)
    if info is None:
        return FlaskResponse('{"ok":false,"error":"not_found"}', mimetype='application/json; charset=utf-8', status=404)
    tail_bytes = request.args.get('tail_bytes', default=None, type=int)
    return _read_text_file(info.task_dir / "useful_log.log", tail_bytes=tail_bytes)


@app.route('/api/task/<uid>/logs/chat')
def api_task_chat_log(uid):
    info = _get_task_info(uid)
    if info is None:
        return FlaskResponse('{"ok":false,"error":"not_found"}', mimetype='application/json; charset=utf-8', status=404)
    tail_bytes = request.args.get('tail_bytes', default=None, type=int)
    return _read_text_file(info.task_dir / "chat_output.log", tail_bytes=tail_bytes)


@app.route('/api/task/<uid>/result_code')
def api_task_result_code(uid):
    info = _get_task_info(uid)
    if info is None:
        return FlaskResponse('{"ok":false,"error":"not_found"}', mimetype='application/json; charset=utf-8', status=404)
    path = info.task_dir / "result_code.ts"
    if not path.is_file():
        return FlaskResponse('', mimetype='text/plain; charset=utf-8', status=404)
    return FlaskResponse(path.read_text(encoding="utf-8"), mimetype='text/plain; charset=utf-8')


@app.route('/download/parser_ts/<uid>')
def download_parser_ts_uid(uid):
    info = _get_task_info(uid)
    if info is None:
        return FlaskResponse('Задача не найдена', mimetype='text/plain; charset=utf-8', status=404)
    path = info.task_dir / "result_code.ts"
    if not path.is_file():
        return FlaskResponse('Файл result_code.ts не найден', mimetype='text/plain; charset=utf-8', status=404)
    return send_file(
        str(path),
        as_attachment=True,
        download_name='result_code.ts',
        mimetype='text/plain; charset=utf-8'
    )


@app.route('/download/all_files_zip/<uid>')
def download_all_files_zip_uid(uid):
    info = _get_task_info(uid)
    if info is None:
        return FlaskResponse('Задача не найдена', mimetype='text/plain; charset=utf-8', status=404)

    required = [
        ('result_code.ts', info.task_dir / "result_code.ts"),
        ('output.log', info.task_dir / "output.log"),
        ('useful_log.log', info.task_dir / "useful_log.log"),
        ('chat_output.log', info.task_dir / "chat_output.log"),
    ]
    # meta.json добавляем best-effort: старые задачи могли быть сгенерированы без него.
    optional = [
        ('meta.json', info.task_dir / "meta.json"),
        ('RESULT_SUCSESS.txt', info.task_dir / "RESULT_SUCSESS.txt"),
        ('RESULT_FAILED.txt', info.task_dir / "RESULT_FAILED.txt"),
    ]
    missing = [name for name, p in required if not p.is_file()]
    if missing:
        return FlaskResponse('Не найдены файлы: ' + ', '.join(missing), mimetype='text/plain; charset=utf-8', status=404)

    buf = BytesIO()
    with zipfile.ZipFile(buf, mode='w', compression=zipfile.ZIP_STORED) as zf:
        for arcname, full_path in required:
            zf.write(str(full_path), arcname=arcname)
        for arcname, full_path in optional:
            try:
                if full_path.is_file():
                    zf.write(str(full_path), arcname=arcname)
            except Exception:
                pass
    buf.seek(0)
    ts = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    return send_file(
        buf,
        as_attachment=True,
        download_name=f'APSP_gen_{uid}_{ts}.zip',
        mimetype='application/zip'
    )

def _gone_legacy():
    return FlaskResponse('{"ok":false,"error":"use_uid_endpoints"}', mimetype='application/json; charset=utf-8', status=410)


@app.route('/api/log')
def get_log():
    return _gone_legacy()


@app.route('/api/useful_log')
def get_useful_log():
    return _gone_legacy()


@app.route('/api/front_main_status')
def front_main_status():
    return _gone_legacy()


@app.route('/api/result_code')
def get_result_code():
    return _gone_legacy()


@app.route('/api/message_global')
def get_message_global():
    return _gone_legacy()


@app.route('/api/new_page_2_state', methods=['GET'])
def api_new_page_2_state_get():
    """Отдаёт JSON-состояние для `templates/main_page_2.html`."""
    state = load_new_page_2_state()
    return FlaskResponse(json.dumps(state, ensure_ascii=False), mimetype='application/json; charset=utf-8')


@app.route('/api/new_page_2_state', methods=['POST'])
def api_new_page_2_state_post():
    """
    Обновляет состояние `main_page_2`.

    Поддерживаем 2 формата:
    1) {"field": "reflection_text", "value": "..."}
    2) {"reflection_text": "...", "goal_text": "..."} (массовое обновление)
    """
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return FlaskResponse('{"ok":false,"error":"invalid_json"}', mimetype='application/json; charset=utf-8', status=400)

    state = load_new_page_2_state()

    if "field" in payload:
        field = payload.get("field")
        value = payload.get("value", "")
        if field not in NEW_PAGE_2_ALLOWED_FIELDS:
            return FlaskResponse('{"ok":false,"error":"unknown_field"}', mimetype='application/json; charset=utf-8', status=400)
        state[field] = normalize_display_text(value)
    else:
        updated_any = False
        for k in NEW_PAGE_2_ALLOWED_FIELDS:
            if k in payload:
                state[k] = normalize_display_text(payload.get(k))
                updated_any = True
        if not updated_any:
            return FlaskResponse('{"ok":false,"error":"no_allowed_fields"}', mimetype='application/json; charset=utf-8', status=400)

    try:
        save_new_page_2_state(state)
    except Exception:
        return FlaskResponse('{"ok":false,"error":"save_failed"}', mimetype='application/json; charset=utf-8', status=500)

    return FlaskResponse('{"ok":true}', mimetype='application/json; charset=utf-8')


@app.route('/api/browser_screenshot', methods=['GET'])
def api_browser_screenshot():
    """
    Отдаёт актуальный (или последний удачный) PNG-скриншот текущей вкладки Playwright.

    Использование на фронте:
      <img src="/api/browser_screenshot?t=TIMESTAMP">

    Если браузер ещё не запущен (shared_page не установлен) — вернёт 404.
    """
    # 1) Если Playwright запущен в ДРУГОМ процессе — берём "запушенный" скриншот (самый частый кейс).
    with PUSHED_SCREENSHOT_LOCK:
        png = PUSHED_SCREENSHOT_STATE.get("png")
        ts = PUSHED_SCREENSHOT_STATE.get("ts")
    meta = {"ts": ts, "age_ms": None, "error": None}

    # 2) Если пуш-кадра нет, но Playwright запущен в ЭТОМ ЖЕ процессе (shared_page установлен) — пробуем снять напрямую.
    if png is None:
        png, meta = get_cached_screenshot_png(min_interval_ms=800, timeout_ms=2_000, full_page=False)

    if png is None:
        return FlaskResponse("browser_not_started", mimetype='text/plain; charset=utf-8', status=404)

    resp = FlaskResponse(png, mimetype="image/png")
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    # Диагностика (не критично)
    try:
        resp.headers["X-Screenshot-Ts"] = str(meta.get("ts") or "")
        resp.headers["X-Screenshot-AgeMs"] = str(meta.get("age_ms") or 0)
        if meta.get("error"):
            resp.headers["X-Screenshot-Warn"] = "stale"
    except Exception:
        pass
    return resp


@app.route('/api/browser_screenshot_push', methods=['POST'])
def api_browser_screenshot_push():
    """
    Принимает PNG-скриншот (байты) и сохраняет как "последний кадр" в памяти Flask-процесса.

    Это нужно, когда Playwright работает в другом процессе (например, MAIN.py),
    и shared_page недоступен из Flask.

    Ожидаемый формат:
      Content-Type: image/png
      Body: raw png bytes
    """
    try:
        raw = request.get_data(cache=False) or b""
    except Exception:
        raw = b""

    if not raw:
        return FlaskResponse('{"ok":false,"error":"empty_body"}', mimetype='application/json; charset=utf-8', status=400)

    # Примитивная проверка PNG сигнатуры
    if not (len(raw) >= 8 and raw[:8] == b"\x89PNG\r\n\x1a\n"):
        return FlaskResponse('{"ok":false,"error":"not_png"}', mimetype='application/json; charset=utf-8', status=400)

    # Ограничим размер (на всякий случай)
    if len(raw) > 8_000_000:
        return FlaskResponse('{"ok":false,"error":"too_large"}', mimetype='application/json; charset=utf-8', status=413)

    with PUSHED_SCREENSHOT_LOCK:
        PUSHED_SCREENSHOT_STATE["png"] = raw
        PUSHED_SCREENSHOT_STATE["ts"] = datetime.now().timestamp()

    return FlaskResponse('{"ok":true}', mimetype='application/json; charset=utf-8')


@app.route('/download/parser_ts')
def download_parser_ts():
    return _gone_legacy()


@app.route('/download/all_files_zip')
def download_all_files_zip():
    return _gone_legacy()

@app.route('/.well-known/appspecific/com.chrome.devtools.json')
def chrome_devtools():
    """Обработчик для Chrome DevTools - убирает 404 предупреждения"""
    return FlaskResponse('{}', mimetype='application/json')

if __name__ == '__main__':
    # В режиме debug Flask включает reloader, который поднимает дочерний процесс.
    # При запуске из IDE/DebugPy это часто выглядит как "Restarting with stat",
    # после чего родительский процесс завершается (в терминале снова появляется приглашение),
    # а все request-логи (GET/POST) и print() оказываются в другом процессе/консоли.
    # Отключаем reloader, чтобы весь вывод стабильно попадал в одно окно.
    run_dev_server(host="127.0.0.1", port=5000, debug=True)

