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
from dataclasses import dataclass
from typing import Any
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Подключение всех библиотек и функций
from import_all_libraries import *
from ChatGPT.OpenAI_ChatGPT import send_message_to_ChatGPT





# 1. Мир (Environment)
FILES = {
    "notes.txt": "Встреча в пятницу. Купить хлеб. Проверить отчёт.",
    "todo.txt": "Срочно: отправить письмо Алексею. Подготовить презентацию.",
    "archive.txt": "Старые заметки за 2022 год."
}



# 2. Инструменты (Tool Layer)
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



# 3. Реестр инструментов (встроен сюда, т.к. это тестовая реализация)
@dataclass(frozen=True)
class ToolArgSpec:
    name: str
    type: str  # простой "человекочитаемый" тип (str/int/bool/json)
    required: bool
    description: str


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    args: tuple[ToolArgSpec, ...]
    returns: str
    example_args: dict[str, Any] | None = None


TOOLS: dict[str, ToolSpec] = {
    "list_files": ToolSpec(
        name="list_files",
        description="Вернуть список доступных файлов в окружении.",
        args=(),
        returns='JSON: {"files": ["notes.txt", "..."]}',
        example_args={},
    ),
    "read_file": ToolSpec(
        name="read_file",
        description="Прочитать содержимое файла по имени.",
        args=(
            ToolArgSpec(
                name="filename",
                type="str",
                required=True,
                description="Имя файла из списка, полученного через list_files.",
            ),
        ),
        returns='JSON: {"status":"ok","filename":"...","content":"..."} или {"status":"error","error":"..."}',
        example_args={"filename": "todo.txt"},
    ),
    "search": ToolSpec(
        name="search",
        description="Найти вхождения подстроки query в тексте text (регистронезависимо).",
        args=(
            ToolArgSpec(
                name="text",
                type="str",
                required=True,
                description="Текст, в котором выполняется поиск (обычно content из read_file).",
            ),
            ToolArgSpec(
                name="query",
                type="str",
                required=True,
                description="Подстрока для поиска.",
            ),
        ),
        returns='JSON: {"found": true/false, "positions": [0, 15, ...]}',
        example_args={"text": "<content from read_file>", "query": "презентац"},
    ),
    "DONE": ToolSpec(
        name="DONE",
        description="Завершить работу и вернуть финальный ответ.",
        args=(),
        returns='JSON: {"final_answer":"..."}',
        example_args={},
    ),
}


def allowed_actions() -> set[str]:
    return set(TOOLS.keys())


def render_tools_for_prompt(tools: dict[str, ToolSpec] | None = None) -> str:
    """
    Человекочитаемое описание инструментов для system prompt.
    Держим в одном месте, чтобы prompt и валидация не расходились.
    """
    tools = tools or TOOLS
    lines: list[str] = []
    lines.append("Доступные действия (tools):")
    for name, spec in tools.items():
        lines.append(f"- {name}: {spec.description}")
        if spec.args:
            lines.append("  args:")
            for a in spec.args:
                req = "обязательный" if a.required else "опциональный"
                lines.append(f"  - {a.name} ({a.type}, {req}): {a.description}")
        else:
            lines.append("  args: (нет)")
        lines.append(f"  returns: {spec.returns}")
        if spec.example_args is not None:
            lines.append(f"  example args: {spec.example_args}")
    return "\n".join(lines)


def render_tools_compact_for_prompt(tools: dict[str, ToolSpec] | None = None) -> str:
    """Компактная версия для вставки в user prompt на каждом шаге."""
    tools = tools or TOOLS
    lines: list[str] = []
    for name, spec in tools.items():
        if spec.args:
            sig = ", ".join(a.name for a in spec.args)
            lines.append(f"- {name}({sig}): {spec.description}")
        else:
            lines.append(f"- {name}: {spec.description}")
    return "\n".join(lines)


def validate_llm_action(
    payload: dict[str, Any],
    tools: dict[str, ToolSpec] | None = None,
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

    # DONE: требуем final_answer
    if action == "DONE":
        fa = payload.get("final_answer")
        if not isinstance(fa, str) or not fa.strip():
            return False, "For action DONE, field 'final_answer' must be a non-empty string."
        return True, ""

    args = payload.get("args", {})
    if args is None:
        args = {}
    if not isinstance(args, dict):
        return False, "Field 'args' must be an object/dict."

    spec = tools[action]
    required_args = [a.name for a in spec.args if a.required]
    missing = [name for name in required_args if name not in args]
    if missing:
        return False, f"Missing required args for action '{action}': {missing}"

    # Лёгкая проверка типов для str (чтобы ловить совсем неверные форматы)
    for a in spec.args:
        if a.name not in args:
            continue
        if a.type == "str" and not isinstance(args[a.name], str):
            return False, f"Arg '{a.name}' must be str."

    return True, ""


# 4. Контракт действий
ALLOWED_ACTIONS = allowed_actions()


# 5. System Prompt (генерируется из реестра инструментов)
SYSTEM_PROMPT = f"""
Ты — reasoning-агент. У тебя есть два источника данных:
- memory: свободный key-value словарь, который ты можешь обновлять через update_memory.
- history: список прошлых шагов (thought/action/args/observation/update_memory).

{render_tools_for_prompt(TOOLS)}

Контракт:
- Отвечай СТРОГО в JSON.
- Один ответ — одно действие.
- Никакого текста вне JSON.
- Если цель достигнута — верни action = DONE и финальный ответ в final_answer.

Формат ответа:
{{
  "thought": "...",
  "action": "...",
  "args": {{ ... }},
  "update_memory": {{ ... }},   # что добавить/обновить в memory (опционально)
  "final_answer": "..."        # только если action == DONE
}}
"""


HISTORY_WINDOW = 10  # сколько последних шагов отдаём в LLM
MAX_STEPS = 20

# Задача агента
user_goal = "Найти, в каком файле идёт речь про презентацию"


# 5. Состояние агента: гибкая память и история
state = {
    "memory": {},      # свободное key-value хранилище, агент сам решает, что писать
    "history": [],     # список шагов: thought/action/args/observation/update_memory
    "chat_id": None,   # id чата для send_message_to_ChatGPT
}


# 6. Вспомогательные функции
def merge_memory(state: dict, updates: dict | None):
    """Безопасно мёрджим обновления в memory."""
    if not updates:
        return
    state["memory"].update(updates)


def call_llm(state: dict):
    """
    Делает шаг агента через ChatGPT.
    Возвращает dict с полями thought/action/args/(update_memory)/final_answer.
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
        chat_id=state["chat_id"]
    )
    state["chat_id"] = result.chat_id

    try:
        return json.loads(result.answer)
    except Exception as ex:
        # Фолбэк, чтобы не зациклиться при ошибке парсинга
        return {
            "action": "DONE",
            "final_answer": f"LLM parse error: {ex}; raw={result.answer}"
        }


# 7. Оркестратор
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
            print(response.get("final_answer"))
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