"""
Этот скрипт получает на вход фрагменты кода parse_page_code, parse_card_code и make_request_code, и формирует их в итоговый код
"""

from pathlib import Path
import sys
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Подключение всех библиотек и функций
from import_all_libraries import * 

from makeRequest_gen import * 






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
        proxy_checker_val = "tor.proxy.ru",
        engine_val = "a-parser",
        mode_val = "normal",
    )
    
    return result.strip()

def get_cuurent_subtitle():
    template_subtitle = Template("""
// Код сгенерирован Автогенератором парсеров v$current_apsp_version_val
// Дата: $current_date
// © BrandPol
""")

    result = template_subtitle.substitute(
        current_apsp_version_val = current_apsp_version,
        current_date = get_current_date()        
    )
    
    return result.strip()

# Собирает название парсера из хоста
def set_parser_name():
    host = data_input_table["host"]
    # Как нужно чистим домен
    parser_file_name = host.split("://")[1].split("/")[0]
    parser_file_name = parser_file_name.replace("www.", "")
    parser_file_name = parser_file_name.replace(".", "").replace("-", "")
    # TODO регионы потом удалять, но это сильно позже

    base_name_part = "JS_Base_" + parser_file_name
    print("Имя парсера: " + base_name_part)

    return base_name_part


def build_final_code(host, parse_card_code_fragment, parse_page_code_fragment):
    make_request_code_value = simple_makeRequest()    
    parse_entry_point_code_value = parse_entry_point_gen()
    default_conf_value = set_defaultConf()
    parser_name = set_parser_name()

    result = template_main_code.substitute(
        make_request_code = make_request_code_value,
        parse_card_code = parse_card_code_fragment,
        parse_page_code = parse_page_code_fragment,
        parse_entry_point_code = parse_entry_point_code_value,
        # field_val = field,
        field_val = "🟨 Заглушка 🟨",
        host_val = host,
        default_conf = default_conf_value,
        subtitle_from_code = get_cuurent_subtitle(),
        parser_name_val = parser_name
    ).strip()
    
    print(f"\n📗 Результат:\n")
    print(result)
    return result


