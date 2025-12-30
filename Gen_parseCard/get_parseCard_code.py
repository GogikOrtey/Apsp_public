"""
Основной скрипт генерации кода для parseCard, в который передаётся набор ссылок на товары.
Возвращает код функции parsePage
""" 

import random
from typing import Any, Dict, List, Tuple, Optional

# region Импорты
# Чтобы при запуске файла из этой папки были видны модули из корня проекта (addedFunc.py и др.)
### Потом убрать, что бы было нормально
from pathlib import Path
import sys
import json
import copy
from typing import Any
import ast

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Подключение всех библиотек и функций
from Gen_parseCard.all_fields_description import *
from Gen_parseCard.extract_selectors_parseCard_from_GPT import *
from import_all_libraries import *
from reasoning_agent.agent_main import *
from playwright_tool.browser_start import *

from playwright_tool.playwright_toolkit import *  # регистрирует инструменты playwright
from new_program.html_toolkit import *  # регистрирует инструменты html_tool

















def gen_main_prompt(host_value):
    main_prompt = """

ЗАДАЧА: 

Во входных данных (input_data) тебе будут даны поля и селекторы, которые извлекают значения для этих полей, из разных страниц товаров для текущего сайта. Тебе нужно будет составить код (для извлечения значений для каждого поля), на JS, используя cheerio. Также тебе будут даны 3 ссылки на страницы с товарами, с этого сайта. На этих страницах ты будешь проверять, корректно ли работает составленный тобой код, для каждого поля по порядку. С каким конкретно полем тебе сейчас нужно работать - указано в глобальном плане задачи (main_plan), и в блоке "Твой фокус прямо сейчас".

В result у тебя есть набор из шести ячеек, для каждого поля, например для поля "name":
- field__name__code - в эту ячейку нужно будет записать готовый код на JS извлечения значения по селектору.
Далее будут идти 3 ячейки, соответствующие трём предоставленным ссылкам. Например:
- field__name__ok_on_1_link
- field__name__ok_on_2_link
- field__name__ok_on_3_link

Тебе нужно будет составить код для извлечения значения текущего поля по селектору, и проверить его на этих трёх страницах (ссылки на которые будут тебе даны в input_data), и записать в эти ячейки в result значения true, если проверка прошла успешно, и извлекается нужное, корректное, и соответствующее семантике поля значение. Подробнее про описание, какие значения являются верными для какого поля, расписано в input_data. А алгоритм проверки корректности значения, расписан ниже.

Здесь ты часто будешь использовать два инструмента - это extract_selector_data_from_cached_pages и run_cheerio_js_extract_vars. Важно помнить, что они не работают с браузером Playwright, и не открывают страницы по переданным ссылкам в браузере, а получают html контент переданных ссылок по простому запросу. Это нужно для локального эмулирования среды парсера, для которого ты собираешь код - там также не будет открываться браузер, а html страниц будет получаться по простым запросам. Но ты не ограничен в использовании инструментов с Playwright для проверок. Т.е. ты спокойно можешь открыть нужную страницу в браузере, и там выполнить какие-то действия, для того что бы что-то найти или проверить. Но в результате нужно будет составить фрагмент кода, и проверить его через run_cheerio_js_extract_vars для каждого поля. 
Т.е.: Playwright используется ТОЛЬКО для поиска селекторов и понимания структуры. Истиной при валидации считается ТОЛЬКО инструменты использующие Cheerio (extract_selector_data_from_cached_pages и run_cheerio_js_extract_vars).

С каким конкретно полем тебе нужно работать сейчас - указано в глобальном плане задачи (main_plan), а также в блоке "Твой фокус прямо сейчас".

АЛГОРИТМ:

1. ПРОВЕРКА СЕЛЕКТОРА

Используй инструмент extract_selector_data_from_cached_pages для получения значений текущего поля, на трёх страницах из input_data, что бы проверить, что селектор корректен. Этот инструмент принимает массив ссылок - можно передать несколько, или одну, и он выполнит его на всех переданных страницах, и вернёт результат также в массиве, в таком-же порядке элементов.

Инструмент вернёт результат в виде:
[
    {
        "link" - ссылка на страницу, на которой было произведено извлечение
        "used_selector" - использованный селектор
        "count_of_elements" - количество элементов, найденных по этому селектору на этой странице
        "main_result" - значение полученное по селектору (первое, если их несколько)
        "all_results" - все значения, полученные по селектору (если их несколько). Это будет массив, также он будет ограничен max 30 элементами
        "html_frame_main_result" - сразу значение инструмента get_html_frame_on_current_page первого элемента
    }, 
    ...
]

Тебе нужно будет проанализировать и просмотреть, что полученные значения для каждой страницы - валидны, корректны, не пусты, и соответствуют семантике поля.

Если в input_data для этого поля указаны несколько селекторов (больше одного), то надо будет выбрать один. Посмотри визуально и определи, каким может быть общий селектор, если они похожи. Если селектор имеет привязку к товару, или его артикулу, в своей части, например "#product-65416", её нужно будет убрать и посмотреть, какие результаты он будет выдавать. Проверь его, убедись что (желательно) выдаёт один результат на страницу, и (обязательно) возвращает нужные данные. 

Если же извлечение значений на всех трёх страницах невозможно при помощи одного селектора, то можно взять несколько. Но помни, что если для корректного извлечения на трёх страницах нужно три разных селектора - то это скорее всего ошибка, и нужно будет подобрать другой селектор для этого поля.

Возможные проблемы, которые ты можешь увидеть при этой проверке, и как их решать:
- Если значение пусто на всех страницах, то значит селектор неверный. Попробуй взять другой.
- Если значение пусто на одной странице, то скорее всего там может просто не быть того элемента, который извлекается в это поле. Это скорее нормальная ситуация. Проанализируй его html_frame и иди дальше.
- Если count_of_elements больше одного хотя бы на одном сайте, то надо будет использовать ?.first() в коде. Пометь это в memory.
- Если значение main_result содержит что-то лишнее, например для поля article извлекается строка "Артикул: 15487", то значит его нужно будет просто очистить далее в написании кода (что бы в итоге получилось "15487" без лишнего текста). Пометь это в memory.
- Если один селектор не работает на всех сайтах, то стоит попробовать второй.
- Если используется несколько селекторов, они объединяются в JS-выражение: ".a" || ".b"
- Если в результате проверок тебе не удастся выделить селектор, который корректно работает на всех трёх страницах из примера, то поставь заглушку, и обязательно добавь комментарий о том, что тебе не удалось подобрать селектор для этого поля (например `const region = "" // Не удалось подобрать селектор для этого поля`). Также, в таком случае нужно будет проставить значения для полей field__[название поля]__ok_on_[номер ссылки]_link = true, что бы продвинуться дальше по main_plan. Но это стоит делать только в порядке исключения.
    - Используй заглушку только после минимум 3-х неудачных попыток подбора разных селекторов.

Когда верный селектор (или набор селекторов) для этого поля будет найден, зафиксируй его в ячейке choosed_selector_field_[название поля] в result. Также просмотри результаты extract_selector_data_from_cached_pages, и если нужна будет какая-то дополнительная обработка значения - зафиксируй это в memory, и переходи далее к шагу генерации кода для этого поля.

————————————————————————

2. НАПИСАНИЕ КОДА

Посмотри, есть ли в result в ячейке field__[название поля]__code какой-либо код. Если его нет, либо если код записан, но по своим предыдущим шагам и по тактическому плану (steps_future) ты видишь, что ещё не закончил его написание, то значит его нужно будет написать. Если значение уже есть и код написан, а также в тактическом плане (steps_future) обозначено что можно переходить к его проверке, то переходи к следующему шагу в алгоритме.

Для написания кода извлечения значения для поля по селектору:

Используй такой общий шаблон:

```
const /* название поля */ = $(/* селектор */).text().trim() /* дополнительная обработка, если нужна */
```

Примеры:

const name = $("h1").text().trim()
const name = $("h1.c-header.c-header_h1").text().trim()
const article = $(".shop2-product-article").text()?.replace("Артикул:", "").trim()
const article = $("span.c-value__value-text.c-product-cart-form__sku-value").text().trim()
const article = $(".s-product-sku meta[itemprop='sku']")?.attr("content").trim()
const manufacturer = $(".gr-vendor-block > a").text().trim()
const region = $("button.a-bar__link--city")?.first().text().trim();

- Можно использовать например || если один селектор не работает на всех страницах:
const brand = $(".c-value:contains('Бренд') > .c-value__value-text")?.first().text() || $(".c-value:contains('Производитель') > .c-value__value-text")?.first().text()

Правила:
- При генерации JS-кода селектор для этого поля должен браться из ячейки choosed_selector_field_[название поля] из result
    - Если там несколько селекторов, то приоритет — один максимально универсальный селектор. Если его нет — объединение через запятую внутри строки селектора $( ".a, .b" ). И только в крайнем случае (когда нужна разная логика обработки, например .text() vs .attr()) использовать JS-оператор ||
- При генерации кода агент обязан учитывать правила и флаги, сохранённые в memory для этого поля.
- Не использовать `?.[i]`, всегда использовать `?.at(i)`.
- Перед `replace`, `match`, `includes` и другими подобными функциями, которые могут упасть, если предыдущее значение окажется null - всегда использовать `?.`, для безопасности.
- По стандарту, устанавливай значение переменных через const. Однако, если далее в коде будет произведено изменение значения этой переменной, то разумеется используй let.
- В ячейку field__[название поля]__code нужно записать код на JS. Чаще всего это одна строка, но иногда бывает необходимо написать 2 или больше. Это также возможно, записывай их в эту же ячейку через ;
    Но не добавляй дополнительных строчек в результат кода без необходимости.
- Помни, что если в селекторе указано извлечение атрибута, например: "product_id": ".single_add_to_cart_button[name='add-to-cart'][value]", то в синтаксисе cheerio нужно будет использовать .attr("value")
- Если пишешь 2 и более строки кода в ячейке для поля, то добавляй перевод на новую строку перед каждой следующей (для красоты)

Инструкции для особых полей:
Для таких полей нужно будет придерживаться следующей дополнительной логики:

- Для поля stock
    Практически всегда мы используем шаблон:
    ```
    const stock = $(/* селектор */).text().trim()?.includes(/* Триггер того что товар в наличии */) ? "InStock" : "OutOfStock"
    ```
    Либо наоборот, триггер того что товара нет в наличии, но так пишем реже, первый вариант предпочтительнее.

    Примеры:

    const stock = $(".b-pay__add2basket").text().trim()?.includes("Купить") ? "InStock" : "OutOfStock"
    const stock = $(".a-sidebar__not-available").text()?.includes("Нет в наличии") ? "OutOfStock" : "InStock";

    Т.е. в значение этого поля должны будут попасть ТОЛЬКО строки "InStock" либо "OutOfStock". Другое значение в этом поле считается ошибкой.

    Если во входных данных (input_data) задан селектор для stock, то там также будут два поля - in_stock_trigger и out_of_stock_trigger. В них будут лежать найденные строки, которые являются триггерами наличия или отсутствия в наличии товара. Т.е. если например есть какие-то данные в in_stock_trigger, то ты можешь проверить, что если по селектору stock извлечённое значение содержит подстроку указанную в in_stock_trigger, то на основе этого можно собирать код для извлечения значения для поля stock.

    Если нет селекторов для статуса наличия в input_data, или наличие товара никак нельзя определить, установи константное значение `const stock = "InStock"`. Но это только в качестве исключения.

- Для полей price, oldprice и других денежных - не забывай, что чаще всего нужно будет добавить обработку, которая очищает значение от текста и других лишних символов. Это могут быть регулярки, например такие как:
    - replace(/[^\d]/g, '') - оставляет только цифры
    - replace(/[^\d.,]/g, '') - оставляет цифры с точками и запятыми
    и т.п.

    Важный момент - если на сайте копейки отделены от основной части цены запятой "," - то её надо заменить на точку ".". Пример: "1568,12" надо будет преобразовать в "1568.12". Но сначала надо делать замену запятой на точку, а потом удалять всё, кроме цифр и точки, если это требуется для корректности поля. Если в строке есть и точка, и запятая — определи, что из них разделитель разрядов, а что — копеек.

    Также, в такое поле не должны попадать обозначения денежных знаков (₽, "руб.", "/шт" и подобные) - в таком поле должно остаться только числовое значение, обозначающее цену товара.    

- Для поля imageLink
    В значении поля нужно получить ссылку на изображение. Иногда требуется добавить HOST текущего сайта (протокол + домен) в начале ссылки, что бы она стала валидной. Важно: переменная HOST уже объявлена в коде ранее и она содержит значение HOST = '""" + host_value + """'
    Тебе не нужно будет задавать значение для HOST в своём фрагменте кода.

    Примеры: 

    const imageLink = $(".a-gallery-carousel__card img")?.attr("data-src") || ""
    const imageLink = $(".slides #photo-0 > a")?.first()?.attr("href")
    const imageLink = HOST + $(".detail-gallery-big-slider__wrapper a")?.attr("href");

    Если в объекте указано несколько ссылок на изображение, то выбери самую главную.
    Если не уверен в правильности собранного url изображения, можешь проверить его через инструмент check_url_status.

Проверь, сколько совпадений выдаёт селектор например на трёх страницах. Если на какой-то больше одного, то для корректной обработки нужно будет добавить ?.first() в обработку значения, после его извлечения по селектору. В редких случаях может оказаться, что тебе нужен например второй, или другой элемент - тогда используй ?.eq(1) и подобный код. Т.е. в итоге мы должны получать и обрабатывать для значения поля - один элемент, если на странице их находится несколько. Если их находится прямо очень много, то возможно селектор неверный. Попробуй взять запасной, или уточнить этот при помощи инструмента get_html_frame_on_current_page.

Помни, что если ты создаёшь дополнительную переменну для обработки поля, например: imageLinkVal для извлечения значений для поля imageLink, то в итоговом фрагменте кода, конечное значение должно записываться в переменную, ТОЧНО соответствующую названию обрабатываемого поля. Но если можно сделать всю обработку в одну строку - то делай в одну.

Также помни, что cheerio не поддерживает псевдоселекторы :has и :contains

Запиши составленный код в result в ячейку с названием текущего поля field__[название поля]__code. И в тактическом плане (steps_future) укажи, что код составлен, и можно переходить к его валидации. Либо, если нужна будет дополнительная проверка которая потребует действия, запиши код также в result, но в steps_future укажи, что конкретно ещё нужно сделать, перед тем как посчитать этот код валидным, и переходить к шагам его проверки.

Когда код для извлечения значений будет составлен, запиши в ячейку field__[название поля]__code_gen_completed в result значение true, и переходи к 3 этапу - валидации кода:

————————————————————————

3. ВАЛИДАЦИЯ НАПИСАННОГО КОДА

Если ты видишь в какой-то из ячеек field__[название поля]__ok_on_[номер ссылки]_link значение false, значит ты уже производил проверку, и для этой страницы твой написанный код в field__[название поля]__code выдал некорректный результат. Значит тебе нужно изменить и поправить его. Можешь запустить какой-то инструмент, что бы получить больше контекста, или если ты уже видишь в чём проблема, то сразу поменяй значение field__[название поля]__code. И пометь эту ячейку field__[название поля]__ok_on_[номер ссылки]_link как None. Так, на следующем шаге ты запустишь и проверишь этот код. Если сразу понять в чём причина не получается - то используй инструменты что бы получить больше контекста.

Если все ячейки field__[название поля]__ok_on_[номер ссылки]_link = None, или некоторые из них равны true, и нет в них значений false, то значит тебе нужно проверить код из field__[название поля]__code - на оставшихся из трёх страниц, которые помечены как None в result.

——————

Здесь тебе нужно будет запустить написанный код, для извлечения значений поля. Этот код уже будет записан в ячейке field__[название поля]__code в result. Для запуска и валидации используй инструмент run_cheerio_js_extract_vars

Ему в аргументах - передай код, который записан в ячейке field__[название поля]__code в result для текущего поля. Этот инструмент вернёт тебе значения для всех переменных, которые были инициализированы в твоём переданном фрагменте кода. Т.е. тебе не нужно передавать в него дополнительно `console.log()` и подобное, он сам вернёт все значения инициализированных переменных. Т.е. ожидается, что ты отправишь ему код, который извлекает значение для одного указанного поля. 

Например: "const name = $("h1").text().trim()"
И он вернёт тебе: 
{
    "name": "Раковина 12d"
}

Можешь проверить сразу на всех трёх ссылках.

Тебе нужно будет проанализировать вывод, полностью ли он корректен, нет ли там пустого значения, или нет ли там склейки текста из нескольких элементов, и т.п.

Если ты увидишь, что на каких-то ссылках написанный тобой код извлекает неверные значения, то пометь ячейки field__[название поля]__ok_on_[номер ссылки]_link в result как false, а в остальные ячейки других страниц - запиши None, вне зависимости от их текущих значений (что бы не забыть потом проверить код на них снова). Значения других ячеек из result не меняй. 

Если значение, извлекаемое инструментом run_cheerio_js_extract_vars из рассматриваемой страницы (или нескольких страниц) корректно, то запиши для них в field__[название поля]__ok_on_[номер ссылки]_link значения true.

ВАЖНО:
- Не оборачивай код, который ты будешь записывать в ячейки result в обратные кавычки, такие как ``` и `. 
- Код JS будет строкой внутри JSON. Обязательно экранируй необходимые символы, такие как обратные слэши (например, replace(/[\\d]/g, '') вместо /[\d]/) и двойные кавычки.


Входные данные (input_data):

"""
    return main_prompt








"""

{
    "choosed_selector_field_name": str
    "field__name__code": str
    "field__name__code_gen_completed": boolean
    "field__name__ok_on_1_link": boolean
    "field__name__ok_on_2_link": boolean
    "field__name__ok_on_3_link": boolean

    "choosed_selector_field_price"
    "field__price__code"
    "field__price__code_gen_completed"
    "field__price__ok_on_1_link"
    "field__price__ok_on_2_link"
    "field__price__ok_on_3_link"

    ... (для всех полей по 6 ячеек)
}

"""













# Генерация схемы и шаблона результата под любые поля из input_data
def build_main_result_schema_and_template(input_data: Dict[str, Any], num_links: int = 3) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    На вход принимает словарь вида:
        {
            "name": ["селектор_1", ...],
            "price": ["селектор_1", ...],
            ...
        }

    Возвращает:
      - main_result_schema: json-schema-подобное описание ожидаемого result для orchestrate()
      - main_result_template: шаблон result (все значения None), который агент заполняет

    num_links — количество страниц/ссылок, на которых агент должен проставлять ok-флаги
    (в текущем пайплайне обычно 3: ok_on_1_link, ok_on_2_link, ok_on_3_link).
    """
    if not isinstance(input_data, dict):
        raise TypeError(f"input_data must be dict, got: {type(input_data).__name__}")
    if not isinstance(num_links, int) or num_links <= 0:
        raise ValueError(f"num_links must be positive int, got: {num_links!r}")

    main_result_schema: Dict[str, Any] = {}
    main_result_template: Dict[str, Any] = {}

    excluded_fields = {"in_stock_trigger", "out_of_stock_trigger"}
    for field_name in input_data.keys():
        if field_name in excluded_fields or str(field_name) in excluded_fields:
            continue
        # 1) выбранный селектор
        key_selector = f"choosed_selector_field_{field_name}"
        main_result_schema[key_selector] = {
            "type": "string",
            # "required": True,
            "description": f"Выбранный селектор для извлечения значений для поля {field_name}",
        }
        main_result_template[key_selector] = None

        # 2) код извлечения
        key_code = f"field__{field_name}__code"
        main_result_schema[key_code] = {
            "type": "string",
            # "required": True,
            "description": f"Код на JS для извлечения значения для поля {field_name} по выбранному селектору",
        }
        main_result_template[key_code] = None

        # 3) флаг, что код написан
        key_done = f"field__{field_name}__code_gen_completed"
        main_result_schema[key_done] = {
            "type": "boolean",
            # "required": True,
            "description": f"Код для поля {field_name} написан",
        }
        main_result_template[key_done] = None

        # 4) ok-флаги по страницам
        for i in range(1, num_links + 1):
            key_ok = f"field__{field_name}__ok_on_{i}_link"
            main_result_schema[key_ok] = {
                "type": "boolean",
                # "required": True,
                "description": f"Корректное ли значение извлекает написанный код для поля {field_name} на {i}й странице",
            }
            main_result_template[key_ok] = None

    return main_result_schema, main_result_template


def _ru_pages_phrase(num_links: int) -> str:
    """
    Утилита для человекочитаемой фразы про количество страниц в goal плана.
    """
    mapping = {
        1: "на одной странице",
        2: "на двух страницах",
        3: "на трёх страницах",
        4: "на четырёх страницах",
        5: "на пяти страницах",
    }
    return mapping.get(num_links, f"на {num_links} страницах")


def build_main_plan_for_parse_card(input_data: Dict[str, Any], num_links: int = 3) -> Dict[str, Any]:
    """
    Генерирует main_plan по схеме из `reasoning_agent/plan_tools.py`:

    {
        "steps": [
            {"step_id": 1, "goal": "...", "fills": [...]},
            ...
        ]
    }

    Для каждого поля создаёт 3 шага (как в описании в этом файле):
      - n + 1: Проверить и выбрать селектор для извлечения значений для поля _
      - n + 2: Сгенерировать код извлечения значений для поля _
      - n + 3: Проверить сгенерированный код извлечения значений для поля _ на N страницах
    """
    if not isinstance(input_data, dict):
        raise TypeError(f"input_data must be dict, got: {type(input_data).__name__}")
    if not isinstance(num_links, int) or num_links <= 0:
        raise ValueError(f"num_links must be positive int, got: {num_links!r}")

    steps: List[Dict[str, Any]] = []
    step_id = 1

    excluded_fields = {"in_stock_trigger", "out_of_stock_trigger"}
    for field_name in input_data.keys():
        if field_name in excluded_fields or str(field_name) in excluded_fields:
            continue
        steps.append(
            {
                "step_id": step_id,
                "goal": f"Проверить и выбрать селектор для извлечения значений для поля {field_name}",
                "fills": [f"choosed_selector_field_{field_name}"],
            }
        )
        step_id += 1

        steps.append(
            {
                "step_id": step_id,
                "goal": f"Сгенерировать код извлечения значений для поля {field_name}",
                "fills": [
                    f"field__{field_name}__code",
                    f"field__{field_name}__code_gen_completed",
                ],
            }
        )
        step_id += 1

        steps.append(
            {
                "step_id": step_id,
                "goal": f"Проверить сгенерированный код извлечения значений для поля {field_name} {_ru_pages_phrase(num_links)}",
                "fills": [f"field__{field_name}__ok_on_{i}_link" for i in range(1, num_links + 1)],
            }
        )
        step_id += 1

    return {"steps": steps}


# Схема результата (legacy-пример для 2 полей: name/price).
# В реальном запуске `get_parseCard_code()` использует динамическую генерацию
# через `build_main_result_schema_and_template(input_data, num_links=3)` под все поля из input_data.
main_result_schema = {
    "choosed_selector_field_name": {
        "type": "string",
        "required": True,
        "description": "Выбранный селектор для извлечения значений для поля name"
    },
    "field__name__code": {
        "type": "string",
        "required": True,
        "description": "Код на JS для извлечения значения для поля name по выбранному селектору"
    },
    "field__name__code_gen_completed": {
        "type": "boolean",
        "required": True,
        "description": "Код для поля name написан"
    },
    "field__name__ok_on_1_link": {
        "type": "boolean",
        "required": True,
        "description": "Корректное ли значение извлекает написанный код для поля name на 1й странице"
    },
    "field__name__ok_on_2_link": {
        "type": "boolean",
        "required": True,
        "description": "Корректное ли значение извлекает написанный код для поля name на 2й странице"
    },
    "field__name__ok_on_3_link": {
        "type": "boolean",
        "required": True,
        "description": "Корректное ли значение извлекает написанный код для поля name на 3й странице"
    },
    "choosed_selector_field_price": {
        "type": "string",
        "required": True,
        "description": "Выбранный селектор для извлечения значений для поля price"
    },
    "field__price__code": {
        "type": "string",
        "required": True,
        "description": "Код на JS для извлечения значения для поля price по выбранному селектору"
    },
    "field__price__code_gen_completed": {
        "type": "boolean",
        "required": True,
        "description": "Код для поля price написан"
    },
    "field__price__ok_on_1_link": {
        "type": "boolean",
        "required": True,
        "description": "Корректное ли значение извлекает написанный код для поля price на 1й странице"
    },
    "field__price__ok_on_2_link": {
        "type": "boolean",
        "required": True,
        "description": "Корректное ли значение извлекает написанный код для поля price на 2й странице"
    },
    "field__price__ok_on_3_link": {
        "type": "boolean",
        "required": True,
        "description": "Корректное ли значение извлекает написанный код для поля price на 3й странице"
    }
}








# Шаблон результата, который агент заполняет в процессе работы
main_result_template = {
    "choosed_selector_field_name": None,
    "field__name__code": None,
    "field__name__code_gen_completed": None,
    "field__name__ok_on_1_link": None,
    "field__name__ok_on_2_link": None,
    "field__name__ok_on_3_link": None,

    "choosed_selector_field_price": None,
    "field__price__code": None,
    "field__price__code_gen_completed": None,
    "field__price__ok_on_1_link": None,
    "field__price__ok_on_2_link": None,
    "field__price__ok_on_3_link": None
}




""" 

n + 1: Проверить и выбрать селектор для извлечения значений для поля _
n + 2: Сгенерировать код извлечения значений для поля _
n + 3: Проверить сгенерированный код извлечения значений для поля _ на трёх страницах

"""





main_plan = {
    "steps": [
        {
            "step_id": 1,
            "goal": "Проверить и выбрать селектор для извлечения значений для поля name",
            "fills": [
                "choosed_selector_field_name"
            ]
        },
        {
            "step_id": 2,
            "goal": "Сгенерировать код извлечения значений для поля name",
            "fills": [
                "field__name__code",
                "field__name__code_gen_completed"
            ]
        },
        {
            "step_id": 3,
            "goal": "Проверить сгенерированный код извлечения значений для поля name на трёх страницах",
            "fills": [
                "field__name__ok_on_1_link",
                "field__name__ok_on_2_link",
                "field__name__ok_on_3_link"
            ]
        },
        {
            "step_id": 4,
            "goal": "Проверить и выбрать селектор для извлечения значений для поля price",
            "fills": [
                "choosed_selector_field_price"
            ]
        },
        {
            "step_id": 5,
            "goal": "Сгенерировать код извлечения значений для поля price",
            "fills": [
                "field__price__code",
                "field__price__code_gen_completed"
            ]
        },
        # ... (другие поля по той же схеме: selector -> code -> ok_on_links)
    ]
}










def extract_only_used_fields(all_fields, used_fields_and_selectors):
    """
    Фильтрует поля из all_fields, и возвращает объект только с теми, которые есть в used_fields_and_selectors
    """

    # 1) Нормализуем used_fields_and_selectors к python-объекту
    used_obj = used_fields_and_selectors
    if isinstance(used_obj, str):
        s = used_obj.strip()
        if s:
            try:
                used_obj = json.loads(s)
            except Exception:
                # fallback на python-подобные строки
                try:
                    used_obj = ast.literal_eval(s)
                except Exception:
                    used_obj = {}
        else:
            used_obj = {}

    # 2) Достаём список имён полей в стабильном порядке
    used_field_names: List[str] = []

    def _add_name(name: Any) -> None:
        if name is None:
            return
        n = str(name).strip()
        if not n:
            return
        if n not in used_field_names:
            used_field_names.append(n)

    if isinstance(used_obj, dict):
        # Поддержка формата {"fields": {...}} или {"fields": [..]}
        if "fields" in used_obj:
            f = used_obj.get("fields")
            if isinstance(f, dict):
                for k in f.keys():
                    _add_name(k)
            elif isinstance(f, (list, tuple, set)):
                for k in f:
                    _add_name(k)

        # Наиболее частый формат: {"name": [селекторы], "price": [селекторы], ...}
        for k in used_obj.keys():
            if k == "fields":
                continue
            _add_name(k)

    elif isinstance(used_obj, (list, tuple, set)):
        for k in used_obj:
            _add_name(k)

    # 3) Плоско собираем все поля из all_fields (оно разбито по разделам)
    all_fields_flat: Dict[str, Any] = {}
    if isinstance(all_fields, dict):
        for _section_name, section_fields in all_fields.items():
            if isinstance(section_fields, dict):
                for field_name, meta in section_fields.items():
                    all_fields_flat[str(field_name)] = meta

    # 4) Возвращаем JSON-строку только по использованным полям
    result: Dict[str, Any] = {}
    for field_name in used_field_names:
        if field_name in all_fields_flat:
            result[field_name] = all_fields_flat[field_name]
        else:
            # Если поле пришло во входе, но отсутствует в справочнике описаний
            result[field_name] = {"_missing_in_all_fields": True}

    return json.dumps(result, ensure_ascii=False, indent=4, default=str)





def format_3_links(arr_links):
    """
    Форматирует массив ссылок в блок вида:

    link_1 = https://...
    link_2 = https://...
    link_3 = https://...

    Используется для вставки в текст промпта.
    """
    # Если уже строка — возвращаем как есть (на случай ручной подстановки).
    if isinstance(arr_links, str):
        return arr_links.strip()

    if arr_links is None:
        links = []
    elif isinstance(arr_links, (list, tuple)):
        links = list(arr_links)
    else:
        # Последняя попытка: привести к списку / строке
        try:
            links = list(arr_links)
        except Exception:
            return str(arr_links).strip()

    # Берём первые 3 ссылки (ожидаемый сценарий — ровно 3).
    links = [("" if x is None else str(x).strip()) for x in links[:3]]

    lines = []
    for i, link in enumerate(links, start=1):
        lines.append(f"link_{i} = {link}")

    return "\n".join(lines)






def get_parseCard_code(used_fields_and_selectors, host_value, random_3_links):
    # Приводим input_data к строке
    if isinstance(used_fields_and_selectors, str):
        used_fields_and_selectors_str = used_fields_and_selectors
    else:
        try:
            used_fields_and_selectors_str = json.dumps(used_fields_and_selectors, ensure_ascii=False, indent=4, default=str)
        except Exception:
            used_fields_and_selectors_str = str(used_fields_and_selectors)

    used_3_links = format_3_links(random_3_links)

    used_fields = extract_only_used_fields(all_fields, used_fields_and_selectors)

    # input_data_str = 
    """
    - Селекторы, которые собрались с 3х страниц
    - Ссылки на 3 страницы
    - Используемые поля и их описание
    """

    input_data_value = (
        used_fields_and_selectors_str + f"\n\n" + 
        "ТРИ ВХОДНЫЕ ССЫЛКИ:" + f"\n\n" + 
        used_3_links + f"\n\n" + 
        "ОПИСАНИЕ ИСПОЛЬЗУЕМЫХ ПОЛЕЙ:" + f"\n\n" + 
        used_fields + f"\n\n"
    )

    task = (
        gen_main_prompt(host_value) + 
        input_data_value
        )

    # print(task)

    # Генерирую схему/шаблон/план динамически, на основе входных полей
    dynamic_result_schema, dynamic_result_template = build_main_result_schema_and_template(used_fields_and_selectors, num_links=3)
    dynamic_main_plan = build_main_plan_for_parse_card(used_fields_and_selectors, num_links=3)

    # print(dynamic_main_plan)
    # print(dynamic_result_schema)
    # print(dynamic_result_template)

    resulr_answer = orchestrate(
        task = task,
        max_steps = 200,
        result_schema = dynamic_result_schema,
        result_template = dynamic_result_template,
        plan = dynamic_main_plan,
        step_by_step_running = False, # Разрешаем агенту работать автоматически
    ) 

    result_task = get_result()
    return result_task









# Проверка:

used_fields_and_selectors_test = {
    "name": [
        "h1.product_title.entry-title"       
    ],
    "price": [
        "div#product-65416 .summary.entry-summary p.price .woocommerce-Price-amount",     
        "#product-81354 .summary.entry-summary p.price .woocommerce-Price-amount",        
        "#product-65494 .summary.entry-summary p.price .woocommerce-Price-amount"
    ],
    "imageLink": [
        "div#product-65416 .woocommerce-product-gallery img.wp-post-image",
        "#product-81354 .woocommerce-product-gallery__wrapper .woocommerce-product-gallery__image:first-child img.wp-post-image",      
        "#product-65494 .woocommerce-product-gallery img.wp-post-image"
    ],
    "article": [
        "div#product-65416 .product_meta .sku_wrapper .sku",
        "#product-81354 .product_meta .sku_wrapper .sku",
        "#product-65494 .product_meta .sku_wrapper .sku"
    ]
}

# used_fields_and_selectors_test = {
#     "stock": []
# }


random_3_links_test = [
    'https://makitaclub.ru/products/831271-6/', 
    'https://makitaclub.ru/products/jv002gz/', 
    'https://makitaclub.ru/products/nabor-rychnyh-instrumentov-i-osnastki-makita-d-42042-103-predmeta/'
]




# host_value_test = "https://makitaclub.ru"

# # Запускаю браузер с видимым окном
# launch_browser(headless = False)

# goto_url( 
#     url = "https://makitaclub.ru/?s=%D0%B8%D0%BD%D1%81%D1%82%D1%80%D1%83%D0%BC%D0%B5%D0%BD%D1%82&post_type=product",
#     wait_until = "load",
#     timeout = 30_000
# )

# resilt = get_parseCard_code(used_fields_and_selectors_test, host_value_test, random_3_links_test)

# print("resilt:")
# print(resilt)


""" 
{
    "choosed_selector_field_name": "h1.product_title.entry-title",
    "field__name__code": "const name = $(\"h1.product_title.entry-title\").first().text().trim()",
    "field__name__code_gen_completed": true, 
    "field__name__ok_on_1_link": true,       
    "field__name__ok_on_2_link": true,       
    "field__name__ok_on_3_link": true,       
    "choosed_selector_field_price": "p.price 
.woocommerce-Price-amount",
    "field__price__code": "const price = $(\"p.price .woocommerce-Price-amount\").first().text().trim()?.replace(/\\s+/g, \" \")?.replace(/,/g, \".\")?.replace(/[^\\d.]/g, \"\")", 
    "field__price__code_gen_completed": true,    "field__price__ok_on_1_link": true,      
    "field__price__ok_on_2_link": true,      
    "field__price__ok_on_3_link": true,      
    "choosed_selector_field_imageLink": ".woocommerce-product-gallery img.wp-post-image", 
    "field__imageLink__code": "const imageLink = $(\".woocommerce-product-gallery img.wp-post-image\").first()?.attr(\"data-large_image\") || $(\".woocommerce-product-gallery img.wp-post-image\").first()?.attr(\"data-src\") || $(\".woocommerce-product-gallery img.wp-post-image\").first()?.attr(\"src\") || \"\"",  
    "field__imageLink__code_gen_completed": true,
    "field__imageLink__ok_on_1_link": true,  
    "field__imageLink__ok_on_2_link": true,  
    "field__imageLink__ok_on_3_link": true,  
    "choosed_selector_field_article": ".product_meta .sku_wrapper .sku",
    "field__article__code": "const article = 
$(\".product_meta .sku_wrapper .sku\").first().text().trim()",
    "field__article__code_gen_completed": true,
    "field__article__ok_on_1_link": true,    
    "field__article__ok_on_2_link": true,    
    "field__article__ok_on_3_link": true     
    "choosed_selector_field_stock": "form.cart .single_add_to_cart_button, form.cart button.single_add_to_cart_button, button.single_add_to_cart_button",
    "field__stock__code": "const addToCartText = $(\"form.cart .single_add_to_cart_button, form.cart button.single_add_to_cart_button, 
button.single_add_to_cart_button\")?.first().text().trim(); const stock = addToCartText?.includes(\"В корзину\") ? \"InStock\" : \"OutOfStock\";",
    "field__stock__code_gen_completed": true,    "field__stock__ok_on_1_link": true,      
    "field__stock__ok_on_2_link": true,      
    "field__stock__ok_on_3_link": true       
}
"""