"""
Этот скрипт получает на вход фрагменты кода parse_page_code, parse_card_code и make_request_code, и формирует их в итоговый код
"""

from pathlib import Path
import sys
from typing import Any
import textwrap

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Подключение всех библиотек и функций
from import_all_libraries import * 

from makeRequest_gen import * 





# region Главный шаблон

template_main_code = Template("""
import { getDefaultConf, defaultEditableConf, defaultOpts, getCacher } from "../Base-Custom/Constants";
import { AsyncHTTPXRequestOptsCustom, defaultConf, editableConf, Item } from "../Base-Custom/Types";
import { InvalidLinkError, NotFoundError } from "../Base-Custom/Errors";
import { JS_Base_Custom } from "../Base-Custom/Base-Custom";
import { getTimestamp } from "../Base-Custom/Utils";
import { SetType, tools } from "a-parser-types";
import { Cacher } from "../Base-Custom/Cache";
import {
    toArray, isBadLink,
    $field_val
} from "../Base-Custom/Fields"
import * as cheerio from "cheerio";

//#region Кастомные типы данных
type ResultItem = Item<typeof fields>

//#region Константы
const fields = {
    $field_val
}

const HOST = "$host_val"

export class $parser_name_val extends JS_Base_Custom {
    $default_conf

    static editableConf: editableConf = [
        ...defaultEditableConf
    ];

    //#region Точка входа
    $parse_entry_point_code

    //#region Парсинг поиска
    $parse_page_code

    //#region Парсинг товара
    $parse_card_code

    //#region Выполнение запроса
    $make_request_code
}

$subtitle_from_code
""")

# region Функции заполнения

# Генерирует верхнюю процедуру, которая называется parse и имеет описание "Точка входа"
def parse_entry_point_gen():
    # Если parsePage возвращает результаты, которые надо записать в Items
    is_parse_page_mode_returned_results = """
                        let items = await this.parsePage(set);
                        items.forEach(item => results.items.addElement(item));
    """

    # И если не возвращает (наиболее чатый случай)
    is_parse_page_mode_no_returned_results = """
                        await this.parsePage(set);
    """

    template_parse_entry_point_code = Template("""
    async parse(set: SetType, results: { [key: string]: any }) {
        if (!set.type || set.type === "none") set.type = "page";
        if (!set.region || set.region === "none") set.region = "";
        try {
            switch (set.type) {
                case "page": {
                    if (!set.page || set.page === "none") set.page = 1;
                    $return_results_page_mode
                    results.success = 1;
                    break;
                }
                case "card": {
                    const cacher = getCacher<ResultItem>(this, set)
                    let items = cacher.cache || await this.parseCard(set, cacher);
                    items.forEach(item => results.items.addElement(item));
                    results.success = 1;
                    break;
                }
                default:
                    this.logger.put("Указан неверный тип сбора")
                    results.success = 0;
            }
        } catch (e: any) {
            if (e instanceof NotFoundError || e instanceof InvalidLinkError) {
                this.logger.put(e.message);
                results.isBadLink = 1;
                results.success = 1;
            } else {
                this.logger.put(`$${e.name} >> $${e.message}   $${set.query}  type - $${set.type} page $${set.page} }`);
                results.success = 0;
            }
        }
        return results;
    }
    """)

    result = template_parse_entry_point_code.substitute(
        return_results_page_mode = is_parse_page_mode_no_returned_results.strip()
    ).strip()

    return result


def set_defaultConf():
    template_default_conf = Template("""
        static defaultConf: defaultConf = {
            ...getDefaultConf(toArray(fields), "ζ", [isBadLink]),
            parsecodes: { 200: 1, 404: 1 },
            proxyChecker: "$proxy_checker_val",
            requestdelay: "3,5",
            engine: "$engine_val",
            mode: "$mode_val",
        };
    """)

    #TODO Подставлять сюда параметры, которые будут рассчитаны в makeRequest_gen
    result = template_default_conf.substitute(
        # proxy_checker_val = "tor.proxy.ru",
        proxy_checker_val = "fineproxy.org",
        engine_val = "a-parser",
        mode_val = "normal",
    )
    
    return result.strip()

def get_cuurent_subtitle():
    template_subtitle = Template("""
// Код сгенерирован Auto-gen parsers v$current_apsp_version_val
// Дата: $current_date
// © BrandPol
""")

    result = template_subtitle.substitute(
        current_apsp_version_val = current_apsp_version,
        current_date = get_current_date()        
    )
    
    return result.strip()

# Собирает название парсера из хоста
def set_parser_name(host):
    # Как нужно чистим домен
    parser_file_name = host.split("://")[1].split("/")[0]
    parser_file_name = parser_file_name.replace("www.", "")
    parser_file_name = parser_file_name.replace(".", "").replace("-", "")
    # TODO регионы потом удалять, но это сильно позже

    base_name_part = "JS_Base_" + parser_file_name
    print("Имя парсера: " + base_name_part)

    return base_name_part





# region Запись в файл

# Используем корень проекта (на уровень выше new_program) для вывода
RESULT_OUTPUT_DIR = ROOT_DIR / "result_code_gen" / "result"
RESULT_CODE_TS_PATH = RESULT_OUTPUT_DIR / "result_code.ts"

def result_file_JS(result_code):
    RESULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_CODE_TS_PATH.write_text(result_code, encoding="utf-8")
    print("📘 result_code успешно записан в result_code.ts")







# region build_final_code

def build_final_code(host, parse_card_code_fragment, parse_page_code_fragment, fields_descr):
    # Добавляем 4 пробела в начало каждой строки
    parse_page_code_fragment = textwrap.indent(parse_page_code_fragment, '    ')

    make_request_code_value = simple_makeRequest()    
    parse_entry_point_code_value = parse_entry_point_gen()
    default_conf_value = set_defaultConf()
    parser_name = set_parser_name(host)

    result = template_main_code.substitute(
        make_request_code = make_request_code_value,
        parse_card_code = parse_card_code_fragment,
        parse_page_code = parse_page_code_fragment,
        parse_entry_point_code = parse_entry_point_code_value,
        field_val = fields_descr,
        host_val = host,
        default_conf = default_conf_value,
        subtitle_from_code = get_cuurent_subtitle(),
        parser_name_val = parser_name
    ).strip()
    
    print(f"\n📗 Результат:\n")
    print(result)
    result_file_JS(result) # Записываем результат в файл

    return result









# region Проверка

host_test = "https://makitaclub.ru"

parse_card_code_fragment_test = """
    async parseCard(set: SetType, cacher: Cacher<ResultItem[]>) {
        let items: ResultItem[] = []

        /* 🟨 Заглушка для parseCard 🟨 */

        const data = await this.makeRequest(set.query);
        const $ = cheerio.load(data);

        const timestamp = getTimestamp()

        const item: ResultItem = {
            timestamp
        }
        items.push(item);

        cacher.cache = items
        return items;
    }
"""

parse_page_code_fragment = """
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

    let products = $('.products .product-card a.stretched-link[href*="/products/"]')      
    if (products.length == 0) {
        this.logger.put(`По запросу ${set.query} ничего не найдено`)
        throw new NotFoundError()
    }
    products.slice(0, +this.conf.itemsCount).each((i, product) => {
        let link = $(product)?.attr('href')  
        this.query.add({ ...set, query: link, type: "card", lvl: 1 })
    })
}
"""
if __name__ == "__main__":    
    result_final_code = build_final_code(host_test, parse_card_code_fragment_test, parse_page_code_fragment)

# print("result_final_code:")
# print(result_final_code)