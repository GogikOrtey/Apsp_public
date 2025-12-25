"""
Единое место для runtime-состояния reasoning-агента, чтобы инструменты (agent_tools)
могли безопасно взаимодействовать с main_plan без циклических импортов agent_main <-> agent_tools.

Важно: здесь хранится ссылка на dict main_plan, который мутируется in-place.
"""

from __future__ import annotations

from typing import Any

_MAIN_PLAN: dict[str, Any] | None = None


def set_main_plan(plan: dict[str, Any] | None) -> None:
    """Устанавливает текущий main_plan (ссылка сохраняется)."""
    global _MAIN_PLAN
    _MAIN_PLAN = plan if isinstance(plan, dict) else None


def get_main_plan() -> dict[str, Any] | None:
    """Возвращает текущий main_plan (или None, если он ещё не установлен)."""
    return _MAIN_PLAN


