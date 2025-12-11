### В этом скрипте собираются все фрагменты кода

# Вынесенные отдельно функции
from addedFunc import *
from gen_data_input_table import data_input_table # Входные данные
from extracting_selector_from_html import * 

# Подключение всех библиотек
from import_all_libraries import * 

# Подключение модулей генерации

from makeRequest_gen import * 
from parseCard_gen import * 
from parsePage_gen import * 
from extraction_selectors_main import * 


this_module_title = """


--------------------------------------------------------------------------------------------------

                                        GLOBAL CODE GEN

--------------------------------------------------------------------------------------------------

"""

final_title = """


--------------------------------------------------------------------------------------------------

                                    FINAL RESULT PARSER CODE

--------------------------------------------------------------------------------------------------

"""



#region Собираю поля
# Собирает поля в строку из тех что есть в нашем сборе, и сортирует их по шаблону
def extract_fields():
    # Это пускай будет пример сортировки полей
    ### TODO Потом ещё посмотреть это место
    order_string = "name, stock, link, price, oldprice, article, brand, a2, imageLink, timestamp"

    # Разбиваем строку порядка на список полей, убираем пробелы
    field_order = [field.strip() for field in order_string.split(",")]

    # Собираю поля для объекта item: исключаю триггеры, добавляю stock, timestamp
    other_keys = [k for k in data_input_table["links"]["simple"][0].keys() if k not in ("InStock_trigger", "OutOfStock_trigger")]

    # Сортируем поля в items_fields согласно order_string
    # Создаем список для отсортированных полей
    sorted_items_fields = []

    # 1. Добавляем поля в порядке из field_order
    for field in field_order:
        # Проверяем, есть ли поле в other_keys или это специальные поля
        if field in other_keys or field in ["stock", "timestamp", "link"]:
            sorted_items_fields.append(field)

    # 2. Добавляем оставшиеся поля из other_keys, которых нет в field_order
    for field in other_keys:
        if field not in sorted_items_fields and field not in ["stock", "timestamp", "link"]:
            sorted_items_fields.append(field)

    # 3. Убеждаемся, что timestamp всегда в конце
    if "timestamp" in sorted_items_fields:
        sorted_items_fields.remove("timestamp")
        sorted_items_fields.append("timestamp")

    # Формируем строку с полями
    items_fields = ", ".join(sorted_items_fields)

    return items_fields






#region Доп. фрагм шаблона

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
// Код сгенерирован APSP v$current_apsp_version_val
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


# # result_file_JS(result_selectors, "https://megapteka.ru/basket")
# result_file_JS(result_selectors, "https://www.perekrestok.ru/cat/")





#region gen_main_code
def gen_main_code():
    print(this_module_title)

    # Если поля не собраны, то собираю их здесь в строку, и также сохраняю
    fields_str = data_input_table.get("fields_str")
    if not fields_str:
        fields_str = extract_fields()
        data_input_table["fields_str"] = fields_str

    # Теперь точно валидное значение
    field = fields_str
    print(f"field = {field}")

    host = data_input_table["host"]




    # region > test


    # # Извлекаем все селекторы из всех страниц, для parseCard
    # all_extracted_selectors = get_all_selectors(data_input_table)

    # # Генерируем parseCard
    # parse_card_code_value = get_parseCard_code(all_extracted_selectors)

    # # Генерируем parsePage
    # parse_page_code_value = ""



    # Извлекаем все селекторы из всех страниц, для parseCard
    # Генерируем parseCard
    parse_card_code_value = ""

    # Генерируем parsePage
    parse_page_code_value = main_generate_parsePage()



    # # Обе функции

    # # Извлекаем все селекторы из всех страниц, для parseCard
    # all_extracted_selectors = get_all_selectors(data_input_table)

    # # Генерируем parseCard
    # parse_card_code_value = get_parseCard_code(all_extracted_selectors)

    # # Генерируем parsePage
    # parse_page_code_value = main_generate_parsePage()








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

    make_request_code_value = simple_makeRequest()    
    parse_entry_point_code_value = parse_entry_point_gen()
    default_conf_value = set_defaultConf()
    parser_name = set_parser_name()

    result = template_main_code.substitute(
        make_request_code = make_request_code_value,
        parse_card_code = parse_card_code_value,
        parse_page_code = parse_page_code_value,
        parse_entry_point_code = parse_entry_point_code_value,
        field_val = field,
        host_val = host,
        default_conf = default_conf_value,
        subtitle_from_code = get_cuurent_subtitle(),
        parser_name_val = parser_name
    ).strip()

    ################### Потом убрать
    print(final_title)
    print(result)

    return result




# region result_file_JS
# Сохраняет результирующий код парсера в файл
def result_file_JS(result_code):
    filename = "result_code_gen/result/result_code.ts"
    os.makedirs(os.path.dirname(filename), exist_ok=True)  # создаём папку, если её нет

    with open(filename, "w", encoding="utf-8") as f:
        f.write(result_code)


# Печатает и сохраняет массив с сообщеними, ошибками и предупреждениями
def print_and_save_message_global():  
    if len(message_global) > 0:

        filename = "result_code_gen/result/message_global.txt"
        with open(filename, "w", encoding="utf-8") as f:
            
            generated_status = "🟩 Sucsess 🟩"
            print(f"\nСообщения из message_global:")
            for elem in message_global:
                key = list(elem.keys())[0]
                value = elem[key]

                # Печать
                if key == "1":
                    print(f"🟧 {value}")
                    generated_status = "🟧 Falled 🟧"
                elif key == "2":
                    print(f"🟡 [Предупреждение]: {value}")
                else:
                    print(f"🟦 {value}")

                # Ошибки, которые рейзятся через raise ErrorHandler, не попадают сюда, т.к. они прерывают скрипт
                # А здесь ошибки которые с типом 🟧 - это те, которые произошли, но программа пошла дальше
                # Все эти ошибки, предупреждения и информационные сообщения будут выводиться пользователю

                # Запись в файл
                f.write(f"{key}: {value}\n")
            print("")
            print(f"Итоговый статус генерации: {generated_status}")




# Декоратор, который засекает время генерации всего кода
def measure_time(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start

        print("")
        if elapsed < 60:
            print(f"🕚 Время выполнения: {elapsed:.2f} секунд")
        else:
            print(f"🕚 Время выполнения: {elapsed / 60:.1f} минут")

        import import_all_libraries        
        print(f"🧢 Кол-во обращений к внешнему ИИ: {import_all_libraries.count_request_to_AI}") 

        return result
    return wrapper

# Основная функция
@measure_time
def result_parser_code():
    result_code = gen_main_code()
    result_file_JS(result_code)
    print_and_save_message_global() # Печатает и сохраняет массив с ошибками и предупреждениями


# result_parser_code()
