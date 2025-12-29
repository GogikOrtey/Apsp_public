""" 
Обработка дигинетики и любых других кастомных запросов на PP 

Полностью генерит код PP
И использует инструменты его проверки в песочнице
А также инструменты работы с запросами в Playwright
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






def gen_MAIN_TASK(link, search_request, semantics):
    MAIN_TASK = """

Во входных данных (input_data) тебе даны селекторы на элементы этой страницы. Они понадобятся тебе в ходе выполнения проверок и решения задачи. В каждом массиве есть input_data по 3 селектора, из них первый - это самый стабильный и предпочтительный, по умолчанию используй его. Но если вдруг первый окажется по каким-то причинам неподходящим или нерабочим, то есть ещё два запасных селектора, которые указывают также на этот элемент.

ЗАДАЧА:

Нужно проверить, выполняется ли загрузка товаров дополнительным запросами. 

АЛГОРИТМ:

———————————————————————— Шаг алгоритма 1: Проверка, подгружаются ли данные доп. запросами

1. Перейди на страницу поиска для первого запроса: """ + link + """

2. Посчитай количество результатов по селектору, указанному в product_link_selectors. Запиши количество в result в поле count_of_products_first.

3. Пролистни страницу в самый низ, используя инструмент scroll_to_bottom

4. Заново посчитай количество результатов по селектору товара product_link_selectors. 
Если это количество например увеличилось минимум на 5-10 элементов - значит на странице выполняется подгрузка результатов через дополнительные запросы. Зафиксируй это в result: в поле is_site_used_add_request = true. 

Если количество результатов по селектору товара не изменилось, то запиши в поле is_site_used_add_request значение false, и заверши задание через DONE.

———————————————————————— Шаг алгоритма 2: Получение типа запроса, которым выполняется загрузка результатов (diginetica или custom)

Если на странице выполняется подгрузка результатов через дополнительные запросы, и в result поле is_site_used_add_request = true, значит нужно определить тип, через что выполняется загрузка данных о товаре.

- Получи полные элементы товаров используя инструмент parse_product_blocks_on_current_page. Он вернёт тебе структурные блоки 2го и 3го по счёту товаров на странице, достаточно передать ему селектор, который ты сейчас проверяешь, из поля product_link_selectors. Этот инструмент ожидает именно селектор на ссылку товара, и сам пройдётся по дереву DOM и извлечёт полные блоки товаров. Иногда инструмент parse_product_blocks_on_current_page может отработать некорректно, тогда используй универсальную функцию get_html_frame_on_current_page. В ней можно расширить окно контекста при необходимости. Также помни, что селектор product_link_selectors указывает не на весь блок товара на странице, а только на ссылку на этот товар.

- Извлеки название и цену 2го товара. Сохрани их в result в поля name_second_product и price_second_product.

- Используя инструмент поиска пои истории запросов на этой странице в Playwright _________________________
выполни поиск по названию товара (или по части названия)
    - Если совпадения есть, и обращение идёт к https://sort.diginetica.net то зафиксируй в result в поле search_type значение "diginetica".
    - Если обращение идёт не к https://sort.diginetica.net, и в результатах с инструмента ________________ по поиску по названию есть результаты, но в них нет того, который обращался бы к diginetica, то зафиксируй в result в поле search_type значение "custom".
    - Если поиск по истории запросов по названию второго товара не дал результатов, то повтори поиск с ценой (значение записано в result в поле price_second_product)
        - Если и он не дал результатов, то попробуй произвести поиск по названию и цене последнего товара, которых находится селектором product_link_selectors (используя инструмент get_html_frame_on_current_page и указав в селекторе что бы он вернул последний элемент).
        - Русские буквы могут кодироваться, если нет результатов, то попробуй искать английсике слова из названий, или другие части (например с числами). Также помни, что на странице цена может быть например с пробелом, отделяющим тысячи, и запятой, напримре отделяющей копейки, а в api оно может приходить без пробелов и точек/запятых
        - Если поиск по названию и цене товара не дал результатов в истории запросов, то верни FAILED с текстом, что не удалось обнаружить как товары загружаются на страницу

Переходи на следующий шаг алгоритма, когда значение search_type будет зафиксировано.

———————————————————————— Шаг алгоритма 3: Написание кода процедуры получения результатов поиска

Здесь тебе нужно будет написать и проверить код процедуры, на вход которой будут подаваться значения поискового запроса (set.query). В set.query будет содержаться строка поиска (например "Кусачки" или "Плитка").

ПРИМЕРЫ для search_type = "diginetica":

async parsePage(set: SetType) {
    const url = new URL("https://sort.diginetica.net/search")
    const pageSize = 500;
    const urlParam = {
        st: set.query,
        apiKey: "TW6F7714EE", // CHANGE_HERE: В большинстве случаев меняется только этот параметр
        strategy: "advanced_xname,zero_queries",
        fullData: true,
        withCorrection: true,
        withFacets: true,
        treeFacets: true,
        regionId: global,
        useCategoryPrediction: false,
        size: pageSize,
        offset: set.offset,
        showUnavailable: true,
        unavailableMultiplier: 0.2,
        preview: false,
        withSku: false,
        sort: "DEFAULT",
    };

    const data = await this.makeRequest(url.href, set.region, urlParam)
    const json = JSON.parse(data);

    if (json.totalHits == 0) {
        this.logger.put(`По запросу ${set.query} ничего не найдено`)
        throw new NotFoundError()
    }
    if (set.offset === 0) {
        const totalPages = Math.ceil(json.totalHits / pageSize);
        for (let shift = 1; shift <= Math.min(totalPages, +this.conf.pagesCount); shift++) {
            this.query.add(({ ...set, query: set.query, type: "page", offset: shift * pageSize, lvl: 1 }));
        }
    }
    json.products.slice(0, +this.conf.itemsCount).forEach(product => {
        let link = `https://apelsin.ru${product?.link_url}` // CHANGE_HERE: Вот тут надо будет подставить верный хост текущего сайта
        this.query.add({ ...set, query: link, type: "card", lvl: 1 })
    })
}

Пример 2:

async parsePage(set) {
    let url = "https://sort.diginetica.net/search"
    const pageSize = 500;
    const urlParam = {
        st: set.query,
        apiKey: '28429CHU1K',
        strategy: "advanced,zero_queries",
        fullData: true,
        withCorrection: true,
        withFacets: true,
        treeFacets: true,
        regionId: global,
        useCategoryPrediction: false,
        size: pageSize,
        offset: set.offset,
        showUnavailable: true,
        unavailableMultiplier: 0.2,
        preview: false,
        withSku: false,
        sort: "DEFAULT",
    };
    const data = await this.makeRequest(url, urlParam)
    const json = JSON.parse(data);

    let items = [];
    if (json.totalHits > 0) {
        if (set.offset === 0) {
            const totalPages = Math.ceil(json.totalHits / pageSize);
            for (let shift = 1; shift <= Math.min(totalPages, +this.conf.pagescount); shift++) {
                this.query.add(({...set, query: set.query, type: "page", offset: shift * pageSize, lvl: 1}));
            }
        }
        json.products.slice(0, +this.conf.itemscount).forEach(product => {
            let link = 'https://www.antica.su' + product.link_url
            this.query.add({...set, query: link, type: "card", lvl: 1})
        })
    } else {
        this.logger.put(`По запросу ${set.query} ничего не найдено`)
        throw new NotFoundError()
    }
    return items;
}

Пример 3:

async parsePage(set) {
    let url = "https://sort.diginetica.net/search"
    const pageSize = 500;
    const urlParam = {
        st: set.query,
        apiKey: "NY2D9562L7",
        strategy: "advanced_xname,zero_queries",
        fullData: true,
        withCorrection: true,
        withFacets: true,
        treeFacets: true,
        regionId: global,
        useCategoryPrediction: false,
        size: pageSize,
        offset: set.offset,
        showUnavailable: true,
        unavailableMultiplier: 0.2,
        preview: false,
        withSku: false,
        sort: "DEFAULT",
    };
    const data = await this.makeRequest(url, urlParam)
    const json = JSON.parse(data);

    let items = [];
    if (json.totalHits == 0){
        this.logger.put(`По запросу ${set.query} ничего не найдено`)
        throw new NotFoundError()
    }
    if (set.offset === 0) {
        const totalPages = Math.ceil(json.totalHits / pageSize);
        for (let shift = 1; shift <= Math.min(totalPages, +this.conf.pagesCount); shift++) {
            this.query.add(({...set, query: set.query, type: "page", offset: shift * pageSize, lvl: 1}));
        }
    }
    json.products.slice(0, +this.conf.itemscount).forEach(product => {
        let link = "https://elemis.ru" + product?.link_url
        this.query.add({...set, query: link, type: "card", lvl: 1})
    })
    return items;
}

Как ты видишь, структура всегда практически одинаковая.
Нужно будет подставить apiKey
И верный host, где мы задаём let link = ... 

ВАЖНО: НЕ меняй синугатуру метода, структуру и названия переменных. Код должен получиться похожим на шаблон, и изменения должны затронуть только некоторые элементы.

Подобранные запросы можно проверить, используя инструмент ________

Запиши полученный код процедуры parsePage в result в поле result_code

———————————————————————— Если не diginetica:

Если is_site_used_add_request = true И search_type = "custom", то пример с diginetica уже не подойдёт. В таком случае тебе нужно будет самостоятельно проанализировать запросы страницы, и выделить тот запрос, в ответе которого приходят результаты поиска, включая ссылки на товары. 

Далее, тебе нужно будет составить валидный код, в котором будет отправляться этот запрос, с нужными рабочими параметрами, и параметром, которым задаётся поисковый запрос = set.query (это важно). Записать его также в result в поле result_code, проверить, и при необходимости изменить, что бы он работал корректно - при проверке возвращал первые 10 ссылок на товары с указанного запроса поиска.

Если search_type = custom, код должен тоже реализовывать интерфейс parsePage(set).

Если что, в search_input_selectors указан селектор поля ввода. При необходимости, ты сможешь выполнить поиск на этом сайте по другому запросу из семантики.

———————————————————————— Шаг алгоритма 4: Проверка написанного кода

Далее тебе нужно будет запустить код, записанный в result в поле result_code, используя инструмент ____________.

Т.е. передай в него код ровно из result_code. Также, нужно будет передать запрос на поиск, во втором аргументе. Выполни две проверки - сначала с тем запросом который сейчас открыт на странице Playwright: '""" + search_request + """', а затем следующим запросом из семантики: """ + semantics + """

Этот инструмент вернёт тебе первые 10 ссылок на товары. Убедись что они валидные (используя инструмент check_url_status)

Если код не работает, падает с ошибкой, или возвращает не рабочие ссылки, то нужно будет его изменить, и обновить значение поля result_code в result.

Когда рабочий код будет написан и проверен - запиши в result в поле check_code_ok значение true. Важно: не записывай в это поле значение false, если при проверке код окажется не рабочим. Это поле ожидает только записи значения true.


Входные данные (input_data):

"""
    return MAIN_TASK






"""
Схема результата:

{
    "count_of_products_first": number
    "is_site_used_add_request": boolean
    "name_second_product": string
    "price_second_product": string
    "search_type": "diginetica" | "custom"
    "result_code": string
    "check_code_ok": boolean
}

"""





























   
   










# # Схема результата
# main_result_schema = {
#     "start_page_url": {
#         "type": "string",
#         "required": True,
#         "description": "URL первой страницы, с которой мы начали."
#     },
#     "url_for_2_page": {
#         "type": "string",
#         "required": True,
#         "description": "URL второй страницы, будет получена путём перехода на вторую страницу выдачи со страницы start_page_url."
#     },
#     "info_from_page_parameter": {
#         "type": "string",
#         "required": True,
#         "description": "Информация о том, как задаётся параметр пагинации page в URL"
#     },
#     "info_from_search_query_parameter": {
#         "type": "string",
#         "required": True,
#         "description": "Информация о том, как задаётся параметр поискового запроса в URL"
#     },
#     "url_for_second_search_query": {
#         "type": "string",
#         "required": True,
#         "description": "URL страницы по другому поисковому запросу"
#     },
#     "result_code_url_builder": {
#         "type": "string",
#         "required": True,
#         "description": "Сформированный фрагмент кода который позволяет задать произвольный запрос поиска и страницу пагинации"
#     },
#     "search_output_set_by_add_query": {
#         "type": "boolean",
#         "required": False,
#         "description": "Примет значение true если товары загружаются доп. запросами, а не через URL (необязательное поле для заполнения)"
#     }
# }

# # Шаблон результата, который агент заполняет в процессе работы
# main_result_template = {
#     "start_page_url": None,
#     "url_for_2_page": None,
#     "info_from_page_parameter": None,
#     "info_from_search_query_parameter": None,
#     "url_for_second_search_query": None,
#     "result_code_url_builder": None,
#     "search_output_set_by_add_query": None
# }



# main_plan = {
#     "steps": [
#         {
#             "step_id": 1,
#             "goal": "Зафиксировать URL первой страницы выдачи (1 шаг алгоритма)",
#             "fills": [
#                 "start_page_url"
#             ]
#         },
#         {
#             "step_id": 2,
#             "goal": "Перейти на 2-ю страницу через пагинацию и зафиксировать новый URL (1 шаг алгоритма)",
#             "fills": [
#                 "url_for_2_page",
#                 "search_output_set_by_add_query"
#             ]
#         },
#         {
#             "step_id": 3,
#             "goal": "По разнице start_page_url и url_for_2_page определить параметр пагинации и описать его (2 шаг алгоритма)",
#             "fills": [
#                 "info_from_page_parameter"
#             ]
#         },
#         {
#             "step_id": 4,
#             "goal": "Выполнить поиск по другому запросу и зафиксировать URL новой страницы (3 шаг алгоритма)",
#             "fills": [
#                 "url_for_second_search_query"
#             ]
#         },
#         {
#             "step_id": 5,
#             "goal": "По разнице start_page_url и url_for_second_search_query определить параметр поискового запроса и описать его (3 шаг алгоритма)",
#             "fills": [
#                 "info_from_search_query_parameter"
#             ]
#         },
#         {
#             "step_id": 6,
#             "goal": "Сформировать JS-код генерации URL на основе info_from_page_parameter и info_from_search_query_parameter (4 шаг алгоритма)",
#             "fills": [
#                 "result_code_url_builder"
#             ]
#         }
#     ]
# }






def agent_step_6_2_diginetica_and_custom_req_on_PP(input_data, search_request, semantics, link):
    # Приводим input_data к строке
    if isinstance(input_data, str):
        input_data_str = input_data
    else:
        try:
            input_data_str = json.dumps(input_data, ensure_ascii=False, indent=4, default=str)
        except Exception:
            input_data_str = str(input_data)

    # Приводим input_data к строке
    if isinstance(semantics, str):
        semantics_str = semantics
    else:
        try:
            semantics_str = json.dumps(semantics, ensure_ascii=False, indent=4, default=str)
        except Exception:
            semantics_str = str(semantics)

    task = (
        f"Сейчас в браузере Playwright открыта страница результатов товаров с поисковой выдачи по запросу '{search_request}'." +
        gen_MAIN_TASK(link, search_request, semantics_str) + 
        input_data_str)

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





#  Проверка:

if __name__ == "__main__":     
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

    # Из шага 2 из поля second_html:
    link = "https://makitaclub.ru/?s=%D0%B8%D0%BD%D1%81%D1%82%D1%80%D1%83%D0%BC%D0%B5%D0%BD%D1%82&post_type=product"


    # Запускаю браузер с видимым окном
    launch_browser(headless = False)

    goto_url( 
        url = "https://makitaclub.ru/?s=%D0%B8%D0%BD%D1%81%D1%82%D1%80%D1%83%D0%BC%D0%B5%D0%BD%D1%82&post_type=product",
        wait_until = "load",
        timeout = 30_000
    )

    # Поля похожи на те, что есть в 6
    resilt = agent_step_6_2_diginetica_and_custom_req_on_PP(input_data_test, search_request_test, semantics_test, link)

    print("resilt:")
    print(resilt)
    print(f"\result_code:")
    print(resilt.get("result_code"))



