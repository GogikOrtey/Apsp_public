"""
Модуль для обработки данных из шагов 2 и 3
Собирает данные в единый JSON формат data_input_table
"""
import json
from collections import OrderedDict
from urllib.parse import urlparse


def _extract_host_from_url(url: str) -> str:
    """
    Извлекает host (scheme://netloc) из URL.

    Примеры:
      - https://c-s-k.ru/catalog/... -> https://c-s-k.ru
      - c-s-k.ru/catalog/... -> https://c-s-k.ru

    Возвращает пустую строку, если извлечь не удалось.
    """
    if not url or not isinstance(url, str):
        return ""

    url = url.strip()
    if not url:
        return ""

    # urlparse("example.com/path") трактует это как path, поэтому добавляем "//"
    # (тогда домен попадает в netloc). Схему по умолчанию считаем https.
    parsed = urlparse(url if "://" in url else f"//{url}")

    netloc = parsed.netloc.strip()
    if not netloc:
        return ""

    scheme = (parsed.scheme or "https").strip()
    return f"{scheme}://{netloc}"


def _order_examples(examples_data, selected_fields):
    """
    Приводит примеры к порядку выбранных полей.
    """
    examples = examples_data.get("simple", []) if examples_data else []
    if not selected_fields:
        return examples

    ordered_examples = []
    for example in examples:
        ordered = OrderedDict()
        for field in selected_fields:
            ordered[field] = example.get(field, "")
        ordered_examples.append(ordered)
    return ordered_examples


def _order_search_requests(search_requests_data):
    """
    Фиксированный порядок полей для search_requests.
    """
    requests = search_requests_data.get("search_requests", []) if search_requests_data else []
    ordered_requests = []
    for req in requests:
        ordered_requests.append(OrderedDict([
            ("query", req.get("query", "")),
            ("url_search_query_page_2", req.get("url_search_query_page_2", "")),
            ("count_of_page_on_pagination", req.get("count_of_page_on_pagination", "")),
            ("total_count_of_results", req.get("total_count_of_results", "")),
            ("links_items", req.get("links_items", [])),
        ]))
    return ordered_requests


def process_results(examples_data, search_requests_data, selected_fields=None):
    """
    Собирает данные из шагов 2 и 3 в единый JSON формат
    
    Args:
        examples_data: Данные из шага 2 (содержит "simple")
        search_requests_data: Данные из шага 3 (содержит "search_requests")
        selected_fields: Порядок полей, выбранный на шаге 1
    
    Returns:
        dict: Собранный JSON в формате data_input_table
    """
    simple_ordered = _order_examples(examples_data, selected_fields or [])
    search_requests_ordered = _order_search_requests(search_requests_data)

    # Автозаполнение host из первой ссылки links.simple[0].link (если есть)
    first_link = ""
    if simple_ordered and isinstance(simple_ordered, list):
        first_item = simple_ordered[0] if len(simple_ordered) > 0 else None
        if isinstance(first_item, dict):
            first_link = first_item.get("link", "") or ""
    extracted_host = _extract_host_from_url(first_link)

    # Инициализируем структуру результата с сохранением порядка ключей
    data_input_table = OrderedDict([
        ("host", extracted_host),
        ("fields_str", ""),
        ("links", OrderedDict([
            ("simple", simple_ordered)
        ])),
        ("search_requests", search_requests_ordered)
    ])
    
    # Выводим результат в консоль
    print('\n' + '=' * 30)
    print('ОБРАБОТКА РЕЗУЛЬТАТОВ (data_input_table)')
    print('=' * 30)
    print('\nИтоговый JSON (data_input_table):')
    print(json.dumps(data_input_table, ensure_ascii=False, indent=2, sort_keys=False))
    print('\n' + '=' * 30 + '\n')
    
    return data_input_table

