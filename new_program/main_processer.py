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

from front_client import update_content_front_last_phase_result

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Подключение всех библиотек и функций
from Gen_parseCard.main_gen_parseCard import *
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
from new_program.check_request_this_site_ok import *
from new_program.agent_step_6_2_diginetica_and_custom_req_on_PP import *

# region Задачи

""" 

Глобальный план:






- Фронт собрать 
    - [прописать что нужно]
- Тестировать, уже с использованием фронта








- Найти хороший пример, на котором буду всё показывать (котёл-насос)
    - И второй по хорошести тоже добавить
- Добавить скриншоты браузера с текущего состояния
- Нужно добавить выводимые селекторы
    - Как минимум те, которые были найдены на странице (на 9 шаге это выводить в видимое поле)



- Добавить потом fallback при неверной заданной ссылке на new_page_1





















Доп: 

- Потом надо будет добавить инструменты:
    - Для отправки curl запросов, простых и с параметрами
    - Для получения данных из запросов на странице Playwright, поиск и работу с ними
        - Для примера, можно например взять avon.ru и detmir.ru
- Добавить проверку на то, такая же страница открывается вне браузера по прямому curl запросу, или нет
- Надо будет добавить скриншоты состояния из браузера, по актуальным шагам
- Прописать fallback ошибок если шагов не хватило
    - Или если агент закончит работу с ячным ответом Failed


- Собрать все возможные исключения, которые прописал, и обработать их
- Ещё есть задачи которые прописаны ниже. В конце их глянуть
- Для run_js_parsePage_get_card_links добавить обёртку безопасности

В среднем - 15 минут на генерацию






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
    start_time = time.time()
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
    update_content_front_last_phase_result(json.dumps(HGF_result, ensure_ascii=False, indent=4))
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
    update_content_front_last_phase_result(json.dumps(result_agent_answer_from_2_step, ensure_ascii=False, indent=4))
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
    update_content_front_last_phase_result(json.dumps(TNF_result, ensure_ascii=False, indent=4))

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

    """

    # region Шаг 4, 5, 6 - Агенты

    search_request = result_agent_answer_from_2_step.get("used_search_request")

    # region Шаг 6_2 - Кастомные запросы

    
    parse_page_code_fragment = None
    result_agent_step_4_product = None
    result_agent_step_5_pagination = None
    result_agent_step_6_URL_construct = None

    semantics_list = HGF_result.get("semantics") or []
    semantics = {"semantics": semantics_list}

    if not TNF_result.get("pagination_container_selectors") or not TNF_result.get("pagination_page2_selectors"):
        
        # Генерация PP для дигинетики

        parse_page_code_fragment = agent_step_6_2_diginetica_and_custom_req_on_PP(TNF_result, search_request, semantics, result_agent_answer_from_2_step.get("second_html")).get("result_code")
        update_content_front_last_phase_result(json.dumps(parse_page_code_fragment, ensure_ascii=False, indent=4))
    
    else:

        # Генерация PP по кусочкам, в обычном формате

        print("Запуск result_agent_step_4_product")
        result_agent_step_4_product = agent_step_4_product(TNF_result, search_request)
        update_content_front_last_phase_result(json.dumps(result_agent_step_4_product, ensure_ascii=False, indent=4))
        """ 
        Формируент фрагмент кода для вставки в PC - обработка извлечения ссылки на товар

        let HOST = "https://example.com"
        let products = $('.products-selector')
        let product = products?.eq(0)
        let link = HOST + $(product)?.attr('href')
        console.log("link = " + link)
        """

        print("Запуск result_agent_step_5_pagination")
        result_agent_step_5_pagination = agent_step_5_pagination(TNF_result, search_request)
        update_content_front_last_phase_result(json.dumps(result_agent_step_5_pagination, ensure_ascii=False, indent=4))
        """ 
        Формируент фрагмент кода для вставки в PC - обработка извлечения максимального количества страниц пагинации

        let totalPages = Math.max(...$(selector).get().map(item => +$(item).text().trim()).filter(Boolean))
        или
        let totalPages = +$('.pagination a')?.eq(-3)?.attr('href')?.match(/[?&]page=(\d+)/)?.at(1);
        """

        print("Запуск result_agent_step_6_URL_construct")
        result_agent_step_6_URL_construct = agent_step_6_URL_construct(TNF_result, search_request, semantics, url_input)   
        update_content_front_last_phase_result(json.dumps(result_agent_step_6_URL_construct, ensure_ascii=False, indent=4)) 
        """ 
        Формируент фрагмент кода для вставки в PC - обработка создания URL на основе кастомного запроса и номера страницы выдачи

        let url = new URL(`${HOST}/content/search/`)
        url.searchParams.set("s", "")
        url.searchParams.set("q", set.query)
        url.searchParams.set("PAGEN_1", set.page)
        """








    # Генерируем кастомные исключения, для понятной отладки в случае ошибок
    # (актуально только для “обычного” сценария, когда PP ещё не сгенерен)
    if parse_page_code_fragment is None:
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



    # region Шаг 6_1 - Собираем ссылки на товары с трёх страниц

    """ 
    Собираю 15 примеров ссылок с тех URL которые у нас уже есть
    """

    product_link_selectors = TNF_result.get("product_link_selectors") or []
    if not isinstance(product_link_selectors, list) or not product_link_selectors or not product_link_selectors[0]:
        raise ValueError(
            "TNF_result.product_link_selectors пустой/отсутствует — не могу выбрать selector_product для шага 6.1"
        )

    # В “кастомной” ветке пагинации может не быть, и тогда у нас реально есть только 1 URL (second_html).
    # В этом случае step 6_1 соберёт 15 ссылок с одной страницы (с повторением, если ссылок < 15).
    if isinstance(result_agent_step_6_URL_construct, dict) and result_agent_step_6_URL_construct.get("start_page_url"):
        input_data_for_3_links = {
            "first_url": result_agent_step_6_URL_construct.get("start_page_url"),
            "second_url": result_agent_step_6_URL_construct.get("url_for_2_page"),
            "third_url": result_agent_step_6_URL_construct.get("url_for_second_search_query"),
            "selector_product": product_link_selectors[0],
            "additional_processing_for_the_link_value": (result_agent_step_4_product or {}).get("additional_processing_for_the_link_value"),
        }
    else:
        input_data_for_3_links = {
            "first_url": result_agent_answer_from_2_step.get("second_html"),
            "selector_product": product_link_selectors[0],
            "additional_processing_for_the_link_value": None,
        }

    result_agent_step_6_1_get_links_for_product = agent_step_6_1_get_links_for_product(input_data_for_3_links, search_request)
    update_content_front_last_phase_result(json.dumps(result_agent_step_6_1_get_links_for_product, ensure_ascii=False, indent=4)) 

    """
    {
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
    """







    # region Шаг 7 - Сборка кода

    if parse_page_code_fragment == None:

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
    update_content_front_last_phase_result(parse_page_code_fragment) 


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

    five_links_1 = (result_agent_step_6_1_get_links_for_product or {}).get("five_links_1") or []
    if not isinstance(five_links_1, list) or not five_links_1 or not five_links_1[0]:
        raise ValueError(
            "Шаг 6.1 вернул пустой/некорректный five_links_1 — не могу проверить доступность сайта простыми запросами."
        )
    check_url_t = five_links_1[0]
    # Проверяем на первой странице товара
    result_check_simple_request_on_this_site = check_request_this_site_ok(check_url_t)
    result_check_simple_request_on_this_site_status = result_check_simple_request_on_this_site.get("request_ok")

    print(f"\nПроверка, можно ли будет получать контент с сайта обычными запросами\n")
    print_json(result_check_simple_request_on_this_site)
    update_content_front_last_phase_result(json.dumps(result_check_simple_request_on_this_site, ensure_ascii=False, indent=4)) 

    if result_check_simple_request_on_this_site_status == False:
        error_text = """
        
        🟡 Данные с текущего сайта нельзя будет корректно получать простыми http request запросами.
        По прямому запросу сайт выдаёт другой контент, чем в браузере.
        📘 Нужно подключать логику решалки

        Данный функционал не реализован на текущий момент 🟡

        """
        return error_text

    # region Шаг 9 - parseCard

    # 15 примеров ссылок товаров лежат в result_agent_step_6_1_get_links_for_product

    (parse_card_code_fragment, fields_descr)  = main_gen_parseCard(result_agent_step_6_1_get_links_for_product, url_input)
    update_content_front_last_phase_result(parse_card_code_fragment) 

    """ 
    async parseCard(set: SetType, cacher: Cacher<ResultItem[]>) {
        let items: ResultItem[] = []

        const data = await this.makeRequest(set.query);
        const $ = cheerio.load(data);        

        const name = $("h1.product_title.entry-title").first().text().trim()
        const price = $("p.price .woocommerce-Price-amount").first().text().trim()?.replace(/\s+/g, " ")?.replace(/,/g, ".")?.replace(/[^\d.]/g, "")
        const imageLink = $(".woocommerce-product-gallery img.wp-post-image").first()?.attr("data-large_image") || $(".woocommerce-product-gallery img.wp-post-image").first()?.attr("data-src") || $(".woocommerce-product-gallery img.wp-post-image").first()?.attr("src") || ""
        const article = $(".product_meta .sku_wrapper .sku").first().text().trim()        
        const addToCartText = $("form.cart .single_add_to_cart_button, form.cart button.single_add_to_cart_button, button.single_add_to_cart_button")?.first().text().trim(); 
        const stock = addToCartText?.includes("В корзину") ? "InStock" : "OutOfStock";
        const timestamp = getTimestamp()     

        const item: ResultItem = {
            name, price, imageLink, article, stock, link, timestamp
        }
        items.push(item);

        cacher.cache = items
        return items;
    }
    """

    # region Шаг 10 - Итоговый код

    result_final_code = build_final_code(url_input, parse_card_code_fragment, parse_page_code_fragment, fields_descr)

    print("result_final_code:")
    print(result_final_code)

    # print("🟦 Завершили все фазы для parsePage ✅")
    # input("Нажмите Enter, чтобы закрыть браузер...")

    print(f"\n")
    emit_execution_time(start_time, emit=print, print_time_smile=True)

    return result_final_code
    



def main_processer_base(link):
    try:
        result = main_processer(link)
    except BaseException:
        result = traceback.format_exc()
    return result



# region Тестовый запуск
if __name__ == "__main__":
    # link = "https://makitaclub.ru"
    link = "https://kotel-nasos.ru/nastennyy-gazovyy-kotel-28-kvt-eca-gerda-28-hm-ng_1/"
    # link = "https://makitatrading.ru"
    # link = "https://galleryceramics.ru"

    main_processer_base(link)










































# region Старые задачи

"""
Задачи на будущее:

Для тестов можно использовать gpt-5-mini

- Потом как закончу, прогнать GPT, что бы собрал все импорты библиотек в один файл
    - Если получится - упростить использование поддерикторий
    - И возможно, если останется время - убрать лишние библиотеки, которые сейчас уже не используются
        - Просто прогнать поиском по их объявлениям, если нет - то комментируем

Добавить в правило:
- Если ты совершил 2 одинаковых действия подряд и delta_text равен 0, ты ОБЯЗАН сменить тактику: попробовать find_elements, сделать scroll, или проверить, нет ли перекрывающих элементов (модальных окон).

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
- Добавить инструмент - получить полную историю выполнения задания

- Пока что убрал идею с генерацией 2х и более селекторов для товара. Потом можно будет вернуться к ней, или если точность бует низкой
- Добавить инструмент для эмуляции .formatPrice()

- Сделать headles = True для Playwright

"""

# region Примеры ссылок

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


————————————————————————

Не ок:

link = "https://apelsin.ru"
link = "https://donplafon.ru/"
link = "https://domostroy.shop"

"""


""" 
Привет, я составил такой запрос для своего reasoning-агента. 
Посмотри, всё ли достаточно понятно? Нет ли орфографических ошибок? Нет ли логических ошибок? Верно ли составлена схема и шаблон для result, в правильных ли местах я прошу заполнить эти поля? Нет ли каких-то мест, где алгоритм прописан недостаточно точно, которые модель может понять не так, какие-то моменты которые я пропустил в алгоритме, и в общем целостность и понятность задачи:
"""







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
