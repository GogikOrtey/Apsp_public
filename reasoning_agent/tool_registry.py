"""
Единый реестр инструментов для reasoning-агента.

Зачем:
- хранить описание инструментов (назначение, аргументы, обязательность, примеры) в одном месте
- генерировать из него system prompt
- валидировать ответы LLM (action/args/final_answer)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class ToolArgSpec:
    name: str
    type: str  # простой "человекочитаемый" тип (str/int/bool/json)
    required: bool
    description: str


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    args: tuple[ToolArgSpec, ...]
    returns: str
    example_args: dict[str, Any] | None = None


TOOLS: dict[str, ToolSpec] = {
    "list_files": ToolSpec(
        name="list_files",
        description="Вернуть список доступных файлов в окружении.",
        args=(),
        returns='JSON: {"files": ["notes.txt", "..."]}',
        example_args={},
    ),
    "read_file": ToolSpec(
        name="read_file",
        description="Прочитать содержимое файла по имени.",
        args=(
            ToolArgSpec(
                name="filename",
                type="str",
                required=True,
                description="Имя файла из списка, полученного через list_files.",
            ),
        ),
        returns='JSON: {"status":"ok","filename":"...","content":"..."} или {"status":"error","error":"..."}',
        example_args={"filename": "todo.txt"},
    ),
    "search": ToolSpec(
        name="search",
        description="Найти вхождения подстроки query в тексте text (регистронезависимо).",
        args=(
            ToolArgSpec(
                name="text",
                type="str",
                required=True,
                description="Текст, в котором выполняется поиск (обычно content из read_file).",
            ),
            ToolArgSpec(
                name="query",
                type="str",
                required=True,
                description="Подстрока для поиска.",
            ),
        ),
        returns='JSON: {"found": true/false, "positions": [0, 15, ...]}',
        example_args={"text": "<content from read_file>", "query": "презентац"},
    ),
    "DONE": ToolSpec(
        name="DONE",
        description="Завершить работу и вернуть финальный ответ.",
        args=(),
        returns='JSON: {"final_answer":"..."}',
        example_args={},
    ),
}


def allowed_actions() -> set[str]:
    return set(TOOLS.keys())


def render_tools_for_prompt(tools: dict[str, ToolSpec] | None = None) -> str:
    """
    Человекочитаемое описание инструментов для system prompt.
    Держим в одном месте, чтобы prompt и валидация не расходились.
    """
    tools = tools or TOOLS
    lines: list[str] = []
    lines.append("Доступные действия (tools):")
    for name, spec in tools.items():
        lines.append(f"- {name}: {spec.description}")
        if spec.args:
            lines.append("  args:")
            for a in spec.args:
                req = "обязательный" if a.required else "опциональный"
                lines.append(f"  - {a.name} ({a.type}, {req}): {a.description}")
        else:
            lines.append("  args: (нет)")
        lines.append(f"  returns: {spec.returns}")
        if spec.example_args is not None:
            lines.append(f"  example args: {spec.example_args}")
    return "\n".join(lines)


def render_tools_compact_for_prompt(tools: dict[str, ToolSpec] | None = None) -> str:
    """Компактная версия для вставки в user prompt на каждом шаге."""
    tools = tools or TOOLS
    lines: list[str] = []
    for name, spec in tools.items():
        if spec.args:
            sig = ", ".join(a.name for a in spec.args)
            lines.append(f"- {name}({sig}): {spec.description}")
        else:
            lines.append(f"- {name}: {spec.description}")
    return "\n".join(lines)


def validate_llm_action(
    payload: dict[str, Any],
    tools: dict[str, ToolSpec] | None = None,
) -> tuple[bool, str]:
    """
    Минимальная структурная валидация ответа LLM под наш контракт.
    Возвращает (ok, error_message).
    """
    tools = tools or TOOLS

    action = payload.get("action")
    if not isinstance(action, str):
        return False, "Field 'action' must be a string."

    if action not in tools:
        return False, f"Unknown action: {action}. Allowed: {sorted(tools.keys())}"

    # DONE: требуем final_answer
    if action == "DONE":
        fa = payload.get("final_answer")
        if not isinstance(fa, str) or not fa.strip():
            return False, "For action DONE, field 'final_answer' must be a non-empty string."
        return True, ""

    args = payload.get("args", {})
    if args is None:
        args = {}
    if not isinstance(args, dict):
        return False, "Field 'args' must be an object/dict."

    spec = tools[action]
    required_args = [a.name for a in spec.args if a.required]
    missing = [name for name in required_args if name not in args]
    if missing:
        return False, f"Missing required args for action '{action}': {missing}"

    # Лёгкая проверка типов для str (чтобы ловить совсем неверные форматы)
    for a in spec.args:
        if a.name not in args:
            continue
        if a.type == "str" and not isinstance(args[a.name], str):
            return False, f"Arg '{a.name}' must be str."

    return True, ""


