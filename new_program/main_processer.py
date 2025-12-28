"""
Это главный скрипт, который будет работать с playwright, агентами, и остальными функциями

На вход к нему будет подаваться ссылка на товар на любой сайт

И в результате он должен будет сгенерировать код парсера этого сайта, и сохранить в result_code.ts
"""

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

from new_program.html_toolkit import *
from new_program.HGF_main_page_selector_and_semantic_handler import *
from new_program.TNF_extract_data_from_search_page import *
from new_program.use_agent_for_step_2_gen_parsePage import *
from new_program.agent_step_4_product import *
from new_program.agent_step_5_pagination import *
from new_program.agent_step_6_URL_construct import *
from new_program.agent_step_6_1_get_links_for_product import *
from new_program.agent_step_7_build_code_parsePage import *
from new_program.build_final_code import *

# region Задачи

""" 

План на будущее:

- Сделать генерацию parseCard
    - С полями разобраться - сделать структуру и добавить описаний
        - Можно кстати все описания сгенерить через chatGPT
    - Запрос для извлечения селекторов дописать (усилить и расширить на большое кол-во полей)
        - Надо прописать, что бы он извлекал главный и запасной селектор для каждого поля
    - И написать запрос для агента - пошагового автовалиатора кода
    - Вставить parseCard в общий итоговый шаблон кода
        - После генерации фрагмента кода parseCard нужно будет добавлять туда строки с link и timestamp

- Тестирование, и запуск кода в А-Парсере

- Работу с дигинетикой надо будет обязательно добавить, она частенько встречается

- В конце - фронт
































Доп:

- Добавил 6.5 шаг, но не запускал весь алгоритм с ним
- Надо не забыть задавать хост в шаблоне готового кода
- Потом надо будет добавить инструменты:
    - Для отправки curl запросов, простых и с параметрами
    - Для получения данных из запросов на странице Playwright, поиск и работу с ними
        - Для примера, можно например взять avon.ru и detmir.ru
- Добавить проверку на то, такая же страница открывается вне браузера по прямому curl запросу, или нет
- Надо будет добавить скриншоты состояния из браузера, по актуальным шагам
- Собрать все возможные исключения, которые прописал, и обработать их
- Ещё есть задачи которые прописаны ниже. В конце их глянуть







Сайты, на которых тестирую:

https://makitaclub.ru
https://makita-land.ru
https://kotel-nasos.ru

som1.ru
krason.ru

https://makitatrading.ru
https://systemarf.ru
https://makita-snab.ru
https://line-tools.ru
https://makita-online.ru

Доп. ссылки прописаны внизу этого файла

Дигинетика:
https://apelsin.ru

"""









def main_processer(input_url):
    # 0. Чистим URL, запускам браузер и переходим на него

    # Чистим входящий url - до host, что бы получить ссылку на главную страницы
    url_input = normalize_url(input_url)

    # Запускаю браузер с видимым окном
    launch_browser(headless = False)

    goto_url( 
        url = url_input,
        wait_until = "load",
        timeout = 30_000
    )
    
    ############# Что делаеть если браузер вдруг внезапно закроется посреди выполнения алгоритма?
    ############# Что делаеть если не дождёмся загрузки страницы в таймаут?

    # html_content = get_html_from_cache(url_input)

    html_content = get_shared_page().content()
    html_content_zip = clean_html_universal(html_content)

    # # Сохранения страниц - может пригодится для отладки
    # save_page_html(html_content, filename = "page_html.html")
    # save_page_html(html_content_zip, filename = "page_html_zip.html")

    # region Шаг 1 - HGF

    HGF_result = HGF_main_page_selector_and_semantic_handler(html_content_zip)
    print(f"\nHGF_result:\n")
    print(HGF_result)

    # # Пример ответа HGF для сайта makitaclub.ru
    # HGF_result = r"""
    # """

    """

    {
        "status": "ok",
        "error_type": null,
        "analysis_message": "Страница успешно обработана",
        "semantics": [
            "инструмент",
            "дрель",
            "шуруповерт",
            "перфоратор",
            "болгарка",
            "пила",
            "шлифмашина",
            "пылесос",
            "аккумулятор",
            "оснастка"
        ],
        "search_input_selectors": [
            "#woocommerce-product-search-field-0",   
            "form.woocommerce-product-search input.search-field",
            ".site-search form.woocommerce-product-search input[type=\"search\"]",
            "input.search-field[name=\"s\"]",        
            "form[role=\"search\"] input[type=\"search\"]"
        ],
        "search_button_selectors": [
            "form.woocommerce-product-search button[type=\"submit\"]",
            ".site-search form.woocommerce-product-search button[type=\"submit\"]",
            "form[role=\"search\"] button[type=\"submit\"]",
            ".woocommerce-product-search button[type=\"submit\"]",
            ".site-search button[type=\"submit\"]"   
        ]
    }

    https://galleryceramics.ru/
    {
        "status": "ok",
        "error_type": null,
        "analysis_message": "Контент интернет-магазина доступен: присутствуют меню, каталог, баннеры и форма поиска. Капча (reCAPTCHA) встречается как фоновый элемент в формах и не блокирует доступ к сайту.",
        "semantics": [
            "плитка",
            "керамогранит",
            "сантехника",
            "мозаика",
            "унитаз",
            "раковина",
            "смеситель",
            "душ",
            "ванна",
            "мебель"
        ],
        "search_input_selectors": [
            "#title-search-input",
            "form.search.search--hastype input#title-search-input",
            "#title-search input[name=\"q\"]",
            "#title-search_fixed input#title-search-input_fixed",
            "form.search input.search-input[name=\"q\"]"
        ],
        "search_button_selectors": [
            "#title-search button.btn-search[type=\"submit\"]",
            "form.search.search--hastype button.btn-search[name=\"s\"]",
            "#title-search form.search button[type=\"submit\"].btn-search",
            "#title-search_fixed button.btn-search[type=\"submit\"]",
            "#title-search_fixed form.search button[name=\"s\"].btn-search"
        ]
    }
    """

    # Преобразуем строку в JSON-объект, чтобы далее работать как со словарём
    HGF_result = json.loads(HGF_result)

    ############# Что делаеть при ошибке парсинга, когда HGF вернула невалидный ответ?

    # Проверяем статус
    if HGF_result.get("status") != "ok":
        raise ValueError(f"Ошибка HGF - извлечение селекторов поля ввода и сбора семантики неудачно с сайта! \nПолный ответ: \n{HGF_result}")

    # Удаляем первые 3 поля
    keys_to_remove = list(HGF_result.keys())[:3]
    for key in keys_to_remove:
        del HGF_result[key]

    # region Шаг 2 - Агент 

    result_agent_answer_from_2_step = use_agent_for_step_2_gen_parsePage(HGF_result)
    print("result_agent_answer_from_2_step:")
    print(result_agent_answer_from_2_step)

    """ 
    Пример ответа агента:

    {
        "used_seletor_search_input": "#woocommerce-product-search-field-0",
        "used_seletor_search_button": "",
        "used_search_request": "инструмент",
        "second_html": "https://makitaclub.ru/?s=%D0%B8%D0%BD%D1%81%D1%82%D1%80%D1%83%D0%BC%D0%B5%D0%BD%D1%82&post_type=product"
    }

    

    """

    # region Шаг 3 - TNF

    # # Для тестов
    # goto_url( 
    #     url = "https://makitatrading.ru/catalog/?q=%D0%B8%D0%BD%D1%81%D1%82%D1%80%D1%83%D0%BC%D0%B5%D0%BD%D1%82&s=%D0%9D%D0%B0%D0%B9%D1%82%D0%B8",
    #     wait_until = "load",
    #     timeout = 30_000
    # )
    
    # Получает html страницы результатов поисковой выдачи, и вытаскивает от туда нужные селекторы при помощи TNF

    html_content = get_shared_page().content()
    html_content_zip = clean_html_universal(html_content)

    # save_page_html(html_content, filename = "page_html.html")
    # save_page_html(html_content_zip, filename = "page_html_zip.html")

    TNF_result = TNF_extract_data_from_search_page(html_content_zip)
    print(f"\nTNF_result:\n")
    print(TNF_result)

    # Преобразует строку ответа в json
    TNF_result = json.loads(TNF_result)

    # Проверяем статус
    if TNF_result.get("status") != "ok":
        raise ValueError(f"Ошибка TNF - извлечение селекторов товара и пагинации неудачно с сайта! \nПолный ответ: \n{TNF_result}")

    # Удаляем первые 3 поля
    keys_to_remove = list(TNF_result.keys())[:3]
    for key in keys_to_remove:
        del TNF_result[key]

    """
    Пример ответа:

    https://makitaclub.ru/?s=%D0%B8%D0%BD%D1%81%D1%82%D1%80%D1%83%D0%BC%D0%B5%D0%BD%D1%82&post_type=product
    {
        "status": "ok",
        "error_type": null,
        "analysis_message": "Страница результатов поиска WooCommerce доступна, капча/блокировки и сообщения об  отсутствии результатов не обнаружены. Все ключевые элементы найдены.",
        "search_input_selectors": [
            "#woocommerce-product-search-field-0",
            "form.woocommerce-product-search input.search-field[type='search'][name='s']",
            ".site-search .woocommerce-product-search input.search-field"
        ],
        "search_button_selectors": [
            "form.woocommerce-product-search button[type='submit']",
            ".site-search form.woocommerce-product-search button",
            ".widget_product_search form button[type='submit']"
        ],
        "total_results_count_selectors": [
            "p.woocommerce-result-count",
            ".storefront-sorting > p.woocommerce-result-count",
            "main#main p.woocommerce-result-count"
        ],
        "product_link_selectors": [
            ".products .product-card a.stretched-link[href*='/products/']",
            ".products a.stretched-link[href*='/products/']",
            ".products .card a.stretched-link"
        ],
        "pagination_container_selectors": [
            "nav.woocommerce-pagination",
            ".storefront-sorting nav.woocommerce-pagination",
            "ul.page-numbers"
        ],
        "pagination_page2_selectors": [
            "nav.woocommerce-pagination a.page-numbers[href*='/page/2/']",
            "ul.page-numbers a.page-numbers[href*='/page/2/']",
            "nav.woocommerce-pagination a.next.page-numbers[href*='/page/2/']"
        ],
        "pagination_last_page_selectors": [
            "nav.woocommerce-pagination ul.page-numbers li:nth-last-child(2) > a.page-numbers",
            "ul.page-numbers li:nth-last-child(2) > a.page-numbers",
            "nav.woocommerce-pagination a.page-numbers[href*='/page/']"
        ],
        "last_page_number_displayed": true
    }


    https://makitatrading.ru/catalog/?q=%D0%B8%D0%BD%D1%81%D1%82%D1%80%D1%83%D0%BC%D0%B5%D0%BD%D1%82&s=%D0%9D%D0%B0%D0%B9%D1%82%D0%B8
    {
        "status": "ok",
        "error_type": null,
        "analysis_message": "Страница с результатами поиска доступна, товары и пагинация найдены.",
        "search_input_selectors": [
            "#title-search-input",
            "form#searchForm input[name='q']",
            "#searchForm input[type='search']"
        ],
        "search_button_selectors": [
            "#searchForm input[type='submit'][name='s']",
            "form#searchForm input.btn.btnRed[type='submit']",
            "#searchForm input[value='Найти']"
        ],
        "total_results_count_selectors": null,
        "product_link_selectors": [
            ".catalog.catalogCards .itemCard[itemtype='http://schema.org/Product'] > a.image[href^='/catalog/   product/']",
            ".catalog.catalogCards .itemCard a.item_title[href^='/catalog/product/']",
            ".catalog.catalogCards a[href^='/catalog/product/']"
        ],
        "pagination_container_selectors": [
            "nav#pagination",
            "#pagination > ul",
            "nav#pagination ul"
        ],
        "pagination_page2_selectors": [
            "nav#pagination a[href*='PAGEN_2=2']",
            "#pagination a[href*='PAGEN_2=2']",
            "nav#pagination ul li a[href*='PAGEN_2=2']"
        ],
        "pagination_last_page_selectors": [
            "nav#pagination ul li:nth-last-child(2) > a",
            "#pagination ul li:nth-last-child(2) > a",
            "nav#pagination li:not(.active):not(:first-child):not(:last-child):nth-last-child(2) > a"
        ],
        "last_page_number_displayed": true
    }


    https://galleryceramics.ru/catalog/?q=%D0%BF%D0%BB%D0%B8%D1%82%D0%BA%D0%B0&type=catalog&s=%D0%9D%D0%B0%D0%B9%D1%82%D0%B8
    {
        "status": "ok",
        "error_type": null,
        "analysis_message": "Страница поиска с результатами (156 товаров) успешно распознана. На странице присутствует reCAPTCHA (бейдж), но 
      полезный контент и нужные элементы доступны.","search_input_selectors": [
            "#title-search-input",
            "form.search.search--hastype input[name='q']#title-search-input",
            "header .search-wrapper #title-search input.search-input[name='q']"
        ],
        "search_button_selectors": [
            "#title-search button.btn-search[type='submit']",
            "#title-search form.search.search--hastype button[name='s'][type='submit']",
            "header .search-wrapper #title-search button.btn-search"
        ],
        "total_results_count_selectors": [
            ".topic__heading .element-count-wrapper .element-count",
            "h1#pagetitle + .element-count-wrapper .element-count",
            ".topic .topic__heading span.element-count"
        ],
        "product_link_selectors": [
            ".catalog-block .catalog-block__wrapper .catalog-block__info-title > a.dark_link[href*='/catalog/']",
            ".catalog-block__wrapper a.js-popup-title[href*='/catalog/']",
            ".catalog-block__wrapper a.image-list__link[href*='/catalog/']"
        ],
        "pagination_container_selectors": [
            ".bottom_nav_wrapper .module-pagination",
            ".bottom_nav .module-pagination__wrapper",
            ".bottom_nav_wrapper .bottom_nav .module-pagination"
        ],
        "pagination_page2_selectors": [
            ".bottom_nav_wrapper .module-pagination a.module-pagination__item[href*='PAGEN_2=2']",    ".bottom_nav .module-pagination__wrapper 
      a[href*='PAGEN_2=2'
            ]",".bottom_nav_wrapper a.arrows-pagination__next[href*='PAGEN_2=2']"
        ],
        "pagination_last_page_selectors": [
            ".bottom_nav_wrapper .module-pagination__wrapper a.module-pagination__item:last-of-type",
            ".bottom_nav_wrapper .module-pagination__wrapper a.module-pagination__item[href*='PAGEN_2=']",
            ".bottom_nav_wrapper .module-pagination__wrapper a.module-pagination__item:nth-last-of-type(1)"
        ],
        "last_page_number_displayed": true
    }

    """

    # region Шаг 4, 5, 6 - Агенты

    search_request = result_agent_answer_from_2_step.get("used_search_request")

    print("Запуск result_agent_step_4_product")
    result_agent_step_4_product = agent_step_4_product(TNF_result, search_request)


    print("Запуск result_agent_step_5_pagination")
    result_agent_step_5_pagination = agent_step_5_pagination(TNF_result, search_request)


    semantics_list = HGF_result.get("semantics") or []
    semantics = {"semantics": semantics_list}

    print("Запуск result_agent_step_6_URL_construct")
    result_agent_step_6_URL_construct = agent_step_6_URL_construct(TNF_result, search_request, semantics, url_input)

    

    # Генерируем кастомные исключения, для понятной отладки в случае ошибок
    if not isinstance(result_agent_step_4_product, dict):
        raise TypeError(
            f"agent_step_4_product должен вернуть dict, получили: {type(result_agent_step_4_product).__name__}"
        )
    if not isinstance(result_agent_step_5_pagination, dict):
        raise TypeError(
            f"agent_step_5_pagination должен вернуть dict, получили: {type(result_agent_step_5_pagination).__name__}"
        )
    if not isinstance(result_agent_step_6_URL_construct, dict):
        raise TypeError(
            f"agent_step_6_URL_construct должен вернуть dict, получили: {type(result_agent_step_6_URL_construct).__name__}"
        )



    # region Шаг 6.5 - Собираем ссылки на товары с трёх страниц

    product_link_selectors = TNF_result.get("product_link_selectors") or []
    if not isinstance(product_link_selectors, list) or not product_link_selectors or not product_link_selectors[0]:
        raise ValueError(
            "TNF_result.product_link_selectors пустой/отсутствует — не могу выбрать selector_product для шага 6.1"
        )

    input_data_for_3_links = {
        "first_url": result_agent_step_6_URL_construct.get("start_page_url"),
        "second_url": result_agent_step_6_URL_construct.get("url_for_2_page"),
        "third_url": result_agent_step_6_URL_construct.get("url_for_second_search_query"),
        "selector_product": product_link_selectors[0],
        "additional_processing_for_the_link_value": result_agent_step_4_product.get("additional_processing_for_the_link_value"),
    }

    result_agent_step_6_1_get_links_for_product = agent_step_6_1_get_links_for_product(input_data_for_3_links, search_request)







    # region Шаг 7 - Сборка кода

    GET_PRODUCT_LINK_LINES_CODE = result_agent_step_4_product.get("builded_code_product_processing")
    GET_MAX_PAGE_BLOCK = result_agent_step_5_pagination.get("builded_code_get_max_page_on_pagination")
    URL_BLOCK = result_agent_step_6_URL_construct.get("result_code_url_builder")

    if not GET_PRODUCT_LINK_LINES_CODE:
        raise ValueError("Пустой/отсутствует builded_code_product_processing (шаг 4).")
    if not GET_MAX_PAGE_BLOCK:
        raise ValueError("Пустой/отсутствует builded_code_get_max_page_on_pagination (шаг 5).")
    if not URL_BLOCK:
        raise ValueError("Пустой/отсутствует result_code_url_builder (шаг 6).")


    # Собираю вход для шага сборки всей процедуры parsePage
    object_for_code_block_parsePage = {
        "URL_BLOCK": URL_BLOCK,
        "GET_MAX_PAGE_BLOCK": GET_MAX_PAGE_BLOCK,
        "GET_PRODUCT_LINK_LINES_CODE": GET_PRODUCT_LINK_LINES_CODE
    }

    print("object_for_code_block_parsePage:")
    object_for_code_block_parsePage_string = json.dumps(object_for_code_block_parsePage, ensure_ascii=False, indent=4, default=str)
    print(object_for_code_block_parsePage_string)


    """
    Пример результата:

    {
        "URL_BLOCK": "let url = set.page && +set.page > 1 ? new URL(`${HOST}/page/${set.page}/`) : new URL(`${HOST}/`)\nurl.searchParams.set('s', set.query)\nurl.searchParams.set('post_type', 'product')",
        "GET_MAX_PAGE_BLOCK": "let totalPages = Math.max(...$(\"nav.woocommerce-pagination .page-numbers\").get().map(item => +$(item).text().trim()).filter(Boolean))",
        "GET_PRODUCT_LINK_LINES_CODE": "let products = $('.products .product-card a.stretched-link[href*=\"/products/\"]')\nlet product = products?.eq(0)\nlet link = $(product)?.attr('href')\nconsole.log('link = ' + link)"       
    }

    {
        "URL_BLOCK": "let url = new URL(`${HOST}/catalog/`)\nurl.searchParams.set(\"q\", set.query)\nurl.searchParams.set(\"s\", \"Найти\")\nurl.searchParams.set(\"PAGEN_2\", set.page)",
        "GET_MAX_PAGE_BLOCK": "let totalPages = Math.max(...$(\"nav#pagination a\").get().map(item => +$(item).text().trim()).filter(Boolean))",
        "GET_PRODUCT_LINK_LINES_CODE": "let HOST = \"https://makitatrading.ru\";\nlet products = $('.catalog.catalogCards .itemCard[itemtype=\"http://schema.org/Product\"] a.item_title[href^=\"/catalog/product/\"]');\nlet product = products?.eq(0);\nlet link = HOST + $(product)?.attr('href');\nconsole.log('link = ' + link);"
    }
    """


    # Вот тут добавить вызов функции сборщика кода
    print("Запускаем agent_step_7_build_code_parsePage")
    
    parse_page_code_fragment = agent_step_7_build_code_parsePage(object_for_code_block_parsePage)

    print("📒 parse_page_code_fragment:")
    print(parse_page_code_fragment)


    """ 
    async parsePage(set: SetType) {
        let url = set.page && +set.page > 1 ? new URL(`${HOST}/page/${set.page}/`) : new URL(`${HOST}/`)
        url.searchParams.set('s', set.query)     
        url.searchParams.set('post_type', 'product')

        const data = await this.makeRequest(url.href)
        const $ = cheerio.load(data)

        if (set.page === 1) {
            let totalPages = Math.max(...$("nav.woocommerce-pagination .page-numbers").get().map(item => +$(item).text().trim()).filter(Boolean))
            this.debugger.put(`totalPages = ${totalPages}`)
            for (let page = 2; page <= Math.min(totalPages, +this.conf.pagesCount); page++) { 
                this.query.add({ ...set, query: set.query, type: "page", page: page, lvl: 1 });
            }
        }

        let items: ResultItem[] = [];
        let products = $('.products .product-card a.stretched-link[href*="/products/"]')      
        if (products.length == 0) {
            this.logger.put(`По запросу ${set.query} ничего не найдено`)
            throw new NotFoundError()
        }
        products.slice(0, +this.conf.itemsCount).each((i, product) => {
            let link = $(product)?.attr('href')  
            this.query.add({ ...set, query: link, type: "card", lvl: 1 })
        })
        return items;
    }
    """

    # region Шаг 8 - Проверка открытия страницы

    """ 
    
    Тут нужно будет проверить, открывается ли одинаковая страница в Playwright и по прямому запросу. Если между ними есть больше 15% разницы, то кидать ошибку, что "По прямому запросу сайт выдаёт другой контент, чем в браузере"

    """

    # region Шаг 9 - parseCard

    # 15 примеров ссылок товаров лежат в result_agent_step_6_1_get_links_for_product

    parse_card_code_fragment = "" #########















    # region Шаг 10 - Итоговый код

    result_final_code = build_final_code(url_input, parse_card_code_fragment, parse_page_code_fragment)

    print("result_final_code:")
    print(result_final_code)

    print("🟦 Завершили все фазы для parsePage ✅")
    input("Нажмите Enter, чтобы закрыть браузер...")

    return result_final_code
    




















link = "https://makitaclub.ru"
# link = "https://kotel-nasos.ru/nastennyy-gazovyy-kotel-28-kvt-eca-gerda-28-hm-ng_1/"
# link = "https://makitatrading.ru"
# link = "https://galleryceramics.ru"
main_processer(link)



















































def main_processer_old(input_url):
    print("Запускаем основной процесс")

    # 1. Чистим входящий url - до host, что бы получить ссылку на главную страницы
    url = normalize_url(input_url)

    # 2. Запускаем браузер и переходми на эту страницу
        # Дожидаемя полной загрузки страницы, но с таймаутом в 20 секунд
    
    # 3. HGF_main_page_selector_and_semantic_handler
    
    # region Шаг 1 - HGF

    ### Тут возможно стоит брать html контент из playwright
    ######## И не понятно, надо ли проверять, отличается ли контент в браузере от контента по прямому запросу, без него
    html_content = get_html_from_cache(url)
    html_content_zip = clean_html_universal(html_content)

    # save_page_html(html_content, filename = "page_html.html")
    # save_page_html(html_content_zip, filename = "page_html_zip.html")

    HGF_result = HGF_main_page_selector_and_semantic_handler(html_content_zip)
    print(f"\nHGF_result:\n")
    print(HGF_result)

    """
    Пример результата в HGF_result:
    input_data:
    {
        "status": "ok",
        "error_type": null,
        "analysis_message": "Страница успешно обработана",
        "semantics": ["инструмент", "дрель", "шуруповерт", "перфоратор", "болгарка", "пила", "лобзик", "шлифмашина", "пылесос", "аккумулятор"],
        "search_input_selectors": [
            "#woocommerce-product-search-field-0",
            ...
        ],
        "search_button_selectors": [
            "form.woocommerce-product-search button[type=\"submit\"]",
            ...
        ]
    }
    """

    """ 
    {
        "status": "ok",
        "error_type": null,
        "analysis_message": "Страница успешно обработана",
        "semantics": [
            "инструмент",
            "дрель",
            "шуруповерт",
            "перфоратор",
            "болгарка",
            "пила",
            "шлифмашина",
            "пылесос",
            "аккумулятор",
            "оснастка"
        ],
        "search_input_selectors": [
            "#woocommerce-product-search-field-0",   
            "form.woocommerce-product-search input.search-field",
            ".site-search form.woocommerce-product-search input[type=\"search\"]",
            "input.search-field[name=\"s\"]",        
            "form[role=\"search\"] input[type=\"search\"]"
        ],
        "search_button_selectors": [
            "form.woocommerce-product-search button[type=\"submit\"]",
            ".site-search form.woocommerce-product-search button[type=\"submit\"]",
            "form[role=\"search\"] button[type=\"submit\"]",
            ".woocommerce-product-search button[type=\"submit\"]",
            ".site-search button[type=\"submit\"]"   
        ]
    }
    """

    # 4. Включается агент, он валидирует поле поиска и переходит на страницу результатов

    # region Шаг 2 - Агент

    """

    Более формально:

    Если ошибка на любом шаге, то:
    1. Перезагрузить страницу
    2. Выбрать следующий элемент на том месте, где произошла ошибка - это либо селектор поля ввода, либо запрос из семантики, либо селектор кнопки начала поиска. Для тех шагов, на которых ошибки не было - использовать ранее использованные значения.
    3. Начать алгоритм с первого шага

    Алгоримтм:

    - Выбрать первый селектор, проверить что он даёт результат на странице
    - Получить окружающий html код вокруг этого элемента, убедиться что это действительно поле ввода запроса на поиск
    - Использовать инструмент наведения фокуса на этот элемент
        - Который под капотом будет делать Click-Wait-Click с таймаутом 1 секунда
        - Если произоёшл fallback, то нажимать Esc на странице, и повторять Click-Wait-Click на указанный элемент
        # Если ошибка?
    - Использовать инструмент вставки значений в это поле (первый запрос из семантики)
        - Используя методы PL
        - Если будет ошибка, то вернуть её агенту. Он сможет попробовать использовать инструменты для её устранения, либо перезагрузить страницу и начать с первого шага алгориитма
    После вставки текста в поле ввода
    - Сохраняет текущий URL страницы
    - Нажимает Enter
    - Ждёт редиректа (изменился URL либо сильно поменялся html код страницы), либо таймаут 15 секунд
    - При таймауте, нажимает на кнопку старта поиска
    - Если ничего не происходит - анализирует ситуацию, и используя инструменты пытается найти решение, ему нужно перейти на страницу результатов поисковой выдачи. Также может перезагрузить страницу и начать сначала, попробовав другие селекторы
    - Когда переход на новую страницу завершён и она загруилась, извлекает html страницы, и передаёт следующему инструменту. Свою работу завершает






    Перед запуском агента открываем браузер

    ЗАДАЧА:

    

    Алгоритм, что тебе нужно сделать:

    1. Выбрать селектор (используя данные из поля search_input_selectors из input_data), проверить что он даёт результат на странице (инструмент find_elements)
    2. Получить окружающий html код вокруг этого элемента, убедиться что это действительно поле ввода запроса на поиск (инструмент get_html_frame)
    3. Использовать инструмент наведения фокуса на этот элемент (это smart_focus)
    4. Использовать инструмент вставки значений в это поле (запроса из семантики, это значение из поля semantics из input_data), это human_like_input
    
    После вставки текста в поле ввода
    5. Сохранить текущий URL страницы (get_current_url) - можешь записать его в memory
    6. Нажими Enter (press_enter)
    7. Дождись редиректа (wait_for_navigation_or_content)
    Если редирект успешен, то запиши в result в поле second_html - URL страницы на которую был совершён переход.

    Если редиректа не было в указанный таймаут после нажатия Enter, то попробуй нажать кнопку запуска поиска (элемент из search_button_selectors из input_data). Инструмент smart_focus - нужен только для поля ввода, его не следует использовать для кнопки запуска поиска. Для клика по элементу можно использовать click_element
    - Если ничего не происходит 
        пометь текущую пару (input_selector, button_selector) как нерабочую в memory
        если есть ещё неиспользованные селекторы:
            page_restart
            перейти к шагу 1
        иначе:
            FAILED с результатом, что не удалось найти рабочих селекторов поля поиска, и не получилось добиться перехода на следующую страницу.
    - Возможно стоит попробовать другие селекторы search_input_selectors и search_button_selectors. Для этого ты можешь перезагрузить текущую страницу (page_restart), и начать алгоритм заново, с выбора селектора, но уже теперь в memory сохрани что первый селектор - не сработал как надо, и стоит попробовать второй

    Задача успешно завершится, когда ты заполнишь поле second_html в result.
    Если не указано иного, то выбирай первые элементы из массивов в input_data.









    Установить лимит истории в 20, лимит шагов в 40.












    # Отдельно реализовать:

    # - get_html_frame (дописать) - Доработать код в get_html_frame, и вынести его в html_toolkit
    # - Формирование curl запроса, с body, заголовками и прочим
    # - Проверяет, валидный ли это селектор Cheerio
    # - Получение всех запросов в браузере, с их параметрами и частью body (обрезанной в середине)
    # - Получение результатов конкретного запроса, с указанием сколько контента из ответа нужно показать
    # - Поиск запросов в которых есть вхождение подстроки (как в результатах так и в запросах, это можно будет например контролировать параметрами)    
    # - Реализовать инструмент, который возвращает html между двумя найденными вхождениями одинаковых селекторов
    # и возможно как-то собирает полный элемент между ними. Возвращает с доп. информацией
    #     - Да, это прям надо сделать автоматически, для валидации селектора товара






    # Понадобятся такие функции инструменты:
    # - get_html_frame (дописать) - Доработать код в get_html_frame, и вынести его в html_toolkit
    # - validate_interactivity(selector):
    #     - Что делает: Вызывает isEditable(), isVisible() и isEnabled()
    #     - Зачем: Быстрая проверка, стоит ли вообще пытаться взаимодействовать с этим селектором.
    # - smart_focus(selector):
    #     - Логика: Реализует цикл Click -> Wait(1s) -> Click.
    #     - Встроенная обработка ошибок: Если клик перехвачен (interception), процедура должна автоматически выполнить page.keyboard.press('Escape') и попробовать снова.
    #     - Если не получилось, то возвращаем подробную ошибку
    # - human_like_input(selector, text):
    #     - Логика: Очистка поля -> Ввод через locator.pressSequentially(text, { delay: 100 }).
    #     - Зачем: Посимвольный ввод активирует скрипты валидации на сайте, которые «не видят» обычную вставку текста.
    # - wait_for_navigation_or_content(old_url, timeout):
    #     - Ждёт изменения URL и прогрузку страницы
    #     - Либо если после таймаута html поменялось более чем на 20% (но считать от текстового содержания страниц, без учёта html тегов)
    # - page_restart()
    #     - Перезагружает текущую страницу

    # Инструменты которые пригодятся в будущем:
    # - Переход на указанную страницу по url
    # - Проверка, какой код вернёт запрос на указанный URL (проверка валидности)
    # - Формирование curl запроса, с body, заголовками и прочим
    # - Получение всех запросов в браузере, с их параметрами и частью body (обрезанной в середине)
    # - Получение результатов конкретного запроса, с указанием сколько контента из ответа нужно показать
    # - Поиск запросов в которых есть вхождение подстроки (как в результатах так и в запросах, это можно будет например контролировать параметрами)
    # - Проверяет, валидный ли это селектор Cheerio
    # - Реализовать инструмент, который возвращает html между двумя найденными вхождениями одинаковых селекторов
    # и возможно как-то собирает полный элемент между ними. Возвращает с доп. информацией
    #     - Да, это прям надо сделать автоматически, для валидации селектора товара
    # - Поиск на текущей html странице по подстроке (вернёт максимум 5 вхождений +- 200 символов вокруг, также вернёт кол-во вхождений)
    # - Найти и вернуть элемент по селектору (также max 5, + кол-во найденных. Можно запросить только кол-во)
    

    

    """


    """

        1. По лучшему селектору находит элемент поля ввода запроса на поиск
            - Если поиск не дал результатов, то пробует запасные селекторы
            - Если и запасные не сработали, то error
        
        2. Проверка и валидация, верное ли это поле, путём:
            - Проверки через playwright, является ли это элемент полем ввода, и возможен ли туда ввод текста
                - При выполнении вставки текста, PL сам может выкинуть исключение. Тогда его стоит ловить, и обрабатывать уже на стороне агента, т.к. в исключении будет подробно прописана причина ошибки
            - Проверка окружающего html кода этого элемента
                - Это надо будет сделать, что бы он посмотрел на код, и сам решил, действительно ли это нужный элемент. И далее либо пошёл дальше с использвоанием его, либо взял другой

        3. Наводит фокус на это поле
            - Тут могут быть проблемы со всплывающим окном, и по этому возможно стоит 2 раза наводить фокус
            - Проверить методом Actionability Checks при click(). Если поле ввода перектыто модальным окном - получу ошибку
                - Тогда нажать кнопку Esc, это закроет большинство модальных окон
                - И снова попробовать навести фокус. Если снова ошибка - то error агента
            - И вообще стоит использовать Click-Wait-Click с таймаутом 1 секунда
        4. Вставляет в это поле первый запрос из семантики
        5. Запоминает текущий URL страницы
        6. Нажимает Enter
        7. Ждёт 15 секунд, пока URL не поменяется, нас не перекинет на другую страницу, и она не загрузится
            7.1 Если после 15 секунд URL не поменялся, и загрузки новой страницы не произошло, то агент:
            7.2 Нажимает на кнопку начала поиска
            7.3 Также ждёт перехода
            7.4 Если первая кнопка не сработала - то у нас есть ещё 4 запасных
            7.5 Если после нажатия всех кнопок ничего не произошло - error
        8. Получает html страницы результатов

        Завершает свою задачу, и передаёт html следующему инструменту

    """

    """

    Он возвращает:
    - Рабочую сессию с PL, на этой странице
    - URL этой страницы
    - html этой страницы

    """

    # 5. Когда попал на страницу результатов - отправляет её в TNF_extract_data_from_search_page

    # region Шаг 3 - TNF

    """
    
    Получает html страницы результатов поиска.
    
    Возвращает набор параметров вида:

    {
        "status": "ok" | "error",
        "error_type": string | null,
        "analysis_message": string,
        
        "search_input_selectors": [string, string, string],
        "search_button_selectors": [string, string, string] | null,
        "total_results_count_selectors": [string, string, string] | null,
        
        "product_link_selectors": [string, string, string],
        
        "pagination_container_selectors": [string, string, string] | null,
        "pagination_page2_selectors": [string, string, string] | null,
        "pagination_last_page_selectors": [string, string, string] | null,
        
        "last_page_number_displayed": boolean | null
    }
    """

    # 6. Активируется агент, и ему нужно:

    # region Шаг 4 - агент

    """

    - Валидирует селектор товара
        Прописать по каким признакам. Например:
        - Кол-во на странице
        - То что выделяется объект, в котором есть название, цена, кнопка "В корзину" или подобнае, изображение товара, и возможно описание
    - Записывает селектор товара в результаты
    - Запоминает URL
    - Находит кнопку 

    Глобально ему нужно будет проверить:
    - Селектор товара
    - Где получить максимальное количество страниц выдачи (число)
    - Собрать запрос на любую станицу выдачи и любой поисковый запрос

    Формат ответа может быть таким:

    {
        "engine_config": {
            "base_url_template": "https://example.com/catalogsearch/result/index/?q={{query}}&p={{page}}",
            "pagination_type": "page_number", // или "offset"
            "start_page_index": 1,
            "total_pages": 15,
            "items_per_page": 24
        },
        "validated_selectors": {
            "product_link": "div.products a.stretched-link[href]",
            "pagination_container": "nav.woocommerce-pagination",
            "total_count_label": "p.woocommerce-result-count"
        },
        "search_payload_info": {
            "query_param": "q",
            "page_param": "p"
        },
        "confidence_score": 0.95,
        "reasoning_log": "Успешно определен шаблон URL через сравнение 1 и 2 страницы. Лимит страниц (15) вычислен на основе общего кол-ва товаров (350) и кол-ва на странице (24)."

        // И тут можно например 10 ссылок на товары - полученных не через LLM а простыми селекторами
        // за одно и проверим правильно ли они извлекаются
    }



    Т.е. на этом этапе уже должно хватать данных для того что бы собрать parsePage

    Детект доп. запросов:
    - Нужно будет пройтись этими селекторами на html полученной через curl
        - Если всё работает - то ок, далее работаем с playwright
        - Если не работают на этой html, а в playwright работают - то смотрим запросы,
            - и ищем там подстроки названий товаров, или их цен (или чего-то английского)
        - Если селекторы не работают ни в PL ни на голом html, то возвращаем ошибку агента


    Проверка корректности формирования url на кастомную страницу:
    - Взять текущий url, посмотреть url из кнопки на 2ю страницу, попробовать собрать шаблон 
        и перейти с ним на 3ю и 4ю страницы
        - На них проверить, работают ли селекторы товаров
        - Разные ли получаются ссылки на товары
    
    - Надо будет собрать ссылку на последнюю страницу, проверить что она корректно открывается
        - Если нет, то на предпоследнюю


    Проверка пагинации:
    - Нужно будет запустить код той страшной регулярки на селекторе пагинации, и убедиться что он возвращает верное число
        - Если нет, то надо будет писать свой код. И далее, если надо будет - пост обработку регуляркой, что бы в итоге было нужное число


    Тогда агент собирает результат:
    - Параметры set.page и set.query, куда их вставить в запрос на формирование URL
    - Селектор блока пагинации, который работает с большой регуляркой
        - Либо селектор последней страницы, если селектор блока не работает с регуляркой
        - Тогда надо будет проверить, что доп. обработок не требуется, и если требуются, то описать их в виде текста и кода
    - Селектор для извлечения товара
        - Либо кусок кода, которым можно извлечь нужное значение 


    Далее, агент запускает инструмент LLM, которая формирует результирующий код процедуры parsePage, на основе этих данных

        Каким может быть системный промпт для этого инструмента:

        "Ты — эксперт по Node.js и Cheerio. Твоя задача — собрать метод parsePage. Используй предоставленные селекторы и фрагменты кода с описанием. Обязательно сохрани использование HOST, this.conf и архитектуру this.query.add. Не меняй сигнатуру метода."


    В итоге проще всего будет сформировать эти блоки кода в агенте, т.к. он сможет их проверить:

    {
        блок кода сборки url
        блок кода пагинации
        блок кода извлечения ссылки на товра
    }

    Собрать всё в 1 функцию, и parsePage будет готова

    """





    # region Шаг 5 - Сборка рез.

































# region Доп. функции

def save_page_html(html: str, filename: str = "page_html.html") -> str:
    """
    Сохраняет HTML в файл рядом со скриптом и возвращает путь к файлу.
    
    Args:
        html: html-содержимое страницы
    """
    print("Сохраняем html страницы в файл", filename)
    output_path = Path(__file__).resolve().parent / filename
    output_path.write_text(html, encoding="utf-8")
    return str(output_path)


































"""
Задачи на будущее:

Для тестов можно использовать gpt-5-mini

- Потом как закончу, прогнать GPT, что бы собрал все мипорты библиотек в один файл
    - Если получится - упростить использование поддерикторий
    - И возможно, если останется время - убрать лишние библиотеки, которые сейчас уже не используются
        - Просто прогнать поиском по их объявлениям, если нет - то комментируем

Добавить в правило:
- Если ты совершил 2 одинаковых действия подряд и delta_text равен 0, ты ОБЯЗАН сменить тактику: попробовать find_elements, сделать scroll, или проверить, нет ли перекрывающих элементов (модальных окон).

И после этого - прикрутить работу с доп. запросами JSON

После этого - тестировать на сайтах из колонки аутсорса. Нужно 85% успеха
Далее - собрать новый фронт, и сделать что бы всё было красиво и функционально


- Добавить функционал local_storage в агента
    - Пока что будем работать без него. Возможно добавим на 4м шаге

- Вот на этом сайте данные поиска подгружаются POST запросом:
https://www.krason.ru/search

- В очень редких случаях пагинации на странице нет вообще - сайт выдаёт все результаты на одной странице. Но тогда на больших запросах будет много результатов (можно будет проверить, если количество результатов плавает на больших запросах, и везде > 100, то скорее всего пагинации нет) - пока что следует поставить заглушку на этот случай, в будущем доработать
  - Иногда вместо пагинации есть бесконечная автоподгрузка, через запросы - пока что следует поставить заглушку на этот случай, в будущем доработать
  - Иногда, очень редко, нет ни кнопки последней страницы, ни указания количества результатов. Тогда нужно будет реализовывать динамическую пагинацию - пока что следует поставить заглушку на этот случай, в будущем доработать
- Можно будет в будущем обработать ситуацию когда есть кнопка "Показать ещё"
    - Бесконечная прокрутка: Если пагинация реализована через кнопку «Показать еще» (Load More) без нумерации страниц, укажи селектор этой кнопки в поле `next_page_button` и пометь тип пагинации как `load_more`.


Надо:
- Протестировать инструмент перехода к ранее выполненному шагу плана
- Если первый селектор поиска не верный
- Если нажатие кнопки Enter не меняет state браузера, и нужно будет использовать кнопку начала поиска


- Помнить, что лимит шагов агента может быть исчерпан, без решения задачи - потом обработать это 

- Надо будет проверять, как работает get_html_frame, и возможно править её

- Сделать документацию - описание у каждого скрипта
- Почистить старые

- Пофиксить баги в get_html_frame
- Возможно стоит добавить агенту возможность добавлять в результат сразу несколько полей
- Добавить инструмент - получить полную историю выполнения задания

- Пока что убрал идею с генерацией 2х и более селекторов для товара. Потом можно будет вернуться к ней, или если точность бует низкой
- Добавить инструмент для эмуляции .formatPrice()

"""


"""
Старые простые:
(смотрел по простоте реализации)

https://domo-terra.ru
https://domplitok.ru
https://dvkeramik.ru
https://e-dz.ru
https://electron.bg
https://www.electrovek.ru
https://www.elemor.ru
https://ceraboom.ru
https://ceramama.ru
https://ceramicmall.ru
https://ceramictilecenter.ru
https://ceram-stroy.ru
https://www.ceramtrade.ru
https://championtool.ru
https://www.chipdip.ru        
https://comfort-klimat.ru    
https://cosmofun.ru          
https://c-s-k.ru             
https://galen.bg           
https://galleryceramics.ru 
https://gazovik-omsk.ru    
https://gaz-shop78.ru      
https://gidro-top.ru       
https://glavsantex.ru      
https://goodzone23.ru      
https://gra-nit.ru         
https://gresstore.ru       
https://gastehmarket.ru
https://daewoo-power.ru
https://chiedocover.ru
https://edrinks.bg
https://dom-septik24.ru 
https://makita-line.ru

Обработать другие расписанные ситуации

"""


""" 
Привет, я составил такой запрос для своего reasoning-агента. 
Посмотри, всё ли достаточно понятно? Нет ли орфографических ошибок? Нет ли логических ошибок? Верно ли составлена схема и шаблон для result, в правильных ли местах я прошу заполнить эти поля? Нет ли каких-то мест, где алгоритм прописан недостаточно точно, которые модель может понять не так, какие-то моменты которые я пропустил в алгоритме, и в общем целостность и понятность задачи:
"""