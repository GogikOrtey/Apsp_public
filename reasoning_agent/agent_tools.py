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

from reasoning_agent.runtime_state import (
    get_main_plan as _get_runtime_main_plan,
    get_long_term_memory as _get_runtime_long_term_memory,
)

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

# # Пример входных данных 2
# FILES = {
#     "notes.txt": "Встреча в пятницу. Купить хлеб. Проверить отчёт.",
#     "todo.txt": "Нужно на собрании показать презентацию Алексею и Анне",
#     "archive.txt": "Старые заметки за 2022 год.",
#     "schedule_alexey.txt": "Расписание Алексея: Свободен с 12:30 до 16:00",
#     "schedule_anna.txt": "Расписание Анны: Свободна с 14:00 до 15:00",
#     # "schedule_anna.txt": "Расписание Анны: Занята весь день - в коммандировке", # Плохой пример
#     "schedule_vladimir.txt": "Расписание Владимира: Свободен весь день",
# }


### Тут надо будет потом реализовать функцию, которая принимает результат, и разбивает его на схему и шаблон
### А также добавить простую дефолтную схему, с одним результатом


# # Старая схема результата
# main_result_schema = {
#     "file_name": {
#         "type": "string",
#         "required": True,
#         "description": "Имя файла"
#     },
#     "file_content": {
#         "type": "string",
#         "required": True,
#         "description": "Содержимое файла"
#     }
# }

# # Старый шаблон результата, который агент заполняет в процессе работы
# main_result_template = {
#     "file_name": None,
#     "file_content": None
# }



# Текущая схема и текущий результат, который агент постепенно заполняет.
# Инициализация делается через init_result(...) (см. ниже).
RESULT_SCHEMA: dict[str, Any] = {}
RESULT: dict[str, Any] = {}


def init_result(schema: dict[str, Any] | None = None, template: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Инициализирует (или переинициализирует) схему результата и сам результат.
    """
    global RESULT_SCHEMA, RESULT
    if not isinstance(schema, dict) or not schema:
        raise ValueError("init_result: result_schema должен быть передан явно и не может быть пустым")
    if not isinstance(template, dict) or not template:
        raise ValueError("init_result: result_template должен быть передан явно и не может быть пустым")
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


####### Старые инструменты, для примера

# @tool(
#     name="list_files",
#     description="Возвращает список всех файлов в окружении",
#     args=[],
#     # ВАЖНО: лучше хранить `returns` как структуру (dict/list), а не как JSON-строку внутри строки.
#     # Тогда при json.dumps() не будет экранирования кавычек вида \"...\".
#     returns={
#         "files": ["notes.txt", "todo.txt", "..."]
#     },
#     example_args={}
# )
# def list_files():
#     # JSON-friendly ответ, чтобы совпадало с аннотацией returns
#     return {"files": list(FILES.keys())}


# @tool(
#     name="read_file",
#     description="Читает содержимое файла по имени. Возвращает словарь с содержимым и статусом",
#     args=[
#             {
#                 "name": "filename", 
#                 "type": "str", 
#                 "required": True, 
#                 "description": "Имя файла"
#             }
#         ],
#     returns=[
#         {"status": "ok", "content": "..."},
#         {"status": "error", "content": None}
#     ],
#     example_args={"filename": "todo.txt"}
# )
# def read_file(filename):
#     if filename in FILES:
#         return {"status": "ok", "content": FILES[filename]}
#     else:
#         return {"status": "error", "content": None}


# @tool(
#     name="search_in_file",
#     description="Ищет вхождения подстроки в тексте файла",
#     args=[
#         {
#             "name": "filename",
#             "type": "str", 
#             "required": True, 
#             "description": "Имя файла"
#         },
#         {
#             "name": "substr", 
#             "type": "str", 
#             "required": True, 
#             "description": "Подстрока для поиска"
#         }
#     ],
#     returns={
#         "status": "ok|error",
#         "count": "int",
#         "first_index": "int|null"
#     },
#     example_args={"filename": "todo.txt", "substr": "презентац"}
# )
# def search_in_file(filename, substr):
#     if filename not in FILES:
#         return {"status": "error", "count": 0, "first_index": None}
    
#     text = FILES[filename]
#     count = text.count(substr)
#     first_index = text.find(substr) if count > 0 else None
    
#     return {"status": "ok", "count": count, "first_index": first_index}



# region update_result
@tool(
    name="update_result",
    description=(
        "Обновляет поле(я) в объекте результата (result). "
        "Можно обновлять либо одно поле (field/value), либо сразу несколько через updates. "
        "Используй это, чтобы постепенно собрать финальный ответ по заданной схеме."
    ),
    args=[
        {
            "name": "field",
            "type": "str",
            "required": False,
            "description": "Имя поля в result (для одиночного обновления). Пример: 'file_name' или 'meta.url'"
        },
        {
            "name": "value",
            "type": "any",
            "required": False,
            "description": "Значение, которое нужно записать в указанное поле (для одиночного обновления)"
        },
        {
            "name": "updates",
            "type": "any",
            "required": False,
            "description": (
                "Пакетное обновление нескольких полей. "
                "Вариант 1: список объектов [{'field': 'a', 'value': 1}, ...]. "
                "Вариант 2: словарь {'a': 1, 'b.c': 2}. "
                "Можно передать вместе с field/value — тогда применятся все обновления."
            )
        }
    ],
    returns={
        "status": "ok|error",
        "result": "{...}",
        "error": "str|null"
    },
    example_args={
        "updates": [
            {"field": "file_name", "value": "todo.txt"},
            {"field": "file_content", "value": "Привет!"}
        ]
    }
)
def update_result(field: str | None = None, value: Any = None, updates: Any = None):
    global RESULT, RESULT_SCHEMA

    def _apply_one_update(one_field: Any, one_value: Any) -> dict[str, Any]:
        if not isinstance(one_field, str) or not one_field.strip():
            return {"status": "error", "result": RESULT, "error": "field должен быть непустой строкой"}

        path = [p for p in one_field.strip().split(".") if p]
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

        node[path[-1]] = one_value
        return {"status": "ok", "result": RESULT, "error": None}

    # Собираем список обновлений из (updates) и/или (field/value)
    updates_list: list[dict[str, Any]] = []

    if updates is not None:
        if isinstance(updates, dict):
            for k, v in updates.items():
                updates_list.append({"field": k, "value": v})
        elif isinstance(updates, list):
            for item in updates:
                updates_list.append(item)
        else:
            return {
                "status": "error",
                "result": RESULT,
                "error": "updates должен быть dict или list"
            }

    if field is not None or value is not None:
        updates_list.append({"field": field, "value": value})

    if not updates_list:
        return {
            "status": "error",
            "result": RESULT,
            "error": "Нужно передать либо (field и value), либо updates"
        }

    updated = 0
    for item in updates_list:
        if not isinstance(item, dict):
            return {
                "status": "error",
                "result": RESULT,
                "error": "Каждый элемент updates должен быть объектом вида {'field': ..., 'value': ...}"
            }
        one_field = item.get("field")
        one_value = item.get("value")
        r = _apply_one_update(one_field, one_value)
        if r.get("status") != "ok":
            # Возвращаем текущий RESULT (возможны частичные обновления)
            return r
        updated += 1

    update_content_front_update_result(str(RESULT))
    return {"status": "ok", "result": RESULT, "updated": updated}

# Примечание: поддерживаются вложенные пути через точку, например "meta.url" или "b.c"
# Но сейчас не используются в сценариях использования агента
# И они не протестированы


# region update_memory
@tool(
    name="update_memory",
    description=(
        "Добавляет значение в долговременную память агента (long_term_memory). "
        "Используй, когда нужно сохранить факт/наблюдение, которое понадобится позже."
    ),
    args=[
        {
            "name": "value",
            "type": "any",
            "required": True,
            "description": "Значение для сохранения (обычно строка). Если передан массив — будет добавлен целиком (extend)."
        }
    ],
    returns={
        "status": "ok|error",
        "added": "int",
        "memory_size": "int|null",
        "error": "str|null"
    },
    example_args={"value": "old_url=https://makitaclub.ru/"}
)
def update_memory(value: Any):
    memory = _get_runtime_long_term_memory()
    if memory is None:
        return {
            "status": "error",
            "added": 0,
            "memory_size": None,
            "error": "long_term_memory не инициализирован (runtime_state.get_long_term_memory() == None)"
        }

    # Поддерживаем как одиночное значение, так и список значений
    if isinstance(value, list):
        memory.extend(value)
        return {"status": "ok", "added": len(value), "memory_size": len(memory), "error": None}

    memory.append(value)
    return {"status": "ok", "added": 1, "memory_size": len(memory), "error": None}


# region goto_main_plan_step
@tool(
    name="goto_main_plan_step",
    description=(
        "Перемещает main_plan на указанный РАНЕЕ выполненный шаг (назад относительно текущего). "
        "Используй, когда нужно переиграть/уточнить уже закрытую фазу плана. "
        "По умолчанию очищает поля result из fills выбранного шага, чтобы оркестратор не продвинул план вперёд сразу же."
    ),
    args=[
        {
            "name": "step_index",
            "type": "int",
            "required": False,
            "description": "Индекс шага в main_plan.steps (0..N-1). Можно не задавать, если задан step_id."
        },
        {
            "name": "step_id",
            "type": "int",
            "required": False,
            "description": "Идентификатор шага step_id (обычно 1..N). Можно не задавать, если задан step_index."
        },
        {
            "name": "clear_fills",
            "type": "bool",
            "required": False,
            "description": "Очищать ли поля result, указанные в fills выбранного шага (по умолчанию True)."
        },
        {
            "name": "reset_following_steps",
            "type": "bool",
            "required": False,
            "description": "Сбросить ли статусы всех последующих шагов в pending (по умолчанию True)."
        }
    ],
    returns={
        "status": "ok|error",
        "error": "str|null",
        "from_step": "int",
        "to_step": "int",
        "cleared_fields": "array",
        "steps_status": "array"
    },
    example_args={"step_id": 1, "clear_fills": True, "reset_following_steps": True}
)
def goto_main_plan_step(
    step_index: int | None = None,
    step_id: int | None = None,
    clear_fills: bool = True,
    reset_following_steps: bool = True,
):
    main_plan = _get_runtime_main_plan()
    if not isinstance(main_plan, dict):
        return {"status": "error", "error": "main_plan не инициализирован (runtime_state пуст)"}

    steps = main_plan.get("steps")
    if not isinstance(steps, list) or not steps:
        return {"status": "error", "error": "main_plan.steps пуст или имеет неверный формат"}

    current_idx = main_plan.get("current_step", 0)
    if not isinstance(current_idx, int) or current_idx < 0:
        current_idx = 0

    target_idx: int | None = None
    if isinstance(step_index, int):
        target_idx = step_index
    elif isinstance(step_id, int):
        for i, s in enumerate(steps):
            if isinstance(s, dict) and s.get("step_id") == step_id:
                target_idx = i
                break

    if target_idx is None:
        return {"status": "error", "error": "Нужно указать step_index (0..N-1) или step_id (1..N)"}

    if not isinstance(target_idx, int) or target_idx < 0 or target_idx >= len(steps):
        return {"status": "error", "error": f"target_idx вне диапазона: {target_idx}"}

    if target_idx >= current_idx:
        return {
            "status": "error",
            "error": f"Можно перейти только на более ранний шаг: target={target_idx}, current={current_idx}"
        }

    target_step = steps[target_idx] if isinstance(steps[target_idx], dict) else {}
    if target_step.get("status") != "done":
        return {
            "status": "error",
            "error": f"Целевой шаг должен быть выполненным (status='done'), сейчас: {target_step.get('status')!r}"
        }

    # Откатываем current_step и статусы
    main_plan["status"] = "in_progress"
    main_plan["current_step"] = target_idx

    for i, s in enumerate(steps):
        if not isinstance(s, dict):
            continue
        if i < target_idx:
            s["status"] = "done"
        elif i == target_idx:
            s["status"] = "in_progress"
        else:
            if reset_following_steps:
                s["status"] = "pending"

    cleared_fields: list[str] = []
    if clear_fills:
        fills = target_step.get("fills") if isinstance(target_step.get("fills"), list) else []
        for f in fills:
            if not isinstance(f, str) or not f.strip():
                continue
            # update_result делает минимальную валидацию по RESULT_SCHEMA
            resp = update_result(f.strip(), None)
            if isinstance(resp, dict) and resp.get("status") == "ok":
                cleared_fields.append(f.strip())

    steps_status = []
    for s in steps:
        if not isinstance(s, dict):
            continue
        steps_status.append({"step_id": s.get("step_id"), "status": s.get("status")})

    return {
        "status": "ok",
        "error": None,
        "from_step": current_idx,
        "to_step": target_idx,
        "cleared_fields": cleared_fields,
        "steps_status": steps_status
    }
# endregion goto_main_plan_step


