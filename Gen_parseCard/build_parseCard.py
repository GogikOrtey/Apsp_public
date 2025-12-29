"""
Основной скрипт генерации кода для parseCard, в который передаётся набор ссылок на товары.
Возвращает код функции parsePage
""" 

import random
import textwrap
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





def build_parseCard_get_all_generated_code_str(
    input_data: Dict[str, Any],
    used_fields_and_selectors: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Собирает итоговый блок кода (строкой) из входного JSON `input_data`.

    Ожидается, что `input_data` содержит ключи вида:
    - field__{field}__code

    А `used_fields_and_selectors` (если передан) задаёт фиксированный набор/порядок полей, например:
    {"name": [...], "price": [...], ...}

    Возвращает одну строку с кодом, склеенную из всех найденных фрагментов.
    Переносы строк внутри каждого фрагмента сохраняются.
    """
    if not isinstance(input_data, dict):
        raise TypeError(f"input_data must be dict, got {type(input_data).__name__}")
    if used_fields_and_selectors is not None and not isinstance(used_fields_and_selectors, dict):
        raise TypeError(
            "used_fields_and_selectors must be dict or None, "
            f"got {type(used_fields_and_selectors).__name__}"
        )

    code_snippets: List[str] = []

    # Порядок полей берём из used_fields_and_selectors (если он передан).
    # Иначе — восстанавливаем порядок по ключам input_data.
    if used_fields_and_selectors is not None:
        fields_in_order = list(used_fields_and_selectors.keys())
    else:
        fields_in_order: List[str] = []
        for k in input_data.keys():
            if not isinstance(k, str):
                continue
            if k.startswith("field__") and k.endswith("__code"):
                # k = "field__{field}__code"
                field_name = k[len("field__") : -len("__code")]
                if field_name and field_name not in fields_in_order:
                    fields_in_order.append(field_name)

    for field_name in fields_in_order:
        code_key = f"field__{field_name}__code"
        raw_code = input_data.get(code_key)
        if raw_code is None:
            continue

        if not isinstance(raw_code, str):
            raw_code = str(raw_code)

        # Важно: внутренние \n сохраняем; подчищаем только хвостовые пробелы/переносы,
        # чтобы при склейке не раздувать пустые строки.
        cleaned = raw_code.rstrip()
        if not cleaned.strip():
            continue

        code_snippets.append(cleaned)

    # Между фрагментами ставим пустую строку, чтобы блок читаемо разделял поля.
    return "\n".join(code_snippets)


input_data_test = {
    "choosed_selector_field_name": "h1.product_title.entry-title",
    "field__name__code": "const name = $(\"h1.product_title.entry-title\").first().text().trim()",
    "field__name__code_gen_completed": True, 
    "field__name__ok_on_1_link": True,       
    "field__name__ok_on_2_link": True,       
    "field__name__ok_on_3_link": True,       
    "choosed_selector_field_price": "p.price .woocommerce-Price-amount",
    "field__price__code": "const price = $(\"p.price .woocommerce-Price-amount\").first().text().trim()?.replace(/\\s+/g, \" \")?.replace(/,/g, \".\")?.replace(/[^\\d.]/g, \"\")", 
    "field__price__code_gen_completed": True,    
    "field__price__ok_on_1_link": True,      
    "field__price__ok_on_2_link": True,      
    "field__price__ok_on_3_link": True,      
    "choosed_selector_field_imageLink": ".woocommerce-product-gallery img.wp-post-image", 
    "field__imageLink__code": "const imageLink = $(\".woocommerce-product-gallery img.wp-post-image\").first()?.attr(\"data-large_image\") || $(\".woocommerce-product-gallery img.wp-post-image\").first()?.attr(\"data-src\") || $(\".woocommerce-product-gallery img.wp-post-image\").first()?.attr(\"src\") || \"\"",  
    "field__imageLink__code_gen_completed": True,
    "field__imageLink__ok_on_1_link": True,  
    "field__imageLink__ok_on_2_link": True,  
    "field__imageLink__ok_on_3_link": True,  
    "choosed_selector_field_article": ".product_meta .sku_wrapper .sku",
    "field__article__code": "const article = $(\".product_meta .sku_wrapper .sku\").first().text().trim()",
    "field__article__code_gen_completed": True,
    "field__article__ok_on_1_link": True,    
    "field__article__ok_on_2_link": True,    
    "field__article__ok_on_3_link": True,
    "choosed_selector_field_stock": "form.cart .single_add_to_cart_button, form.cart button.single_add_to_cart_button, button.single_add_to_cart_button",
    "field__stock__code": "const addToCartText = $(\"form.cart .single_add_to_cart_button, form.cart button.single_add_to_cart_button, button.single_add_to_cart_button\")?.first().text().trim(); const stock = addToCartText?.includes(\"В корзину\") ? \"InStock\" : \"OutOfStock\";",
    "field__stock__code_gen_completed": True,    
    "field__stock__ok_on_1_link": True,      
    "field__stock__ok_on_2_link": True,      
    "field__stock__ok_on_3_link": True      
}



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
    ],
    "stock": []
}




def get_fields_description(used_fields_and_selectors_test):
    """
    Return a comma-separated list of field names.

    Examples:
      {"name": [...], "price": [...]} -> "name, price"
      ["name", "price"] -> "name, price"
    """
    fields = (
        used_fields_and_selectors_test.keys()
        if hasattr(used_fields_and_selectors_test, "keys")
        else used_fields_and_selectors_test
    )
    result = ", ".join(map(str, fields))
    result = result + ", link, timestamp"
    return result



def build_all_code_parseCard(result_build_parseCard, result_get_fields_description):
    result = """    async parseCard(set: SetType, cacher: Cacher<ResultItem[]>) {
        let items: ResultItem[] = []

        const data = await this.makeRequest(set.query);
        const $ = cheerio.load(data);

""" + result_build_parseCard + """
        const link = set.query;
        const timestamp = getTimestamp()

        const item: ResultItem = {
            """ + result_get_fields_description + """
        }
        items.push(item);

        cacher.cache = items
        return items;
    }
    """

    return result























def build_parseCard(input_data, used_fields_and_selectors):
    # Обрабатываю строки кода
    result_build_parseCard = build_parseCard_get_all_generated_code_str(
        input_data=input_data,
        used_fields_and_selectors=used_fields_and_selectors,
    )
    # Добавляем 4 пробела в начало каждой строки
    result_build_parseCard = textwrap.indent(result_build_parseCard, '        ')

    # Ключи ипользованных полей
    result_get_fields_description = get_fields_description(used_fields_and_selectors)

    # Весь код parseCard
    result_build_all_code_parseCard = build_all_code_parseCard(result_build_parseCard, result_get_fields_description)

    print(f"\n📗 Результат генерации parseCard 📗\n")
    print(result_build_all_code_parseCard)

    return (result_build_all_code_parseCard, result_get_fields_description)












if __name__ == "__main__":
    build_parseCard(input_data_test, used_fields_and_selectors_test)







"""

const name = $("h1.product_title.entry-title").first().text().trim()
const price = $("p.price .woocommerce-Price-amount").first().text().trim()?.replace(/\s+/g, " ")?.replace(/,/g, ".")?.replace(/[^\d.]/g, "")
const imageLink = $(".woocommerce-product-gallery img.wp-post-image").first()?.attr("data-large_image") || $(".woocommerce-product-gallery img.wp-post-image").first()?.attr("data-src") || $(".woocommerce-product-gallery img.wp-post-image").first()?.attr("src") || ""    
const article = $(".product_meta .sku_wrapper .sku").first().text().trim()

"""