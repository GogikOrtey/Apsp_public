# Собираю нового полнофункционального агента

#region Импорты
# Чтобы при запуске файла из этой папки были видны модули из корня проекта (addedFunc.py и др.)
### Потом убрать, что бы было нормально
from pathlib import Path
import sys
import os
import json
import traceback
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

long_term_memory = []  # Долговременная память, в которую агент может записать данные, при помощи memory_updates
steps_future_value = "" # Описание следующих шагов, которые наметила себе модель

# ////////////////////////////////////////// development_feedback добавить

# region Собираю аннотации инструментов
tools_annotation = get_tools_annotations()
print(tools_annotation)



# region Обработчик хранения истории
history = [] # Хранилище всей истории шагов
count_of_step_on_history = 0 # Текущий номер шага в истории шагов

# Добавляет запись в историю с автоинкрементом порядкового номера
def add_history_entry(entry: dict[str, Any]) -> None:
    global count_of_step_on_history
    count_of_step_on_history += 1
    history.append({"step": count_of_step_on_history, **entry})







#region Системный промпт

SYSTEM_PROMPT = """
Ты — reasoning-агент, который решает задачи пошагово, используя доступные инструменты.

ОБЩИЕ ПРАВИЛА:
- Ты выполняешь задачу итеративно, шаг за шагом
- На каждом шаге ты выбираешь ОДНО действие (action)
- Если задача решена — используй action="DONE"
- Ты не выдумываешь результаты инструментов — они приходят извне
- Ты не повторяешь уже выполненные действия без причины

ПАМЯТЬ (memory):
- memory содержит информацию, которую ты ранее сохранил
- memory передаётся тебе полностью на каждом шаге
- memory не ограничена HISTORY_WINDOW
- если информация может понадобиться позже — сохрани её через memory_updates

ПЛАН (steps_future):
- steps_future — это текущая гипотеза плана, а не обязательство
- используй её как ориентир
- на каждом шаге переписывай steps_future полностью
- если контекст неясен — оставь только один ближайший шаг
- если план стал неактуален — замени его полностью

ИСТОРИЯ:
- история содержит последние шаги твоих действий и наблюдений
- история может быть усечена, старые шаги могут исчезать
- если информация из текущего шага может понадобиться позже — сохрани её в memory

ИНСТРУМЕНТЫ:
- используй только инструменты из списка доступных
- передавай корректные аргументы
- не используй инструмент, если результат уже известен

ФОРМАТ ОТВЕТА:
- ты ВСЕГДА отвечаешь строго валидным JSON
- без пояснений, без markdown, без текста вне JSON

"""







#region Формирование запроса шага
def build_step_prompt(task, history, tools_json: str) -> str:
    global steps_future_value, long_term_memory

    history_for_prompt = list(history[-HISTORY_WINDOW:]) or []
    history_text = json.dumps(history_for_prompt, ensure_ascii=False, indent=2)

    # Элемент, который будет удалён на следующем шаге
    if len(history) > HISTORY_WINDOW:
        first_deleted_element_history = json.dumps(
            history[-HISTORY_WINDOW - 1],
            ensure_ascii=False,
            indent=2
        )
    else:
        first_deleted_element_history = "null"

    steps_future_for_prompt = steps_future_value or []
    steps_future_text = json.dumps(steps_future_for_prompt, ensure_ascii=False, indent=2)

    long_term_memory_value = json.dumps(long_term_memory, ensure_ascii=False, indent=2)

    return f"""
ТЕКУЩАЯ ЗАДАЧА:
{task}

ДОСТУПНЫЕ ИНСТРУМЕНТЫ (аннотации):
{tools_json}

ВАЖНО О КОНТЕКСТЕ:
История ограничена {HISTORY_WINDOW} шагами.
Следующий элемент истории будет удалён:

{first_deleted_element_history}

Если в этом шаге есть информация, которая может понадобиться позже — 
сохрани её сейчас в memory_updates.

====================================

ИСТОРИЯ ПОСЛЕДНИХ ШАГОВ:
{history_text}

====================================

ДОЛГОВРЕМЕННАЯ ПАМЯТЬ (memory):
{long_term_memory_value}

====================================

ТЕКУЩИЙ ПЛАН (steps_future):
{steps_future_text}

====================================

ТВОЯ ЗАДАЧА НА ЭТОМ ШАГЕ:
- Проанализировать задачу, историю, память и план
- Определить следующую цель шага (target)
- Выбрать ОДИН инструмент (action)
- Подготовить аргументы (args)
- При необходимости:
  - обновить steps_future
  - сохранить данные в memory_updates
  - оставить development_feedback

====================================

ФОРМАТ ОТВЕТА (СТРОГО JSON):

{{
    "target": "краткое описание цели текущего шага",
    "action": "ИМЯ_ИНСТРУМЕНТА | DONE",
    "args": {{ ... }},

    "reasoning": "твои рассуждения",

    "steps_future": [
        "шаг 1",
        "шаг 2"
    ],

    "memory_updates": [
        "строка памяти 1",
        "строка памяти 2"
    ],

    "development_feedback": [
        {{
            "type": "tool_gap | improvement | other",
            "description": "что можно улучшить"
        }}
    ]
}}

ПРАВИЛА:
- target, action, args, reasoning — ОБЯЗАТЕЛЬНЫ
- steps_future, memory_updates, development_feedback — ОПЦИОНАЛЬНЫ
- если поле не нужно — НЕ передавай его
- для завершения задачи используй action="DONE"
- финальный ответ помести в args.final_answer
"""






# Собирает промпт для очередного шага
def build_step_prompt(task, history, tools_json: str, ) -> str:
    global steps_future_value, long_term_memory

    # Обрезаем историю - берём последние HISTORY_WINDOW записей истории (сейчас это 10)
    history_for_prompt = list(history[-HISTORY_WINDOW:]) or []
    history_text = json.dumps(history_for_prompt, ensure_ascii=False, indent=2)

    # Если план пустой, явно передаём "[]", чтобы модель понимала отсутствие плана
    steps_future_for_prompt = steps_future_value or []
    steps_future_text = json.dumps(steps_future_for_prompt, ensure_ascii=False)

    long_term_memory_value = json.dumps(long_term_memory, ensure_ascii=False, indent=2)



    """

        first_deleted_element_history - это элемент истории, который будет удалён при следующем шаге.
        Здесь нужно написать модели, что ей необходимо сохранить что-то в долговременную память с этого шага, если она считает это важным, и если это потребуется для дальнейшей работы

    """


    return f"""
Задача: {task}

Доступные инструменты:
{tools_json}



//////////// Прописать, что ему нужно: Вызвать следующий инструмент


История прошлых шагов:
{first_deleted_element_history} //////////////// Написать её сборщик
{history_text}

memory содержит информацию, которую ты ранее сохранил и счёл важной для будущих шагов.
Эта память:
- Передаётся тебе на каждом шаге полностью
- Не теряется из-за ограничения истории
- Может использоваться при планировании, выборе инструментов и reasoning

Если ты получаешь новую информацию, которая может понадобиться позже, сохрани её через memory_updates.
Текущая память:

memory = {long_term_memory_value} 

steps_future — это твой текущий план следующих действий, основанный на известном контексте.
На каждом шаге:
- Используй steps_future как ориентир, а не как обязательство
- Переписывай steps_future полностью, с учётом выполненных шагов, новых знаний и изменений в контексте
- Если контекст неясен — оставь только один ближайший шаг
- Если план стал неактуален — замени его полностью

Текущий steps_future:
{steps_future_text}

Формат ответа (строго валидный JSON, без лишнего текста):
...

Правила формирования ответа:
...
- Для завершения задачи ставь action="DONE" и клади итоговый текст в args.final_answer.
...

//////// Прописать чёткий формат ответа, и контракт с правилами формирования этого ответа
//// Структуру я прописал для себя ниже - надо формализовать, и добавить сюда, в запрос
"""









# region Орекстратор
# Запускает цикл агентных шагов
def orchestrate(task: str = main_task, max_steps: int = MAX_STEPS) -> str:
    global steps_future_value, long_term_memory
    for step in range(1, max_steps + 1):
        print(f"\n———————————   Шаг {step}   ———————————")

        # 1. Формируем запрос для текущего шага
        prompt = build_step_prompt(task, history, tools_annotation)

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

            Правила обработки этих объектов, пришедших с ответом модели:

            target, action, args, reasoning - обязательные поля, должны быть в каждом ответе
            также они все полностью сохраняются в историю шагов, в одном объекте текущего шага

            steps_future, memory_updates, development_feedback - опциональные поля, их может не быть
            они не сохраняются в историю

            Как работает:
            На каждом шаге выполняется action с переданными args

            steps_future - одновляется на каждом шаге, и передаётся в запросе шага
            
            memory_updates - добавляет переданные строки в массив long_term_memory

            development_feedback - модель может сказать мне как разработчику, что ей не хватает какого-то функционала (без прерывания выполнения задачи)

        """




        # 4. Сохраняем ответ модели
        ########################## Потом ещё подумать над форматом истории, посмотреть какой будет красивее
        add_history_entry({"role": "assistant", "content": step_reply})



        # 5. Обработчик дополнительных действий

        new_steps_future = step_reply.get("steps_future")
        if new_steps_future is not None:
            # Обновляем глобальный план даже если он пустой (модель могла очистить его)
            steps_future_value = new_steps_future

        memory_updates = step_reply.get("memory_updates") or []
        if memory_updates:
            # Дополняем долговременную память новыми фактами от модели
            long_term_memory.extend(memory_updates)

        # Если есть development_feedback, выводит его и дописывает в лог
        log_development_feedback(step_reply.get("development_feedback"))



        # 6. Выполнение действия 
        tool_name = step_reply.get("action")
        tool_args = step_reply.get("args") or {}

        # 6.1 Обработка завершения работы агента
        if tool_name == "DONE":
            if isinstance(tool_args, dict):
                completion_text = tool_args.get("final_answer") or ""
            elif isinstance(tool_args, str):
                completion_text = tool_args
            else:
                completion_text = str(tool_args)

            # Фолбэк на случай пустого текста, чтобы не потерять ответ
            if not completion_text:
                completion_text = json.dumps(tool_args, ensure_ascii=False)

            done_result = {"status": "done", "message": completion_text}
            add_history_entry({"role": "tool", "name": "DONE", "result": done_result})
            print(f"✅ Агент завершил задачу: {completion_text}")
            return completion_text

        # 6.2 Вызов инструмента
        tool_result = run_tool(tool_name, tool_args)
        print(f"🛠️ {tool_name}({tool_args}) -> {tool_result}")

        # Запись результатов инструмента в историю
        add_history_entry({"role": "tool", "name": tool_name, "result": tool_result})

    print("⚠️ Достигнут лимит шагов без финального ответа.")
    return "Лимит шагов исчерпан без решения."





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
        ############################################





# region Вспомогательные обработчики

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
        return {
            "status": "error",
            "error": str(ex),
            "traceback": traceback.format_exc()
        }

# Если есть development_feedback, выводит его и дописывает в development_feedback.log
def log_development_feedback(feedback):
    if not feedback:
        return

    m = "🟨"
    print(f"\n{m}{m}{m}{feedback}\n{m}{m}{m}")

    log_path = Path(__file__).resolve().parent / "development_feedback.log"
    with open(log_path, "a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(feedback, ensure_ascii=False) + "\n")





if __name__ == "__main__":
    orchestrate()