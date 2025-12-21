# [ВАЖНО]: Это простой пример. Не используй код из этого файла как пример, скорее всего в этом файле плохой код

"""
Простой пример reasoning-агента.

Цель: найти, в каком файле идёт речь про презентацию.

Ключевые изменения:
- нет жёсткой структуры state (current_file/checked_files и т.п.)
- есть свободная память memory, которую агент может обновлять сам
- в историю history пишем thought/action/args/observation/update_memory
"""

# Чтобы при запуске файла из этой папки были видны модули из корня проекта (addedFunc.py и др.)
### Потом убрать, что бы было нормально
from pathlib import Path
import sys
import os
import json
from typing import Any
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Подключение всех библиотек и функций
from import_all_libraries import *
from ChatGPT.OpenAI_ChatGPT import send_message_to_ChatGPT





# region 1. Мир (Environment)
FILES = {
    "notes.txt": "Встреча в пятницу. Купить хлеб. Проверить отчёт.",
    "todo.txt": "Срочно: отправить письмо Алексею. Подготовить презентацию.",
    "archive.txt": "Старые заметки за 2022 год."
}



# region 2. Инструменты (Tool Layer)
class Tools:
    def __init__(self, files: dict):
        self.files = files

    def list_files(self):
        return {
            "files": list(self.files.keys())
        }

    def read_file(self, filename: str):
        if filename not in self.files:
            return {
                "status": "error",
                "error": f"File not found: {filename}"
            }
        return {
            "status": "ok",
            "filename": filename,
            "content": self.files[filename]
        }

    def search(self, text: str, query: str):
        positions = []
        start = 0
        while True:
            idx = text.lower().find(query.lower(), start)
            if idx == -1:
                break
            positions.append(idx)
            start = idx + 1

        return {
            "found": len(positions) > 0,
            "positions": positions
        }



# region 3. Реестр инструментов 
# (встроен сюда, т.к. это тестовая реализация)
# Формат специально сделан JSON-friendly: это обычный dict/list, который можно
# напрямую отдавать в prompt или сериализовать через json.dumps(...).
TOOLS: dict[str, dict[str, Any]] = {
    "list_files": {
        "name": "list_files",
        "description": "Вернуть список доступных файлов в окружении.",
        "args": [],
        "returns": 'JSON: {"files": ["notes.txt", "..."]}',
        "example_args": {},
    },
    "read_file": {
        "name": "read_file",
        "description": "Прочитать содержимое файла по имени.",
        "args": [
            {
                "name": "filename",
                "type": "str", 
                "required": True,
                "description": "Имя файла из списка, полученного через list_files.",
            },
        ],
        "returns": 'JSON: {"status":"ok","filename":"...","content":"..."} или {"status":"error","error":"..."}',
        "example_args": {"filename": "todo.txt"},
    },
    "search": {
        "name": "search",
        "description": "Найти вхождения подстроки query в тексте text (регистронезависимо).",
        "args": [
            {
                "name": "text",
                "type": "str",
                "required": True,
                "description": "Текст, в котором выполняется поиск (обычно content из read_file).",
            },
            {
                "name": "query",
                "type": "str",
                "required": True,
                "description": "Подстрока для поиска.",
            },
        ],
        "returns": 'JSON: {"found": true/false, "positions": [0, 15, ...]}',
        "example_args": {"text": "<content from read_file>", "query": "презентац"},
    },
    "DONE": {
        "name": "DONE",
        "description": "Завершить работу и вернуть финальный ответ.",
        "args": [
            {
                "name": "final_answer",
                "type": "str",
                "required": True,
                "description": "Финальный ответ пользователю.",
            },
        ],
        "returns": "(завершение): args.final_answer будет выведен как итоговый ответ",
        "example_args": {"final_answer": "Про презентацию говорится в файле todo.txt."},
    },
}


def allowed_actions() -> set[str]:
    return set(TOOLS.keys())


def render_tools_for_prompt(tools: dict[str, dict[str, Any]] | None = None) -> str:
    """
    Человекочитаемое описание инструментов для system prompt.
    Держим в одном месте, чтобы prompt и валидация не расходились.
    """
    tools = tools or TOOLS
    lines: list[str] = []
    lines.append("Доступные действия (tools):")
    for name, spec in tools.items():
        lines.append(f"- {name}: {spec.get('description')}")
        args = spec.get("args") or []
        if args:
            lines.append("  args:")
            for a in args:
                req = "обязательный" if a.get("required") else "опциональный"
                lines.append(f"  - {a.get('name')} ({a.get('type')}, {req}): {a.get('description')}")
        else:
            lines.append("  args: (нет)")
        lines.append(f"  returns: {spec.get('returns')}")
        if spec.get("example_args", None) is not None:
            lines.append(f"  example args: {spec.get('example_args')}")
    return "\n".join(lines)


def render_tools_compact_for_prompt(tools: dict[str, dict[str, Any]] | None = None) -> str:
    """Компактная версия для вставки в user prompt на каждом шаге."""
    tools = tools or TOOLS
    lines: list[str] = []
    for name, spec in tools.items():
        args = spec.get("args") or []
        if args:
            sig = ", ".join((a or {}).get("name", "?") for a in args)
            lines.append(f"- {name}({sig}): {spec.get('description')}")
        else:
            lines.append(f"- {name}: {spec.get('description')}")
    return "\n".join(lines)


def validate_llm_action(
    payload: dict[str, Any],
    tools: dict[str, dict[str, Any]] | None = None,
) -> tuple[bool, str]:
    """
    Минимальная структурная валидация ответа LLM под наш контракт.
    Возвращает (ok, error_message).
    """
    tools = tools or TOOLS

    action = payload.get("action")
    if not isinstance(action, str):
        return False, "Field 'action' must be a string."

    if action not in tools:
        return False, f"Unknown action: {action}. Allowed: {sorted(tools.keys())}"

    args = payload.get("args", {})
    if args is None:
        args = {}
    if not isinstance(args, dict):
        return False, "Field 'args' must be an object/dict."

    # DONE: требуем args.final_answer
    if action == "DONE":
        fa = args.get("final_answer")
        if not isinstance(fa, str) or not fa.strip():
            return False, "For action DONE, arg 'final_answer' must be a non-empty string."
        return True, ""

    spec = tools[action]
    spec_args = spec.get("args") or []
    required_args = [(a or {}).get("name") for a in spec_args if (a or {}).get("required")]
    required_args = [n for n in required_args if isinstance(n, str) and n]
    missing = [name for name in required_args if name not in args]
    if missing:
        return False, f"Missing required args for action '{action}': {missing}"

    # Лёгкая проверка типов для str (чтобы ловить совсем неверные форматы)
    for a in spec_args:
        arg_name = (a or {}).get("name")
        arg_type = (a or {}).get("type")
        if not isinstance(arg_name, str) or not arg_name:
            continue
        if arg_name not in args:
            continue
        if arg_type == "str" and not isinstance(args[arg_name], str):
            return False, f"Arg '{arg_name}' must be str."

    return True, ""


# region 4. Контракт действий
ALLOWED_ACTIONS = allowed_actions()


# region 5. System Prompt (генерируется из реестра инструментов)
SYSTEM_PROMPT = f"""
Ты — reasoning-агент. У тебя есть два источника данных:
- memory: свободный key-value словарь, который ты можешь обновлять через update_memory.
- history: список прошлых шагов (thought/action/args/observation/update_memory).

{render_tools_for_prompt(TOOLS)}

Контракт:
- Отвечай СТРОГО в JSON: один top-level JSON-объект.
- РОВНО одно действие за ответ (один шаг).
- Никакого текста вне JSON, никаких markdown-блоков, никаких пояснений.
- НЕ ПИШИ результаты/наблюдения инструментов (например {{"files":[...]}} или {{"status":"ok",...}}) — их возвращает система, не ты.
- НЕ ПИШИ несколько JSON подряд. Если хочешь сделать несколько шагов — выбери только следующий шаг.
- Если цель достигнута — верни action = DONE и финальный ответ в args.final_answer.

Формат ответа:
{{
  "thought": "...",
  "action": "...",
  "args": {{ ... }},
  "update_memory": {{ ... }},   # что добавить/обновить в memory (опционально)
}}

Невалидно (запрещено):
- два JSON подряд: {{...}}{{...}}
- JSON + "наблюдение инструмента": {{...}}{{"files":[...]}}
- любой текст вне JSON

Валидно (ровно один объект):
{{
    "thought":"...",
    "action":"list_files",
    "args":{{}}
}}
"""


# region 6. Параметры
HISTORY_WINDOW = 10  # сколько последних шагов отдаём в LLM
MAX_STEPS = 20

# Задача агента
user_goal = "Найти, в каком файле идёт речь про презентацию"


# 5. Состояние агента: гибкая память и история
state = {
    "memory": {},      # свободное key-value хранилище, агент сам решает, что писать
    "history": [],     # список шагов: thought/action/args/observation/update_memory
    # "chat_id": None,   # id чата для send_message_to_ChatGPT
}


# 6. Вспомогательные функции
def merge_memory(state: dict, updates: dict | None):
    """Безопасно мёрджим обновления в memory."""
    if not updates:
        return
    state["memory"].update(updates)


def parse_llm_json_action(answer_text: str) -> dict[str, Any]:
    """
    По контракту LLM должен вернуть один JSON-объект.
    На практике иногда возвращается несколько JSON подряд (например: {...}{...}{...}),
    из-за чего json.loads падает с ошибкой `Extra data`.

    Здесь мы извлекаем первый top-level JSON-объект, содержащий поле 'action'.
    """
    s = (answer_text or "").strip()

    # Если модель завернула JSON в code fence, попробуем вытащить содержимое между ```
    if "```" in s:
        parts = s.split("```")
        if len(parts) >= 3:
            s = max(parts[1::2], key=len).strip()

    # Быстрый путь: валидный одиночный JSON
    try:
        payload = json.loads(s)
        if isinstance(payload, dict) and isinstance(payload.get("action"), str):
            return payload
    except Exception:
        pass

    decoder = json.JSONDecoder()
    idx = 0
    while idx < len(s):
        start = s.find("{", idx)
        if start == -1:
            break
        try:
            obj, end = decoder.raw_decode(s, start)
            if isinstance(obj, dict) and isinstance(obj.get("action"), str):
                return obj
            idx = end
        except Exception:
            idx = start + 1

    raise ValueError("Could not parse a valid JSON action payload from LLM output.")


def call_llm(state: dict):
    """
    Делает шаг агента через ChatGPT.
    Возвращает dict с полями thought/action/args/(update_memory).
    Для action == DONE финальный ответ должен быть в args.final_answer.
    """
    recent_history = state["history"][-HISTORY_WINDOW:]
    memory_json = json.dumps(state["memory"], ensure_ascii=False, indent=2)
    history_json = json.dumps(recent_history, ensure_ascii=False, indent=2)

    prompt = f"""
Цель: {user_goal}

Memory (свободное key-value хранилище, обновляется через update_memory):
{memory_json}

Недавние шаги (последние {HISTORY_WINDOW}):
{history_json}

Напоминание по инструментам:
{render_tools_compact_for_prompt(TOOLS)}

Выбери следующее действие из {list(ALLOWED_ACTIONS)}.
Ответь строго в JSON по контракту system prompt.
"""

    result = send_message_to_ChatGPT(
        prompt=prompt,
        is_print=True,
        model="gpt-5.2",
        temperature=0.1,
        system_prompt=SYSTEM_PROMPT,
        # chat_id=state["chat_id"]
    )
    # state["chat_id"] = result.chat_id

    try:
        payload = parse_llm_json_action(result.answer)
        # Нормализация под новый контракт: final_answer должен быть аргументом DONE.
        if isinstance(payload, dict) and payload.get("action") == "DONE":
            args = payload.get("args")
            if args is None or not isinstance(args, dict):
                args = {}
                payload["args"] = args
            if "final_answer" not in args and isinstance(payload.get("final_answer"), str):
                args["final_answer"] = payload["final_answer"]
        return payload
    except Exception as ex:
        # Фолбэк, чтобы не зациклиться при ошибке парсинга
        return {
            "action": "DONE",
            "args": {
                "final_answer": f"LLM parse error: {ex}; raw={result.answer}"
            },
        }


# region 7. Оркестратор
def run_agent():
    tools = Tools(FILES)

    for step in range(MAX_STEPS):
        response = call_llm(state)
        action = response.get("action")

        ok, err = validate_llm_action(response, TOOLS)
        if not ok:
            raise ValueError(f"Invalid LLM response: {err}; payload={response}")

        observation = {}

        if action == "DONE":
            print("\n=== DONE ===")
            print((response.get("args") or {}).get("final_answer"))
            break

        if action == "list_files":
            observation = tools.list_files()

        elif action == "read_file":
            filename = response.get("args", {}).get("filename")
            observation = tools.read_file(filename)

        elif action == "search":
            text = response.get("args", {}).get("text", "")
            query = response.get("args", {}).get("query", "")
            observation = tools.search(text, query)

        # Обновляем память, если агент прислал update_memory
        merge_memory(state, response.get("update_memory"))

        # Сохраняем шаг в историю (LLM видит только хвост в prompt)
        state["history"].append({
            "thought": response.get("thought"),
            "action": action,
            "args": response.get("args", {}),
            "observation": observation,
            "update_memory": response.get("update_memory", {})
        })

        print(f"\nAction: {action}")
        print(f"Observation: {observation}")
        print(f"Memory: {state['memory']}")
    else:
        print("\n=== DONE ===")
        print("Достигнут лимит шагов, остановка.")


run_agent()