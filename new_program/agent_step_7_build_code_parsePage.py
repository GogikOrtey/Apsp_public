"""
Собирает полный код parsePage по поступившим фрагментам
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
import re
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from new_program.html_toolkit import *

# Подключение всех библиотек и функций
from import_all_libraries import *
from ChatGPT.OpenAI_ChatGPT import send_message_to_ChatGPT




"""




"""





# region Пропмты

SYSTEM_PROMPT = """
Ты — детерминированный трансформер исходного кода. Ты не создаёшь, не исправляешь и не интерпретируешь код — ты только выполняешь точную подстановку фрагментов по правилам и возвращаешь результат без каких-либо пояснений.
"""

MAIN_PROMPT = """

ЗАДАЧА:

В input_data тебе даны 3 фрагмента кода. Их нужно будет встроить в шаблон кода.
Код написан на JS.
При вставке фрагментов соблюдай вложенность (отступы), соответствующую контексту места вставки в шаблоне.

————————————————————————

ШАБЛОН КОДА:

async parsePage(set: SetType) {
    /* INSERT_HERE URL_BLOCK */

    const data = await this.makeRequest(url.href)
    const $ = cheerio.load(data)

    if (set.page === 1) {
        /* INSERT_HERE GET_MAX_PAGE_BLOCK */
        this.debugger.put(`totalPages = ${totalPages}`)
        for (let page = 2; page <= Math.min(totalPages, +this.conf.pagesCount); page++) {
            this.query.add({ ...set, query: set.query, type: "page", page: page, lvl: 1 });
        }
    }

    let items: ResultItem[] = [];
    /* INSERT_HERE GET_PRODUCT_LINK_LINES_CODE - ONLY GET PRODUCTS OBGECTS */
    if (products.length == 0) {
        this.logger.put(`По запросу ${set.query} ничего не найдено`)
        throw new NotFoundError()
    }
    products.slice(0, +this.conf.itemsCount).each((i, product) => {
        /* INSERT_HERE GET_PRODUCT_LINK_LINES_CODE - ONLY GET LINK PRODUCT */
        this.query.add({ ...set, query: link, type: "card", lvl: 1 })
    })
    return items;
}

————————————————————————

ИНСТРУКЦИЯ: 

В шаблоне кода ты видишь 4 места для вставки фрагментов. Они обозначены комментариями /* INSERT_HERE ... */

1. Вместо комментария /* INSERT_HERE URL_BLOCK */ вставь блок кода из поля URL_BLOCK во входных данных (input_data) - целиком
2. Вместо комментария /* INSERT_HERE GET_MAX_PAGE_BLOCK */ вставь блок кода из поля GET_MAX_PAGE_BLOCK во входных данных (input_data) - целиком

3. Далее важно: В поле GET_PRODUCT_LINK_LINES_CODE находится блок кода, но его не нужно всталять целиком. Из него нужно извлечь:
    3.1 Код, который задаёт переменную let products = ... . Чаще всего это одна строка. Помести её вместо комментария /* INSERT_HERE GET_PRODUCT_LINK_LINES_CODE - ONLY GET PRODUCTS OBGECTS */. Игнорируй код задания хоста в этом фрагменте (let HOST = ...), его не нужно сюда добавлять.

    Далее будет идти строчка похожая на "let product = products?.eq(0);". её также нужно игнорировать

    3.2 Фрагмент кода, который задаёт ссылку (let link =) - нужно поместить вместо комментария  /* INSERT_HERE GET_PRODUCT_LINK_LINES_CODE - ONLY GET LINK PRODUCT */. Нужно брать всю строку целиком, где происходит присваивание link = ..., не модифицируя её содержимое.

    Строку "console.log('link = ' + link)" нужно игнорировать и не добавлять в результат.

————————————————————————

СТРОГИЕ ПРАВИЛА (ОБЯЗАТЕЛЬНО К ВЫПОЛНЕНИЮ):

1. Ты работаешь как ДЕТЕРМИНИРОВАННЫЙ ТРАНСФОРМЕР КОДА, а не как помощник.
   Твоя задача — только вставить указанные фрагменты в указанные места.

2. Запрещено:
   - изменять любой символ, пробел, перевод строки или форматирование в исходном шаблоне кода
   - переименовывать переменные
   - менять кавычки, отступы, точки с запятой
   - переписывать строки кода в исходном шаблоне
   - оптимизировать, исправлять или "улучшать" код
   - удалять или добавлять любые строки, кроме тех, которые явно указаны как INSERT_HERE

3. Разрешено ТОЛЬКО:
   - удалить комментарии вида `/* INSERT_HERE ... */`
   - и вставить на их место соответствующие фрагменты из input_data по правилам инструкции

4. Весь остальной код шаблона должен быть возвращён БАЙТ-В-БАЙТ идентичным исходному шаблону.

5. Если какой-либо фрагмент из input_data не может быть однозначно сопоставлен правилам (например, не найден `let products =` или `let link =`), ты обязан:
   - не генерировать никакой код
   - а вывести слово: ERROR

6. Переменные `products` и `link` обязаны существовать в результирующем коде и быть объявлены через `let`.

7. Переменная `HOST` уже существует во внешнем коде.
   Запрещено объявлять, переопределять или модифицировать `HOST` внутри результата.
   Разрешено использовать HOST в выражениях, но запрещено объявлять или изменять его.

————————————————————————

ФОРМАТ ВЫВОДА (КРИТИЧЕСКИ ВАЖНО):

1. В ответе должен быть выведен ТОЛЬКО финальный JS-код.
2. Запрещено выводить:
   - пояснения
   - комментарии
   - заголовки
   - markdown
   - ``` или ```js
   - любые пояснительные тексты
   - варианты решений
   - сообщения вроде "готово", "вот результат" и т.п.

3. Ответ должен начинаться ПРЯМО с первой строки кода и заканчиваться последней строкой кода.

4. Любой текст вне кода считается ошибкой.

————————————————————————

ВХОДНЫЕ ДАННЫЕ (input_data):

"""















# Примеры: 

""" 

Входные данные (input_data):

URL_BLOCK:
let url = set.page && +set.page > 1 ? new URL(`${HOST}/page/${set.page}/`) : new URL(`${HOST}/`)
url.searchParams.set('s', set.query)
url.searchParams.set('post_type', 'product') 

GET_MAX_PAGE_BLOCK:
let totalPages = Math.max(...$("nav.woocommerce-pagination .page-numbers").get().map(item 
=> +$(item).text().trim()).filter(Boolean))  

GET_PRODUCT_LINK_LINES_CODE:
let products = $('.products .product-card a.stretched-link[href*="/products/"]')
let product = products?.eq(0)
let link = $(product)?.attr('href')
console.log('link = ' + link)


————————————————————————

URL_BLOCK:
let url = new URL(`${HOST}/catalog/`)        
url.searchParams.set("q", set.query)
url.searchParams.set("s", "Найти")
url.searchParams.set("PAGEN_2", set.page)    

GET_MAX_PAGE_BLOCK:
let totalPages = Math.max(...$("nav#pagination a").get().map(item => +$(item).text().trim()).filter(Boolean))

GET_PRODUCT_LINK_LINES_CODE:
let HOST = "https://makitatrading.ru";       
let products = $('.catalog.catalogCards .itemCard[itemtype="http://schema.org/Product"] a.item_title[href^="/catalog/product/"]');     
let product = products?.eq(0);
let link = HOST + $(product)?.attr('href');  
console.log('link = ' + link);



"""


















""" 

async parsePage(set: SetType) {
    let url = new URL(`${HOST}/search`)
    url.searchParams.set("q", set.query)
    url.searchParams.set("page", set.page)

    const data = await this.makeRequest(url.href)
    const $ = cheerio.load(data)

    if (set.page === 1) {
        let totalPages = Math.max(...$("").get().map(item => +$(item).text().trim()).filter(Boolean))
        this.debugger.put(`totalPages = ${totalPages}`)
        for (let page = 2; page <= Math.min(totalPages, +this.conf.pagesCount); page++) {
            this.query.add({ ...set, query: set.query, type: "page", page: page, lvl: 1 });
        }
    }

    let items: ResultItem[] = [];
    let products = $("")
    if (products.length == 0) {
        this.logger.put(`По запросу ${set.query} ничего не найдено`)
        throw new NotFoundError()
    }
    products.slice(0, +this.conf.itemsCount).each((i, product) => {
        let link = $(product)?.attr("href")
        this.query.add({ ...set, query: link, type: "card", lvl: 1 })
    })
    return items;
}

"""















# region Внешняя функция

def agent_step_7_build_code_parsePage(input_code_fragments):
    print("Запускаем agent_step_7_build_code_parsePage")

    def _format_code_fragments_to_sections(fragments) -> str:
        """ 
        Распаковывает код из JSON построчно, и формирует красиво и более читаемо
        """
        if fragments is None:
            return ""
        if not isinstance(fragments, dict):
            return str(fragments)

        sections = []

        for block_name, code in fragments.items():
            title = str(block_name).strip()
            code_str = "" if code is None else str(code)

            # Выполняем переводы строк
            code_str = code_str.replace("\r\n", "\n").replace("\r", "\n").strip("\n")

            sections.append(f"{title}:\n{code_str}")

        return "\n\n".join(sections).strip() + "\n"

    input_code_fragments_str = _format_code_fragments_to_sections(input_code_fragments)
    print(input_code_fragments_str)

    request_from_LLM = (
        MAIN_PROMPT
        + input_code_fragments_str
    )
    result_request = send_message_to_ChatGPT(request_from_LLM, temperature = 0.1, system_prompt = SYSTEM_PROMPT)

    # send_message_to_ChatGPT возвращает ChatGPTResult; достаём текст ответа
    result_text = result_request.answer if hasattr(result_request, "answer") else str(result_request)

    # Удаляем обертку ``` ``` если модель вернула JSON внутри Markdown
    if "```" in result_text:
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", result_text, re.DOTALL)
        if match:
            result_text = match.group(1)

    return result_text







# # Для тестов:

# input_code_fragments = {
#     "URL_BLOCK": "let url = set.page && +set.page > 1 ? new URL(`${HOST}/page/${set.page}/`) : new URL(`${HOST}/`)\nurl.searchParams.set('s', set.query)\nurl.searchParams.set('post_type', 'product')",
#     "GET_MAX_PAGE_BLOCK": "let totalPages = Math.max(...$(\"nav.woocommerce-pagination .page-numbers\").get().map(item => +$(item).text().trim()).filter(Boolean))",
#     "GET_PRODUCT_LINK_LINES_CODE": "let products = $('.products .product-card a.stretched-link[href*=\"/products/\"]')\nlet product = products?.eq(0)\nlet link = $(product)?.attr('href')\nconsole.log('link = ' + link)"       
# }

# # input_code_fragments = {
# #     "URL_BLOCK": "let url = new URL(`${HOST}/catalog/`)\nurl.searchParams.set(\"q\", set.query)\nurl.searchParams.set(\"s\", \"Найти\")\nurl.searchParams.set(\"PAGEN_2\", set.page)",
# #     "GET_MAX_PAGE_BLOCK": "let totalPages = Math.max(...$(\"nav#pagination a\").get().map(item => +$(item).text().trim()).filter(Boolean))",
# #     "GET_PRODUCT_LINK_LINES_CODE": "let HOST = \"https://makitatrading.ru\";\nlet products = $('.catalog.catalogCards .itemCard[itemtype=\"http://schema.org/Product\"] a.item_title[href^=\"/catalog/product/\"]');\nlet product = products?.eq(0);\nlet link = HOST + $(product)?.attr('href');\nconsole.log('link = ' + link);"
# # }


# result_agent_step_7_build_code_parsePage = agent_step_7_build_code_parsePage(input_code_fragments)
# print(f"\nresult_agent_step_7_build_code_parsePage:\n")
# print(result_agent_step_7_build_code_parsePage)