"""
Единое место для runtime-состояния reasoning-агента, чтобы инструменты (agent_tools)
могли безопасно взаимодействовать с main_plan без циклических импортов agent_main <-> agent_tools.

Важно: здесь хранится ссылка на dict main_plan, который мутируется in-place.
Также здесь может храниться ссылка на long_term_memory (list), чтобы инструменты могли
писать в память без прямого импорта agent_main (иначе будет циклический импорт).
"""

from __future__ import annotations

from typing import Any

_MAIN_PLAN: dict[str, Any] | None = None
_LONG_TERM_MEMORY: list[Any] | None = None


def set_main_plan(plan: dict[str, Any] | None) -> None:
    """Устанавливает текущий main_plan (ссылка сохраняется)."""
    global _MAIN_PLAN
    _MAIN_PLAN = plan if isinstance(plan, dict) else None


def get_main_plan() -> dict[str, Any] | None:
    """Возвращает текущий main_plan (или None, если он ещё не установлен)."""
    return _MAIN_PLAN


def set_long_term_memory(memory: list[Any] | None) -> None:
    """
    Устанавливает текущую ссылку на long_term_memory.

    Важно: должна быть именно ссылка на list, который мутируется in-place (append/extend).
    """
    global _LONG_TERM_MEMORY
    _LONG_TERM_MEMORY = memory if isinstance(memory, list) else None


def get_long_term_memory() -> list[Any] | None:
    """Возвращает текущую long_term_memory (или None, если она ещё не установлена)."""
    return _LONG_TERM_MEMORY


