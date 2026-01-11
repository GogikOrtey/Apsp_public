from __future__ import annotations

from typing import Any, Dict, Iterable, Set


def filter_all_fields_nested(
    all_fields: Any,
    selected_fields: Iterable[str] | None,
) -> Dict[str, Dict[str, Any]]:
    """
    Фильтрует вложенный справочник all_fields (категория -> {field_key -> meta})
    по набору selected_fields, сохраняя исходную структуру.

    - Не модифицирует входной объект.
    - Категории без полей после фильтрации выкидываются.
    - Если вход некорректный — возвращает {}.
    """
    if not isinstance(all_fields, dict):
        return {}
    if not selected_fields:
        # Возвращаем копию верхнего уровня (без deep-copy метаданных)
        return {
            str(cat): dict(fields) for cat, fields in all_fields.items() if isinstance(fields, dict)
        }

    selected: Set[str] = {str(x).strip() for x in selected_fields if str(x).strip()}
    if not selected:
        return {
            str(cat): dict(fields) for cat, fields in all_fields.items() if isinstance(fields, dict)
        }

    result: Dict[str, Dict[str, Any]] = {}
    for category, fields in all_fields.items():
        if not isinstance(fields, dict):
            continue
        filtered_fields: Dict[str, Any] = {}
        for field_key, meta in fields.items():
            k = str(field_key)
            if k in selected:
                filtered_fields[k] = meta
        if filtered_fields:
            result[str(category)] = filtered_fields
    return result


