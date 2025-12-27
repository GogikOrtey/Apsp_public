""" 
Здесь будет реализация алгоритма работы агента для 4го шага
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

from reasoning_agent.agent_main import *

from playwright_tool.playwright_toolkit import *  # регистрирует инструменты playwright
from new_program.html_toolkit import *  # регистрирует инструменты html_tool


""" 



"""














def gen_main_task_all(selector_product_link, host_value):
    main_task_all = """

Во входных данных (input_data) тебе даны селекторы на элементы этой страницы. Они понадобятся тебе в ходе выполнения проверок и решения задачи. В каждом массиве есть input_data по 3 селектора, из них первый - это самый стабильный и предпочтительный, по умолчанию используй его. Но если вдруг первый окажется по каким-то причинам неподходящим или нерабочим, то есть ещё два запасных селектора, которые указывают также на этот элемент.

Тебе нужно:

Определить, какой параметр или участок в URL отвечают за указание страницы и указание поискового запроса. И составить код позволяющий задавать произвольный запрос и страницу.

Алгоритм (4 фазы):

———————————————————————— ФАЗА 1:

1. Сохрани текущий URL страницы в result в поле start_page_url. Его можно получить инструментом get_current_url

2. Найди на текущей странице элемент, по нажатию на который будет выполнен переход на 2ю страницу. Его селектор должен лежать в поле pagination_page2_selectors в input_data. Нажми на него (инструмент click_element), затем дождись перехода (инструмент wait_for_navigation_or_content). 

Если перехода не произошло, изучи подробнее окружение элемента pagination_page2_selectors, используя инструмент get_html_frame_on_current_page, либо попробуй два других запасных селектора. Если перехода не происходит и страница не меняется - возвращай FAILED с сообщением, что не удалось перейти на вторую страницу поисковой выдачи.

Когда переход произойдёт, зафиксируй новый URL в result в поле url_for_2_page.

———————————————————————— ФАЗА 2:

На основе значений из result:
start_page_url = URL первой страницы
url_for_2_page = URL второй страницы

найди закономерность, как задаётся пагинация.
- Чаще всего она задаётся дополнительным параметром в URL. Пример: https://kotel-nasos.ru/search/?page=2&query=%D0%BA%D0%BE%D1%82%D0%B5%D0%BB
- Реже, она задаётся внутри пути URL. Пример: https://makitaclub.ru/page/2/?s=инструмент&post_type=product
- Редко пагинация задаётся оффсетом в URL.

Если ты видишь, что URL первой страницы и URL второй страницы одинаковы, или если ты не можешь выделить явных признаков количества страниц и задания поискового запроса в URL, то запиши в result в поле search_output_set_by_add_query значение true и возвращай FAILED с сообщением, что скорее всего товары загружаются доп. запросами.

В этой фазе тебе нужно найти, как именно задаётся пагинация. Если это доп. параметр - то понять, какой параметр за это отвечает (чаще всего это "page", "p", "PAGEN_1" и подобные). Запиши в memory параметр, который по твоему мнению задаёт пагинацию.

Далее сформируй ссылки на 3ю и 4ю страницы, и проверь их при помощи инструмента check_url_status. Если статус корректен, значит параметр был найден верно. Если нет, то уточняй параметр, и проверь что на странице поиска >= 4 страниц выдачи (просмотрев инструментом get_html_frame_on_current_page по селектору pagination_container_selectors).

Когда параметр задания страниц будет найден корректно, зафиксируй эту информацию в свободной форме, в result в поле info_from_page_parameter. На эту информацию ты будешь опираться в будущем, когда будешь собирать код, так что запиши туда нужное достаточное количество информации.

———————————————————————— ФАЗА 3:

На этой фазе тебе нужно будет найти, где и как задаётся поисковый запрос в URL.

1. Перейди снова на первую страницу (инструмент goto_url). Её URL лежит в result в поле start_page_url

2. Найди на странице поле ввода (это селектор search_input_selectors из input_data). Наведи на него фокус (инструмент smart_focus), и введи второй (или другой) запрос из семантики (объект semantics во входных данных), также проверь, что он отличается от того запроса, по которому был выполнен поиск сейчас: '""" + selector_product_link + """'. Для ввода текста запроса в поле ввода используй инструмент human_like_input. Далее нажми enter (инструмент press_enter) и дождись редиректа (инструмент wait_for_navigation_or_content). Если редиректа не последовало, используй кнопку запуска поиска (селектор search_button_selectors из input_data и инструмент click_element для нажатия).

3. Получи текущий URL (инструментом get_current_url). Сравни его с URL первой страницы, который лежит в result в поле start_page_url. Сохрани его в result в поле url_for_second_search_query.

4. На основе различий start_page_url и url_for_second_search_query из result выдели место, где задаётся поисковый запрос. Зафиксируй эту информацию в свободной форме в result в поле info_from_search_query_parameter, запиши туда нужное достаточное количество информации для дальнейшей генерации кода.

———————————————————————— ФАЗА 4:

В конце, тебе нужно будет сформировать фрагмент кода на JS, который позволит задавать произвольный запрос и указывать произвольную страницу. Код на языке JS.

Мы используем такой синтаксис:

let url = new URL(`${HOST}/search`)
url.searchParams.set("q", set.query)
url.searchParams.set("page", set.page)

В нём мы задаём значения параметров через url.searchParams.set

Значения set.query и set.page будут приходить из кода выше. В них будут заданы параметры: 
- set.query - поисковой запрос
- set.page - номер страницы пагинации

Значение переменной HOST будет инициализировано выше, и 
HOST = '""" + host_value + """'
тебе не нужно будет задавать значение для HOST в своём фрагменте кода.

При создании кода ориентируйся на значения из result:
- В поле info_from_page_parameter зафиксирована информация, какой параметр или участок URL отвечает за изменение страницы page.
- В поле info_from_search_query_parameter зафиксирована информация, какой параметр или участок URL отвечает за изменение поискового запроса search_query.

Чаще всего параметры поиска и текущей страницы задаются в searchParams, но иногда они задаются напрямую в строке URL, в таком случае нужно будет использовать синтаксис с ${}. Также, в исходном URL могут быть заданы дополнительные параметры, которые не влияют на запрос и текущую страницу, все эти параметры нужно будет сохранить.

Значение URL на 2 страницу поиска текущего сайта ты можешь посмотреть в поле url_for_2_page в result.

Примеры кода:

- Пример 1:
    Строка на поиск у сайта, на 2ю страницу поиска: 
    https://galen.bg/catalogsearch/result/index/?p=2&q=мл

    Фрагмент с формированием URL:
    let url = new URL(`${HOST}/catalogsearch/result/index/`)
    url.searchParams.set("q", set.query)
    url.searchParams.set("p", set.page)

- Пример 2:
    Строка на поиск у сайта, на 2ю страницу поиска: 
    https://stroytorg812.ru/content/search/?s=&q=Ванна&PAGEN_1=2

    Фрагмент с формированием URL:
    let url = new URL(`${HOST}/content/search/`)
    url.searchParams.set("s", "")
    url.searchParams.set("q", set.query)
    url.searchParams.set("PAGEN_1", set.page)

- Пример 3:
    Строка на поиск у сайта, на 2ю страницу поиска: 
    https://gidro-top.ru/search/Ванна/?page=2

    Фрагмент с формированием URL:
    let url = new URL(`${HOST}/search/${set.query}/`)
    url.searchParams.set('/?page', set.page);

Тебе нужно будет составить только необходимый фрагмент кода на JS, в котором будет формироваться URL с использованием этих параметров. Не добавляй дополнительных строчек в результат кода без необходимости. Помести его в result в поле result_code_url_builder.

Входные данные:

"""
    return main_task_all


""" 

{
    "start_page_url"
    "url_for_2_page"
    "info_from_page_parameter"
    "info_from_search_query_parameter"
    "url_for_second_search_query"
    "result_code_url_builder"
    "search_output_set_by_add_query"
}

"""











# Схема результата
main_result_schema = {
    "start_page_url": {
        "type": "string",
        "required": True,
        "description": "URL первой страницы, с которой мы начали."
    },
    "url_for_2_page": {
        "type": "string",
        "required": True,
        "description": "URL второй страницы, будет получена путём перехода на вторую страницу выдачи со страницы start_page_url."
    },
    "info_from_page_parameter": {
        "type": "string",
        "required": True,
        "description": "Информация о том, как задаётся параметр пагинации page в URL"
    },
    "info_from_search_query_parameter": {
        "type": "string",
        "required": True,
        "description": "Информация о том, как задаётся параметр поискового запроса в URL"
    },
    "url_for_second_search_query": {
        "type": "string",
        "required": True,
        "description": "URL страницы по другому поисковому запросу"
    },
    "result_code_url_builder": {
        "type": "string",
        "required": True,
        "description": "Сформированный фрагмент кода который позволяет задать произвольный запрос поиска и страницу пагинации"
    },
    "search_output_set_by_add_query": {
        "type": "string",
        "required": False,
        "description": "Примет значение true если товары загружаются доп. запросами, а не через URL (необязательное поле для заполнения)"
    }
}

# Шаблон результата, который агент заполняет в процессе работы
main_result_template = {
    "start_page_url": None,
    "url_for_2_page": None,
    "info_from_page_parameter": None,
    "info_from_search_query_parameter": None,
    "url_for_second_search_query": None,
    "result_code_url_builder": None,
    "search_output_set_by_add_query": None
}













input_data_test = {
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
    "last_page_number_displayed": "true"
}




# main_plan = {
#     "steps": [
#         {
#             "step_id": 1,
#             "goal": "Определить источник/селектор, из которого можно надежно извлечь максимальное количество страниц (числа в элементах пагинации; либо номер в элементе перехода на последнюю страницу; либо totalCount в тексте счетчика результатов). Зафиксировать выбранный тип структуры и селектор.",
#             "fills": [
#                 "type_struct_extract_max_page",
#                 "pagination_max_page_value_selector"
#             ]
#         },
#         {
#             "step_id": 2,
#             "goal": "Сформировать итоговый код, который возвращает числовое значение totalPages согласно выбранному типу структуры извлечения. Если выбран тип use_total_count — предварительно определить количество товаров на одной странице. Проверить работоспособность кода инструментом get_total_pages_on_current_page_cheerio_code и зафиксировать результат.",
#             "fills": [
#                 "builded_code_get_max_page_on_pagination"
#             ]
#         }
#     ]
# }

###### Добавить семантику!

def agent_step_4_state_3_URL_construct(input_data, search_request, selector_product_link, semantics, host_value):
    # Приводим input_data к строке
    if isinstance(input_data, str):
        input_data_str = input_data
    else:
        try:
            input_data_str = json.dumps(input_data, ensure_ascii=False, indent=4, default=str)
        except Exception:
            input_data_str = str(input_data)

    ###################### semantics
    ###################### Значение для переменной HOST - host_value

    task = (
        f"Сейчас в браузере Playwright открыта страница результатов товаров с поисковой выдачи по запросу '{search_request}'." +
        gen_main_task_all(selector_product_link, host_value) + 
        input_data_str + f"\n\n" +
        semantics)

    resulr_answer = orchestrate(
        task = task,
        max_steps = 40,
        result_schema = main_result_schema,
        result_template = main_result_template,
        # plan = main_plan,
        # step_by_step_running = False, # Разрешаем агенту работать автоматически
    ) 

    result_task = get_result()
    return result_task





# Проверка:

search_request_test = "инструмент"

semantics_test = {
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
    ]
}

host_value_test = "https://makitaclub.ru"

# Запускаю браузер с видимым окном
launch_browser(headless = False)

goto_url( 
    url = "https://makitaclub.ru/?s=%D0%B8%D0%BD%D1%81%D1%82%D1%80%D1%83%D0%BC%D0%B5%D0%BD%D1%82&post_type=product",
    wait_until = "load",
    timeout = 30_000
)

resilt = agent_step_4_state_3_URL_construct(input_data_test, search_request_test, ".products .product-card a.stretched-link[href*='/products/']", semantics_test, host_value_test)

print("resilt:")
print(resilt)
print("result_code_url_builder:")
print(resilt.get("result_code_url_builder"))













