import copy
import json
from typing import Any, Callable



from pathlib import Path
import sys
from typing import Any
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ChatGPT.OpenAI_ChatGPT import send_message_to_ChatGPT
from reasoning_agent.agent_tools import *


# Здесь реализован функционал для генерации плана действий в формальном виде,
# из текста задачи, либо из неформального представления плана
# Использует get_result_schema(), который возвращает схему результата задачи, из agent_tools.py


# region Схема main_plan

# Схема описывает "сырой" план, который возвращает модель (до нормализации кодом).
# В runtime reasoning-агент использует нормализованный main_plan (см. MAIN_PLAN_TEMPLATE и _normalize_to_main_plan).
MAIN_PLAN_SCHEMA: dict[str, Any] = {
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
                }
            },
            "required": ["step_id", "goal", "fills"]
        }
    }
}

# Базовый шаблон плана (без шагов), чтобы удобно инициализировать пустой объект
MAIN_PLAN_TEMPLATE: dict[str, Any] = {
    "status": "not_started",
    "current_step": 0,
    "steps": []
}




# region Создаёт main_plan
# из текста задачи

PLANNER_SYSTEM_PROMPT = """
Ты — модуль планирования для reasoning-агента.

Твоя задача — составить МИНИМАЛЬНЫЙ глобальный план,
который определяет, КАКИЕ ЧАСТИ РЕЗУЛЬТАТА должны быть получены
и В КАКИХ ЛОГИЧЕСКИХ ШАГАХ.

ВАЖНЫЕ ПРАВИЛА:

1. Каждый шаг плана ОБЯЗАТЕЛЬНО должен заполнять
   хотя бы одно поле из result_schema.
   Шаги без fills ЗАПРЕЩЕНЫ.

2. План НЕ описывает алгоритм, стратегию или технические действия.
   Он описывает ТОЛЬКО логические подзадачи,
   необходимые для заполнения результата.

3. Если несколько действий приводят к заполнению одних и тех же полей —
   это ДОЛЖЕН быть один шаг.

4. Reasoning-агент сам решает, КАК выполнить шаг.
   План не должен содержать:
   - переборов
   - подготовки данных
   - поиска способов решения
   - технических подшагов

5. Не делай предположений о структуре входных данных,
   если они явно не указаны в тексте задачи.

6. Количество шагов должно быть минимально достаточным
   для заполнения result_schema.

Верни результат СТРОГО в формате JSON.
Никакого текста вне JSON.
"""

def create_main_plan_from_task(
    task_text: str,
    result_schema: dict[str, Any],
    llm_sender: Callable[..., Any] = send_message_to_ChatGPT,
) -> dict[str, Any]:
    """
    Создаёт формальный main_plan из текста задачи.
    Возвращает словарь вида {"status": "ok|error", "plan": {...}, "error": "..."}.
    """
    if not isinstance(task_text, str) or not task_text.strip():
        return {"status": "error", "plan": None, "error": "task_text должен быть непустой строкой"}

    user_prompt = f"""
Текст задачи:

{task_text.strip()}

—————————————————————————————————

Схема результата (result_schema):

{get_result_schema_for_planner(result_schema)}

—————————————————————————————————

Составь глобальный план в формате:

{{
  "steps": [
    {{
      "step_id": number,
      "goal": string,
      "fills": array of strings
    }}
  ]
}}

—————————————————————————————————

Правила:
- каждый шаг должен заполнять хотя бы одно поле result
- шагов должно быть минимально возможное количество
- не описывай технические действия

Верни только JSON.
"""

    print(PLANNER_SYSTEM_PROMPT)
    llm_result = llm_sender(
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





# region Формализует main_plan
# из неформального представления

PLAN_FORMALIZER_SYSTEM_PROMPT = """
Ты — модуль формализации плана.

Твоя задача — преобразовать неформально описанный план
в строго формальный JSON-объект.

Правила:
- Не изменяй смысл шагов.
- Не добавляй новых шагов.
- Не удаляй существующие шаги.
- Если шаги не пронумерованы — пронумеруй их.
- Используй result_schema, чтобы определить, какие поля результата должен заполнять каждый шаг.
- Заполняй только поля, которые логически соответствуют цели шага.
- Шаги должны быть минимальными и необходимыми для заполнения result_schema.
- Не описывай технические действия.
"""

def formalize_main_plan(
    informal_plan_text: str,
    result_schema: dict[str, Any],
    llm_sender: Callable[..., Any] = send_message_to_ChatGPT,
) -> dict[str, Any]:
    """
    Преобразует неформально описанный план в формальный main_plan.
    Возвращает словарь вида {"status": "ok|error", "plan": {...}, "error": "..."}.
    """
    if not isinstance(informal_plan_text, str) or not informal_plan_text.strip():
        return {"status": "error", "plan": None, "error": "informal_plan_text должен быть непустой строкой"}

    user_prompt = f"""Возьми неформальный план:

"
{informal_plan_text.strip()}
"

—————————————————————————————————

Верни формализованный план в формате JSON:

{{
  "steps": [
    {{
      "step_id": number,
      "goal": string,
      "fills": array of strings
    }}
  ]
}}

—————————————————————————————————

Схема результата (result_schema):

{get_result_schema_for_planner(result_schema)}

—————————————————————————————————

Правила:
- каждый шаг должен заполнять хотя бы одно поле result
- шагов должно быть минимально возможное количество
- не описывай технические действия

Верни только JSON.
"""

    print(PLAN_FORMALIZER_SYSTEM_PROMPT)
    llm_result = llm_sender(
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




# region Доп. функции - нормализаторы

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
        candidate = cleaned[start: end + 1]
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

# Собирает схему результатов в формате "имя поля": "описание"
def get_result_schema_for_planner(schema: dict) -> dict:
    """
    Будет выглядеть (обогащённо required-флагом, чтобы планировщик не требовал optional-поля):
    {
        "file_name": {"description": "Имя файла", "required": true},
        "file_content": {"description": "Содержимое файла", "required": true},
        "meeting_time": {"description": "Время проведения собрания", "required": true}
    }
    """
    return {
        field: {
            "description": (meta.get("description", "") if isinstance(meta, dict) else ""),
            "required": (meta.get("required", True) if isinstance(meta, dict) else True),
        }
        for field, meta in (schema.items() if isinstance(schema, dict) else [])
    }





# region Примеры

# # Примеры использования (не вызываются по умолчанию; можно раскомментировать при отладке)
# # Генерация плана из текста задачи
# example_task_text = """
# Найти, в каком файле говорится про презентацию, и в какое время можно
# собрать на собрании необходимых человек. Название файла поместить в file_name,
# его содержание - в file_content, а наилучшее время для проведения собрания - в meeting_time
# """
# plan_from_task = create_main_plan_from_task(example_task_text, get_result_schema())

# # Генерация плана из неформального описания плана
# example_informal_plan = """
# 1. Найти файл, в котором говорится про презентацию
# 2. Узнать, в какое время можно собрать на собрании необходимых человек
# """
# plan_from_informal = formalize_main_plan(example_informal_plan, get_result_schema())

