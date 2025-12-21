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

# Собирает промпт для очередного шага
def build_step_prompt(task, history, tools_json: str) -> str:
    history_text = json.dumps(history, ensure_ascii=False, indent=2)





    """

        Комментарии к сбору запроса на каждый шаг:

        first_deleted_element_history - это элемент истории, который будет удалён при следующем шаге.
        Здесь нужно написать модели, что ей необходимо сохранить что-то в долговременную память с этого шага, если она считает это важным, и если это потребуется для дальнейшей работы

    """




    return f"""
Задача: {task}

Доступные инструменты (вызови один за шаг):
{tools_json}

История прошлых шагов:
{first_deleted_element_history}
{history_text}

memory содержит информацию, которую ты ранее сохранил и счёл важной для будущих шагов.
Эта память:
* Передаётся тебе на каждом шаге полностью
* Не теряется из-за ограничения истории
* Может использоваться при планировании, выборе инструментов и reasoning

Если ты получаешь новую информацию, которая может понадобиться позже, сохрани её через memory_updates.
Текущая память:

memory = {long_term_memory}

steps_future — это твой текущий план следующих действий, основанный на известном контексте.
На каждом шаге:
* Используй steps_future как ориентир, а не как обязательство
* Переписывай steps_future полностью, с учётом выполненных шагов, новых знаний и изменений в контексте
* Если контекст неясен — оставь только один ближайший шаг
* Если план стал неактуален — замени его полностью

Текущий steps_future:
{steps_future_value}




//////// Прописать чёткий формат ответа
"""
























# region Обработчик хранения истории
history = [] # Хранилище всей истории шагов
count_of_step_on_history = 0 # Текущий номер шага в истории шагов








# region Валидатор ответа 
# Парсит ответ модели с текущего шага, как JSON
def parse_step_response(raw_text: str) -> dict[str, Any]:
    """
    Пробует распарсить ответ модели как JSON.
    Если не получилось, возвращает комментарий-заглушку.
    """
    try:
        return json.loads(raw_text)
    except Exception:
        print("Произошла ошибка при парсинге ответа модели как JSON")      
        raise

        """
        Позже тут прописать логику, что если JSON невалидный - то мы просто повторяем ему текущйи шаг. Возможно добавляя подсказку, что "Предыдущий твой ответ - был невалидным JSON, постарайся в этот раз недопустить такого"
        """


# region Дополнительные переменные

# Долговременная память, в которую агент может записать данные, при помощи memory_updates
long_term_memory = [] 
steps_future_value = ""


# region Орекстратор

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

        """
            На текущем шаге получаем ответ модели вида:
            {
                "target": "",  // Краткое описание действия, которое агент собирается выполнить на этом шаге
                "action": "search_in_file", // Инструмент, который он вызывает
                "args": {                   // Аргументы для этого инструмента, либо {}
                    "file": "config.yaml",
                    "substring": "timeout"
                },
                "reasoning": "",   // Рассуждения модели
                "steps_future": [  // Шаги, которые модель наметила себе на будущее
                  "Найти упоминания таймаута в других конфигурационных файлах",
                  "Сравнить значения с дефолтными настройками",
                  "Сохранить результаты в память"
                ],
                "memory_updates": [  // Добавление записи в долговременную память 
                    "timeout найден в config.yaml и равен 30",
                    ...
                ],
                "development_feedback": [
                  {
                    "type": "tool_gap",
                    "description": "Нужен инструмент глобального поиска подстроки по всем файлам"
                  }
                ]
            }

        """



        """

            Правила обработки этих объектов, пришадших с ответом модели:

            target, action, args, reasoning - обязательные поля, должны быть в каждом ответе
            также они все полностью сохраняются в историю шагов, в одном объекте текущего шага

            steps_future, memory_updates, development_feedback - опциональные поля, их может не быть
            они не сохраняются в историю

            Как работает:
            На каждом шаге выполняется action с переданными args

            steps_future - одновляется на каждом шаге, и передаётся в запросе шага
            memory_updates - добавляет переданные строки в массив long_term_memory
            development_feedback - надо что бы он выводился в консоль с пометкой 🟨🟨🟨 до и после сообщения.
            И также что бы он добавлял его в файл development_feedback.log



            Нужно сделать:

            История запросов к модели и результатов выполнения инструментов хранится в глобальной history, и передаётся агенту, обрезаясь до HISTORY_WINDOW (в текущем случае 10 последних сообщений)

            Также нужно будет добавять к каждому сообщению в истории - его порядковый номер


            Нужно добавить функцию завершения цикла - например, что бы агент вызывал функцию с именем DONE, и в аргумнтах текстом прописывал, что было успешно сделано, в рамках всей задачи




        """








        # 4. Сохраняем 
        history.append({"role": "assistant", "content": step_reply})

        # action_type = step_reply.get("type")
        # if action_type == "finish":
        #     message = step_reply.get("message", "")
        #     print(f"✅ Завершено: {message}")
        #     save_memory(history)
        #     return message

        # Выполнение действия 
        tool_name = step_reply.get("tool_name")
        tool_args = step_reply.get("tool_args") or {}
        tool_result = run_tool(tool_name, tool_args)
        print(f"🛠️ {tool_name}({tool_args}) -> {tool_result}")

        # Запись результатов инструмента в историю
        history.append({"role": "tool", "name": tool_name, "result": tool_result})

    print("⚠️ Достигнут лимит шагов без финального ответа.")
    # save_memory(history)
    return "Лимит шагов исчерпан без решения."


if __name__ == "__main__":
    orchestrate()