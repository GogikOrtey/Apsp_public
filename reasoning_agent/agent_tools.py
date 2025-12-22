# Здесь будут описания инструментов для агента

import json
import copy
from typing import Any

from pathlib import Path
import sys
import json
import copy
from typing import Any
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Импортируем LLM-клиент для генерации и формализации плана
from ChatGPT.OpenAI_ChatGPT import send_message_to_ChatGPT

"""

Начальные инструменты:

list_files - возвращает список файлов в окружении
read_file - читает содержимое файла по имени
search_in_file - ищет вхождения подстроки в тексте файла

"""




# region Входные данные

# # Пример входных данных 1
# FILES = {
#     "notes.txt": "Встреча в пятницу. Купить хлеб. Проверить отчёт.",
#     "todo.txt": "Срочно: отправить письмо Алексею. Подготовить презентацию.",
#     "archive.txt": "Старые заметки за 2022 год."
# }

# Пример входных данных 2
FILES = {
    "notes.txt": "Встреча в пятницу. Купить хлеб. Проверить отчёт.",
    "todo.txt": "Нужно на собрании показать презентацию Алексею и Анне",
    "archive.txt": "Старые заметки за 2022 год.",
    "schedule_alexey.txt": "Расписание Алексея: Свободен с 12:30 до 16:00",
    "schedule_anna.txt": "Расписание Анны: Свободна с 14:00 до 15:00",
    "schedule_vladimir.txt": "Расписание Владимира: Свободен весь день",
}


### Тут надо будет потом реализовать функцию, которая принимает результат, и разбивает его на схему и шаблон
### А также добавить простую дефолтную схему, с одним результатом


# Пример схемы результата (ее можно переопределить при запуске агента)
DEFAULT_RESULT_SCHEMA = {
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

# Базовый шаблон результата, который агент заполняет в процессе работы
DEFAULT_RESULT_TEMPLATE = {
    "file_name": None,
    "file_content": None,
    "meeting_time": None
}

# Текущая схема и текущий результат, который агент постепенно заполняет.
# Инициализация делается через init_result(...) (см. ниже).
RESULT_SCHEMA: dict[str, Any] = copy.deepcopy(DEFAULT_RESULT_SCHEMA)
RESULT: dict[str, Any] = copy.deepcopy(DEFAULT_RESULT_TEMPLATE)


def init_result(schema: dict[str, Any] | None = None, template: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Инициализирует (или переинициализирует) схему результата и сам результат.
    """
    global RESULT_SCHEMA, RESULT
    if schema is None:
        schema = DEFAULT_RESULT_SCHEMA
    if template is None:
        template = DEFAULT_RESULT_TEMPLATE
    RESULT_SCHEMA = copy.deepcopy(schema)
    RESULT = copy.deepcopy(template)
    return {"status": "ok", "result_schema": RESULT_SCHEMA, "result": RESULT}


def get_result() -> dict[str, Any]:
    """Возвращает текущий объект результата (для оркестратора/промпта)."""
    return RESULT


def get_result_schema() -> dict[str, Any]:
    """Возвращает текущую схему результата (для оркестратора/промпта)."""
    return RESULT_SCHEMA



# region Декоратор анннотаций

TOOLS = {} # Описания будут собираться в этот словарь

def tool(name, description, args=None, returns=None, example_args=None):
    """Декоратор для регистрации инструмента с аннотацией"""
    def decorator(func):
        TOOLS[name] = {
            "func": func,
            "name": name,
            "description": description,
            "args": args or [],
            "returns": returns,
            "example_args": example_args or {}
        }
        return func
    return decorator









# region Возврат аннотаций
def get_tools_annotations(as_json: bool = True):
    """
    Возвращает аннотации всех инструментов (без самих функций).

    as_json=True  -> вернуть красивую JSON-строку (удобно печатать/логировать)
    as_json=False -> вернуть Python-dict (удобно смотреть в дебаггере без экранирования)
    """
    annotations = {}
    for name, data in TOOLS.items():
        annotations[name] = {
            "name": data["name"],
            "description": data["description"],
            "args": data["args"],
            "returns": data["returns"],
            "example_args": data["example_args"]
        }
    
    if not as_json:
        return annotations # В виде JSON
    return json.dumps(annotations, ensure_ascii=False, indent=4) # В текстовом виде








# region Реализация инструментов с аннотациями

@tool(
    name="list_files",
    description="Возвращает список всех файлов в окружении",
    args=[],
    # ВАЖНО: лучше хранить `returns` как структуру (dict/list), а не как JSON-строку внутри строки.
    # Тогда при json.dumps() не будет экранирования кавычек вида \"...\".
    returns={
        "files": ["notes.txt", "todo.txt", "..."]
    },
    example_args={}
)
def list_files():
    # JSON-friendly ответ, чтобы совпадало с аннотацией returns
    return {"files": list(FILES.keys())}


@tool(
    name="read_file",
    description="Читает содержимое файла по имени. Возвращает словарь с содержимым и статусом",
    args=[
            {
                "name": "filename", 
                "type": "str", 
                "required": True, 
                "description": "Имя файла"
            }
        ],
    returns=[
        {"status": "ok", "content": "..."},
        {"status": "error", "content": None}
    ],
    example_args={"filename": "todo.txt"}
)
def read_file(filename):
    if filename in FILES:
        return {"status": "ok", "content": FILES[filename]}
    else:
        return {"status": "error", "content": None}


@tool(
    name="search_in_file",
    description="Ищет вхождения подстроки в тексте файла",
    args=[
        {
            "name": "filename",
            "type": "str", 
            "required": True, 
            "description": "Имя файла"
        },
        {
            "name": "substr", 
            "type": "str", 
            "required": True, 
            "description": "Подстрока для поиска"
        }
    ],
    returns={
        "status": "ok|error",
        "count": "int",
        "first_index": "int|null"
    },
    example_args={"filename": "todo.txt", "substr": "презентац"}
)
def search_in_file(filename, substr):
    if filename not in FILES:
        return {"status": "error", "count": 0, "first_index": None}
    
    text = FILES[filename]
    count = text.count(substr)
    first_index = text.find(substr) if count > 0 else None
    
    return {"status": "ok", "count": count, "first_index": first_index}



# region update_result
@tool(
    name="update_result",
    description=(
        "Обновляет поле в объекте результата (result). "
        "Используй это, чтобы постепенно собрать финальный ответ по заданной схеме."
    ),
    args=[
        {
            "name": "field",
            "type": "str",
            "required": True,
            "description": "Имя поля в result"
        },
        {
            "name": "value",
            "type": "any",
            "required": True,
            "description": "Значение, которое нужно записать в указанное поле"
        }
    ],
    returns={
        "status": "ok|error",
        "result": "{...}",
        "error": "str|null"
    },
    example_args={"field": "file_name", "value": "todo.txt"}
)
def update_result(field: str, value: Any):
    global RESULT, RESULT_SCHEMA

    if not isinstance(field, str) or not field.strip():
        return {"status": "error", "result": RESULT, "error": "field должен быть непустой строкой"}

    path = [p for p in field.strip().split(".") if p]
    if not path:
        return {"status": "error", "result": RESULT, "error": "Некорректный путь поля"}

    # Минимальная валидация: первый сегмент должен существовать в схеме (если схема dict)
    if isinstance(RESULT_SCHEMA, dict) and path[0] not in RESULT_SCHEMA:
        return {
            "status": "error",
            "result": RESULT,
            "error": f"Поле '{path[0]}' отсутствует в result_schema"
        }

    node = RESULT
    for key in path[:-1]:
        if key not in node or not isinstance(node.get(key), dict):
            node[key] = {}
        node = node[key]

    node[path[-1]] = value
    return {"status": "ok", "result": RESULT}




# region Создание плана
MAIN_PLAN_SCHEMA: dict[str, Any] = {
    "status": {
        "type": "string",
        "enum": ["not_started", "in_progress", "completed"],
        "description": "Текущее состояние выполнения плана в целом"
    },
    "current_step": {
        "type": "integer",
        "description": "Индекс текущего шага (0 означает, что работа по шагам ещё не начата)"
    },
    "steps": {
        "type": "array",
        "description": "Список шагов плана",
        "items": {
            "type": "object",
            "properties": {
                "step_id": {
                    "type": "integer",
                    "description": "Номер шага в плане (1..N)"
                },
                "goal": {
                    "type": "string",
                    "description": "Цель шага, единственная инструкция для reasoning-агента"
                },
                "fills": {
                    "type": "array",
                    "description": "Список полей результата (result), которые должны быть заполнены на этом шаге",
                    "items": {"type": "string"}
                },
                "status": {
                    "type": "string",
                    "enum": ["pending", "in_progress", "done"],
                    "description": "Состояние шага (управляется кодом, не моделью)"
                }
            },
            "required": ["step_id", "goal", "fills", "status"]
        }
    }
}

# Базовый шаблон плана (без шагов), чтобы удобно инициализировать пустой объект
MAIN_PLAN_TEMPLATE: dict[str, Any] = {
    "status": "not_started",
    "current_step": 0,
    "steps": []
}


# Системные промпты для генерации/формализации плана
PLANNER_SYSTEM_PROMPT = """
Ты — модуль планирования задач.

Твоя задача — извлечь глобальный пошаговый план решения
ТОЛЬКО на основе текста задачи.

Ты НЕ решаешь задачу.
Ты НЕ анализируешь входные данные.
Ты НЕ выполняешь шаги.

Ты только:
- выделяешь логические шаги
- описываешь, что должен сделать агент
- возвращаешь результат СТРОГО в формате JSON

Если задача подразумевает несколько независимых подзадач —
каждая должна быть отдельным шагом.
"""

PLAN_FORMALIZER_SYSTEM_PROMPT = """
Ты — модуль формализации плана.

Твоя задача — преобразовать неформально описанный план
в строго формальный JSON-объект.

Ты не изменяешь смысл шагов.
Ты не добавляешь новых шагов.
Ты не удаляешь существующие шаги.

Если шаги не пронумерованы — пронумеруй их.
"""


def _strip_json(text: str) -> str:
    """
    Пытается аккуратно извлечь JSON-строку из ответа модели:
    - убирает тройные кавычки ```json ... ```
    - если парсинг не удался, пытается найти самый первый '{' и последний '}'
    """
    if not isinstance(text, str):
        return ""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("json\n", "").replace("json\r\n", "")
    # Вторая попытка — взять подстроку между первым { и последним }
    try:
        json.loads(cleaned)
        return cleaned
    except Exception:
        pass
    if "{" in cleaned and "}" in cleaned:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        candidate = cleaned[start : end + 1]
        return candidate
    return cleaned


def _parse_plan_response(answer_text: str) -> dict[str, Any] | None:
    """
    Превращает строку из LLM в Python-объект.
    Ожидается структура { "steps": [ {step_id, goal, fills} ] }.
    """
    try:
        cleaned = _strip_json(answer_text)
        return json.loads(cleaned)
    except Exception:
        return None


def _normalize_to_main_plan(raw_plan: dict[str, Any]) -> dict[str, Any]:
    """
    Нормализует ответ модели в структуру main_plan c полями status/current_step.
    Если модель вернула список шагов без статусов — статусы выставляются в pending.
    """
    plan = copy.deepcopy(MAIN_PLAN_TEMPLATE)

    steps_src = raw_plan.get("steps") if isinstance(raw_plan, dict) else None
    if isinstance(steps_src, list):
        normalized_steps = []
        for item in steps_src:
            if not isinstance(item, dict):
                continue
            step_id = item.get("step_id")
            goal = item.get("goal") or ""
            fills = item.get("fills") if isinstance(item.get("fills"), list) else []
            if step_id is None or goal == "":
                continue
            normalized_steps.append(
                {
                    "step_id": step_id,
                    "goal": goal,
                    "fills": fills,
                    "status": "pending"
                }
            )
        plan["steps"] = normalized_steps
    return plan


def create_main_plan_from_task(task_text) -> dict[str, Any]:
    """
    Создаёт формальный main_plan из текста задачи.
    Возвращает словарь вида {"status": "ok|error", "plan": {...}, "error": "..."}.
    """
    if not isinstance(task_text, str) or not task_text.strip():
        return {"status": "error", "plan": None, "error": "task_text должен быть непустой строкой"}

    user_prompt = f"""Текст задачи:

{task_text.strip()}

Верни глобальный план в формате:

{{
  "steps": [
    {{
      "step_id": number,
      "goal": string,
      "fills": array of strings
    }}
  ]
}}

Никакого текста вне JSON."""

    print(PLANNER_SYSTEM_PROMPT)
    llm_result = send_message_to_ChatGPT(
        prompt=user_prompt,
        system_prompt=PLANNER_SYSTEM_PROMPT,
        is_print=True
    )

    raw_plan = _parse_plan_response(llm_result.answer)
    if raw_plan is None:
        return {
            "status": "error",
            "plan": None,
            "error": "Не удалось распарсить JSON из ответа модели",
            "raw_answer": llm_result.answer
        }

    plan = _normalize_to_main_plan(raw_plan)
    return {"status": "ok", "plan": plan, "raw_answer": llm_result.answer}


def formalize_main_plan(informal_plan_text) -> dict[str, Any]:
    """
    Преобразует неформально описанный план в формальный main_plan.
    Возвращает словарь вида {"status": "ok|error", "plan": {...}, "error": "..."}.
    """
    if not isinstance(informal_plan_text, str) or not informal_plan_text.strip():
        return {"status": "error", "plan": None, "error": "informal_plan_text должен быть непустой строкой"}

    user_prompt = f"""Неформальный план:

{informal_plan_text.strip()}

Верни формализованный план в формате:

{{
  "steps": [
    {{
      "step_id": number,
      "goal": string,
      "fills": array of strings
    }}
  ]
}}

Только JSON."""

    print(PLAN_FORMALIZER_SYSTEM_PROMPT)
    llm_result = send_message_to_ChatGPT(
        prompt=user_prompt,
        system_prompt=PLAN_FORMALIZER_SYSTEM_PROMPT,
        is_print=True
    )

    raw_plan = _parse_plan_response(llm_result.answer)
    if raw_plan is None:
        return {
            "status": "error",
            "plan": None,
            "error": "Не удалось распарсить JSON из ответа модели",
            "raw_answer": llm_result.answer
        }

    plan = _normalize_to_main_plan(raw_plan)
    return {"status": "ok", "plan": plan, "raw_answer": llm_result.answer}


# Пример: построить план из текста задачи
example_task_text = """
Найти, в каком файле говорится про презентацию, и в какое время можно
собрать на собрании необходимых человек. Название файла поместить в file_name,
его содержание - в file_content, а наилучшее время для проведения собрания - в meeting_time
"""
plan_from_task = create_main_plan_from_task(example_task_text)
# print("plan_from_task:", json.dumps(plan_from_task, ensure_ascii=False, indent=4))

# # Пример: формализовать неформальный план
# example_informal_plan = """
# 1. Найти файл, в котором говорится про презентацию
# 2. Узнать, в какое время можно собрать на собрании необходимых человек
# """
# plan_from_informal = formalize_main_plan(example_informal_plan)
# print("plan_from_informal:", json.dumps(plan_from_informal, ensure_ascii=False, indent=4))