"""
Flask-фронт APSP.

Назначение:
- UI страницы `new_page_1/new_page_2/new_page_3` (см. `Apsp_front/templates/*`)
- API-эндпоинты для UI: лог, состояние прогресса, выдача результата, скриншоты

Важно:
- В этом файле НЕТ Flask `session`/`secret_key` (старый многошаговый флоу удалён).
- Часть состояния/файлов используется как "простой IPC" между Flask и `MAIN.py`/Playwright.
"""

from flask import Flask, render_template, request, redirect, url_for, send_from_directory, send_file
import json
import sys
import threading
import zipfile
from pathlib import Path
from io import BytesIO
from datetime import datetime

# Корень репозитория (нужно для импорта модулей из верхнего уровня проекта).
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Проект исторически использует "агрегатор" импортов.
# Да, это не идеально (может переопределять имена), но так устроен текущий проект.
from import_all_libraries import *
from new_program.main_processer import *
# Скриншот текущей Playwright-страницы (если браузер запущен)
from playwright_tool.shared_page import get_cached_screenshot_png
# Важно: `import *` выше может перетереть имя `Response` не-flask'овским классом.
# Явно фиксируем, что в этом файле под Response для HTTP-ответов используется именно flask.Response.
from flask import Response as FlaskResponse

app = Flask(__name__)

# Абсолютные пути: не зависят от текущей рабочей директории.
FRONT_DIR = Path(__file__).resolve().parent              # .../APSP_public/Apsp_front
PROJECT_ROOT = FRONT_DIR.parent                         # .../APSP_public

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
NEW_PAGE_2_STATE_FILE_PATH = RESULT_OUTPUT_DIR / 'new_page_2_state.json'
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
# UI (`templates/new_page_2.html`) опрашивает `/api/front_main_status`, чтобы понять,
# когда фоновая задача завершилась и можно перейти на new_page_3.
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

@app.route('/')
def index():
    """Главная страница"""
    return redirect(url_for('new_page_1'))

@app.route('/new_page_1', methods=['GET', 'POST'])
def new_page_1():
    """
    Простая отдельная форма (без шагов и без зависимостей от многошагового флоу).
    """
    site_url = ''
    if request.method == 'POST':
        site_url = sanitize_text(request.form.get('site_url', ''))

        # Если пусто — ничего не делаем (остаёмся на странице).
        if site_url.strip():
            # При старте нового прогона очищаем состояние СРАЗУ (до запуска фонового потока),
            # чтобы не было гонки: фон может успеть записать прогресс, а /new_page_2 потом сотрёт его.
            try:
                save_new_page_2_state({})
            except Exception:
                pass
            # И очищаем общий лог, чтобы /api/log не отдавал хвосты предыдущего запуска.
            try:
                LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
                with open(LOG_FILE_PATH, 'w', encoding='utf-8') as f:
                    f.write('')
            except Exception:
                pass
            # Запускаем обработку в фоне, чтобы не блокировать переход на следующую страницу.
            def runner_front(link: str):
                try:
                    from MAIN import main_funk_start_on_front
                    main_funk_start_on_front(link)
                except Exception as e:
                    print(f"Ошибка в main_funk_start_on_front: {e}")
                    set_front_main_state(running=False, done=False, error=str(e))
                    return
                set_front_main_state(running=False, done=True, error=None)

            set_front_main_state(running=True, done=False, error=None)
            threading.Thread(target=runner_front, args=(site_url,), daemon=True).start()
            return redirect(url_for('new_page_2'))

    return render_template('new_page_1.html', site_url=site_url)


@app.route('/new_page_2', methods=['GET'])
def new_page_2():
    """
    Широкая страница-дашборд (пока без логики; наполнение подключим позже).
    """
    return render_template('new_page_2.html')


@app.route('/new_page_3', methods=['GET'])
def new_page_3():
    """
    Отдельная страница: показать содержимое result_code_gen/result/result_code.ts
    так же "красиво", как на step6 (построчно с подсветкой/номерами строк).
    """
    return render_template('new_page_3.html')

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

@app.route('/api/log')
def get_log():
    """
    Возвращает содержимое файла `output.log`.

    UI может передавать `tail_bytes`, чтобы получать только хвост файла
    (иначе браузер/страница могут "упасть" на очень больших логах).
    """
    try:
        if LOG_FILE_PATH.is_file():
            tail_bytes = request.args.get('tail_bytes', default=None, type=int)
            # Без tail_bytes — старое поведение (весь файл).
            if tail_bytes is None:
                with open(LOG_FILE_PATH, 'r', encoding='utf-8') as f:
                    content = f.read()
                resp = FlaskResponse(content, mimetype='text/plain; charset=utf-8')
                resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
                resp.headers["Pragma"] = "no-cache"
                return resp

            # С tail_bytes — отдаём только хвост файла (чтобы UI не умирал на сотнях тысяч строк).
            # Ограничиваем верхнюю границу, чтобы не унести память/CPU по ошибке.
            if tail_bytes < 0:
                tail_bytes = 0
            if tail_bytes > 10_000_000:
                tail_bytes = 10_000_000

            truncated = False
            with open(LOG_FILE_PATH, 'rb') as f:
                try:
                    f.seek(0, 2)  # end
                    size = f.tell()
                except Exception:
                    size = None
                if not size or tail_bytes == 0:
                    chunk = b""
                else:
                    start = max(0, size - tail_bytes)
                    truncated = start > 0
                    f.seek(start)
                    chunk = f.read()
                    # Если читаем "не с начала" — режем до первой полной строки (после \n),
                    # чтобы не показывать пользователю "обрезанный" кусок строки.
                    if truncated:
                        nl = chunk.find(b'\n')
                        if nl != -1:
                            chunk = chunk[nl + 1:]
            content = chunk.decode('utf-8', errors='replace')
            resp = FlaskResponse(content, mimetype='text/plain; charset=utf-8')
            resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            resp.headers["Pragma"] = "no-cache"
            try:
                resp.headers["X-Log-Tail-Bytes"] = str(tail_bytes)
                resp.headers["X-Log-Truncated"] = "1" if truncated else "0"
            except Exception:
                pass
            return resp
        else:
            resp = FlaskResponse('', mimetype='text/plain; charset=utf-8')
            resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            resp.headers["Pragma"] = "no-cache"
            return resp
    except Exception as e:
        return FlaskResponse(f'Ошибка чтения файла: {str(e)}', mimetype='text/plain; charset=utf-8', status=500)


@app.route('/api/front_main_status')
def front_main_status():
    """Возвращает состояние выполнения main_funk_start_on_front() (MAIN.py)."""
    return get_front_main_state()

@app.route('/api/result_code')
def get_result_code():
    """Возвращает содержимое файла result_code.ts"""
    try:
        if RESULT_CODE_FILE_PATH.is_file():
            with open(RESULT_CODE_FILE_PATH, 'r', encoding='utf-8') as f:
                content = f.read()
            return FlaskResponse(content, mimetype='text/plain; charset=utf-8')
        else:
            return FlaskResponse('', mimetype='text/plain; charset=utf-8')
    except Exception as e:
        return FlaskResponse(f'Ошибка чтения файла: {str(e)}', mimetype='text/plain; charset=utf-8', status=500)


@app.route('/api/message_global')
def get_message_global():
    """Возвращает содержимое файла message_global.txt (с обрезкой переносов строк сверху/снизу)."""
    try:
        if MESSAGE_GLOBAL_FILE_PATH.is_file():
            with open(MESSAGE_GLOBAL_FILE_PATH, 'r', encoding='utf-8') as f:
                content = f.read()
            # Удаляем переносы строк только сверху и снизу (внутренние переносы сохраняем)
            content = content.strip('\r\n')
            return FlaskResponse(content, mimetype='text/plain; charset=utf-8')
        else:
            return FlaskResponse('', mimetype='text/plain; charset=utf-8')
    except Exception as e:
        return FlaskResponse(f'Ошибка чтения файла: {str(e)}', mimetype='text/plain; charset=utf-8', status=500)


@app.route('/api/new_page_2_state', methods=['GET'])
def api_new_page_2_state_get():
    """Отдаёт JSON-состояние для `templates/new_page_2.html`."""
    state = load_new_page_2_state()
    return FlaskResponse(json.dumps(state, ensure_ascii=False), mimetype='application/json; charset=utf-8')


@app.route('/api/new_page_2_state', methods=['POST'])
def api_new_page_2_state_post():
    """
    Обновляет состояние `new_page_2`.

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
    """Скачать сгенерированный парсер .ts"""
    if not RESULT_CODE_FILE_PATH.is_file():
        return FlaskResponse('Файл result_code.ts не найден', mimetype='text/plain; charset=utf-8', status=404)

    return send_file(
        str(RESULT_CODE_FILE_PATH),
        as_attachment=True,
        download_name='result_code.ts',
        mimetype='text/plain; charset=utf-8'
    )


@app.route('/download/all_files_zip')
def download_all_files_zip():
    """
    Скачать все полезные выходные файлы одним .zip.

    Делаем "store" (без сжатия), чтобы:
    - не тратить CPU на сервере
    - быстрее отдавать архив на больших файлах
    """
    required_files = [
        ('result_code.ts', RESULT_CODE_FILE_PATH),
        ('output.log', LOG_FILE_PATH),
        ('message_global.txt', MESSAGE_GLOBAL_FILE_PATH),
    ]

    candidates = []
    missing = []
    for arcname, full_path in required_files:
        if not full_path.is_file():
            missing.append(arcname)
        else:
            candidates.append((arcname, full_path))

    if missing:
        return FlaskResponse(
            'Не найдены файлы: ' + ', '.join(missing),
            mimetype='text/plain; charset=utf-8',
            status=404
        )

    buf = BytesIO()
    # Без сжатия (store)
    with zipfile.ZipFile(buf, mode='w', compression=zipfile.ZIP_STORED) as zf:
        for arcname, full_path in candidates:
            zf.write(str(full_path), arcname=arcname)

    buf.seek(0)

    # Имя архива: APSP_gen_ + timestamp (дата и время)
    ts = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    return send_file(
        buf,
        as_attachment=True,
        download_name=f'APSP_gen_{ts}.zip',
        mimetype='application/zip'
    )

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
    app.run(debug=True, host='127.0.0.1', port=5000, use_reloader=False)

