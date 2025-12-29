"""
Основной скрипт генерации кода для parseCard, в который передаётся набор ссылок на товары.
Возвращает код функции parsePage
""" 

import random
from typing import Any, Dict, List, Tuple, Optional

# region Импорты
# Чтобы при запуске файла из этой папки были видны модули из корня проекта (addedFunc.py и др.)
### Потом убрать, что бы было нормально
from pathlib import Path
import sys
import json
import copy
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Подключение всех библиотек и функций
from Gen_parseCard.build_parseCard import *
from Gen_parseCard.extract_selectors_parseCard_from_GPT import *
from Gen_parseCard.get_parseCard_code import *
from import_all_libraries import *

def _normalize_selector_value(value: Any) -> Optional[str]:
    """
    Нормализует значения селекторов из JSON-ответа LLM.
    Возвращает строку или None.
    """
    if value is None:
        return None

    # Иногда модель может вернуть "null"/"None" строкой
    if isinstance(value, str):
        v = value.strip()
        if not v:
            return None
        if v.lower() in {"null", "none"}:
            return None
        return v

    # На всякий случай: приводим простые типы к строке
    try:
        return str(value).strip() or None
    except Exception:
        return None


def merge_selectors_from_multiple_pages(results: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """
    Сливает несколько объектов вида {field: selector_or_null} в один:
    - значения становятся массивами строк
    - поля, которые во всех результатах None/null/пустые — удаляются
    - одинаковые значения схлопываются до массива из одного элемента
    - разные значения -> массив уникальных значений (в порядке появления)
    """
    # Сохраняем порядок ключей (как в первом появлении)
    keys_in_order: List[str] = []
    seen_keys = set()
    for d in results:
        if not isinstance(d, dict):
            continue
        for k in d.keys():
            if k not in seen_keys:
                seen_keys.add(k)
                keys_in_order.append(k)

    stock_present_in_any = any(isinstance(d, dict) and "stock" in d for d in results)

    merged: Dict[str, List[str]] = {}
    for key in keys_in_order:
        uniq_values: List[str] = []
        for d in results:
            if not isinstance(d, dict):
                continue
            normalized = _normalize_selector_value(d.get(key))
            if normalized is None:
                continue
            if normalized not in uniq_values:
                uniq_values.append(normalized)
        if uniq_values:
            merged[key] = uniq_values

    # Если поля stock нет ни в одном входном объекте — добавляем пустой массив
    if not stock_present_in_any and "stock" not in merged:
        merged["stock"] = []

    return merged








def merge_links_and_pick_random(
    links_obj: Dict[str, Any],
    k: int = 3,
    *,
    seed: Optional[int] = None,
) -> Tuple[List[str], List[str]]:
    """
    1) Сливает все ссылки из объекта вида {"group": [url, ...], ...} в один массив.
    2) Выбирает k случайных ссылок (без повторов) и возвращает их отдельным массивом.

    Возвращает: (all_links, random_3_links)
    """
    all_links: List[str] = []

    for value in links_obj.values():
        if isinstance(value, (list, tuple)):
            all_links.extend([x for x in value if isinstance(x, str)])

    rng = random.Random(seed) if seed is not None else random
    random_3_links = all_links.copy() if len(all_links) <= k else rng.sample(all_links, k)
    return all_links, random_3_links



""" 
Пример ссылок, приходящих из главной функции:

"""



















""" 

Тогда план будет такой:

Получаем 15 ссылок на товары

Генерим селекторы, используя 3 случайных из 15

Сливаем результаты селекторов в один объект

Проверка:

1. Локальная:
    - Для каждого поля запускаем новый вызов LLM
    - В нём собираем запрос, что типо вот есть
        - Селектор
        - Его описание
        - Его тип
        - Его значение
        - HTML frame
    - И просим сказать, верное ли значение мы извлекаем, на основе описания поля
        - Пометить OK/OK_DIRTY/CHECK/BAD

1.1 На тех которые не ОК - запускаем функцию правки
    - Для OK_DIRTY одну, простую
    - Для CHECK - посерьёзнее
    - Для BAD - уже запускаем агента

Если несколько селекторов для одного поля
    - Стоит посылать другой промпт, в котором нейронка бы вернула один или несколько минимально необходимых селекторов для парсинга этого элемента на разных страницах сайта
        - Т.е. посылать ей результаты например с 5 разных страниц, и просить выбрать
        - Хотя в таком случае проще и надёжнее запустить агента
        - Типо: "
            Было проанализировано несколько страниц, и были найдены несколько селекторов, которые указывают на значение для поля {поле} {описание поля}. Просмотри этот набор селекторов, и прими рещение, какой из них лучший
            - Цель - выделить один селектор, который ожинаково хорошо работает на всех предоставленных страницах, и извлекает нужное значение для поля.
            - Если выделить ровно один селектор, который бы работал на всех страницах невозможно, то подбери минимальное количество селекторов, что бы они извлекали нужное значение. 
            - Если на каждой странице требуется новый селектор, то значит он неверный. Пронализируй страницу используя инструменты, и подбери другой (или другие) селекторы.
            - Если разные селекторы выдают одинаковый результат на странице, то выбери наиболее надёжный из них.
            
            В результате верни массив, из одного элемента, или из нескольких.
        "

---> Вот на этом этапе уже собираем код parseCard

2. Общая по объектам:
    - Собираем несколько (например 10) объектов в один запрос
    - И просим LLM проверить консистентность для всех полей объекта - подходят ли они, не выбивается ли какой-то из остальных, нет ли пропущенных
    - Если на каком-то объекте или каком-то поле видим ошибку, то посылаем в агента

3. Глобальная проверка - нужно будет запустить сбор на 10 запросов из семантики, на 2 страницы на 5 результатов с каждой. Сформировать в таблицу и отправить LLM, что бы она посмотрела и сказала, видит ли там ошибки





"""






















""" 

Нужно будет отобрать из 15 ссылок - 3 случайных, и отправить их агенту в задании
Селекторы из 3х страниц - слить в 1 объект, просто в массивы

Что бы он:
1. Сначала проверил насколько совпадают html полученные из браузера и из curl запроса на адрес товара
######## Добавить инструмент который бы это делал
    - Если различаются больше чем на 15%
        - То попробовать найти селектором название и цену на обоих страницах
            - Если не находится, то Failed
            - Если находится, то работаем дальше без проблем (с use_curl = True)
        ######### Добавить инструмент мультиселектинга, это когда мы передаём массив селекторов, и нам возвращается результат также в виде массива объектов
        ### И что бы он также за раз возвращал и html_frame вокруг каждого переданного элемента












Осталось:

- Сделать описания для полей
- Проверка, насколько совпадают html полученные из браузера и из curl запроса на адрес товара
- Надо будет добавить описание семантики поля
- Нужно будет динамически генерить поля для result 
- И использовать функцию формализации плана
    - А в неформальном виде также собират динамически, из тех полей, что были найдены на странице





Пример result: 
{
    "choosed_selector_field_name": str
    "field__name__code": str
    "field__name__code_gen_completed": boolean
    "field__name__ok_on_1_link": boolean
    "field__name__ok_on_2_link": boolean
    "field__name__ok_on_3_link": boolean

    "choosed_selector_field_price"
    "field__price__code"
    "field__price__code_gen_completed"
    "field__price__ok_on_1_link"
    "field__price__ok_on_2_link"
    "field__price__ok_on_3_link"

    ... (для всех полей по 6 ячеек)
}


Тогда план:


n + 1: Проверить и выбрать селектор для извлечения значений для поля _
n + 2: Сгенерировать код извлечения значений для поля _
n + 3: Проверить сгенерированный код извлечения значений для поля _ на трёх страницах
...





"""

















































## region Получение селекторов со страницы











































# region main_gen_parseCard

def main_gen_parseCard(input_15_links, host):
    print("") # Убрать

    # 1. Получаем 3 случайные ссылки
    (all_links, random_3_links) = merge_links_and_pick_random(input_15_links)

    # print(random_3_links)

    print("Выбрали такие 3 случайные ссылки на товары:")
    for input_url in random_3_links:
        print(input_url)

    # Извлекем селекторы на этих трёх ссылках
    results_extract_selectors_parseCard_from_GPT: List[Dict[str, Any]] = []
    for input_url in random_3_links:
        result_text = extract_selectors_parseCard_from_GPT(input_url)

        # extract_selectors_parseCard_from_GPT возвращает строку с JSON
        try:
            result_obj = json.loads(result_text)
        except Exception:
            # Фоллбек: пытаемся вырезать первый JSON-объект из строки
            s = str(result_text)
            start = s.find("{")
            end = s.rfind("}")
            if start != -1 and end != -1 and end > start:
                result_obj = json.loads(s[start : end + 1])
            else:
                raise

        if not isinstance(result_obj, dict):
            raise ValueError(f"extract_selectors_parseCard_from_GPT вернул не dict: {type(result_obj)}")

        results_extract_selectors_parseCard_from_GPT.append(result_obj)

    # Сливаем 3 ответа в один объект (значения -> массивы, пустые поля удаляем)
    result_extract_selectors_parseCard_from_GPT = merge_selectors_from_multiple_pages(
        results_extract_selectors_parseCard_from_GPT
    )

    """

    {
        "name": [
            "h1.product_title.entry-title"       
        ],
        "price": [
            "div#product-65416 .summary.entry-summary p.price .woocommerce-Price-amount",     
            "#product-81354 .summary.entry-summary p.price .woocommerce-Price-amount",        
            "#product-65494 .summary.entry-summary p.price .woocommerce-Price-amount"
        ],
        "imageLink": [
            "div#product-65416 .woocommerce-product-gallery img.wp-post-image",
            "#product-81354 .woocommerce-product-gallery__wrapper .woocommerce-product-gallery__image:first-child img.wp-post-image",      
            "#product-65494 .woocommerce-product-gallery img.wp-post-image"
        ],
        "article": [
            "div#product-65416 .product_meta .sku_wrapper .sku",
            "#product-81354 .product_meta .sku_wrapper .sku",
            "#product-65494 .product_meta .sku_wrapper .sku"
        ],
        "stock": []
    }

    """

    result_extract_selectors_parseCard_from_GPT_str = json.dumps(result_extract_selectors_parseCard_from_GPT, ensure_ascii=False, indent=4, default=str)

    print(f"\nresult_extract_selectors_parseCard_from_GPT:\n")
    print(result_extract_selectors_parseCard_from_GPT_str)

    # Валидирую селекторы через агента
    result_get_parseCard_code = get_parseCard_code(result_extract_selectors_parseCard_from_GPT, host, random_3_links)

    # Собираю провалидированные поля в функцию parseCard
    (result, fields_descr) = build_parseCard(result_get_parseCard_code, result_extract_selectors_parseCard_from_GPT)

    # Возвращаю её как строку
    return (result, fields_descr)
    



































host = "https://makitaclub.ru"

test_input = {
    "five_links_1": [
        "https://makitaclub.ru/products/831271-6/",
        "https://makitaclub.ru/products/garantiya-5-let/",
        "https://makitaclub.ru/products/nabor-rychnyh-instrumentov-i-osnastki-makita-d-42042-103-predmeta/",
        "https://makitaclub.ru/products/nabor-instrumentov-56-sht-makita-b-53768/",
        "https://makitaclub.ru/products/akkumulyatornyj-mnogofunktsionalnyj-instrument-makita-tm30dz-10-8v-li-ion-bez-akkumulyatorov-i-zaryadnogo-ustrojstva/"
    ],
    "five_links_2": [
        "https://makitaclub.ru/products/duc204rf/",
        "https://makitaclub.ru/products/jv002gz/",
        "https://makitaclub.ru/products/duc353rf2/",
        "https://makitaclub.ru/products/duc101sf/",
        "https://makitaclub.ru/products/dtd153sy/"
    ],
    "five_links_3": [
        "https://makitaclub.ru/products/dp4021/",
        "https://makitaclub.ru/products/df488d002/",
        "https://makitaclub.ru/products/ddf489z/",
        "https://makitaclub.ru/products/m0600/",
        "https://makitaclub.ru/products/hp002gd201/"
    ]
}



main_gen_parseCard(test_input, host)