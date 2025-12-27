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

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Подключение всех библиотек и функций
from import_all_libraries import *
from ChatGPT.OpenAI_ChatGPT import send_message_to_ChatGPT
from reasoning_agent.chat_terminal import init_chat_channel, chat_print

# Подключаю инструменты
from reasoning_agent.agent_tools import *
from reasoning_agent.plan_tools import *
from reasoning_agent.runtime_state import (
    set_main_plan as _set_runtime_main_plan,
    set_long_term_memory as _set_runtime_long_term_memory,
)







"""         СПИСОК ЗАДАЧ:



"""




"""            ОПИСАНИЕ

Реализация reasoning-агента, который выполняет задачу по шагам, в рамках плана, используя доступные инструменты, и пошагово заполняя результат result найденными значениями

Коротко о том, как тут всё работает:

Перед началом работы надо задать задание (main_task), верную схему результата (main_result_schema) и шаблон результата (main_result_template), который будет заполнять модель.

Если не задан план - он сгенерируется через create_main_plan_from_task(), на основе текста задачи (main_task)
Если есть неформальный - используйте example_informal_plan() из plan_tools.py
Если есть формальный - задайте явно в main_plan

По структуре ответов модели - расписано подробнее ниже, в orchestrate()

Оркестратор вызывает модель, и на каждом шаге она выбирает инструмент, и использует его. Либо пишет данные в result используя update_result, либо возвращает DONE|FAILED и завершает задачу

В результате оркестратор вернёт текст с итогом, а объект result можно будет получить через get_result()

Все доступные инструменты прописаны в agent_tools.py

"""





# region Переменная для хранения задачи

main_task = """
Найти, в каком файле говорится про презентацию, и в какое время можно собрать на собрании необходимых человек. Название файла поместить в file_name, его содержание - в file_content, а наилучшее время для проведения собрания - в meeting_time
"""

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

# Создаю план задачи в формальном виде (устанавливается при запуске)
main_plan = None

# Пример явного плана в формальной форме (оставлен для справки, по умолчанию не используется)
example_main_plan = {
    "status": "not_started",
    "current_step": 0,
    "steps": [
        {
            "step_id": 1,
            "goal": "Определить, в каком файле упоминается презентация, и извлечь из него имя и полное содержание.",
            "fills": [
                "file_name",
                "file_content"
            ],
            "status": "pending"
        },
        {
            "step_id": 2,
            "goal": "Определить наилучшее время, когда на собрании можно собрать всех необходимых людей.",
            "fills": [
                "meeting_time"
            ],
            "status": "pending"
        }
    ]
}

if False and not main_plan:
    # Создаю план задачи в формальном виде
    _main_plan_resp = create_main_plan_from_task(main_task, main_result_schema)

    if isinstance(_main_plan_resp, dict) and _main_plan_resp.get("status") == "ok":
        plan_value = _main_plan_resp.get("plan")
        if isinstance(plan_value, dict):
            main_plan = plan_value

    if not isinstance(main_plan, dict):
        # Фоллбэк на безопасный пустой план
        main_plan = copy.deepcopy(MAIN_PLAN_TEMPLATE)





HISTORY_WINDOW = 12         # = 6 шагов - это сколько последних шагов отдаём в модель, в history
MAX_STEPS = 30              # Максимальное количество шагов агента для решения задачи
INVALID_JSON_RETRIES = 1    # Повторяем запрос шага при невалидном JSON ответа

long_term_memory = []       # Долговременная память, в которую агент может записать данные, при помощи memory_updates
steps_future_value = ""     # Описание следующих шагов, которые наметила себе модель

# region Собираю аннотации инструментов
tools_annotation = get_tools_annotations()

# region Обработчик хранения истории
history = [] # Хранилище всей истории шагов
count_of_step_on_history = 0 # Текущий номер шага в истории шагов

# region Reset state между запусками
def reset_agent_state(*, clear_history: bool = True, clear_memory: bool = True, clear_steps_future: bool = True) -> None:
    """
    Сбрасывает runtime-состояние reasoning-агента между независимыми запусками.

    Важно:
    - НЕ трогает состояние Playwright/браузера (страница остаётся открытой).
    - RESULT/result_schema сбрасываются отдельно через init_result(...) внутри orchestrate().
    - clear_memory=True очищает long_term_memory in-place (runtime_state хранит ссылку на список).
    """
    global count_of_step_on_history, steps_future_value, main_plan

    if clear_history:
        history.clear()
        count_of_step_on_history = 0

    if clear_memory:
        long_term_memory.clear()

    if clear_steps_future:
        steps_future_value = ""

    # main_plan всё равно будет переопределён внутри orchestrate(),
    # но на всякий случай сбрасываем ссылку, чтобы не вводить в заблуждение отладку.
    main_plan = None

# Запускаю второй терминал для кастомного чата
CHAT_LOG_PATH = init_chat_channel()

# --- Safe JSON helpers ---
# В реальном мире инструменты иногда возвращают не-JSON-serializable объекты (set, bytes,
# playwright Page/ElementHandle и т.п.). История и prompt собираются через json.dumps(),
# поэтому важно не падать на сериализации.
def safe_json_dumps(obj: Any, *, indent: int | None = None) -> str:
    """
    Гарантированно возвращает строку: либо JSON, либо безопасный fallback через default=str,
    либо str(obj), чтобы агент не падал на логировании/формировании промпта.
    """
    try:
        return json.dumps(obj, ensure_ascii=False, indent=indent)
    except Exception:  # noqa: BLE001
        try:
            return json.dumps(obj, ensure_ascii=False, indent=indent, default=str)
        except Exception:  # noqa: BLE001
            return str(obj)

# Добавляет запись в историю с автоинкрементом порядкового номера
def add_history_entry(entry: dict[str, Any]) -> None:
    global count_of_step_on_history
    count_of_step_on_history += 1
    history.append({"step": count_of_step_on_history, **entry})




# region Системный промпт

SYSTEM_PROMPT = """
Ты — reasoning-агент, который решает задачи пошагово, строго следуя Глобальному Плану (main_plan).

Ты работаешь в интерактивном браузере (Playwright), и взаимодействуешь с реальной веб-страницей через инструменты (goto_url, click_element, press_key, find_elements и т.п.).
- Страница может изменяться после твоих действий (навигация, SPA-обновления, AJAX).
- Единственный источник истины о состоянии страницы — блок "Контекст браузера (Playwright)" в промпте шага.
- Ты всегда работаешь с одной текущей открытой страницей, на одной вкладке. Если ты выполняешь действие перехода на другую страницу, то текущая страница заменяется новой, и далее ты работаешь только с этой новой версией страницы.

ОБЩИЕ ПРАВИЛА:
- Ты выполняешь задачу итеративно, шаг за шагом, работая в рамках ТЕКУЩЕЙ ФАЗЫ Глобального Плана
- На каждом шаге ты выбираешь ОДНО действие (action)
- На каждом шаге ты возвращаешь ровно ОДИН JSON-объект, соответствующий следующему шагу
- Даже если шаги очевидны — верни только один следующий шаг
- Любой текст в твоём ответе вне одного JSON-объекта считается ошибкой
- Если задача решена (все фазы плана завершены) — используй action="DONE"
- Если в ходе рассуждений ты понимаешь, что цель текущей фазы или всей задачи недостижима (нет данных, логическое противоречие и т.п.) — не выдумывай результат. Заполни доступные поля описанием проблемы и используй action="FAILED", указав причину в args.reason
- Ты не выдумываешь результаты инструментов — они приходят извне
- Ты не повторяешь уже выполненные действия без причины

ГЛОБАЛЬНЫЙ ПЛАН (main_plan):
- План разбит на фазы. У каждой фазы есть цель (goal) и список полей (fills), которые нужно заполнить в result.
- Твоя приоритетная задача — выполнить цель ТЕКУЩЕЙ АКТИВНОЙ ФАЗЫ.
- Не пытайся выполнять задачи будущих фаз, пока не закрыты требования текущей.

ИСТОРИЯ (history):
- history — это кратковременная история твоих последних действий и наблюдений
- history может быть усечена в любой момент, старые шаги могут исчезать
- history не является надёжным источником фактов и отражает лишь ход выполнения задачи
- нельзя рассчитывать на сохранность информации в history между шагами
- любая информация (факт, вывод, наблюдение, результат инструмента), которая может понадобиться для:
заполнения result, принятия решений на следующих шагах, будущих фаз плана - должна быть сохранена в memory через memory_updates или инструмент update_memory(value)
- не нужно сохранять в memory информацию, которая уже надёжно зафиксирована в result

ДОЛГОВРЕМЕННАЯ ПАМЯТЬ (memory):
- memory содержит информацию, которую ты ранее сохранил
- memory передаётся тебе полностью на каждом шаге
- memory не ограничена HISTORY_WINDOW
- если информация может понадобиться позже — сохрани её через memory_updates или инструмент update_memory(value)

ТЕКУЩИЙ ТАКТИЧЕСКИЙ ПЛАН (steps_future):
- steps_future — это твоя тактическая гипотеза действий внутри ТЕКУЩЕЙ ФАЗЫ глобального плана
- используй её как ориентир для декомпозиции цели фазы
- на каждом шаге переписывай steps_future полностью
- если план стал неактуален — замени его полностью

ИНСТРУМЕНТЫ:
- используй только инструменты из списка доступных
- передавай корректные аргументы
- не используй инструмент, если результат уже известен

КОНТЕКСТ БРАУЗЕРА (Playwright):
- Любые селекторы, тексты и DOM-наблюдения действительны ТОЛЬКО для текущей версии страницы (Page version).
- Если Page version изменилась — все старые DOM-наблюдения считаются устаревшими.
- Если после действия last_change.type == "none", значит действие не привело к изменению страницы. В этом случае НЕ повторяй то же действие без изменения стратегии.
- Смена URL всегда означает новую версию страницы (Page version увеличивается), даже если страница визуально похожа.
- History actions since load относится только к текущей версии страницы. При смене Page version это новая страница.

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
- Ты ВСЕГДА отвечаешь строго валидным JSON
- Без пояснений, без markdown, без текста вне JSON
- Не забывай что все обратные слэши и кавычки нужно экранировать, когда будешь записывать значения в поле result, чтобы JSON был валидным.

РЕЗУЛЬТАТ (result):
- Тебе будет дан result_schema и текущий result
- Заполняй result ПОШАГОВО через инструмент update_result(field, value)
- Текущая фаза считается завершенной, когда заполнены все обязательные поля, указанные в её "fills"
- Используй action="DONE" только когда все фазы Глобального Плана выполнены и result полон
- Используй action="FAILED" только когда ты не можешь продвинуться из-за недостижимости цели; в args обязательно передай reason (строку)

МЕНТАЛЬНАЯ МОДЕЛЬ:
- 1. Определи текущую активную ФАЗУ в Глобальном Плане и её цель (goal).
- 2. Проверь, какие поля из списка "fills" текущей фазы еще не заполнены в result.
- 3. Спланируй ОДИН атомарный шаг (action), чтобы приблизиться к заполнению этих полей.
- 4. После ответа управление ВСЕГДА возвращается оркестратору.
- 5. Ты НИКОГДА не выполняешь следующий шаг сам.
"""

print(f"SYSTEM_PROMPT = {SYSTEM_PROMPT}")
chat_print(f"SYSTEM_PROMPT = {SYSTEM_PROMPT}")








""" 

————————————————————————————————————
Контекст браузера (Playwright)

Текущая открытая страница: https://makitaclub.ru/search/?s=makita
HTTP status: 200

DOM summary:
- total elements: 4831
- links: 212
- inputs: 3
- buttons: 17

После какого последнего действия произошли изменения на странице:
- type: navigation | dom_update | none
- trigger: press_enter()
- delta_text: 18%

History actions since load on this page:
1. focus(".search-input")
2. human_like_input("makita")
3. press_enter()
4. wait_for_navigation_or_content()
... 

————————————————————————————————————


"""






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

    block_json = safe_json_dumps(block, indent=4)

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

    # Общий статус плана - скорее отладочная информация.
    # Чтобы не засорять промпт, показываем его только для не-обычных состояний.
    plan_status = main_plan.get("status", "unknown")
    if plan_status in ("completed", "not_started", "unknown"):
        lines.append(f"СТАТУС ПЛАНА: {plan_status}")
    lines.append("ШАГИ ПЛАНА (фазы):")

    steps = main_plan.get("steps", [])
    if not isinstance(steps, list):
        return "Глобальный план задан в некорректном формате."

    for idx, step in enumerate(steps):
        # Маркер текущего шага
        marker = "АКТИВНАЯ ФАЗА" if idx == current_idx else ""
        if isinstance(step, dict) and step.get("status") == "done":
            marker = "ЗАВЕРШЕНО"

        if not isinstance(step, dict):
            step_desc = f"{marker} [Фаза {idx + 1}] (некорректный шаг)"
            lines.append(step_desc)
            continue

        # Показываем required/optional fills по текущей схеме результата (если возможно)
        schema_obj = get_result_schema()
        fills_all = step.get("fills", [])
        fills_required_only: list[str] = []
        fills_optional: list[str] = []
        if isinstance(fills_all, list):
            fills_str = [f.strip() for f in fills_all if isinstance(f, str) and f.strip()]
            required_only = [f for f in fills_str if _is_schema_field_required(schema_obj, f)]
            if required_only:
                fills_required_only = required_only
                fills_optional = [f for f in fills_str if f not in set(required_only)]
            else:
                # Фоллбэк: если required не определён/не распознан — считаем все fills обязательными
                fills_required_only = fills_str

        optional_line = f"   Необязательные поля (required=false): {fills_optional}\n" if fills_optional else ""
        step_desc = (
            f"{marker} [Фаза {step.get('step_id', idx + 1)}]\n"
            f"   Цель (Goal): {step.get('goal', '')}\n"
            f"   Требует заполнить (Fills): {fills_required_only}\n"
            f"{optional_line}"
            f"   Статус: {step.get('status', 'unknown')}"
        )
        lines.append(step_desc)

    return "\n".join(lines)


def build_playwright_context_block_for_prompt(*, max_actions: int = 10) -> str:
    """
    Собирает диагностический блок по текущей странице Playwright для вставки в промпт.

    Важно: блок должен быть "best-effort" и никогда не ломать работу агента.
    """
    try:
        from playwright_tool.shared_page import (  # локальный импорт, чтобы избежать лишних зависимостей при старте
            get_shared_page,
            get_playwright_context_snapshot,
        )
    except Exception:
        return ""

    try:
        page = get_shared_page()
    except Exception:
        return ""

    try:
        snapshot = get_playwright_context_snapshot(max_actions=max_actions)
    except Exception:
        snapshot = {"current_url": None, "http_status": None, "last_change": {}, "actions_since_load": []}

    url = None
    try:
        url = page.url
    except Exception:
        url = None
    if not url:
        url = snapshot.get("current_url")

    http_status = snapshot.get("http_status")
    page_version = snapshot.get("page_version")
    nav_count = snapshot.get("nav_count")
    load_state = snapshot.get("load_state")
    last_document_ts = snapshot.get("last_document_ts")
    last_change = snapshot.get("last_change") or {}
    actions = snapshot.get("actions_since_load") or []

    # Время "с момента загрузки страницы" (best-effort):
    # 1) основной источник — last_document_ts (top-level document response)
    # 2) fallback — performance.now() (секунды с момента начала навигации)
    time_since_load_s: float | None = None
    try:
        if isinstance(last_document_ts, (int, float)) and last_document_ts > 0:
            time_since_load_s = max(0.0, float(time.time()) - float(last_document_ts))
    except Exception:
        time_since_load_s = None

    if time_since_load_s is None:
        try:
            perf_now_s = page.evaluate(
                "() => (typeof performance !== 'undefined' && typeof performance.now === 'function') ? (performance.now() / 1000) : null"
            )
            if isinstance(perf_now_s, (int, float)):
                time_since_load_s = max(0.0, float(perf_now_s))
        except Exception:
            time_since_load_s = None

    time_since_load_text = (
        f"{time_since_load_s:.1f} сек" if isinstance(time_since_load_s, (int, float)) else "—"
    )

    # DOM summary (быстро и дёшево)
    dom_counts = None
    try:
        dom_counts = page.evaluate(
            """() => ({
                total: document.getElementsByTagName('*').length,
                links: document.querySelectorAll('a').length,
                inputs: document.querySelectorAll('input').length,
                buttons: document.querySelectorAll('button').length
            })"""
        )
    except Exception:
        dom_counts = None

    total_elems = dom_counts.get("total") if isinstance(dom_counts, dict) else None
    links = dom_counts.get("links") if isinstance(dom_counts, dict) else None
    inputs = dom_counts.get("inputs") if isinstance(dom_counts, dict) else None
    buttons = dom_counts.get("buttons") if isinstance(dom_counts, dict) else None

    # Форматируем историю действий как в примере
    if actions:
        actions_lines = "\n".join(f"{i + 1}. {a}" for i, a in enumerate(actions))
    else:
        actions_lines = "—"

    last_type = last_change.get("type") or "none"
    last_trigger = last_change.get("trigger") or "unknown"
    last_delta = last_change.get("delta_text") or "null"

    # Если страница закрыта/неактивна — не шумим (но блок оставим, чтобы модель понимала, что нет контекста)
    try:
        if getattr(page, "is_closed", None) and page.is_closed():
            return """
————————————————————————————————————
Контекст браузера (Playwright)

Страница Playwright закрыта (page.is_closed() == True)

"""
    except Exception:
        pass

    return f"""
————————————————————————————————————
Контекст браузера (Playwright)

Текущая открытая страница: {url}
HTTP status: {http_status}
Page version: {page_version}
Navigations since start: {nav_count}
Load state: {load_state}
Time since the page was loaded: {time_since_load_text}

DOM summary:
- total elements: {total_elems}
- links: {links}
- inputs: {inputs}
- buttons: {buttons}

Изменения, которые произошли после последнего действия на странице:
- type: {last_type}
- trigger: {last_trigger}
- delta_text: {last_delta}

History actions since load on this page:
{actions_lines}

"""


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
        # deepcopy может упасть на не-копируемых объектах, если инструмент вернул что-то "живое"
        try:
            entry_copy = copy.deepcopy(entry)
        except Exception:  # noqa: BLE001
            entry_copy = {"role": entry.get("role"), "name": entry.get("name"), "content": str(entry.get("content")), "result": str(entry.get("result"))}

        # Для ответов модели оставляем только target/action/args/reasoning
        if entry_copy.get("role") == "assistant":
            content = entry_copy.get("content") or {}
            entry_copy["content"] = {
                key: content.get(key)
                for key in ("target", "action", "args", "reasoning")
                if key in content
            }

        history_for_prompt.append(entry_copy)

    history_text = safe_json_dumps(history_for_prompt, indent=4)


    # Шаги на будущее
    steps_future_for_prompt = steps_future_value or []
    steps_future_text = safe_json_dumps(steps_future_for_prompt, indent=4)

    # Долговременная память
    long_term_memory_value = safe_json_dumps(long_term_memory, indent=4)


    # Элементы, которые будут удалены на следующем шаге
    def first_deleted_element_put():
        # Показываем два самых "старых" элемента текущего окна, которые первыми выпадут
        if len(history) < HISTORY_WINDOW:
            return ""

        window_slice = history[-HISTORY_WINDOW:]
        about_to_drop = window_slice[:2]

        drop_block = ",\n".join(safe_json_dumps(item, indent=4) for item in about_to_drop)

        str_description = f"""
История ограничена {HISTORY_WINDOW} шагами.
Следующие элементы истории будут удалены:

{drop_block}

Если в этих шагах есть информация, которая может понадобиться позже — сохрани её сейчас в memory_updates

"""
        return str_description

    # Собираю историю последнего шага - цели и результата инструмента
    last_step_state_block = build_last_step_state_block(history)

    # Схема результата и текущий результат (агент заполняет его через update_result)
    result_schema_text = safe_json_dumps(get_result_schema(), indent=4)
    current_result_text = safe_json_dumps(get_result(), indent=4)


    # --- Формирование текста плана ---
    main_plan_text = format_main_plan_for_prompt(main_plan)

    # Получаем цель текущей фазы для явного акцента
    current_idx = main_plan.get("current_step", 0) if isinstance(main_plan, dict) else 0
    steps_list = main_plan.get("steps", []) if isinstance(main_plan, dict) else []
    current_phase_goal = "Цель не определена"
    current_phase_fills = []
    current_phase_optional_fills: list[str] = []

    if isinstance(steps_list, list) and 0 <= current_idx < len(steps_list) and isinstance(steps_list[current_idx], dict):
        current_phase_goal = steps_list[current_idx].get("goal") or current_phase_goal
        current_phase_fills = steps_list[current_idx].get("fills") or []

    # В промпте фокусируем модель на обязательных полях (required=true), чтобы optional не блокировали прогресс.
    schema_obj = get_result_schema()
    if isinstance(current_phase_fills, list):
        fills_str = [f.strip() for f in current_phase_fills if isinstance(f, str) and f.strip()]
        required_only = [f for f in fills_str if _is_schema_field_required(schema_obj, f)]
        if required_only:
            current_phase_fills = required_only
            current_phase_optional_fills = [f for f in fills_str if f not in set(required_only)]
        else:
            current_phase_fills = fills_str
            current_phase_optional_fills = []

    playwright_context_block = build_playwright_context_block_for_prompt(max_actions=12)

    optional_focus_line = (
        f"Опциональные поля (required=false, не блокируют завершение фазы): {current_phase_optional_fills}\n"
        if current_phase_optional_fills
        else ""
    )

    return f"""
ДОСТУПНЫЕ ИНСТРУМЕНТЫ (аннотации):
{tools_json}

————————————————————————————————————

ТЕКУЩАЯ ЗАДАЧА (общее описание):
{task}

————————————————————————————————————

ГЛОБАЛЬНЫЙ ПЛАН ЗАДАЧИ (main_plan):
{main_plan_text}

————————————————————————————————————

ТВОЙ ФОКУС ПРЯМО СЕЙЧАС (текущая фаза):
Цель фазы: {current_phase_goal}
Необходимо заполнить поля в result: {current_phase_fills}
{optional_focus_line}

ТАКТИЧЕСКИЙ ПЛАН (steps_future) должен вести к завершению этой фазы
{playwright_context_block}
————————————————————————————————————

ТРЕБУЕМЫЙ ФОРМАТ РЕЗУЛЬТАТА (result_schema):
{result_schema_text}

————————————————————————————————————

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

1. Ориентация по плану:
   - Сверься с целью ТЕКУЩЕЙ ФАЗЫ main_plan
   - Посмотри на fills в текущей фазе в main_plan: какие данные являются итоговым критерием успеха этой фазы?

2. Оценка прогресса:
   - Проанализируй историю: какая информация для достижения цели фазы уже получена, а какой не хватает?
   - Если нужные данные для fills уже найдены в истории — внеси их в результат используя update_result
   - Если данных еще нет — определи, какой промежуточный шаг необходим сейчас

3. Выбор действий:
   - Сформулируй цель текущего шага (target), которая максимально приблизит тебя к выполнению цели всей фазы
   - Выбери ОДИН подходящий инструмент (action) и подготовь аргументы (args)

4. Коррекция тактики:
   - Обнови steps_future, чтобы наметить цепочку шагов до конца текущей фазы
   - Если обнаружена важная информация «на будущее» (для следующих фаз) — сохрани её в memory_updates
   - При необходимости оставь development_feedback

————————————————————————————————————

ФОРМАТ ОТВЕТА (СТРОГО JSON):

{{
    "target": "краткое описание цели текущего шага",
    "action": "ИМЯ_ИНСТРУМЕНТА | DONE | FAILED",
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
- если задача/фаза недостижима — используй action="FAILED" и передай причину в args.reason (строка)
- чтобы собрать финальный ответ, заполняй result через action="update_result"
- action="DONE" используй только когда result заполнен и содержит итог в нужном формате
"""


# region Продвижение по Main Plan
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


def _get_schema_node_by_path(schema: Any, path: str) -> Any:
    """
    Best-effort получение узла схемы по dotted-path.
    Поддерживает 2 распространённых варианта:
    - "плоская" схема: schema[field] -> meta
    - JSONSchema-подобная: node["properties"][field] -> meta
    """
    node: Any = schema
    for part in [p for p in str(path).split(".") if p]:
        if not isinstance(node, dict):
            return None
        if part in node:
            node = node.get(part)
            continue
        props = node.get("properties")
        if isinstance(props, dict) and part in props:
            node = props.get(part)
            continue
        return None
    return node


def _is_schema_field_required(schema: Any, path: str) -> bool:
    """
    Определяет обязательность поля по result_schema.
    По умолчанию (если в схеме нет required) считаем поле обязательным для обратной совместимости.
    """
    node = _get_schema_node_by_path(schema, path)
    if not isinstance(node, dict):
        return True
    req = node.get("required")
    if isinstance(req, bool):
        return req
    if isinstance(req, str):
        v = req.strip().lower()
        if v in ("true", "1", "yes", "y"):
            return True
        if v in ("false", "0", "no", "n"):
            return False
    return True


def _required_fills_or_all(fills: list[Any], schema: Any) -> list[str]:
    """
    Возвращает список fills, которые required=true по схеме.
    Если не удалось выделить ни одного required fill (или fills некорректен) — возвращаем исходные fills (str-only),
    чтобы не "закрывать" шаги случайно.
    """
    fills_str = [f.strip() for f in fills if isinstance(f, str) and f.strip()]
    if not fills_str:
        return []
    required_only = [f for f in fills_str if _is_schema_field_required(schema, f)]
    return required_only or fills_str


def update_main_plan_progress(main_plan: dict[str, Any]) -> dict[str, Any]:
    """
    Автоматически продвигает main_plan по фазам:
    - текущая фаза выполнена, когда все REQUIRED (required=true) поля из её fills заполнены в result
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

    # Нормализуем статусы шагов для совместимости со "старыми" планами,
    # где status мог отсутствовать или быть неизвестным.
    allowed_step_statuses = {"pending", "in_progress", "done"}
    for s in steps:
        if not isinstance(s, dict):
            continue
        st = s.get("status")
        if st not in allowed_step_statuses:
            s["status"] = "pending"

    current_idx = main_plan.get("current_step", 0)
    if not isinstance(current_idx, int) or current_idx < 0:
        current_idx = 0
        main_plan["current_step"] = 0

    # Если вышли за границы — план выполнен
    if current_idx >= len(steps):
        main_plan["status"] = "completed"
        return main_plan

    # Выставляем статус текущего шага как in_progress, если он ещё не начат
    if isinstance(steps[current_idx], dict) and steps[current_idx].get("status") in (None, "", "unknown", "not_started", "pending"):
        steps[current_idx]["status"] = "in_progress"

    step = steps[current_idx] if isinstance(steps[current_idx], dict) else {}
    fills = step.get("fills") if isinstance(step.get("fills"), list) else []
    if not fills:
        # По правилам планировщика fills не должны быть пустыми
        return main_plan

    result_obj = get_result()
    result_schema_obj = get_result_schema()

    def _get_by_path(obj: Any, path: str) -> Any:
        node = obj
        for part in [p for p in str(path).split(".") if p]:
            if not isinstance(node, dict) or part not in node:
                return None
            node = node.get(part)
        return node

    fills_to_check = _required_fills_or_all(fills, result_schema_obj)
    for f in fills_to_check:
        val = _get_by_path(result_obj, f)
        if not _is_result_field_filled(val):
            return main_plan

    # Закрываем текущую фазу
    steps[current_idx]["status"] = "done"
    next_idx = current_idx + 1

    # Переходим к следующей фазе или закрываем план
    if next_idx < len(steps):
        main_plan["current_step"] = next_idx
        if isinstance(steps[next_idx], dict) and steps[next_idx].get("status") in (None, "", "unknown", "not_started", "pending"):
            steps[next_idx]["status"] = "in_progress"
        main_plan["status"] = "in_progress"
    else:
        main_plan["current_step"] = next_idx
        main_plan["status"] = "completed"

    return main_plan














# region Орекстратор
# Запускает цикл агентных шагов
def orchestrate(
    task: str = main_task,
    max_steps: int = MAX_STEPS,
    result_schema: dict[str, Any] | None = None,
    result_template: dict[str, Any] | None = None,
    plan: dict[str, Any] | None = None,
    step_by_step_running = True # Если = True то после каждого шага агента он ожидает нажатия Enter в консоли
) -> str:
    global steps_future_value, long_term_memory, main_plan, tools_annotation
    start = time.time()

    # Сбрасываем состояние между независимыми запусками orchestrate, чтобы не было "утечек" history/memory.
    # RESULT/result_schema сбрасываются ниже через init_result(...).
    reset_agent_state(clear_history=True, clear_memory=True, clear_steps_future=True)

    # Обновляем аннотации инструментов перед запуском, чтобы подхватить
    # все модули с @tool, которые могли быть импортированы до вызова orchestrate.
    tools_annotation = get_tools_annotations()

    # Выбираем схему и шаблон результата для текущего запуска (обязательно переданы снаружи)
    schema_to_use = copy.deepcopy(result_schema or main_result_schema)
    template_to_use = copy.deepcopy(result_template or main_result_template)

    # Инициализируем объект результата для текущего запуска
    init_result(schema_to_use, template_to_use)

    # Формируем план: приоритет — явно переданный, иначе генерируем из текущей задачи и схемы
    if plan is not None:
        main_plan = copy.deepcopy(plan)
    else:
        main_plan = None

    if not isinstance(main_plan, dict):
        _plan_resp = create_main_plan_from_task(task, schema_to_use)
        if isinstance(_plan_resp, dict) and _plan_resp.get("status") == "ok":
            generated_plan = _plan_resp.get("plan")
            if isinstance(generated_plan, dict):
                main_plan = generated_plan

    # Фоллбэк на шаблон, если плана нет или пришёл в неверном формате
    if not isinstance(main_plan, dict):
        main_plan = copy.deepcopy(MAIN_PLAN_TEMPLATE)

    # Делаем main_plan доступным инструментам (через runtime_state) без циклических импортов
    try:
        _set_runtime_main_plan(main_plan)
    except Exception:
        pass

    # Делаем long_term_memory доступной инструментам (через runtime_state) без циклических импортов
    try:
        _set_runtime_long_term_memory(long_term_memory)
    except Exception:
        pass

    # Синхронизируем прогресс плана с уже предзаполненным result (например, из result_template)
    try:
        update_main_plan_progress(main_plan)
    except Exception:
        pass

    for step in range(1, max_steps + 1):
        step_banner = f"\n———————————   Шаг {step}   ———————————\n"
        print(step_banner)
        chat_print(step_banner)

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
            args_text = safe_json_dumps(model_args)

        model_summary = (
            f"🟢 reasoning: {step_reply.get('reasoning') or '—'}\n"     # Рассуждения модели
            f"🔵 target: {step_reply.get('target') or '—'}\n"    # Действие, которое агент собирается выполнить
            f"🟡 action: {step_reply.get('action') or '—'}\n"           # Вызывает инструмент
            f"{'   🔶 args: ' + args_text if args_text != '—' else ''}" # С аргументами
            f"\n"
        )
        chat_print(model_summary)
        print(model_summary)


        if step_by_step_running:
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
            они не сохраняются в массив history

            Как работает:
            На каждом шаге выполняется action с переданными args

            steps_future - обновляется на каждом шаге, и передаётся в запросе шага
            
            memory_updates - добавляет переданные строки в массив long_term_memory

            development_feedback - модель может сказать мне как разработчику, что ей не хватает какого-то функционала (без прерывания выполнения задачи)


            Результат пошагово записывается в result, при помощи вызова инструмента update_result
            Перед началом работы надо задать верную схему результата (result_schema) и шаблон результата, который будет заполнять модель, и который будет передаваться ей в каждом запросе шага, в фрагменте 
            текущий результат (result)

            Оркестратор сам двигает план по фазам, т.к. сам проверяет их выполнение при каждом шаге, и в методе format_main_plan_for_prompt он сам проставляет какая фаза активна на текущий момент

        """


        # 4. Сохраняем ответ модели в history
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

            # 2) Новый режим: возвращаем накопленный result
            if not completion_text:
                completion_text = safe_json_dumps(get_result(), indent=4)

            done_result = {"status": "done", "result": get_result(), "message": completion_text}
            add_history_entry({"role": "tool", "name": "DONE", "result": done_result})
            print(f"✅ Агент завершил задачу: {completion_text}")
            emit_execution_time(start, emit=print, print_time_smile=True)
            return completion_text

        # 6.2 Обработка провала (недостижимость цели)
        if tool_name == "FAILED":
            reason = None
            if isinstance(tool_args, dict):
                reason = tool_args.get("reason")
            if not isinstance(reason, str) or not reason.strip():
                reason = "Причина не указана (ожидалось args.reason: string)"

            result_text = safe_json_dumps(get_result(), indent=4)

            failed_payload = {
                "status": "failed",
                "reason": reason,
                "result": get_result(),
                "message": f"FAILED: {reason}"
            }
            add_history_entry({"role": "tool", "name": "FAILED", "result": failed_payload})

            final_text = ""
            final_text = safe_json_dumps(failed_payload, indent=4)

            print(f"❌ Агент завершил задачу с ошибкой/недостижимостью: {reason}\nТекущий result:\n{result_text}")
            emit_execution_time(start, emit=print, print_time_smile=True)
            return final_text

        # 6.3 Вызов инструмента
        tool_result = run_tool(tool_name, tool_args)
        tool_log = f"🛠️  {tool_name}({tool_args})"
        print(tool_log)
        chat_print(tool_log)

        try:
            tool_result_text = safe_json_dumps(tool_result)
        except Exception:  # noqa: BLE001
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
    emit_execution_time(start, emit=print, print_time_smile=True)
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
    def _sanitize_tool_result(result: Any) -> Any:
        """
        Убирает визуальный шум из стандартных ответов инструментов.
        Сейчас: удаляет ключ 'error', если он присутствует и равен None.
        """
        if isinstance(result, dict) and "error" in result and result.get("error") is None:
            cleaned = dict(result)
            cleaned.pop("error", None)
            return cleaned
        return result

    tool = TOOLS.get(tool_name)
    if not tool:
        return {"status": "error", "error": f"Неизвестный инструмент: {tool_name}"}
    try:
        # Вызывает функцию из agent_tools.py с заданными аргументами
        tool_result = tool["func"](**(tool_args or {}))
        return _sanitize_tool_result(tool_result)
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

#     # try:
#     #     import global_variable
#     #     print(
#     #         f"🔢 Использовано токенов — input: {global_variable.total_input_tokens}, "
#     #         f"output: {global_variable.total_output_tokens}"
#     #     )
#     # except Exception as ex:
#     #     print(f"Не удалось вывести статистику токенов: {ex}")