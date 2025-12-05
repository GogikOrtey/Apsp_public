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

def format_js(code: str) -> str:
    opts = jsbeautifier.default_options()
    opts.indent_size = 2
    opts.wrap_line_length = 120
    return jsbeautifier.beautify(code, opts)

# Собирает финальный код для вставки в шаблон
from string import Template

# Собирает финальный код для вставки в шаблон
def selector_checker_and_parseCard_gen(result_selectors, data_input_table):
    print("Проверяем селекторы, и генерируем parseCard")
    #print_json(result_selectors)  # по желанию раскомментировать

    # Подготовка множества триггеров InStock (строки)
    all_inStock_selectors = {elem.get("InStock_trigger") for elem in data_input_table["links"]["simple"] if elem.get("InStock_trigger")}
    # all_inStock_selectors содержит значения из data_input_table (если они там в виде строки или списка) --
    # предполагаю, что это строки, как в вашем примере. Если там массивы — можно будет адаптировать.
    # Для безопасности приведём к set строк:
    all_inStock_selectors = {s if isinstance(s, str) else ",".join(s) for s in all_inStock_selectors}
    count_of_unical_text_selectors = len(all_inStock_selectors)

    # Вспомог: объединяем массив селекторов в одну строку для $("sel1, sel2")
    def join_selectors_array(sel_array):
        # sel_array ожидается список строк
        if not sel_array:
            return ""
        # убираем лишние пробелы
        sel_array = [s.strip() for s in sel_array if s and s.strip()]
        if not sel_array:
            return ""
        if len(sel_array) == 1:
            return sel_array[0]
        # объединяем через запятую — это корректно для cheerio/jQuery
        return ", ".join(sel_array)

    # Вспомог: если селектор содержит hint на атрибут (href/src) — используем attr
    def detect_attr_selector(sel_array):
        joined = " ".join(sel_array).lower()
        if "href" in joined:
            return "href"
        if "src" in joined:
            return "src"
        return None

    # Генератор куска для триггера наличия
    def using_InStock_triggers_value(result_selectors_local, use_OutOfStock=False):
        key_stock = "InStock_trigger" if not use_OutOfStock else "OutOfStock_trigger"
        true_value = '"InStock"' if not use_OutOfStock else '"OutOfStock"'
        false_value = '"OutOfStock"' if not use_OutOfStock else '"InStock"'

        sel_array = result_selectors_local.get(key_stock, [])
        sel_string = join_selectors_array(sel_array)
        if not sel_string:
            return 'const stock = "InStock"\n'

        # all_inStock_selectors_js — javascript literal: либо "string", либо ["a","b"]
        if count_of_unical_text_selectors == 1:
            all_js = f'"{next(iter(all_inStock_selectors))}"'
        else:
            all_js = "[" + ", ".join(f'"{x}"' for x in all_inStock_selectors) + "]"

        # если в all_inStock_selectors только одно значение — можно использовать .includes(single)
        if count_of_unical_text_selectors == 1:
            # условие: $("...").text()?.includes("needle")
            result_stock_selector = (
                f'const stock = $("{sel_string}")'
                f'.text()?.includes({all_js}) ? {true_value} : {false_value}'
            )
        else:
            # несколько триггеров: .some(s => $("...").text()?.includes(s))
            result_stock_selector = (
                f'const stock = {all_js}.some(s => $("{sel_string}")'
                f'.text()?.includes(s)) ? {true_value} : {false_value}'
            )

        # если было несколько селекторов — добавим .first()
        if isinstance(result_selectors_local.get(key_stock), list) and len(result_selectors_local.get(key_stock)) > 1:
            # вставим .first() после $("/...") — заменим $("sel") на $("sel").first()
            result_stock_selector = result_stock_selector.replace('$("', '$("', 1)
            # более аккуратно — просто добавим .first() сразу после $("{sel_string}")
            result_stock_selector = result_stock_selector.replace(f'$("{sel_string}")', f'$("{sel_string}").first()')
        return result_stock_selector

    # Обработка логики наличия
    if "InStock_trigger" not in result_selectors and "OutOfStock_trigger" not in result_selectors:
        print("Нет триггеров наличия, считаем что все товары в наличии")
        result_stock_selector = 'const stock = "InStock"\n'
    elif "InStock_trigger" in result_selectors and "OutOfStock_trigger" in result_selectors:
        print("Оба триггера есть")
        # если указаны одинаковые массивы/строки — используем InStock как приоритет
        if result_selectors["InStock_trigger"] == result_selectors["OutOfStock_trigger"]:
            print("Они одинаковые, используем InStock")
            result_stock_selector = using_InStock_triggers_value(result_selectors)
        else:
            # логика: если есть оба и разные — используем InStock триггер как в оригинале (можно расширить)
            result_stock_selector = using_InStock_triggers_value(result_selectors)
    elif "InStock_trigger" in result_selectors and "OutOfStock_trigger" not in result_selectors:
        print("Есть только триггер InStock, используем его")
        result_stock_selector = using_InStock_triggers_value(result_selectors)
    elif "InStock_trigger" not in result_selectors and "OutOfStock_trigger" in result_selectors:
        print("Есть только триггер OutOfStock, используем его")
        result_stock_selector = using_InStock_triggers_value(result_selectors, use_OutOfStock=True)

    # Начинаем собирать varFromSelector для всех остальных полей
    lines = []
    # добавляем строку stock
    lines.append(result_stock_selector.rstrip("\n"))

    # Перебираем ключи — пропускаем триггеры
    for key, sel_array in result_selectors.items():
        if key in ("InStock_trigger", "OutOfStock_trigger"):
            continue
        # предполагаем, что sel_array — list
        if not isinstance(sel_array, (list, tuple)):
            sel_array = [sel_array] if sel_array else []

        sel_string = join_selectors_array(sel_array)
        if not sel_string:
            # если селектор пуст — создаём пустую переменную
            lines.append(f'const {key} = ""')
            continue

        # определяем нужно ли брать .attr(...)
        attr = detect_attr_selector(sel_array)
        # если найден attr, используем .attr('href'/'src'), иначе .text()?.trim()
        selector_expr = f'$("{sel_string}")'
        # # если несколько селекторов — ставим .first()
        # if len(sel_array) > 1:
        #     selector_expr = selector_expr + '?.first()'



        """
            * Вот здесь нужно проверить, если у селектора больше 1 результата, то добавляем 
                * selector_expr = selector_expr + '?.first()'

            * И далее здесь проверить, если селектор возвращает на всех страницах именно то что нужно
                * то всё ок, его и вставляем
                * но если он возвращает данные, в которых есть то что нужно, то мы
                * отправляем это всё на обработку в ИИ для уточнения строчки кода

            * Также поля нужно будет отсортировать, и написать в том порядке, в котором 

            * Для imageLink проверить, есть ли хост в ссылке
                * Если нет, то добавлять его, но прописать проверку на то, получили ли мы данные

        """


        if attr:
            lines.append(f'\tconst {key} = {selector_expr}?.attr("{attr}")?.trim()')
        else:
            # используем optional chaining (?.) чтобы не упасть при undefined
            lines.append(f'\tconst {key} = {selector_expr}.text()?.trim()')




    # Собираем финальную строку varFromSelector
    value_field = "\n".join(lines) + "\n"

    # В конце убираем завершающие переносы
    value_field = value_field.rstrip("\n")

    # Собираю поля для объекта item: исключаю триггеры, добавляю stock, timestamp
    other_keys = [k for k in result_selectors.keys() if k not in ("InStock_trigger", "OutOfStock_trigger")]
    # формируем как "name, price, article, ... , stock, timestamp"
    items_fields = ", ".join(other_keys + ["stock", "timestamp"])

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

    # formatted = format_js(result)
    # print(formatted)
    # return formatted


# Пример использования (тот же, что вы дали)
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

# вызов для проверки (раскомментируйте для отладки)
# selector_checker_and_parseCard_gen(result_selectors, {"links": {"simple": [{"InStock_trigger": ".nal.y"}]}})

parse_card_code = selector_checker_and_parseCard_gen(result_selectors, data_input_table)