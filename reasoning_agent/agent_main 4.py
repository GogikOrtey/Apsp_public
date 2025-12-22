# Полнофункциональный агент с использованием плана

# region Импорты
# Чтобы при запуске файла из этой папки были видны модули из корня проекта (addedFunc.py и др.)
### Потом убрать, что бы было нормально
from pathlib import Path
import sys
import os
import json
import copy
import traceback
import time
from typing import Any
from chat_terminal import init_chat_channel, chat_print
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Подключение всех библиотек и функций
from import_all_libraries import *
from ChatGPT.OpenAI_ChatGPT import send_message_to_ChatGPT

# Подключаю инструменты
from reasoning_agent.agent_tools import *
from reasoning_agent.plan_tools import *







"""         СПИСОК ЗАДАЧ:



Локальные задачи:

* Добавить создание плана, следование ему, и методы взаимодействия с ним
    * При старте агента, перед первым шагом - он создаёт план, в формальном виде
    * Этот план добавляется всегда в промпт шага
    * Надо прописать инструкции, что бы
        * Агент следовал плану
        * Мог обновлять его
    * Программа проверяет, выполнены ли условия для завершения шага. И если да - то делает активным следующий
    * Нужно написать инструменты для взаимодействия с планом
    * И продумать, в какой структуре стоит передавать агенту текущий state плана







Глобальные задачи:

1. Реализовать создание пошагового плана, следование ему и методы взаимодействия с ним
2. Развернуть Playwright
3. Реализовать инструменты для агента, для взаимодействия с ним
4. Попробовать простроить план и формат результатов, что бы он зашёл на главную страницу сайта, собрал семантику, нашёл поле ввода, ввёл в него данные, и сдетектил переход на страницу - и вернул нужные данные которые собрал

Далее - усиливать план и агента, что бы он смог сам собрать все необходимые данные для генерации parsePage и ссылки для parseCard
    Пока что без запросов в JSON
Затем - отлаживать на этих данных генератор кода для parseCard
И после этого - прикрутить работу с доп. запросами JSON

После этого - тестировать на сайтах из колонки аутсорса. Нужно 85% успеха
Далее - собрать новый фронт, и сделать что бы всё было красиво и функционально


"""








# region Переменная для хранения задачи

main_task = """
Найти, в каком файле говорится про презентацию, и в какое время можно собрать на собрании необходимых человек. Название файла поместить в file_name, его содержание - в file_content, а наилучшее время для проведения собрания - в meeting_time
"""

# Неформального плана - нет

# Создаю план задачи в формальном виде
_main_plan_resp = create_main_plan_from_task(main_task, get_result_schema())
# create_main_plan_from_task возвращает объект-обёртку {"status": "...", "plan": {...}, ...}
# В рантайме reasoning-агенту нужен именно нормализованный main_plan (status/current_step/steps).
if isinstance(_main_plan_resp, dict) and _main_plan_resp.get("status") == "ok" and isinstance(_main_plan_resp.get("plan"), dict):
    main_plan = _main_plan_resp["plan"]
else:
    try:
        main_plan = copy.deepcopy(MAIN_PLAN_TEMPLATE)
    except Exception:
        main_plan = {"status": "not_started", "current_step": 0, "steps": []}






# # Схема результата и шаблон для этой задачи (можно переопределить при запуске orchestrate(...))
# # По умолчанию берём примеры из agent_tools.py
# main_result_schema = copy.deepcopy(DEFAULT_RESULT_SCHEMA)
# main_result_template = copy.deepcopy(DEFAULT_RESULT_TEMPLATE)

# Схема результата
main_result_schema = {
    "file_name": {
        "type": "string",
        "required": True,
        "description": "Имя файла"
    },
    "file_content": {
        "type": "string",
        "required": True,
        "description": "Содержимое файла"
    },
    "meeting_time": {
        "type": "string",
        "required": True,
        "description": "Время проведения собрания"
    }
}

# Шаблон результата, который агент заполняет в процессе работы
main_result_template = {
    "file_name": None,
    "file_content": None,
    "meeting_time": None
}


HISTORY_WINDOW = 20         # сколько последних шагов отдаём в LLM
MAX_STEPS = 30              # Максимальное количество шагов агента для решения задачи
INVALID_JSON_RETRIES = 1    # Повторяем запрос шага при невалидном JSON ответа

long_term_memory = []       # Долговременная память, в которую агент может записать данные, при помощи memory_updates
steps_future_value = ""     # Описание следующих шагов, которые наметила себе модель

# region Собираю аннотации инструментов
tools_annotation = get_tools_annotations()

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
- На каждом шаге ты возвращаешь ровно ОДИН JSON-объект, соответствующий следующему шагу
- Даже если шаги очевидны — верни только один следующий шаг
- Любой текст вне одного JSON-объекта считается ошибкой
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

РЕЗУЛЬТАТ (result):
- Тебе будет дан result_schema (формат результата) и текущий result
- Заполняй result ПОШАГОВО через инструмент update_result(field, value)
- Когда result заполнен достаточно, чтобы выполнить задачу — используй action="DONE"

МЕНТАЛЬНАЯ МОДЕЛЬ:
- Ты выполняешь только ОДИН атомарный шаг
- После ответа управление ВСЕГДА возвращается оркестратору
- Оркестратор сам вызовет инструмент и вернёт результат
- Ты НИКОГДА не выполняешь следующий шаг сам

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

    block_json = json.dumps(block, ensure_ascii=False, indent=4)

    return f"""
————————————————————————————————————
СОСТОЯНИЕ ПОСЛЕДНЕГО ШАГА:

{block_json}
"""


# Вспомогательная функция для красивого отображения плана в промпте
def format_main_plan_for_prompt(main_plan: dict[str, Any]) -> str:
    if not main_plan or "steps" not in main_plan:
        return "Глобальный план не задан."

    lines: list[str] = []
    current_idx = main_plan.get("current_step", 0)

    lines.append(f"СТАТУС ПЛАНА: {main_plan.get('status', 'unknown')}")
    lines.append("ШАГИ ПЛАНА (ФАЗЫ):")

    steps = main_plan.get("steps", [])
    if not isinstance(steps, list):
        return "Глобальный план задан в некорректном формате."

    for idx, step in enumerate(steps):
        # Маркер текущего шага
        marker = "🟢 АКТИВНАЯ ФАЗА" if idx == current_idx else "⚪"
        if isinstance(step, dict) and step.get("status") == "done":
            marker = "✅ ЗАВЕРШЕНО"

        if not isinstance(step, dict):
            step_desc = f"{marker} [Фаза {idx + 1}] (некорректный шаг)"
            lines.append(step_desc)
            continue

        step_desc = (
            f"{marker} [Фаза {step.get('step_id', idx + 1)}]\n"
            f"   Цель (Goal): {step.get('goal', '')}\n"
            f"   Требует заполнить (Fills): {step.get('fills', [])}\n"
            f"   Статус: {step.get('status', 'unknown')}"
        )
        lines.append(step_desc)

    return "\n".join(lines)


def build_step_prompt(task, history, tools_json: str, main_plan: dict[str, Any]) -> str:
    global steps_future_value, long_term_memory

    # История шагов
    # Копируем элементы, чтобы не трогать оригинальную history
    history_for_prompt = []
    history_slice = history[-HISTORY_WINDOW:] or []
    # Если показываем элементы, которые скоро выпадут, не дублируем их в истории
    if len(history) >= HISTORY_WINDOW:
        history_slice = history_slice[2:]

    for entry in history_slice:
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

    history_text = json.dumps(history_for_prompt, ensure_ascii=False, indent=4)


    # Шаги на будущее
    steps_future_for_prompt = steps_future_value or []
    steps_future_text = json.dumps(steps_future_for_prompt, ensure_ascii=False, indent=4)

    # Долговременная память
    long_term_memory_value = json.dumps(long_term_memory, ensure_ascii=False, indent=4)


    # Элементы, которые будут удалены на следующем шаге
    def first_deleted_element_put():
        # Показываем два самых "старых" элемента текущего окна, которые первыми выпадут
        if len(history) < HISTORY_WINDOW:
            return ""

        window_slice = history[-HISTORY_WINDOW:]
        about_to_drop = window_slice[:2]

        drop_block = ",\n".join(
            json.dumps(item, ensure_ascii=False, indent=4) for item in about_to_drop
        )

        str_description = f"""
История ограничена {HISTORY_WINDOW} шагами.
Следующие элементы истории будут удалены:

{drop_block}

Если в этих шагах есть информация, которая может понадобиться позже — сохрани её сейчас в memory_updates

"""
        return str_description

    # Собираю историю последнего шага - цели и результата инстурмента
    last_step_state_block = build_last_step_state_block(history)

    # Схема результата и текущий результат (агент заполняет его через update_result)
    try:
        result_schema_text = json.dumps(get_result_schema(), ensure_ascii=False, indent=4)
    except TypeError:
        result_schema_text = str(get_result_schema())

    try:
        current_result_text = json.dumps(get_result(), ensure_ascii=False, indent=4)
    except TypeError:
        current_result_text = str(get_result())



    # --- НОВАЯ ЧАСТЬ: Формирование текста плана ---
    main_plan_text = format_main_plan_for_prompt(main_plan)

    # Получаем цель текущей фазы для явного акцента
    current_idx = main_plan.get("current_step", 0) if isinstance(main_plan, dict) else 0
    steps_list = main_plan.get("steps", []) if isinstance(main_plan, dict) else []
    current_phase_goal = "Цель не определена"
    current_phase_fills = []

    if isinstance(steps_list, list) and 0 <= current_idx < len(steps_list) and isinstance(steps_list[current_idx], dict):
        current_phase_goal = steps_list[current_idx].get("goal") or current_phase_goal
        current_phase_fills = steps_list[current_idx].get("fills") or []

    return f"""
ГЛОБАЛЬНЫЙ ПЛАН ЗАДАЧИ (MAIN PLAN):
{main_plan_text}

————————————————————————————————————

ТВОЙ ФОКУС ПРЯМО СЕЙЧАС (ТЕКУЩАЯ ФАЗА):
Цель фазы: {current_phase_goal}
Необходимо заполнить поля в result: {current_phase_fills}

ТАКТИЧЕСКИЙ ПЛАН (steps_future) должен вести к завершению этой фазы.

————————————————————————————————————

ДОСТУПНЫЕ ИНСТРУМЕНТЫ (аннотации):
{tools_json}

ТЕКУЩАЯ ЗАДАЧА (Общее описание):
{task}

ТРЕБУЕМЫЙ ФОРМАТ РЕЗУЛЬТАТА (result_schema):
{result_schema_text}

ТЕКУЩИЙ РЕЗУЛЬТАТ (result):
{current_result_text}
{last_step_state_block}
————————————————————————————————————
{first_deleted_element_put()}
ИСТОРИЯ ПОСЛЕДНИХ ШАГОВ:
{history_text}

————————————————————————————————————

ДОЛГОВРЕМЕННАЯ ПАМЯТЬ (memory):
{long_term_memory_value}

————————————————————————————————————

ТЕКУЩИЙ ТАКТИЧЕСКИЙ ПЛАН (steps_future):
{steps_future_text}

————————————————————————————————————

ТВОЯ ЗАДАЧА НА ЭТОМ ШАГЕ:
- Проанализировать задачу, историю, память и план
- Проверить, какие поля (fills) еще пустые в result, для этой фазы
- Определить следующую цель шага (target)
- Выбрать ОДИН инструмент (action)
- Подготовить аргументы (args)
- При необходимости:
  - обновить steps_future
  - сохранить данные в memory_updates
  - оставить development_feedback

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
- в ответе верни только один JSON объект, соответствующий следующему шагу
- для завершения задачи используй action="DONE"
- чтобы собрать финальный ответ, заполняй result через action="update_result"
- action="DONE" используй только когда result заполнен и содержит итог в нужном формате
"""


# region Main Plan progress helpers
def _is_result_field_filled(value: Any) -> bool:
    """
    Эвристика заполненности поля результата:
    - None -> не заполнено
    - str -> непустая после strip
    - остальное -> считаем заполненным (включая 0/False, т.к. это валидные значения)
    """
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def update_main_plan_progress(main_plan: dict[str, Any]) -> dict[str, Any]:
    """
    Автоматически продвигает main_plan по фазам:
    - текущая фаза выполнена, когда все её fills заполнены в result
    - оркестратор двигает current_step и статусы шагов

    Важно: main_plan мутируется in-place, но также возвращается для удобства.
    """
    if not isinstance(main_plan, dict):
        return main_plan

    steps = main_plan.get("steps")
    if not isinstance(steps, list) or not steps:
        return main_plan

    if main_plan.get("status") in (None, "", "unknown", "not_started"):
        main_plan["status"] = "in_progress"

    current_idx = main_plan.get("current_step", 0)
    if not isinstance(current_idx, int) or current_idx < 0:
        current_idx = 0
        main_plan["current_step"] = 0

    # Если вышли за границы — план выполнен
    if current_idx >= len(steps):
        main_plan["status"] = "completed"
        return main_plan

    # Выставляем статус текущего шага как in_progress, если ещё pending
    if isinstance(steps[current_idx], dict) and steps[current_idx].get("status") == "pending":
        steps[current_idx]["status"] = "in_progress"

    step = steps[current_idx] if isinstance(steps[current_idx], dict) else {}
    fills = step.get("fills") if isinstance(step.get("fills"), list) else []
    if not fills:
        # По правилам планировщика fills не должны быть пустыми
        return main_plan

    result_obj = get_result()

    def _get_by_path(obj: Any, path: str) -> Any:
        node = obj
        for part in [p for p in str(path).split(".") if p]:
            if not isinstance(node, dict) or part not in node:
                return None
            node = node.get(part)
        return node

    for f in fills:
        val = _get_by_path(result_obj, f)
        if not _is_result_field_filled(val):
            return main_plan

    # Закрываем текущую фазу
    steps[current_idx]["status"] = "done"
    next_idx = current_idx + 1

    # Переходим к следующей фазе или закрываем план
    if next_idx < len(steps):
        main_plan["current_step"] = next_idx
        if isinstance(steps[next_idx], dict) and steps[next_idx].get("status") == "pending":
            steps[next_idx]["status"] = "in_progress"
        main_plan["status"] = "in_progress"
    else:
        main_plan["current_step"] = next_idx
        main_plan["status"] = "completed"

    return main_plan

# endregion












# region Орекстратор
# Запускает цикл агентных шагов
def orchestrate(
    task: str = main_task,
    max_steps: int = MAX_STEPS,
    result_schema: dict[str, Any] | None = None,
    result_template: dict[str, Any] | None = None
) -> str:
    global steps_future_value, long_term_memory

    # Инициализируем объект результата для текущего запуска
    init_result(result_schema or main_result_schema, result_template or main_result_template)

    for step in range(1, max_steps + 1):
        step_banner = f"\n———————————   Шаг {step}   ———————————\n"
        print(step_banner)
        chat_print(step_banner)

        # 0. Пробуем продвинуть план на основании уже заполненного result (если это возможно)
        try:
            update_main_plan_progress(main_plan)
        except Exception:
            pass

        # 1. Формируем запрос для текущего шага
        prompt = build_step_prompt(task, history, tools_annotation, main_plan)

        # 2. Отправляем его в ChatGPT и получаем ответ
        result = send_message_to_ChatGPT(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            chat_id=None,  # без истории на стороне модели, храним сами
            model="gpt-5.2",
            is_print=True
        )

        # 3. Валидируем ответ
        step_reply = parse_step_response(result.answer, prompt, INVALID_JSON_RETRIES)

        # Краткий вывод ответа модели
        args_text = "—"
        model_args = step_reply.get("args")
        if model_args:
            try:
                args_text = json.dumps(model_args, ensure_ascii=False)
            except TypeError:
                args_text = str(model_args)

        model_summary = (
            f"🟢 reasoning: {step_reply.get('reasoning') or '—'}\n"     # Рассуждения модели
            f"🔵 target: {step_reply.get('target') or '—'}\n"    # Действие, которое агент собирается выполнить
            f"🟡 action: {step_reply.get('action') or '—'}\n"           # Вызывает инструмент
            f"{'   🔶 args: ' + args_text if args_text != '—' else ''}" # С аргументами
            f"\n"
        )
        chat_print(model_summary)
        print(model_summary)


        # Перед каждым следующим шагом ждем подтверждения пользователем
        input(f"\n-----> Нажмите Enter чтобы продолжить")
        print("")


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


            Результат пошагово записывается в result, при помощи вызова инструмента update_result
            Перед началом работы надо задать верную схему результата (result_schema) и шаблон результата, который будет заполнять модель, и который будет передаваться ей в каждом запросе шага, в фрагменте 
            Текущий результат (result)

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
            completion_text = ""

            # # 1) Backward-compatible режим: старое поле final_answer
            # if isinstance(tool_args, dict) and isinstance(tool_args.get("final_answer"), str) and tool_args.get("final_answer"):
            #     completion_text = tool_args["final_answer"]

            # 2) Новый режим: возвращаем накопленный result
            if not completion_text:
                try:
                    completion_text = json.dumps(get_result(), ensure_ascii=False, indent=4)
                except TypeError:
                    completion_text = str(get_result())

            done_result = {"status": "done", "result": get_result(), "message": completion_text}
            add_history_entry({"role": "tool", "name": "DONE", "result": done_result})
            print(f"✅ Агент завершил задачу: {completion_text}")
            return completion_text

        # 6.2 Вызов инструмента
        tool_result = run_tool(tool_name, tool_args)
        tool_log = f"🛠️  {tool_name}({tool_args})"
        print(tool_log)
        chat_print(tool_log)

        try:
            tool_result_text = json.dumps(tool_result, ensure_ascii=False)
        except TypeError:
            tool_result_text = str(tool_result)

        tool_result_log = f"Инструмент вернул результат: {tool_result_text}"
        print(tool_result_log)
        chat_print(tool_result_log)

        # Запись результатов инструмента в историю
        add_history_entry({"role": "tool", "name": tool_name, "result": tool_result})

        # После каждого действия пробуем продвинуть план (особенно важно после update_result)
        try:
            update_main_plan_progress(main_plan)
        except Exception:
            pass

    print("⚠️ Достигнут лимит шагов без финального ответа.")
    return "Лимит шагов исчерпан без решения"



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
        # 1. Сначала пробуем "мягкую" очистку от Markdown, не беспокоя модель
        clean_text = raw_text.strip()
        if "```" in clean_text:
            # Извлекаем содержимое между ```json и ``` или просто ```
            import re
            match = re.search(r"```(?:json)?\s*(.*?)\s*```", clean_text, re.DOTALL)
            if match:
                clean_text = match.group(1)
        
        try:
            return json.loads(clean_text)
        except Exception as e:
            attempt += 1
            if attempt > max_retries:
                raise

            # 2. Если не помогло — просим модель исправиться, показывая старый текст
            retry_prompt = f"""{prompt}

Твой предыдущий ответ был невалидным JSON. 
--- ТЕКСТ ТВОЕГО ОТВЕТА ---

{raw_text}

--- ОШИБКА ПАРСИНГА ---

{str(e)}

Пожалуйста, исправь ошибку и верни только валидный JSON. Убедись, что все поля на месте и кавычки экранированы правильно.
"""
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





if __name__ == "__main__":
    orchestrate()

    # try:
    #     import global_variable
    #     print(
    #         f"🔢 Использовано токенов — input: {global_variable.total_input_tokens}, "
    #         f"output: {global_variable.total_output_tokens}"
    #     )
    # except Exception as ex:
    #     print(f"Не удалось вывести статистику токенов: {ex}")