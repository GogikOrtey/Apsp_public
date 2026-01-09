#region Импорты и инициализация

# Чтобы при запуске файла из папки New/ были видны модули из корня проекта (addedFunc.py и др.)
### Потом убрать, что бы было нормально
from pathlib import Path
import sys
import os
import importlib
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Подключение всех библиотек и функций
from import_all_libraries import * 
from task_runtime.stop_store import raise_if_stop_requested
from task_runtime.timeout_store import raise_if_timeout

# Заружаем ключ OpenAI и инициализируем клиент
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_AI_API_KEY")
if not api_key:
    raise RuntimeError(
        "OpenAI API key not found. Add OPEN_AI_API_KEY to your .env file"
    )

import httpx
from openai import APIConnectionError, APITimeoutError, RateLimitError, APIError

_OPENAI_HTTP_CLIENT: httpx.Client | None = None

def _has_proxy_env() -> bool:
    keys = (
        "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
        "http_proxy", "https_proxy", "all_proxy", "no_proxy",
    )
    return any(os.getenv(k) for k in keys)

def _build_openai_http_client(*, trust_env: bool) -> httpx.Client:
    timeout_s = float(os.getenv("OPENAI_TIMEOUT_S", "120"))
    connect_timeout_s = float(os.getenv("OPENAI_CONNECT_TIMEOUT_S", "30"))
    timeout = httpx.Timeout(timeout_s, connect=connect_timeout_s)
    return httpx.Client(timeout=timeout, trust_env=trust_env)

def _set_openai_client(*, api_key: str, trust_env: bool) -> OpenAI:
    global _OPENAI_HTTP_CLIENT, client
    try:
        if _OPENAI_HTTP_CLIENT is not None:
            _OPENAI_HTTP_CLIENT.close()
    except Exception:
        pass
    _OPENAI_HTTP_CLIENT = _build_openai_http_client(trust_env=trust_env)
    client = OpenAI(api_key=api_key, http_client=_OPENAI_HTTP_CLIENT)
    return client

def _parse_bool_env(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    v = str(v).strip().lower()
    return v not in ("0", "false", "no", "off", "")

_TRUST_ENV = _parse_bool_env("OPENAI_TRUST_ENV", True)
client = _set_openai_client(api_key=api_key, trust_env=_TRUST_ENV)
atexit.register(lambda: _OPENAI_HTTP_CLIENT.close() if _OPENAI_HTTP_CLIENT else None)

def _openai_responses_create_with_retry(params: dict, *, max_attempts: int | None = None):
    """
    Обёртка над client.responses.create:
    - ретраи на сетевые/временные ошибки
    - если включён trust_env и в окружении есть прокси, при TLS-ошибке через proxy
      пробуем один раз пересоздать клиента с trust_env=False (обход системных прокси)
    """
    attempts = int(os.getenv("OPENAI_MAX_RETRIES", "3")) if max_attempts is None else int(max_attempts)
    attempts = max(1, attempts)

    last_exc: Exception | None = None
    tried_no_env_proxy_fallback = False
    success = False

    try:
        for attempt in range(1, attempts + 1):
            try:
                resp = client.responses.create(**params)
                success = True
                return resp
            except (APIConnectionError, APITimeoutError) as ex:
                last_exc = ex

                # Частый кейс в Windows/корп-сетях: env-прокси ломает TLS-туннель.
                if _TRUST_ENV and _has_proxy_env() and not tried_no_env_proxy_fallback:
                    tried_no_env_proxy_fallback = True
                    print("🟠 OpenAI: обнаружены proxy env vars; пробую повторить запрос без trust_env (в обход системных прокси).")
                    _set_openai_client(api_key=api_key, trust_env=False)
                    continue

                if attempt >= attempts:
                    raise

                # backoff: 1s, 2s, 4s...
                delay_s = min(2 ** (attempt - 1), 8)
                print(
                    f"🟠 OpenAI: временная сетевая ошибка ({type(ex).__name__}: {ex}). "
                    f"Повтор через {delay_s}s (попытка {attempt}/{attempts})"
                )
                time.sleep(delay_s)
            except RateLimitError as ex:
                last_exc = ex
                if attempt >= attempts:
                    raise
                delay_s = min(2 ** (attempt - 1), 30)
                print(f"🟠 OpenAI: rate limit ({ex}). Повтор через {delay_s}s (попытка {attempt}/{attempts})")
                time.sleep(delay_s)
            except APIError:
                # Ошибки API обычно не лечатся ретраями (но иногда 5xx можно). Пока без ретраев.
                raise
    finally:
        # Если фоллбек на trust_env=False не помог — вернём клиента к исходной настройке,
        # чтобы не ломать последующие вызовы у тех, кому прокси всё-таки нужен.
        if tried_no_env_proxy_fallback and not success:
            try:
                _set_openai_client(api_key=api_key, trust_env=_TRUST_ENV)
            except Exception:
                pass

    if last_exc:
        raise last_exc
    raise RuntimeError("OpenAI request failed for unknown reason")


def _openai_responses_with_heartbeat(
    params: dict,
    *,
    max_attempts: int | None = None,
    heartbeat_interval_s: float = 5.0,
) -> "OpenAI.Response":
    """
    Запускает OpenAI-запрос в отдельном потоке и, пока ждём ответ,
    раз в heartbeat_interval_s пытается пушить скриншот Playwright в UI.

    Важно: пуш скриншота делается в текущем (owner) thread, чтобы не ловить greenlet.error.
    Если Playwright недоступен — просто игнорируем ошибку.
    """
    import threading
    import time as _time

    result_holder: dict[str, object] = {}
    error_holder: dict[str, BaseException] = {}
    done = threading.Event()

    def _worker():
        try:
            result_holder["resp"] = _openai_responses_create_with_retry(params, max_attempts=max_attempts)
        except BaseException as exc:  # noqa: BLE001
            error_holder["err"] = exc
        finally:
            done.set()

    t = threading.Thread(target=_worker, daemon=True, name="apsp_openai_request")
    t.start()

    last_push = _time.monotonic()
    interval = max(0.5, float(heartbeat_interval_s))

    while not done.wait(timeout=0.25):
        try:
            raise_if_stop_requested(None)
            raise_if_timeout()
        except Exception:
            # Прерываем ожидание по запросу пользователя.
            raise
        now = _time.monotonic()
        if now - last_push >= interval:
            last_push = now
            try:
                from playwright_tool.shared_page import maybe_push_screenshot_to_front  # noqa: WPS433

                maybe_push_screenshot_to_front(min_interval_ms=0, timeout_ms=2000)
            except Exception:
                # Не ломаем ожидание OpenAI, если Playwright недоступен.
                pass

    if "err" in error_holder:
        raise error_holder["err"]
    return result_holder.get("resp")



CHATGPT_HISTORY_PATH = ROOT_DIR / "ChatGPT_history.log"
CHATGPT_HISTORY_GLOBAL_PATH = ROOT_DIR / "ChatGPT_history_global.log"
CHAT_ID_PREFIX = "chat_"
MAX_MESSAGES_FOR_PROMPT = 10
SESSION_TTL_DAYS = 7
_SESSION_HISTORY_INITIALIZED = False


def _try_bump_new_page_2_timer_reset_seq() -> None:
    """
    Best-effort сигнал для фронта (`/main_page_2`): инкрементит `timer_reset_seq`
    в state-файле текущей задачи (UID) или (legacy) в `result_code_gen/result/new_page_2_state.json`,
    чтобы UI мог сбросить таймер.
    """
    try:
        import json
        import os

        # В многозадачном режиме (UID) пишем в RESULT_TASKS/<uid>/new_page_2_state.json
        # (контекст выставляется в `Apsp_front/app.py` через `set_current_task(...)`).
        try:
            from task_runtime.task_context import get_current_task_dir  # noqa: WPS433
        except Exception:
            get_current_task_dir = None

        task_dir = None
        try:
            task_dir = get_current_task_dir() if get_current_task_dir else None
        except Exception:
            task_dir = None

        if task_dir:
            state_path = task_dir / "new_page_2_state.json"
        else:
            state_path = ROOT_DIR / "result_code_gen" / "result" / "new_page_2_state.json"

        try:
            with state_path.open("r", encoding="utf-8") as f:
                state = json.load(f)
            if not isinstance(state, dict):
                state = {}
        except Exception:
            state = {}

        prev = state.get("timer_reset_seq")
        try:
            prev_int = int(str(prev)) if prev not in (None, "") else 0
        except Exception:
            prev_int = 0

        state["timer_reset_seq"] = str(prev_int + 1)

        state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = state_path.with_suffix(state_path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(str(tmp_path), str(state_path))
    except Exception:
        # Не ломаем основной пайплайн, если UI-сигнал не удалось записать
        return

#region Функции для работы с историей

class ChatGPTResult:
    # Обёртка над ответом: текст + chat_id + сырой ответ
    def __init__(self, answer: str, chat_id: str, raw_response):
        self.answer = answer
        self.chat_id = chat_id
        self.raw_response = raw_response

    def __repr__(self) -> str:
        return f"ChatGPTResult(chat_id='{self.chat_id}', answer={self.answer!r})"

    def __str__(self) -> str:
        return self.answer


def _count_tokens_for_messages(messages: list[dict], answer_text: str, model: str) -> tuple[int, int]:
    """
    Подсчитывает количество токенов для входных сообщений и ответа модели.
    Используем максимально простой подход — считаем токены по конкатенации контента всех сообщений.
    """
    try:
        tiktoken = importlib.import_module("tiktoken")
    except ImportError:
        raise ImportError("tiktoken не установлен")

    try:
        enc = tiktoken.encoding_for_model(model)
    except Exception:
        # Фоллбэк, если модель не найдена
        enc = tiktoken.get_encoding("cl100k_base")

    input_text = "\n".join(
        str(m.get("content", ""))
        for m in messages
        if isinstance(m, dict) and m.get("content") is not None
    )
    output_text = answer_text or ""

    input_tokens = len(enc.encode(input_text))
    output_tokens = len(enc.encode(output_text))
    return input_tokens, output_tokens


def _write_json_file(path: Path, payload):
    # Пишем JSON с ensure_ascii=False и отступами
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=4)


def _read_json_file(path: Path, default):
    # Читаем JSON, безопасно возвращая default при ошибке/отсутствии файла
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _ensure_session_history():
    # Гарантируем наличие файла сессии (очищается при старте модуля)
    global _SESSION_HISTORY_INITIALIZED
    if _SESSION_HISTORY_INITIALIZED:
        return
    _write_json_file(CHATGPT_HISTORY_PATH, [])
    _SESSION_HISTORY_INITIALIZED = True


def _load_session_history() -> list:
    # Загружаем историю текущей сессии
    _ensure_session_history()
    return _read_json_file(CHATGPT_HISTORY_PATH, [])


def _save_session_history(history: list):
    # Сохраняем историю текущей сессии
    _write_json_file(CHATGPT_HISTORY_PATH, history)


def _generate_chat_id() -> str:
    # Генерируем короткий chat_id
    return f"{CHAT_ID_PREFIX}{uuid4().hex[:8]}"


def _find_chat(history: list, chat_id: str):
    # Находим чат по идентификатору
    return next((c for c in history if c.get("chat_id") == chat_id), None)


def _append_message(chat: dict, role: str, content: str):
    # Добавляем сообщение в историю чата
    ts = int(time.time())
    chat.setdefault("messages", [])
    chat["messages"].append(
        {
            "index": len(chat["messages"]) + 1,
            "role": role,
            "content": content,
            "timestamp": ts,
            "datetime": datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M:%S"),
        }
    )


def build_api_messages(chat_messages: list[dict]) -> list[dict]:
    # Приводим внутренние сообщения к формату OpenAI API
    api_messages = []
    for msg in chat_messages:
        api_messages.append(
            {
                "role": msg["role"],
                "content": msg["content"],
            }
        )
    return api_messages


def _build_api_messages(chat: dict) -> list[dict]:
    # Берём последние сообщения (хвост) и добавляем системный промпт
    messages = chat.get("messages", [])
    if len(messages) > MAX_MESSAGES_FOR_PROMPT:
        print(f"⚠️ История чата {chat.get('chat_id')} превышает {MAX_MESSAGES_FOR_PROMPT} сообщений. Отправляем только последние.")
    tail = messages[-MAX_MESSAGES_FOR_PROMPT:]
    projected = build_api_messages(tail)
    system_prompt = chat.get("system_prompt") or system_prompts["neutral"]
    return [{"role": "system", "content": system_prompt}, *projected]


def init_new_chat(system_prompt: str | None = None, chat_id: str | None = None) -> str:
    # Создаём новый чат (или по заданному chat_id) и возвращаем его id
    history = _load_session_history()
    new_chat_id = chat_id or _generate_chat_id()
    chat_record = {
        "chat_id": new_chat_id,
        "created_at": int(time.time()),
        "system_prompt": system_prompt or system_prompts["neutral"],
        "messages": [],
    }
    history.append(chat_record)
    _save_session_history(history)
    return new_chat_id


def _persist_session_history_to_global():
    # Переносим сессионный лог в глобальный, удаляя сессии старше TTL
    try:
        session_history = _load_session_history()
        if not session_history:
            return

        cutoff = time.time() - SESSION_TTL_DAYS * 24 * 60 * 60
        fresh_sessions = [
            chat for chat in session_history if chat.get("created_at", 0) >= cutoff
        ]

        global_history = _read_json_file(CHATGPT_HISTORY_GLOBAL_PATH, [])
        global_history = [
            chat for chat in global_history if chat.get("created_at", 0) >= cutoff
        ]

        merged = {chat.get("chat_id"): chat for chat in global_history if chat.get("chat_id")}
        for chat in fresh_sessions:
            merged[chat["chat_id"]] = chat

        merged_list = list(merged.values())
        merged_list.sort(key=lambda c: c.get("created_at", 0), reverse=True)  # новые сверху

        _write_json_file(CHATGPT_HISTORY_GLOBAL_PATH, merged_list)
    except Exception as ex:
        print(f"⚠️ Не удалось сохранить глобальную историю ChatGPT: {ex}")


# Инициализируем файл истории при старте модуля
_ensure_session_history()
atexit.register(_persist_session_history_to_global)

#region Доп. функции

# # Получить все доступные модели
# models = client.models.list()

# for m in models.data:
#     print(m.id)




"""

Для размышлений и построения плана: o3
Универсальный агент: gpt-5.2
Для работы с кодом: gpt-5.1-codex-max
Для парсинга и анализа: gpt-5.2

Человечная и дружелюбная: gpt-4o

"""




# Системные роли:
"""

Ты опытный Python-разработчик
Ты reasoning-агент: разбивай задачи на шаги, проверяй промежуточные результаты и выдавай план действий.
Ты утка. Крякай на каждый вопрос

Задаётся как:
"input": [
    {
        "role": "system",
        "content": "Ты опытный Python-разработчик"
    },
    ...

"""


# Системные промпты
# (Без них модель может вести себя нестабильно, часто меняя стили общения)
"""
Рекомендуемый нейтральный

You are a helpful, accurate, and concise AI assistant.
Follow the user's instructions carefully.
If something is unclear or missing, ask for clarification.
Do not make up facts.

Вы - полезный, точный и лаконичный ИИ-помощник.
Внимательно следуйте инструкциям пользователя.
Если что-то непонятно или чего-то не хватает, попросите разъяснений.
Не придумывайте факты.




Версия для разработки

You are a precise and reliable AI assistant.
Provide clear, structured, and technically correct answers.
If you are unsure, say so explicitly.
Do not invent details or assumptions.

Вы - точный и надёжный ИИ-помощник.
Давайте чёткие, структурированные и технически правильные ответы.
Если вы не уверены, скажите об этом прямо.
Не придумывайте детали или предположения.




Нейтральный минимальный

You are an AI assistant.
Answer the user's questions to the best of your ability.

Вы - ИИ-помощник.
Отвечайте на вопросы пользователя в меру своих возможностей.
"""


system_prompts = {
    "neutral": """You are a helpful, accurate, and concise AI assistant.
Follow the user's instructions carefully.
If something is unclear or missing, ask for clarification.
Do not make up facts.""",
    "programming_neutral": """You are a precise and reliable AI assistant.
Provide clear, structured, and technically correct answers.
If you are unsure, say so explicitly.
Do not invent details or assumptions.""",
    "minimal": """You are an AI assistant.
Answer the user's questions to the best of your ability.""",
    "duck": "Ты утка. Крякай на каждый вопрос"
}



#region Основные функции

# Простой вариант использования API
def sendMessageToChatGPT_simple(prompt: str, is_print = True, model = "gpt-5.2"):
    if is_print:
        print(f"\n💫Запрос к ChatGPT, модель {model}\nPROMPT:\n{prompt}\n")

    start = time.time()
    response = _openai_responses_with_heartbeat(
        {
            "model": model,
            "input": prompt,
        }
    )

    if is_print:
        print(f'\n💬 AI ANSWER:\n"{response.output_text}"\n')
        emit_execution_time(start, emit=print)

    return response.output_text
    # print(response.output_text)


# result_request = sendMessageToChatGPT_simple(prompt = "Какой сейчас год?", is_print = True)
# sendMessageToChatGPT_for_history("Сколько будет 2+2?", model="gpt-4o")





# Запросы с историей разговора
def send_message_to_ChatGPT(
        prompt: str,                        # Запрос к нейросети
        is_print = True,                    # Печатать ли запрос и ответ в консоли
        model = "gpt-5.2",                  # Используемая модель
        temperature = None,                 # Задание температуры ответа [от 0 до 1.0]
        chat_id: str | None = None,         # Идентификатор чата с историей
        system_prompt: str | None = None    # Кастомный системный промпт для нового чата
    ):

    if not system_prompt:
        print("🟧🟧🟧 system_prompt не был задан 🟧🟧🟧") # Что бы не пропустить если где-то забуду его задать

    # Если chat_id не передан — работаем БЕЗ истории:
    # не читаем/не пишем ChatGPT_history.log и не подмешиваем старые сообщения.
    if not chat_id:
        start = time.time()
        params = {
            "model": model,
            "input": [
                {"role": "system", "content": system_prompt or system_prompts["neutral"]},
                {"role": "user", "content": prompt},
            ],
        }
        if temperature is not None:
            params["temperature"] = temperature

        response = _openai_responses_with_heartbeat(params)
        answer_text = response.output_text

        # Подсчёт токенов для входа/выхода
        try:
            input_tokens, output_tokens = _count_tokens_for_messages(params["input"], answer_text, model)
            global_variable.total_input_tokens += input_tokens
            global_variable.total_output_tokens += output_tokens
        except Exception as ex:
            print(f"⚠️ Не удалось посчитать токены: {ex}")

        if is_print:
            print(f"\n💫 Запрос к ChatGPT без истории, модель {model}. PROMPT:\n{prompt}\n")

        if is_print:
            print(f'💬 AI ANSWER:\n"{answer_text}"')
            emit_execution_time(start, emit=print, print_time_smile=False)
            print(f"\n")

        # chat_id пустой, т.к. историю мы не вели
        _try_bump_new_page_2_timer_reset_seq()
        return ChatGPTResult(answer=answer_text, chat_id="", raw_response=response)

    history = _load_session_history()

    if chat_id:
        chat = _find_chat(history, chat_id)
        if not chat:
            chat_id = init_new_chat(system_prompt=system_prompt, chat_id=chat_id)
            history = _load_session_history()
            chat = _find_chat(history, chat_id)

    if chat is None:
        raise RuntimeError("Не удалось инициализировать чат для истории.")

    if system_prompt:
        chat["system_prompt"] = system_prompt

    start = time.time()
    _append_message(chat, "user", prompt)

    params = {
        "model": model,
        "input": _build_api_messages(chat)
    }
    if temperature is not None:
        params["temperature"] = temperature

    response = _openai_responses_with_heartbeat(params)
    answer_text = response.output_text

    # Подсчёт токенов для входа/выхода
    try:
        input_tokens, output_tokens = _count_tokens_for_messages(params["input"], answer_text, model)
        global_variable.total_input_tokens += input_tokens
        global_variable.total_output_tokens += output_tokens
    except Exception as ex:
        print(f"⚠️ Не удалось посчитать токены: {ex}")

    _append_message(chat, "assistant", answer_text)
    _save_session_history(history)

    if is_print:
        print(f"\n💫 Запрос к ChatGPT с историей, модель {model}, чат {chat_id}. PROMPT:\n{prompt}\n")

    if is_print:
        print(f'💬 AI ANSWER:\n"{answer_text}"')
        emit_execution_time(start, emit=print, print_time_smile=False)
        print(f"\n\n")

    _try_bump_new_page_2_timer_reset_seq()
    return ChatGPTResult(answer=answer_text, chat_id=chat_id, raw_response=response)






#region Использование


# # Запрос с историей
# chat_id = init_new_chat()
# result_request = send_message_to_ChatGPT("Какая самая высокая гора на земле?", chat_id=chat_id)
# result_request = send_message_to_ChatGPT("Когда люди впервые открыли эту гору?", chat_id=chat_id)


# # Простой запрос, без истории
# result_request = send_message_to_ChatGPT("Какая температура солнца?")
# result_request = send_message_to_ChatGPT("В чём обычно измеряют температуру?")


# # Запрос с историей
# result_request = send_message_to_ChatGPT("Какая температура солнца?")
# send_message_to_ChatGPT("В чём обычно измеряют температуру в верхнем слое?", chat_id=result_request.chat_id)



my_prompt_old = """
You are an information-structuring agent.

You receive a list of product fields grouped by sections.
Each field is provided as: 
"field_key": "short russian description"

Your task is to convert this list into a structured JSON object with the following format:

{
  "main": { ... },
  "additional": { ... },
  ...
}

You must preserve all group names and the grouping order exactly as provided.
Fields must be placed inside the same group where they were originally listed.

For each field you must generate an object with the following properties:

- title  
  Use the original short description exactly as provided.

- description  
  Write a more detailed explanation of what this field represents in an online shop product page.
  Include, when possible:
  • what the value means  
  • how it usually looks  
  • where it is typically located on the page (for example: title, h1, product card, near buy button, etc.)

- examples  
  Provide 3–6 realistic example values that could appear in this field on real product pages.

- negative_examples  
  Provide 3–6 realistic values that may appear on the page but should NOT be treated as this field.

- selector_hint  
  Provide 3–5 CSS selector patterns that are commonly used on real sites for this type of data.
  These must be short, generic and reusable (for example: ".price", ".product-title", "[itemprop=name]").

- relations (optional)  
  If this field has logical or semantic relations to other fields (for example price vs oldprice, stock vs availableCount, etc),
  describe them in natural language here.
  If no clear relations exist, omit this property.

Rules:

1. Do NOT invent or rename any field keys.
2. Do NOT move fields between groups.
3. Do NOT remove any fields.
4. Do NOT add new fields that were not provided.
5. Do NOT include type, unit, currency, priority or any technical metadata.
6. Use concise, clear, technical Russian.
7. Output ONLY valid JSON. No comments, no explanations, no markdown.

The goal is to produce a compact but semantically rich schema that allows an LLM-based parser to locate and validate these fields on real product pages.

FIELDS:


+
Основные параметры:
"name": "Наименование товара",
"stock": "Наличие товара",
"imageLink": "Ссылка на фото товара",
"article": "Артикул",
"product_id": "Код товара",
"category": "Категория",
"brand": "Бренд",
"manufacturer": "Производитель",
"model": "Модель",
"description": "Описание товара",

Цены и скидки:
"price": "Цена",
"oldprice": "Старая цена",
"price_discount": "Акционная цена",
"card_price": "Цена по дисконтной карте",
"cashback": "Кешбек \ Бонусы",
"currency": "Валюта",
"vat": "Признак включен ли НДС в указанную цену",
"promotionDate": "Дата окончания действия акции",




+
Склад и наличие:
"availibility": "Статус товара",
"availableCount": "Кол-во товара в наличии",

Идентификация:
"barcode": "Штрихкод",
"ean": "Международный артикул",
"oem": "OEM-номер",
"partNumber": "Партномер (артикул производителя)",





Характеристики:
"color": "Цвет товара",
"material": "Материал",
"collection": "Коллекция товара",
"series": "Серия",
"aromaName": "Аромат",
"uom": "Единица измерения",
"count": "Кол-во товара в упаковке",
"equipment": "Комплектация и измерения/кол-во товаров",
"packaging": "Упаковка",

Габариты и вес:
"weight": "Вес товара",
"volume": "Объём товара",
"size": "Размер товара",
"length": "Длина",
"width": "Ширина",
"height": "Высота",
"diameter": "Диаметр",





Статистика и рейтинги:
"rating": "Рейтинг товара / Кол-во звездочек",
"seller_rating": "Рейтинг товара / Кол-во звездочек",
"reviewsCount": "Количество отзывов",
"ordersCount": "Количество заказов",
"users": "Кол-во пользователей",

Локация и доставка:
"region": "Регион",
"address": "Адрес магазина",
"shop": "Название магазина",
"deliveryDays": "Срок доставки в днях",
"deliveryDate": "Дата доставки",
"deliveryPrice": "Стоимость доставки",
"deliveryAddress": "Адрес доставки",
"breadCrumbs": "Поисковая цепочка",







Юридические данные и продавцы:
"seller": "Продавец",
"shopLink": "Ссылка на магазин",
"sellerLink": "Ссылка на продавца",
"sellerName": "Юридическое название продавца",
"supplierName": "Юридическое название продавца",
"sellerINN": "ИНН продавца",
"sellerORGN": "ОГРН/ОГРНИП продавца",
"sellerAddress": "Адрес продавца",

Аптечные товары:
"releaseForm": "Форма выпуска(мазь,пилюли)",
"dosage": "Дозировка лекарства",






Книжные поля:
"bookype": "Тип книги",
"isbn": "Международный стандартный книжный номер",
"coverType": "Тип обложки",
"publishYear": "Год выпуска",
"pages": "Количество страниц",
"publisher": "Издательство",
"author": "Автор",




Техника и оборудование:
"ram": "Объем оперативной памяти",
"rom": "Объем постоянной памяти",
"voltage": "Напряжение (В)",
"torque": "Максимальный крутящий момент (Н·м)",
"battery_capacity": "Емкость аккумулятора",
"speeds_count": "Количество скоростей",
"bullet_diameter": "Диаметр патрона",
"disk_diameter": "Диаметр диска (мм)",
"power": "Мощность",
"speed_regulation": "Регулировка скорости",
"constant_speed": "Поддержание постоянных оборотов под нагрузкой",
"revolutions": "Число оборотов",






Промышленное / Прочее:
"kcal_100": "Пищевая ценность на 100 г",
"profile_number": "Номер профиля",
"steel_mark": "Марка стали",



"""


if __name__ == "__main__":
    my_prompt = """
    Привет, расскажи интересный факт про звёзды
    """

    result_request = send_message_to_ChatGPT(
            prompt = my_prompt,
            is_print = True,
            model = "gpt-4o",
            # model = "gpt-5.2",
            temperature = 0.15
        )







# Промат для генерации описаний для полей

""" 
You are an information-structuring agent.

You receive a list of product fields grouped by sections.
Each field is provided as: 
"field_key": "short russian description"

Your task is to convert this list into a structured JSON object with the following format:

{
  "required": { ... },
  "additional": { ... },
  "other_groups_if_present": { ... }
}

You must preserve all group names and the grouping order exactly as provided.
Fields must be placed inside the same group where they were originally listed.

For each field you must generate an object with the following properties:

- title  
  Use the original short description exactly as provided.

- description  
  Write a more detailed explanation of what this field represents in an online shop product page.
  Include, when possible:
  • what the value means  
  • how it usually looks  
  • where it is typically located on the page (for example: title, h1, product card, near buy button, etc.)

- examples  
  Provide 3–6 realistic example values that could appear in this field on real product pages.

- negative_examples  
  Provide 3–6 realistic values that may appear on the page but should NOT be treated as this field.

- selector_hint  
  Provide 3–5 CSS selector patterns that are commonly used on real sites for this type of data.
  These must be short, generic and reusable (for example: ".price", ".product-title", "[itemprop=name]").

- relations (optional)  
  If this field has logical or semantic relations to other fields (for example price vs oldprice, stock vs availableCount, etc),
  describe them in natural language here.
  If no clear relations exist, omit this property.

Rules:

1. Do NOT invent or rename any field keys.
2. Do NOT move fields between groups.
3. Do NOT remove any fields.
4. Do NOT add new fields that were not provided.
5. Do NOT include type, unit, currency, priority or any technical metadata.
6. Use concise, clear, technical Russian.
7. Output ONLY valid JSON. No comments, no explanations, no markdown.

The goal is to produce a compact but semantically rich schema that allows an LLM-based parser to locate and validate these fields on real product pages.

"""



""" 
Дополнительные:
"breadCrumbs": "Поисковая цепочка",
"deliveryDays": "Срок доставки в днях",
"rating": "Рейтинг товара / Кол-во звездочек",
"color": "Цвет товара",
"material": "Материал",
"collection": "Коллекция товара",
"series": "Серия",

Габариты и вес:
"weight": "Вес товара",
"volume": "Объём товара",
"size": "Размер товара",
"length": "Длина",
"width": "Ширина",
"height": "Высота",
"diameter": "Диаметр",

"""