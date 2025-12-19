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
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Подключение всех библиотек и функций
from import_all_libraries import *
from ChatGPT.OpenAI_ChatGPT import send_message_to_ChatGPT
from reasoning_agent.tool_registry import (
    TOOLS,
    allowed_actions,
    render_tools_for_prompt,
    render_tools_compact_for_prompt,
    validate_llm_action,
)





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



# 3. Контракт действий (единый источник — reasoning_agent/tool_registry.py)
ALLOWED_ACTIONS = allowed_actions()


# 4. System Prompt (генерируется из реестра инструментов)
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
{
  "thought": "...",
  "action": "...",
  "args": { ... },
  "update_memory": { ... },   # что добавить/обновить в memory (опционально)
  "final_answer": "..."        # только если action == DONE
}
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