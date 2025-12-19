"""

Простой пример reasoning-агента

Здесь ему нужно будет найти, в каком файле идёт речь про презентацию

"""

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

Твоя задача:
Найти, в каком файле содержится слово "презентацию",
и вернуть название файла и предложение, в котором оно встречается.

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


# 6. Заглушка LLM
def mock_llm(state):
    if not state["files"]:
        return {
            "thought": "Нужно получить список файлов",
            "action": "list_files",
            "args": {}
        }

    for filename in state["files"]:
        if filename not in state["checked_files"]:
            return {
                "thought": f"Прочитаю файл {filename}",
                "action": "read_file",
                "args": {"filename": filename}
            }

    if state["found_result"]:
        return {
            "action": "DONE",
            "final_answer": state["found_result"]
        }

    return {
        "action": "DONE",
        "final_answer": "Слово не найдено"
    }



# 7. Оркестратор
def run_agent():
    tools = Tools(FILES)

    while True:
        response = mock_llm(state)

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
