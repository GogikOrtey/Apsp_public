# Вынесенные отдельно функции
from addedFunc import *
from gen_data_input_table import data_input_table # Входные данные
from extracting_selector_from_html import * 

# Подключение всех библиотек
from import_all_libraries import * 

isPrint = False












# region Создаю parseCard

"""
Проверяет, что все селекторы действительно извлекают то что нужно
И если нужно, то собирает код, который правит их результаты, или как-то
по другому обрабатывает (через агента генерации кода)


Если InStock_trigger и OutOfStock_trigger - одинаковые, то
используем проверку на InStock_trigger, а по умолчанию оставляем занчение "OutOfStock"

Проверить, если ImageLink собирается без хоста, то добавить хост

Использует автоформаттер для price и oldPrice
Проверяет, что итоговые значения корректны
    Простейшая проверка - попробовать пройтись parseInt
    const price = $(".b").text().trim().formatPrice()

##### ChatGPT Agent usage
Далее, здесь будут проверяться все значения на ситуации по типу: Например значение артикула может собираться как: "Артикул: 112233"
    а нам нужно собрать только "112233"

"""



# Собирает финальный код для вставки в шаблон
def selector_checker_and_parseCard_gen(result_selectors, data_input_table):
    print("Проверяем селекторы, и генерируем parseCard")
    print_json(result_selectors)

    # Проверка на наличие всех необходимых полей, и селекторов для них
    # Обязательно должны присутствовать поля и селекторы для: name, stock, price
    value_field = ""
    result_stock_selector = ""

    # Собираем все подстроки, которые триггерят InStock 
    all_inStock_selectors = {elem.get("InStock_trigger") for elem in data_input_table["links"]["simple"] if elem.get("InStock_trigger")}
    count_of_unical_text_selectors = len(all_inStock_selectors)

    if count_of_unical_text_selectors == 1:
        all_inStock_selectors_js = f'"{next(iter(all_inStock_selectors))}"'
    else:
        all_inStock_selectors_js = "[" + ", ".join(f'"{x}"' for x in all_inStock_selectors) + "]"

    def using_InStock_triggers_value(result_selectors, use_OutOfStock = False):
        key_stock = "InStock_trigger" if use_OutOfStock == False else "OutOfStock_trigger"
        result_if_stock = '"InStock" : "OutOfStock"' if use_OutOfStock == False else '"OutOfStock" : "InStock"'
        if count_of_unical_text_selectors == 1:
            result_stock_selector = (
                f'const stock = $("{result_selectors[key_stock]}")'
                f'.text()?.includes({all_inStock_selectors_js}) ? {result_if_stock}'
            )
        else:
            result_stock_selector = (
                f'const stock = {all_inStock_selectors_js}.some(s => $("{result_selectors[key_stock]}")'
                f'.text()?.includes(s)) ? {result_if_stock}'
            )
        return result_stock_selector

    # Обработка логики наличия
    if "InStock_trigger" not in result_selectors and "OutOfStock_trigger" not in result_selectors:
        print("Нет триггеров наличия, считаем что все товары в наличии")
        result_stock_selector = 'const stock = "InStock"\n'
    elif "InStock_trigger" in result_selectors and "OutOfStock_trigger" in result_selectors:
        print("Оба триггера есть")
        if result_selectors["InStock_trigger"] == result_selectors["OutOfStock_trigger"]:
            print("Они одинаковые, используем InStock")
            result_stock_selector = using_InStock_triggers_value(result_selectors)
    elif "InStock_trigger" in result_selectors and not "OutOfStock_trigger" in result_selectors:
        print("Есть только триггер InStock, используем его")
        result_stock_selector = using_InStock_triggers_value(result_selectors)
    elif "InStock_trigger" not in result_selectors and "OutOfStock_trigger" in result_selectors:
        print("Есть только триггер OutOfStock, используем его")
        result_stock_selector = using_InStock_triggers_value(result_selectors, use_OutOfStock = True)

    value_field += f"{result_stock_selector}\n"

    # Добавить обработку, что может быть больше одного селектора на поле

    # OutOfStock_trigger в полях прописывается, их нужно чистить от этих объектов
    # и заменять на stock

    # и не забыть проверить на единственность. Если нет, то ставим .first()


    # В конце
    value_field = value_field.rstrip("\n")

    # Собираю поля
    items_fields = ", ".join(result_selectors.keys()) + ", timestamp"

    template_parseCard = Template("""
    async parseCard(set: SetType, cacher: Cacher<ResultItem[]>) {
        let items: ResultItem[] = []

        const data = await this.makeRequest(set.query);
        const $$ = cheerio.load(data);

        $varFromSelector
        const link = set.query
        const timestamp = getTimestamp()

        const item: ResultItem = {
            $itemsFields
        }
        items.push(item);

        cacher.cache = items
        return items;
    }
    """)

    result = template_parseCard.substitute(
        itemsFields=items_fields,
        varFromSelector=value_field,
    )

    print(result)
    return result


# Для примера
result_selectors = {
    "name": [
        "h1.name"
    ],
    "price": [
        ".b"
    ],
    "article": [
        ".char > p:nth-of-type(1)"
    ],
    "brand": [
        ".char > p:nth-of-type(2)"
    ],
    "InStock_trigger": [
        ".nal.y"
    ],
    "imageLink": [
        "html > body > section.wrap > main > article.wide > .card > .img_bl > .img > a.fancybox[href]"
    ],
    "oldPrice": [
        ".thr"
    ]
}

parse_card_code = selector_checker_and_parseCard_gen(result_selectors, data_input_table)