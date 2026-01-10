# CLAUDE.md — рабочая память по проекту APSP_public

Этот файл — **короткое, но точное описание** того, как устроен проект и где лежат ключевые компоненты.
Он нужен, чтобы быстрее ориентироваться при следующих доработках.

## Правило поддержки актуальности (обязательно)

Если проводишь **большие изменения/дополнения** в проекте — в конце проверь, отражены ли они в `CLAUDE.md`. Если нет — **дополни**.

Также **заглядывай в `CLAUDE.md` и при обычных изменениях**, и обновляй его, чтобы описание соответствовало текущей структуре и реализации проекта.

Для своих правок и обзора возможностей проекта ориентируйся на `CLAUDE.md`, но помни: он может быть **ещё не полным**.

Записывай сюда **данные/факты/описания функционала**, которые пригодятся в будущем. Пиши **в общем виде**, без избыточных деталей, но **достаточно точно**, чтобы быстро восстановить логику проекта.

## Быстрый ориентир: как «пощупать» проект

Для запуска проекта нужно запустить MAIN_APP.py
И зайти на http://127.0.0.1:5000

По смыслу это запуск Flask-фронта через `MAIN_APP.py` и переход на `http://127.0.0.1:5000`.

## Важное:
- Количество попыток на перезапуск задачи при падении с ошибкой задаётся в `task_runtime/task_registry.py` (TaskRegistry), по умолчанию = **1** (без автоповторов). Быстро вернуть ретраи можно через env `APSP_TASK_MAX_ATTEMPTS`.
- Дедлайн выполнения задачи — **30 минут** (env `APSP_TASK_TIMEOUT_SECONDS`). При превышении кидается `TaskTimeoutException`, задача сразу переводится в `FAILED` без ретраев, в `result_code.ts` пишется лаконичное сообщение об ошибке.
- Папка результатов `RESULT_TASKS`: на Linux (в контейнере) лежит в `/RESULT_TASKS`, на Windows — на уровень выше папки проекта (рядом с репозиторием).
- При старте Flask-фронта (`Apsp_front/app.py`) выполняется авто-очистка `RESULT_TASKS`: удаляются подпапки, где в `meta.json` поле `created_at_ts` старше **7 дней** (в консоль пишется количество удалённых, если >0).
- Есть кнопка `Stop generation` на `main_page_2` (нижний правый угол слева от таймера). Она вызывает `POST /api/task/<uid>/stop`, который ставит stop-флаг; пайплайн периодически проверяет флаг и кидает `UserStopException` с текстом "Генерация была остановлена пользователем". TaskRegistry не делает ретраи и переводит задачу в FAILED с записью в `result_code.ts`/`meta.json`.

## Утилиты

- `RESULT_TASKS/cleanup_folders_without_meta.py`: ручная чистка папки результатов — находит и удаляет подпапки без `meta.json` (есть режим `--dry-run`).
- `RESULT_TASKS/cleanup_folders_status_work.py`: ручная чистка папки результатов — находит и удаляет подпапки, где в `meta.json` статус `"WORK"` (есть подтверждение, `--dry-run`, `--yes`).

## Фронт (Flask + Jinja)

- **Фронт**: `Apsp_front/` (Flask + Jinja2).
- **Основные страницы** (см. `Apsp_front/app.py` и `Apsp_front/templates/`):
  - `main_page_1`: ввод URL сайта или UID задачи (добавлен счётчик активных задач в углу). При POST проверяет наличие готовых результатов для введённого URL. Если введён UID (12 hex символов), то перенаправляет на страницу задачи (2 или 3 в зависимости от статуса). Если UID не найден, показывает ошибку под полем ввода. Содержит ссылку на `/all_tasks`.
  - `all_tasks`: обзор всех задач из папки `RESULT_TASKS`. Показывает таблицу со всеми задачами (до 70 штук), разделённую на две части: активные задачи (статус `WORK`) сверху, завершённые (`COMPLETED/FAILED`) снизу. Колонки: UID (ссылка на страницу 2 или 3), домен, время начала (HH:MM), время в процессе (мин), текущий шаг (извлекается из `new_page_2_state.json`), статус с эмодзи (✅ SUCCESS / 📘 WORK / 🟠 FAILED). Сортировка по времени создания (новые сначала).
  - `parser_exists`: промежуточная страница, показывается если для введённого URL уже есть готовый парсер со статусом COMPLETED. Предлагает открыть существующий результат или запустить генерацию заново.
  - `main_page_2/<uid>`: наблюдение за генерацией (в UX — 10 шагов; процесс длительный, ~15 минут)
  - `main_page_3/<uid>`: выдача результата (код + статистика выполнения)
  - для `main_page_2`/`main_page_3`: отдельная страница, если UID не указан или указан неверно (см. `Apsp_front/templates/invalid_uid.html`)
  - `404`: стандартная страница "не найдено" для любых неправильных URL (кнопка возврата на `/`)
  - служебный: `check_task_status/<uid>`: отдаёт `RESULT_TASKS/<uid>/meta.json`

## Параллельные задания и UID

- Проект поддерживает **параллельные генерации** (несколько задач одновременно).
- Каждая генерация получает **уникальный UID**.
- Реестр задач: `task_runtime/task_registry.py` (`TaskRegistry`).
  - UID формируется как первые 12 символов `uuid4().hex`.
  - Задача запускается через пул воркеров (внутри используется Playwright pool); лимит параллелизма задаётся `max_workers` (по умолчанию 10, можно переопределить через `APSP_MAX_WORKERS`).
  - При ошибке пайплайна делается до **max_attempts попыток** (по умолчанию 1). Только после исчерпания попыток задача становится `FAILED`.
  - После перезапуска Flask `TaskRegistry.get/exists` умеет **best-effort восстановить** задачу по папке `RESULT_TASKS/<uid>` (чтобы можно было открывать страницу результатов по старому UID).
  - В папке задачи пишется `meta.json` (в `RESULT_TASKS/<uid>/meta.json`):
    - старт/финиш в двух форматах (human + timestamp)
    - статус `WORK/COMPLETED/FAILED`
    - `attempts` (1..max_attempts попыток запуска)
    - дополнительные поля (например `url`, `runtime_status`, `last_error`, `created_at_*`)
  - `result_code.ts` кладётся в `RESULT_TASKS/<uid>/result_code.ts`:
    - при успешной генерации — итоговый TypeScript код
    - при падении пайплайна — stacktrace/текст ошибки, чтобы страница результата и скачивание работали предсказуемо
  - По завершении создаётся `RESULT_SUCSESS.txt` (при успехе) или `RESULT_FAILED.txt` (при ошибке), которые попадают в итоговый ZIP.

## Точка входа генерации

- Основная функция старта генерации:
  `@new_program/main_processer.py:152`
- `main_processer(input_url, uid, task_dir, page)`:
  - нормализует URL
  - обеспечивает наличие Playwright-страницы (`page`)
  - запускает основную цепочку генерации
  - LLM-шаги **HGF (шаг 1)** и **TNF (шаг 3)** возвращают JSON со `status`; при `status != "ok"` (в т.ч. `"error"`) или невалидном JSON — `main_processer` сразу делает `raise` с текстом полного ответа.

## Папка `new_program/` (пайплайн генерации)

`new_program/` содержит модули, которые обслуживают пайплайн:

- обработчики/данные для **LLM** (запросы/промпты/форматы)
- обработчики/данные для **агента**
- записи промежуточных/итоговых артефактов (задачи, результаты и т.п.)

## Reasoning-агент (`reasoning_agent/`)

- Ключевой файл: `reasoning_agent/agent_main.py` + остальная логика в `reasoning_agent/`.
- Модель работы:
  - агенту задают **task**
  - задают **result schema** + **result template** (поля, которые агент должен заполнить)
  - задают **план шагов** (если не задан — генерируется)
  - дальше агент сам выбирает инструменты, выполняет шаги и заполняет result; завершает `DONE|FAILED`
- В многозадачном режиме (параллельные UID) **runtime-состояние агента изолировано по потокам**:
  - `reasoning_agent/agent_main.py`: `history/long_term_memory/steps_future` — `threading.local()`
  - `reasoning_agent/agent_tools.py`: `RESULT/RESULT_SCHEMA` — `threading.local()`
  - `reasoning_agent/runtime_state.py`: `main_plan/long_term_memory` для tools — `threading.local()`
  - `orchestrate(..., uid, task_dir)` умеет (опционально) выставлять `task_runtime.task_context`, чтобы логи/UI-state писались в `RESULT_TASKS/<uid>/...`
  - Если модель завершает шаг действием `FAILED`, `orchestrate()` **рейзит исключение** (а не возвращает JSON), чтобы пайплайн воспринимал это как обычную ошибку. В тексте ошибки есть последний `model_summary`.

## Интеграция с Playwright (`playwright_tool/`)

- Инструменты взаимодействия агента с браузером: `playwright_tool/`.
- Ключевой файл: `playwright_tool/playwright_toolkit.py` — набор tools для “живого” управления страницей (переходы, клики, ожидания, поиск, чтение HTML и т.д.).
- Для обновления превью-скриншота на `main_page_2` без действий Playwright используется фоновый pusher:
  - `playwright_tool/screenshot_pusher.py`: делает OS-level screenshot (Pillow `ImageGrab`) и пушит PNG в Flask
  - в режиме UID — в `/api/task/<uid>/browser_screenshot_push` (см. `_run_task()` в `Apsp_front/app.py`)
- Вызовы OpenAI в `ChatGPT/OpenAI_ChatGPT.py` обёрнуты heartbeat-циклом: пока ждём ответ, раз в ~5 секунд пушится Playwright-скриншот через `maybe_push_screenshot_to_front`, чтобы превью обновлялось даже во время долгих LLM-запросов.

## TODO для будущих дополнений (когда будет время)

- описать точный пайплайн “10 шагов” и какие артефакты создаются
- описать формат артефактов по `uid` (директории задач, логи, скриншоты, результат)
- описать контракт “Agent ↔ Tools”
- зафиксировать API-эндпоинты, которые использует `main_page_2` для статуса/логов/скриншотов


## Роуты Flask (`Apsp_front/app.py`)

### Основные (UI)

- **`GET /`**: редирект на `GET /main_page_1`.
- **`GET|POST /main_page_1`**: форма ввода URL или UID задачи; на `POST` с непустым значением:
  - Если введён UID (12 hex символов): проверяет существование задачи и редиректит на `main_page_2/<uid>` (если задача в работе) или `main_page_3/<uid>` (если завершена). Если UID не найден — показывает ошибку под полем ввода с передачей `uid_not_found=True` в шаблон.
  - Если введён URL: нормализует URL и ищет в `RESULT_TASKS` задачи со статусом `COMPLETED` для того же URL. Если найден — редиректит на `GET /parser_exists`, иначе создаёт задачу (UID) и редиректит на `GET /main_page_2/<uid>/`.
  - При `GET` рендерит `templates/main_page_1.html`. 
  - Кнопка отправки динамически меняется: при вводе UID текст становится "Проверить задачу по UID" и цвет меняется на синий, при обычном URL — "Generate" зелёного цвета.
- **`GET /all_tasks`**: страница обзора всех задач из `RESULT_TASKS`. Читает `meta.json` и `new_page_2_state.json` для каждой задачи, формирует таблицу с данными (UID, домен, время, текущий шаг, статус). Показывает первые 70 задач, разделённых на активные (`WORK`) и завершённые (`COMPLETED/FAILED`). Рендерит `templates/all_tasks.html`.
- **`GET /parser_exists`**: промежуточная страница (параметры `?url=...&existing_uid=...`); показывает что для данного URL уже есть готовый парсер. Две кнопки: открыть существующий результат (`main_page_3/<existing_uid>`) или запустить генерацию заново (`POST /parser_exists/new_generation`). Рендерит `templates/parser_exists.html`.
- **`POST /parser_exists/new_generation`**: принимает `site_url` из формы и запускает новую генерацию (без проверки на существующие результаты), редиректит на `GET /main_page_2/<uid>/`.
- **`GET /main_page_2`** и **`GET /main_page_2/`**: если UID не указан — рендерит `templates/invalid_uid.html` (uid "не указан").
- **`GET /main_page_2/<uid>/`**: "дашборд" задачи; если UID неизвестен — `invalid_uid.html`, иначе `templates/main_page_2.html`.
- **`GET /main_page_3`** и **`GET /main_page_3/`**: если UID не указан — `invalid_uid.html` (uid "не указан").
- **`GET /main_page_3/<uid>/`**: страница результата (статистика из `meta.json` + код); если задача ещё в работе — редирект на `GET /main_page_2/<uid>/`, если UID неизвестен — `invalid_uid.html`, иначе `templates/main_page_3.html`.
- **`GET|POST /example2`**: тестовая/примерная форма без запуска пайплайна; рендерит `templates/example2.html`.

### Системные / служебные / API

- **`404 handler`**: для URL вида `/api/*` возвращает JSON `{"ok":false,"error":"not_found"}` (404), иначе рендерит `templates/page_404.html`.
- **`GET /check_task_status/<uid>/`**: отдаёт `RESULT_TASKS/<uid>/meta.json` (JSON, no-cache). Ошибки: `task_not_found/meta_not_found/meta_read_failed`.

- **`GET /content/<path:filename>`**: отдаёт статические файлы из `Apsp_front/content/`.
- **`GET /favicon.ico`**: отдаёт `Apsp_front/content/favicon_2.png`.
- **`GET /.well-known/appspecific/com.chrome.devtools.json`**: отдаёт `{}` (JSON) чтобы убрать 404-предупреждения Chrome DevTools.

#### API (общие / статистика)

- **`GET /api/tasks/active_count`**: JSON `{"ok":true,"active":N,"max":M}` — количество текущих задач в статусе `running` и максимальный лимит.

#### API (по UID задачи)

- **`GET /api/task/<uid>/status`**: JSON со статусом задачи: `uid`, `url`, `status`, `error` (или 404 `{"ok":false,"error":"not_found"}`).
- **`GET /api/task/<uid>/new_page_2_state`**: JSON состояния `main_page_2` из `RESULT_TASKS/<uid>/new_page_2_state.json` (или 404).
- **`POST /api/task/<uid>/new_page_2_state`**: обновляет состояние (либо `{field,value}`, либо массово разрешёнными полями); возвращает `{"ok":true}` или JSON-ошибку.
- **`GET /api/task/<uid>/browser_screenshot`**: отдаёт `image/png` из `task_runtime.screenshot_store` (или 404 текстом `task_not_found/screenshot_not_available`).
- **`POST /api/task/<uid>/browser_screenshot_push`**: принимает raw PNG-байты и сохраняет в `task_runtime.screenshot_store`; возвращает `{"ok":true}` или JSON-ошибку.
- **`GET /api/task/<uid>/logs/output`**: текст `RESULT_TASKS/<uid>/output.log` (поддерживает `?tail_bytes=...`, no-cache).
- **`GET /api/task/<uid>/logs/useful`**: текст `RESULT_TASKS/<uid>/useful_log.log` (поддерживает `?tail_bytes=...`, no-cache).
- **`GET /api/task/<uid>/logs/chat`**: текст `RESULT_TASKS/<uid>/chat_output.log` (поддерживает `?tail_bytes=...`, no-cache).
- **`GET /api/task/<uid>/result_code`**: текст `RESULT_TASKS/<uid>/result_code.ts` (или 404).

#### Скачивание (по UID задачи)

- **`GET /download/parser_ts/<uid>`**: скачивает `result_code.ts` как attachment.
- **`GET /download/all_files_zip/<uid>`**: скачивает ZIP (`result_code.ts`, `output.log`, `useful_log.log`, `chat_output.log`, + optional `meta.json`, `RESULT_SUCSESS.txt` / `RESULT_FAILED.txt`).

#### Legacy / совместимость (всегда 410)

- **`GET /api/log`**, **`GET /api/useful_log`**, **`GET /api/front_main_status`**, **`GET /api/result_code`**, **`GET /api/message_global`**: всегда `410` JSON `{"ok":false,"error":"use_uid_endpoints"}`.
- **`GET /download/parser_ts`**, **`GET /download/all_files_zip`**: всегда `410` JSON `{"ok":false,"error":"use_uid_endpoints"}`.

#### API без UID (глобальные файлы/состояния)

- **`GET /api/new_page_2_state`**: JSON-состояние из `result_code_gen/result/new_page_2_state.json` (используется legacy-флоу).
- **`POST /api/new_page_2_state`**: обновляет это состояние; возвращает `{"ok":true}` или JSON-ошибку.
- **`GET /api/browser_screenshot`**: отдаёт последний (или актуальный) PNG-скриншот текущей вкладки Playwright (через пуш-кадр или `shared_page`); 404 `browser_not_started`.
- **`POST /api/browser_screenshot_push`**: принимает raw PNG-байты и сохраняет как “последний кадр” для `GET /api/browser_screenshot`; возвращает `{"ok":true}` или JSON-ошибку.

