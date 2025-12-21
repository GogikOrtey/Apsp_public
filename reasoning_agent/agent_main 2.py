# Собираю нового полнофункционального агента

# region Импорты
# Чтобы при запуске файла из этой папки были видны модули из корня проекта (addedFunc.py и др.)
### Потом убрать, что бы было нормально
from pathlib import Path
import sys
import os
import json
import copy
import traceback
from typing import Any
from reasoning_agent.chat_terminal import init_chat_channel, chat_print
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Подключение всех библиотек и функций
from import_all_libraries import *
from ChatGPT.OpenAI_ChatGPT import send_message_to_ChatGPT

# Подключаю инструменты
from reasoning_agent.agent_tools import *







"""         СПИСОК ЗАДАЧ:

* Спросить у GPT, всё ли верно в логе, и хорошо ли читается. Или может стоит улучшить
    * Хорошо ли понятна задача ему например
* Добавить сюда оставшиеся задачи с листочка
* Реализовать краткий лог, который будет выводиться в консоль. А полный - будет писаться сразу в файл, не выводясь в консоль


"""







# region Переменная для хранения задачи

main_task = """
Найти, в каком файле идёт речь про презентацию, и вернуть текст который в этом файле написан
"""

HISTORY_WINDOW = 10         # сколько последних шагов отдаём в LLM
MAX_STEPS = 20              # Максимальное количество шагов агента для решения задачи
INVALID_JSON_RETRIES = 1    # Повторяем запрос шага при невалидном JSON ответа

long_term_memory = []       # Долговременная память, в которую агент может записать данные, при помощи memory_updates
steps_future_value = ""     # Описание следующих шагов, которые наметила себе модель

# region Собираю аннотации инструментов
tools_annotation = get_tools_annotations()
# print(tools_annotation)

# region Обработчик хранения истории
history = [] # Хранилище всей истории шагов
count_of_step_on_history = 0 # Текущий номер шага в истории шагов

# Запускаю второй терминал для кастомного чата
CHAT_LOG_PATH = init_chat_channel()

# Добавляет запись в историю с автоинкрементом порядкового номера
def add_history_entry(entry: dict[str, Any]) -> None:
    global count_of_step_on_history
    count_of_step_on_history += 1
    history.append({"step": count_of_step_on_history, **entry})




# region Системный промпт

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

Помимо решения основной задачи, ты можешь помогать разработчику улучшать архитектуру агента.
Для этого существует специальное поле: development_feedback (опционально, на любом шаге)
Используй development_feedback, если во время выполнения задачи ты обнаружил:
- отсутствие нужного инструмента
- неудобный или ограничивающий контракт инструмента
- избыточную или недостаточную информацию в промпте
- архитектурное ограничение, мешающее рассуждению
- повторяющиеся действия, которые можно автоматизировать

Правила для development_feedback:
- development_feedback НЕ влияет на выполнение текущей задачи
- НЕ используй development_feedback для рассуждений
- НЕ сохраняй туда факты задачи
- development_feedback не передаётся тебе на следующих шагах
- development_feedback предназначен ТОЛЬКО для разработчика

Формат development_feedback — массив объектов:
{
    "type": "tool_gap | improvement | other",
    "description": "<краткое и конкретное описание проблемы или идеи>"
}

ФОРМАТ ОТВЕТА:
- ты ВСЕГДА отвечаешь строго валидным JSON
- без пояснений, без markdown, без текста вне JSON

"""

print(f"SYSTEM_PROMPT = {SYSTEM_PROMPT}")
chat_print(f"SYSTEM_PROMPT = {SYSTEM_PROMPT}")





# region Формирование запроса шага

# Формирует краткий блок состояния последнего шага
# цель -> действие -> результат
def build_last_step_state_block(history) -> str:
    if len(history) < 2:
        return ""

    last_tool = history[-1]
    last_assistant = history[-2]

    if last_tool.get("role") != "tool" or last_assistant.get("role") != "assistant":
        return ""

    content = last_assistant.get("content") or {}

    block = {
        "target": content.get("target"),
        "action": content.get("action"),
        "args": content.get("args"),
        "result": last_tool.get("result"),
    }

    block_json = json.dumps(block, ensure_ascii=False, indent=2)

    return f"""
————————————————————————————————————
СОСТОЯНИЕ ПОСЛЕДНЕГО ШАГА:

{block_json}
————————————————————————————————————

"""


def build_step_prompt(task, history, tools_json: str) -> str:
    global steps_future_value, long_term_memory

    # История шагов
    # Копируем элементы, чтобы не трогать оригинальную history
    history_for_prompt = []
    for entry in history[-HISTORY_WINDOW:] or []:
        entry_copy = copy.deepcopy(entry)

        # Для ответов модели оставляем только target/action/args/reasoning
        if entry_copy.get("role") == "assistant":
            content = entry_copy.get("content") or {}
            entry_copy["content"] = {
                key: content.get(key)
                for key in ("target", "action", "args", "reasoning")
                if key in content
            }

        history_for_prompt.append(entry_copy)

    history_text = json.dumps(history_for_prompt, ensure_ascii=False, indent=2)

    # Шаги на будущее
    steps_future_for_prompt = steps_future_value or []
    steps_future_text = json.dumps(steps_future_for_prompt, ensure_ascii=False, indent=2)

    # Долговременная память
    long_term_memory_value = json.dumps(long_term_memory, ensure_ascii=False, indent=2)

    # Элементы, которые будут удалены на следующем шаге
    def first_deleted_element_put():
        # Показываем два самых "старых" элемента текущего окна, которые первыми выпадут
        if len(history) < HISTORY_WINDOW:
            return ""

        window_slice = history[-HISTORY_WINDOW:]
        about_to_drop = window_slice[:2]

        drop_block = "\n---\n".join(
            json.dumps(item, ensure_ascii=False, indent=2) for item in about_to_drop
        )

        str_description = f"""
История ограничена {HISTORY_WINDOW} шагами.
Следующие элементы истории будут удалены:

{drop_block}

Если в этих шагах есть информация, которая может понадобиться позже — сохрани её сейчас в memory_updates

"""
        return str_description

    # Собираю историю опследнего шага - цели и результата инстурмента
    last_step_state_block = build_last_step_state_block(history)

    return f"""
ТЕКУЩАЯ ЗАДАЧА:
{task}

ДОСТУПНЫЕ ИНСТРУМЕНТЫ (аннотации):
{tools_json}
{last_step_state_block}
————————————————————————————————————
{first_deleted_element_put()}
ИСТОРИЯ ПОСЛЕДНИХ ШАГОВ:
{history_text}

————————————————————————————————————

ДОЛГОВРЕМЕННАЯ ПАМЯТЬ (memory):
{long_term_memory_value}

————————————————————————————————————

ТЕКУЩИЙ ПЛАН (steps_future):
{steps_future_text}

————————————————————————————————————

ТВОЯ ЗАДАЧА НА ЭТОМ ШАГЕ:
- Проанализировать задачу, историю, память и план
- Определить следующую цель шага (target)
- Выбрать ОДИН инструмент (action)
- Подготовить аргументы (args)
- При необходимости:
  - обновить steps_future
  - сохранить данные в memory_updates
  - оставить development_feedback

————————————————————————————————————

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












# region Орекстратор
# Запускает цикл агентных шагов
def orchestrate(task: str = main_task, max_steps: int = MAX_STEPS) -> str:
    global steps_future_value, long_term_memory
    for step in range(1, max_steps + 1):
        step_banner = f"\n———————————   Шаг {step}   ———————————"
        print(step_banner)
        chat_print(step_banner)

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

        chat_print(result)

        # 3. Валидируем ответ
        step_reply = parse_step_response(result.answer, prompt, INVALID_JSON_RETRIES)

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
        tool_log = f"🛠️ {tool_name}({tool_args}) -> {tool_result}"
        print(tool_log)
        chat_print(tool_log)

        # Запись результатов инструмента в историю
        add_history_entry({"role": "tool", "name": tool_name, "result": tool_result})

    print("⚠️ Достигнут лимит шагов без финального ответа.")
    return "Лимит шагов исчерпан без решения."



"""
Пример объектов ответов, хранящихся в истории:

{
    "step": 1,
    "role": "assistant",
    "content": {
        "target": "Получить список файлов, чтобы найти тот, где упоминается презентация",
        "action": "list_files",
        "args": {},
        "reasoning": "Сначала нужно узнать, какие файлы доступны в окружении, затем можно будет искать по ним упоминания про презентацию и прочитать нужный файл целиком.",
        "steps_future": [
            "Получить список файлов",
            "По каждому файлу выполнить поиск подстроки 'презентац' (и при необходимости 'presentation')",
            "Определить файл, где есть упоминание презентации",
            "Прочитать найденный файл и вернуть его полный текст"
        ]
    }
},
{
    "step": 2,
    "role": "tool",
    "name": "list_files",
    "result": {
        "files": [
            "notes.txt",
            "todo.txt",
            "archive.txt"
        ]
    }
}

"""










# region Валидатор ответа 
# Парсит ответ модели с текущего шага, как JSON.
# Если JSON невалидный — повторно спрашивает модель тот же шаг с подсказкой.
def parse_step_response(raw_text: str, prompt: str, max_retries: int = INVALID_JSON_RETRIES) -> dict[str, Any]:
    attempt = 0
    while attempt <= max_retries:
        try:
            return json.loads(raw_text)
        except Exception:
            attempt += 1
            print("Произошла ошибка при парсинге ответа модели как JSON")
            if attempt > max_retries:
                # После исчерпания попыток пробрасываем ошибку, чтобы не скрывать проблему
                raise

            retry_prompt = f"""{prompt}

Предыдущий твой ответ был невалидным JSON.
Повтори этот шаг и верни строго валидный JSON по указанному формату без пояснений вне JSON."""

            retry_result = send_message_to_ChatGPT(
                prompt=retry_prompt,
                system_prompt=SYSTEM_PROMPT,
                chat_id=None,
                model="gpt-5.2",
                is_print=True
            )
            raw_text = retry_result.answer





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





# if __name__ == "__main__":
#     orchestrate()