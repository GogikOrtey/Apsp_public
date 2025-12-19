"""

Простой пример reasoning-агента

Здесь ему нужно будет найти, в каком файле идёт речь про презентацию

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



# 3. Контракт действий
ALLOWED_ACTIONS = {
    "list_files",
    "read_file",
    "search",
    "DONE"
}


# 4. System Prompt
SYSTEM_PROMPT = """
Ты — reasoning-агент.

Ты можешь использовать ТОЛЬКО следующие действия:
- list_files
- read_file(filename)
- search(text, query)
- DONE

Правила:
- Отвечай СТРОГО в JSON
- Один ответ — одно действие
- Никакого текста вне JSON
- Если цель достигнута — верни action = DONE

Формат ответа:

{
  "thought": "...",
  "action": "...",
  "args": { ... }
}
"""


# Задача агента
user_goal = """
Найти, в каком файле идёт речь про презентацию
"""


# 5. Состояние агента
state = {
    "files": [],
    "current_file": None,
    "current_content": None,
    "checked_files": set(),
    "found_result": None
}


# 6. Вызов LLM
def call_llm(state):
    """
    Делает шаг агента через ChatGPT.
    Возвращает dict с полями thought/action/args/final_answer.
    """
    prompt = f"""
Текущая задача: {user_goal.strip()}

Текущее состояние:
- files: {state["files"]}
- checked_files: {list(state["checked_files"])}
- current_file: {state["current_file"]}
- current_content: {state["current_content"]}
- found_result: {state["found_result"]}

Выбери следующее действие из {list(ALLOWED_ACTIONS)}.
Строго следуй контракту: JSON без дополнительного текста.
action обязательно из {list(ALLOWED_ACTIONS)}.
Если цель достигнута — верни action = DONE и финальный ответ в final_answer.
"""

    result = send_message_to_ChatGPT(
        prompt=prompt,
        is_print=True,
        model="gpt-5.2",
        temperature=0.1,
        system_prompt=SYSTEM_PROMPT
    )

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
    max_steps = 20

    for step in range(max_steps):
        response = call_llm(state)

        action = response["action"]

        if action not in ALLOWED_ACTIONS:
            raise ValueError(f"Unknown action: {action}")

        if action == "DONE":
            print("\n=== DONE ===")
            print(response["final_answer"])
            break

        if action == "list_files":
            obs = tools.list_files()
            state["files"] = obs["files"]

        elif action == "read_file":
            filename = response["args"]["filename"]
            obs = tools.read_file(filename)
            state["checked_files"].add(filename)

            if obs["status"] == "ok":
                content = obs["content"]
                state["current_file"] = filename
                state["current_content"] = content

                search_obs = tools.search(content, "презентацию")
                if search_obs["found"]:
                    # очень упрощённо — берём всё предложение
                    state["found_result"] = {
                        "file": filename,
                        "sentence": content
                    }

        print(f"\nAction: {action}")
        print(f"Observation: {obs}")
    else:
        print("\n=== DONE ===")
        print("Достигнут лимит шагов, остановка.")


run_agent()