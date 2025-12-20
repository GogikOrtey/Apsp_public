# Собираю нового полнофункционального агента

#region Импорты
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

# Подключаю инструменты
from reasoning_agent.agent_tools import *


#region Переменная для хранения задачи

main_task = """
Найти, в каком файле идёт речь про презентацию
"""

HISTORY_WINDOW = 10  # сколько последних шагов отдаём в LLM
MAX_STEPS = 20 # Максимальное количество шагов агента для решения задачи



# region Собираю аннотации инструментов
tools_annotation = get_tools_annotations()
print(tools_annotation)




#region Системный промпт
SYSTEM_PROMPT = """

"""

#region Формирование запроса шага
def build_step_prompt(task: str, history: list[dict[str, Any]], tools_json: str) -> str:
    """
    Собирает промпт для очередного шага.
    """
    history_text = json.dumps(history, ensure_ascii=False, indent=2)
    return f"""
Задача: {task}

Доступные инструменты (вызови один за шаг, если нужен):
{tools_json}

История прошлых шагов:
{history_text}

Ответь строго JSON без лишнего текста. Формат:
{{
  "type": "finish" | "tool" | "commentary",
  "tool_name": "<имя_инструмента>"?,   // если type=tool
  "tool_args": {{}}?,                  // словарь аргументов
  "message": "<текст>"                 // комментарий или финальный ответ
}}
"""

#region Контракт ответа шага

#region Обработчик хранения памяти


#region Орекстратор

# Принимает название инструмента, находит функцию соответствующую ему
# в agent_tools.py и вызывает её, с переданными аргументами
def run_tool(tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any]:
    tool = TOOLS.get(tool_name)
    if not tool:
        return {"status": "error", "error": f"Неизвестный инструмент: {tool_name}"}
    try:
        # Вызывает функцию из agent_tools.py с заданными аргументами
        return tool["func"](**(tool_args or {})) 
    except Exception as ex:
        return {"status": "error", "error": str(ex)}


# Оркестратор - запускает цикл агентных шагов
def orchestrate(task: str = main_task, max_steps: int = MAX_STEPS) -> str:
    history: list[dict[str, Any]] = []

    for step in range(1, max_steps + 1):
        print(f"\n———————————   Шаг {step}   ———————————")

        # 1. Формируем запрос для текущего шага
        prompt = build_step_prompt(task, history[-HISTORY_WINDOW:], tools_annotation)

        # 2. Отправляем его в ChatGPT и получаем ответ
        result = send_message_to_ChatGPT(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            chat_id=None,  # без истории на стороне модели, храним сами
            model="gpt-5.2",
            is_print=True
        )

        # 3. Валидируем ответ
        step_reply = parse_step_response(result.answer)
        history.append({"role": "assistant", "content": step_reply})

        action_type = step_reply.get("type")
        if action_type == "finish":
            message = step_reply.get("message", "")
            print(f"✅ Завершено: {message}")
            save_memory(history)
            return message

        if action_type == "tool":
            tool_name = step_reply.get("tool_name")
            tool_args = step_reply.get("tool_args") or {}
            tool_result = run_tool(tool_name, tool_args)
            print(f"🛠️ {tool_name}({tool_args}) -> {tool_result}")
            history.append({"role": "tool", "name": tool_name, "result": tool_result})
            continue

        # commentary или непонятный тип
        print(f"💬 Комментарий: {step_reply.get('message')}")
        continue

    print("⚠️ Достигнут лимит шагов без финального ответа.")
    save_memory(history)
    return "Лимит шагов исчерпан без решения."


if __name__ == "__main__":
    orchestrate()