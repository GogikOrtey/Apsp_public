#region Импорты и инициализация

# Чтобы при запуске файла из папки New/ были видны модули из корня проекта (addedFunc.py и др.)
### Потом убрать, что бы было нормально
from pathlib import Path
import sys
import os
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Подключение всех библиотек и функций
from import_all_libraries import * 

# Заружаем ключ OpenAI и инициализируем клиент
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_AI_API_KEY")
if not api_key:
    raise RuntimeError(
        "OpenAI API key not found. Add OPEN_AI_API_KEY to your .env file"
    )

client = OpenAI(
    api_key=api_key
)



CHATGPT_HISTORY_PATH = ROOT_DIR / "ChatGPT_history.log"
CHATGPT_HISTORY_GLOBAL_PATH = ROOT_DIR / "ChatGPT_history_global.log"
CHAT_ID_PREFIX = "chat_"
MAX_MESSAGES_FOR_PROMPT = 10
SESSION_TTL_DAYS = 7
_SESSION_HISTORY_INITIALIZED = False

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


def _write_json_file(path: Path, payload):
    # Пишем JSON с ensure_ascii=False и отступами
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


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
    response = client.responses.create(
        model=model,
        input=prompt
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
    history = _load_session_history()

    if chat_id:
        chat = _find_chat(history, chat_id)
        if not chat:
            chat_id = init_new_chat(system_prompt=system_prompt, chat_id=chat_id)
            history = _load_session_history()
            chat = _find_chat(history, chat_id)
    else:
        chat_id = init_new_chat(system_prompt=system_prompt)
        history = _load_session_history()
        chat = _find_chat(history, chat_id)

    if chat is None:
        raise RuntimeError("Не удалось инициализировать чат для истории.")

    if system_prompt:
        chat["system_prompt"] = system_prompt

    if is_print:
        print(f"\n💫 Запрос к ChatGPT с историей, модель {model}, чат {chat_id}. PROMPT:\n{prompt}\n")

    start = time.time()
    _append_message(chat, "user", prompt)

    params = {
        "model": model,
        "input": _build_api_messages(chat)
    }
    if temperature is not None:
        params["temperature"] = temperature

    response = client.responses.create(**params)
    answer_text = response.output_text

    _append_message(chat, "assistant", answer_text)
    _save_session_history(history)

    if is_print:
        print(f'💬 AI ANSWER:\n"{answer_text}"')
        emit_execution_time(start, emit=print, print_time_smile=False)
        print(f"\n\n")

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
















