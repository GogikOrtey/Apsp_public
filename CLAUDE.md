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

## Зависимости (Python)

- Единый файл зависимостей: `requirements.txt` в корне репозитория.

## Старт и финиш задачи генерации (человеческая схема)

### Старт (кнопка **Generate** на `main_page_1`)

- Пользователь нажимает **Generate** на `Apsp_front/templates/main_page_1.html` → отправляется форма `POST /main_page_1` с полем `site_url`.
- Сервер (`Apsp_front/app.py`, `main_page_1`):
  - Если `site_url` выглядит как UID (12 hex символов) → **генерация не запускается**, просто открывается существующая задача:
    - `WORK/RUNNING` → редирект на `GET /main_page_2/<uid>/`
    - `COMPLETED/FAILED` → редирект на `GET /main_page_3/<uid>/`
    - UID не найден → ошибка на `main_page_1`
  - Если это URL:
    - Если для этого URL уже есть `COMPLETED` результат → редирект на `GET /parser_exists` (выбор: открыть готовое / запустить заново)
    - Иначе создаётся и запускается новая задача:
      - `TASKS.create(url, user_telegram_id, user_account)` → создаёт UID, папку `RESULT_TASKS/<uid>/`, пишет `meta.json`
      - `TASKS.start(uid, _run_task)` → отправляет выполнение в пул воркеров (Playwright pool)
      - Редирект на `GET /main_page_2/<uid>/` (страница наблюдения за прогрессом)

### Финиш (успех или ошибка) и “результат для 3-й страницы”

- Реальная работа выполняется в runner’е `_run_task(...)` (`Apsp_front/app.py`): создаётся Playwright page и вызывается `new_program/main_processer.py:main_processer(...)`.
- Финальная точка “задача завершена” находится в `task_runtime/task_registry.py` → `TaskRegistry._on_future_done(...)` (callback на завершение future):
  - **Успех**: `main_processer` завершился без исключения → `runtime_status="done"`, в `meta.json` ставится `finished_at_*` и `status=COMPLETED`, создаётся `RESULT_SUCSESS.txt`.
  - **Ошибка/остановка/таймаут**: исключение ловится в `_on_future_done` → `runtime_status="error"`, `status=FAILED`, создаётся `RESULT_FAILED.txt`, и (важно) **всегда** записывается `RESULT_TASKS/<uid>/result_code.ts` с текстом ошибки (чтобы UI и скачивание работали предсказуемо).
    - Можно добавить “человеческий” префикс **перед traceback**: если исключению выставить атрибут `apsp_prefix_block` (строка), то `TaskRegistry` вставит этот блок в `result_code.ts` сразу после заголовка `"🟠 Ошибка генерации: 🟠"`.

### Как показывается результат на `main_page_3`

- `GET /main_page_3/<uid>/` рендерит страницу результата и подтягивает статистику из `RESULT_TASKS/<uid>/meta.json`.
- Сам текст “окна результата” (код или текст ошибки) читается из файла `RESULT_TASKS/<uid>/result_code.ts` через API `GET /api/task/<uid>/result_code`.

Примечание: `MAIN.py:main_funk_start_on_front(...)` — это обёртка вокруг `main_processer` из старого/ручного запуска и **не используется** в актуальном пути кнопки `Generate` (текущий путь идёт через `TaskRegistry` → `_run_task`).

Все финальные исходы сходятся в TaskRegistry._on_future_done() (success / stop / timeout / final failure)

## Важное:
- Количество попыток на перезапуск задачи при падении с ошибкой задаётся в `task_runtime/task_registry.py` (TaskRegistry), по умолчанию = **1** (без автоповторов). Быстро вернуть ретраи можно через env `APSP_TASK_MAX_ATTEMPTS`.
- Дедлайн выполнения задачи — **30 минут** (env `APSP_TASK_TIMEOUT_SECONDS`). При превышении кидается `TaskTimeoutException`, задача сразу переводится в `FAILED` без ретраев, в `result_code.ts` пишется лаконичное сообщение об ошибке.
- Папка результатов `RESULT_TASKS`: на Linux (в контейнере) лежит в `/RESULT_TASKS`, на Windows — на уровень выше папки проекта (рядом с репозиторием).
- При старте Flask-фронта (`Apsp_front/app.py`) выполняется авто-очистка `RESULT_TASKS`: удаляются подпапки, где в `meta.json` поле `created_at_ts` старше **7 дней** (в консоль пишется количество удалённых, если >0).
- Есть кнопка `Stop generation` на `main_page_2` (нижний правый угол слева от таймера). Она вызывает `POST /api/task/<uid>/stop`, который ставит stop-флаг; пайплайн периодически проверяет флаг и кидает `UserStopException` с текстом "Генерация была остановлена пользователем". TaskRegistry не делает ретраи и переводит задачу в FAILED с записью в `result_code.ts`/`meta.json`.
  - Чтобы корректно отличать "ошибку" от "ручной остановки" в UI/Telegram, в `meta.json` при завершении также выставляются поля:
    - `finish_reason`: `success|error|timeout|user_stop`
    - `stopped_by_user`: `true` только для `finish_reason="user_stop"`
  - Эти поля используются для текста/эмодзи в `all_tasks`, `main_page_3` и Telegram-уведомлениях.

## Утилиты

- `RESULT_TASKS/cleanup_folders_without_meta.py`: ручная чистка папки результатов — находит и удаляет подпапки без `meta.json` (есть режим `--dry-run`).
- `RESULT_TASKS/cleanup_folders_status_work.py`: ручная чистка папки результатов — находит и удаляет подпапки, где в `meta.json` статус `"WORK"` (есть подтверждение, `--dry-run`, `--yes`).

## Фронт (Flask + Jinja)

- **Фронт**: `Apsp_front/` (Flask + Jinja2).
- **Основные страницы** (см. `Apsp_front/app.py` и `Apsp_front/templates/`):
  - `main_page_1`: ввод URL сайта или UID задачи (добавлен счётчик активных задач в углу). При POST проверяет наличие готовых результатов для введённого URL. Если введён UID (12 hex символов), то перенаправляет на страницу задачи (2 или 3 в зависимости от статуса). Если UID не найден, показывает ошибку под полем ввода. Содержит ссылку на `/all_tasks`.
  - `all_tasks`: обзор всех задач из папки `RESULT_TASKS`. Показывает таблицу со всеми задачами (до 70 штук), разделённую на две части: активные задачи (статус `WORK`) сверху, завершённые (`COMPLETED/FAILED`) снизу. Колонки: UID (ссылка на страницу 2 или 3), домен, время начала (HH:MM), время в процессе (мин), текущий шаг (извлекается из `new_page_2_state.json`), статус с эмодзи (✅ SUCCESS / 📘 WORK / 🟠 FAILED). Сортировка по времени создания (новые сначала).
  - `parser_exists`: промежуточная страница, показывается если для введённого URL уже есть готовый парсер со статусом COMPLETED. Предлагает открыть существующий результат или запустить генерацию заново.
  - `main_page_2/<uid>`: наблюдение за генерацией (в UX — 10 шагов; процесс длительный, ~15 минут). В `Apsp_front/templates/main_page_2.html` есть отдельные адаптив-стили: на узком экране снимается фиксированная высота контейнера (`90vh`) и `overflow:hidden`, чтобы страница нормально росла и прокручивалась при “колонках в столбик”.
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
- Превью-скриншот на `main_page_2` берётся из `GET /api/task/<uid>/browser_screenshot` (сервер хранит последний кадр в `task_runtime/screenshot_store.py`).
- Playwright-скриншоты делаются через `playwright_tool/shared_page.py:maybe_push_screenshot_to_front(...)` (в т.ч. в heartbeat-цикле OpenAI-запросов в `ChatGPT/OpenAI_ChatGPT.py`, раз в ~5 секунд во время ожидания ответа).
  - Скриншоты автоматически **уменьшаются/оптимизируются** (env `APSP_SCREENSHOT_MAX_WIDTH`, по умолчанию 900) для экономии трафика (важно для ngrok).
  - По умолчанию скриншоты **не пушатся по HTTP на внешний домен** (ngrok и т.п.), чтобы не создавать лишний трафик “сервер → ngrok → сервер”. Включить можно env `APSP_ALLOW_EXTERNAL_SCREENSHOT_PUSH=1`.
- `playwright_tool/screenshot_pusher.py` (desktop `ImageGrab`) — вспомогательный debug-pusher, который показывает **рабочий стол**, а не страницу Playwright.
  - По умолчанию **выключен**; включается только env `APSP_ENABLE_DESKTOP_SCREENSHOT_PUSHER=1` (интервал: `APSP_DESKTOP_SCREENSHOT_PUSHER_INTERVAL_S`, по умолчанию 5.0).
- На `Apsp_front/templates/main_page_2.html` polling автоматически “замедляется” на внешних доменах (ngrok): реже опрашиваются state/status/logs и реже обновляется скриншот, чтобы не перегружать туннель.

## Система аккаунтов (куки на стороне клиента)

Аккаунт пользователя хранится в куке `user_account` на стороне клиента.

Дополнение (flow "авторизация перед запуском"):
- если пользователь пытается запустить генерацию/открыть задачу с `main_page_1`, но аккаунт не привязан (`user_account` отсутствует или = `no_account`),
  то сервер сохраняет введённый текст (URL или UID) в cookie `apsp_pending_site_url` и делает редирект на `GET /login_page?next=/main_page_1?resume=1`.
- после успешной Telegram-авторизации `login_page.html` редиректит на `next`, а `GET /main_page_1?resume=1` автоматически продолжает сценарий (UID → `main_page_2/3`, URL → `parser_exists` или старт новой задачи) без второго клика.
- страницы `parser_exists`, `main_page_2/<uid>/`, `main_page_3/<uid>/`, `all_tasks` теперь тоже требуют авторизацию: если аккаунта нет — редирект на `/login_page?next=<текущий_url>`.

Опционально ("Продолжить без авторизации"):
- на `login_page` есть ссылка **“Продолжить без авторизации”** — она ставит cookie `apsp_skip_auth=1`
- если `apsp_skip_auth=1`, то авторизация **не требуется** (редиректы на `/login_page` отключаются) и запуск работает “как раньше”, просто без `user_account/user_telegram_id`
- если пользователь потом нажимает “Привязать аккаунт Телеграм” — `apsp_skip_auth` удаляется и снова начинает работать обычная логика авторизации

### Серверные функции (`Apsp_front/app.py`)

- **`set_user_account_cookie(response, username, max_age_days=365)`**: устанавливает куку `user_account` с именем пользователя. Параметры: `httponly=False` (доступна из JS), `secure=False` (для HTTP), `samesite='Lax'`.
- **`get_user_account_from_cookie() -> str | None`**: получает имя пользователя из куки (возвращает `None`, если не установлена).
- **`clear_user_account_cookie(response)`**: удаляет куку `user_account` (устанавливает пустое значение с `max_age=0`).

### Клиентские функции (JavaScript в `main_page_1.html`)

- **`setCookie(name, value, days)`**: установка куки на заданное количество дней.
- **`getCookie(name)`**: получение значения куки.
- **`deleteCookie(name)`**: удаление куки.
- **`window.setUserAccount(username)`**: глобальная функция для установки аккаунта (устанавливает куку + обновляет UI).
- **`updateAccountUI()`**: автоматически обновляет интерфейс на основе значения куки при загрузке страницы.

### UI элементы (`main_page_1`)

- **Кнопка аккаунта** (справа сверху): показывает имя пользователя (голубой фон) или `"no_account"` (серый фон с голубой границей).
- **Выпадающее меню**: при клике на кнопку появляется меню с именем пользователя и кнопкой "Выйти из аккаунта".
- **Кнопка "Выйти из аккаунта"**: вызывает API-эндпоинт `/api/account/logout` для серверной очистки куки, затем обновляет UI клиентской функцией.

### API эндпоинты

- **`POST /api/account/logout`**: удаляет куку `user_account` через `clear_user_account_cookie()` и возвращает `{"ok": true}`.

## Привязка Telegram-аккаунта через бота (deep-link + webhook)

Есть страница `GET /login_page` (`Apsp_front/templates/login_page.html`) для привязки Telegram.

### Как работает

- На странице логина пользователь нажимает кнопку **"Привязать аккаунт Телеграм"**.
- Фронт вызывает `POST /api/telegram/auth/start`, получает `token` и ссылку вида `https://t.me/<bot_username>?start=<token>` и открывает Telegram.
- Пользователь нажимает **Start** у бота → в Telegram приходит сообщение `/start <token>`.
- Бот отправляет апдейт в наш webhook `POST /api/telegram/webhook/<secret>`.
- Сервер помечает token как **authorized**, отправляет пользователю сообщение **"Авторизация успешна"** и сохраняет данные пользователя.
  - в сообщении бот даёт ссылку “вернуться в браузер” вида `.../login_page?next=<...>&token=<...>` — чтобы не терялся `next` (например `/main_page_1?resume=1`) и можно было продолжить даже если localStorage недоступен
- Браузер опрашивает `GET /api/telegram/auth/status?token=...`, затем вызывает `POST /api/telegram/auth/finish` и получает куки:
  - `user_account` (для UI; строка вида `@username` или `tg_<id>`)
  - `user_telegram_id` (HttpOnly; Telegram ID пользователя)

### Где лежит реализация

- Логика Telegram: `telegram_connect.py`
- Flask API: `Apsp_front/app.py`

### Переменные окружения

- `APSP_TELEGRAM_BOT_TOKEN`: токен бота от BotFather
- `APSP_TELEGRAM_BOT_USERNAME`: username бота (без `@`)
- `APSP_TELEGRAM_WEBHOOK_SECRET`: секрет в URL вебхука
- `APSP_BASE_URL`: базовый URL сервиса (используется в ссылках в сообщениях, по умолчанию `http://127.0.0.1:5000`)
- `APSP_TELEGRAM_LOG_CHAT_ID`: (опционально) chat_id диагностического чата log_chat (int, часто -100...)
- `APSP_TELEGRAM_INFO_CHAT_ID`: (опционально) chat_id диагностического чата info_chat (int, часто -100...)

Дополнительно:
- `reasoning_agent/agent_main.py:log_development_feedback(...)` теперь (best-effort) дублирует `development_feedback` в Telegram `info_chat` через `telegram_connect.py:try_send_to_info_chat(...)` (если заданы env `APSP_TELEGRAM_BOT_TOKEN` и `APSP_TELEGRAM_INFO_CHAT_ID`).
- `reasoning_agent/agent_main.py:orchestrate(...)` теперь (best-effort) шлёт в Telegram `info_chat` алерт, если любой tool вернул ошибку (`status="error"`/`ok=false`/`error` непустой), включая `UID`, краткий `model_summary` и `tool_result`.

### Настройка `.env` и порядок загрузки

- Для локального запуска и контейнера поддерживается `.env` в корне репозитория (`APSP_public/.env`).
- Загрузка `.env` выполняется в `MAIN_APP.py` **до** импорта `Apsp_front/app.py`. Это важно, потому что `Apsp_front/app.py` читает `APSP_TELEGRAM_*` переменные **во время импорта**.
- Пример шаблона переменных: `env.example` (его нужно копировать в `.env` и заполнить).
- Подробная пошаговая инструкция: `TELEGRAM_SETUP.md`.
- `.env` не коммитим (он в `.gitignore`).

### Webhook: когда нужно вызывать `setWebhook`

- Webhook привязан к конкретному URL.
- **Продакшен (стабильный домен + HTTPS)**: `setWebhook` делается обычно **один раз** на рабочий домен.
- **Локальная разработка через ngrok**: URL часто меняется → `setWebhook` нужно повторять при смене URL.

### Файлы/хранилища Telegram

- `Apsp_front/_telegram_auth/`: временные токены авторизации (pending/authorized).
- `Apsp_front/_telegram_users/`: файлы пользователей Telegram (tg_id/username и др.).
- Эти директории **не коммитятся** (добавлены в `.gitignore`).

### Уведомления в Telegram по задачам

- При создании задачи `TaskRegistry.create(...)` теперь принимает (best-effort) `user_telegram_id` и `user_account` и пишет их в `RESULT_TASKS/<uid>/meta.json`:
  - `user_telegram_id`: Telegram ID пользователя (int)
  - `user_account`: строка вида `@username`/`tg_<id>` (для справки)
- На `main_page_1` и `parser_exists/new_generation` эти значения берутся из кук (`user_telegram_id`, `user_account`) и передаются в `TASKS.create(...)`.
- Сообщение о старте генерации отправляется из пайплайна, а не из Flask:
  - вызов добавлен в `new_program/main_processer.py` (после успешного `goto_url`)
  - реализация/обёртка отправки: `telegram_connect.py` (`send_message_to_user`, `try_notify_task_started`), читает `meta.json` и отправляет пользователю сообщение по `user_telegram_id`.
- Сообщение о завершении генерации отправляется из `task_runtime/task_registry.py` (центральная точка завершения задачи: `TaskRegistry._on_future_done(...)`):
  - два варианта текста: **🟩 успех** или **🟠 ошибка/остановка/таймаут**
  - в сообщении указывается **время выполнения задачи** (в минутах, рассчитывается из `finished_at_ts - started_at_ts` в `meta.json`)
  - вместе с сообщением **прикрепляется ZIP-архив** (тот же состав файлов, что и кнопка "Скачать все файлы .zip" на `main_page_3`)
  - при ошибке/остановке/таймауте **в этом же сообщении (caption)** добавляется причина в виде **code block** (`<pre>...</pre>`)
  - реализация/обёртка: `telegram_connect.py` (`try_notify_task_finished`, `send_bot_document/sendDocument`)

#### Дублирование исходящих Telegram-сообщений в log_chat (для диагностики)

- Любые исходящие сообщения/документы **пользователям** дополнительно (best-effort) дублируются в `log_chat` через `telegram_connect.py:try_send_to_log_chat(...)`.
- Реализация централизована на низком уровне в `telegram_connect.py`:
  - `send_bot_message(..., dup_to_log=True)` — по умолчанию делает дубль в log_chat с заголовком `"Пользователю tg_id=... ушло сообщение:"`
  - `send_bot_document(..., dup_to_log=True)` — аналогично для документов
  - диагностические чаты (`APSP_TELEGRAM_LOG_CHAT_ID`, `APSP_TELEGRAM_INFO_CHAT_ID`) **не дублируются**, чтобы избежать зацикливания
- Для “категорий” событий генерации используются отдельные строки:
  - `"Пользователь _ начал генерацию:"` в `try_notify_task_started(...)`
  - `"Пользователь _ завершил генерацию:"` в `try_notify_task_finished(...)`
  - при этом сами исходящие сообщения start/finish отправляются с `dup_to_log=False`, чтобы в log_chat не было дублей.
- Как расширять “категории” дальше
  - Для новой категории просто добавляйте один вызов _dup_outgoing_to_log_chat(header=..., body=...) в нужном месте (как сделано для start/finish).
  - Если в конкретном месте “общий дубль” не нужен, используйте флаг dup_to_log=False при отправке (я так сделал для start/finish, чтобы в log-chat не было двойных записей).

## TODO для будущих дополнений (когда будет время)

- описать точный пайплайн “10 шагов” и какие артефакты создаются
- описать формат артефактов по `uid` (директории задач, логи, скриншоты, результат)
- описать контракт “Agent ↔ Tools”
- зафиксировать API-эндпоинты, которые использует `main_page_2` для статуса/логов/скриншотов


## Роуты Flask (`Apsp_front/app.py`)

### Основные (UI)

- **`GET /`**: редирект на `GET /main_page_1`. - Это не самая основная страница, но это старт автогенератора. Воможно потом измениться на `/start_page_1`
- **`GET /start_page_1`**: стартовая страница с 2 кнопками (вход в автогенератор и "центр").
- **`GET|POST /auto_solving_problem_page_1`**: страница "ASP: Центр автоматизации решения проблем и починки парсеров" (пока UI-страница с типовыми проблемами + textarea"“Решить проблему"). Кнопка “центр” на `start_page_1` ведёт сюда. На странице есть кнопка “Назад” → `start_page_1`.
- **`GET /before_starting_autogen_info`**: инфо-страница "Описание возможностей автогенератора" перед входом в `main_page_1` (синяя кнопка "Перейти к автогенератору").
- **`GET|POST /select_fields`**: страница выбора полей для парсинга. Список полей подгружается из `Gen_parseCard/all_fields_description.py:all_fields` (категории + метаданные). Обязательные поля (name, link, price, stock, timestamp) заблокированы и всегда выбраны. Есть список “по умолчанию” (обязательные + несколько необязательных для примера). При подтверждении выбор сохраняется в cookie `selected_fields` (comma-separated), затем редирект на `main_page_1`. При создании задачи `selected_fields` также сохраняются в `RESULT_TASKS/<uid>/meta.json` и используются для фильтрации `all_fields` в генерации. На странице показывается оценка времени генерации: **4 минуты + 1 мин/поле (минус 2 служебных поля), начиная с 8-го выбранного поля — 1.5 мин/поле**.
- **`GET|POST /main_page_1`**: форма ввода URL или UID задачи; на `POST` с непустым значением:
  - Если введён UID (12 hex символов): проверяет существование задачи и редиректит на `main_page_2/<uid>` (если задача в работе) или `main_page_3/<uid>` (если завершена). Если UID не найден — показывает ошибку под полем ввода с передачей `uid_not_found=True` в шаблон.
  - Если введён URL: нормализует URL и ищет в `RESULT_TASKS` задачи со статусом `COMPLETED` для того же URL. Если найден — редиректит на `GET /parser_exists`, иначе создаёт задачу (UID) и редиректит на `GET /main_page_2/<uid>/`.
  - При `GET` рендерит `templates/main_page_1.html`. 
  - Кнопка отправки динамически меняется: при вводе UID текст становится "Проверить задачу по UID" и цвет меняется на синий, при обычном URL — "Generate" зелёного цвета.
- **`GET /main_stats`**: страница статистики сервера (CPU/RAM/Disk, uptime) и статистики по задачам (сколько в работе/paused/завершено/ошибка). На `main_page_1` по клику на левый верхний `status-block` делается переход на эту страницу.
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
- **`GET /api/system/stats`**: JSON со статистикой сервера и задач:
  - uptime текущего Flask-процесса (`uptime_seconds/minutes/hours`)
  - CPU/RAM/Disk (через `psutil`, если установлен; иначе `psutil_available=false`)
  - задачи: `active_runtime`, `max_workers`, `total/work/paused/completed/failed` (по папке `RESULT_TASKS/<uid>/meta.json`)
- **`POST /api/account/logout`**: удаляет куку `user_account` через `clear_user_account_cookie()` и возвращает `{"ok": true}`.

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

