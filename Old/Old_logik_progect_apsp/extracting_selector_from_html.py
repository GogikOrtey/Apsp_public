# Здесь собраны все функции, нужные для того что бы получить лучший селектор текстового элемента, из переданного html
# Можно использовать так: 
# selector_result = get_css_selector_from_text_value_element(html, substring)

# Подключение всех библиотек
from import_all_libraries import * 

#############################################

isPrint = False
# isPrint = True 

# region Доп. методы

def clean_html(text: str) -> str:
    if not text:
        return ""
    text = text.replace("&nbsp;", " ").replace("\xa0", " ")
    text = re.sub(r"[\u200b\u200e\u200f\r\n\t]+", " ", text)
    return text.strip()

def normalize_price(s: str) -> str:
    if not s:
        return ""
    s = s.strip().lower()
    s = clean_html(s)
    s = re.sub(r"[^\d,\.]", "", s)
    s = re.sub(r"[^\d]", "", s)
    return s



from difflib import SequenceMatcher



# Здесь хранятся html страницы (типо кеша)
content_html = {
    "simple": [
        # {
        #     "link": "",
        #     "html_content": ""  
        # },    
    ]
}


# region Поиск селекторов
def find_text_selector(
    html: str,
    text: str,
    exact: bool = True,
    return_all_selectors: bool = False,
    isPriceHandle: bool = False,
    allow_complex_classes: bool = False,
    use_table_context: bool = True
):
    # Игнорируем атрибуты, содержащие эти подстроки, при поиске css пути
    IGNORED_SUBSTRS = ["data", "src", "href", "alt", "title", "content", "title"]
    PRIORITY_ATTRS = ["name", "property", "itemprop", "id"]

    if isPriceHandle:
        html = clean_html(html)
        text = normalize_price(text)

    DANGEROUS_CHARS = set(':[]/%%()#') 

    def class_is_dangerous(cls: str) -> bool:
        if not cls:
            return False
        if any(ch in cls for ch in DANGEROUS_CHARS):
            return True
        if '"' in cls or "'" in cls or " " in cls:
            return True
        if cls[0].isdigit():
            return True
        return False

    def escape_attr_value(val: str) -> str:
        return val.replace('"', '\\"')

    def get_simple_table_selector(table_element, target_cell):
        """Создает простой селектор для таблиц"""
        # Находим строку, содержащую целевую ячейку
        row = target_cell.find_parent('tr')
        if not row:
            return None
        
        # Получаем все ячейки в строке
        cells = row.find_all(['td', 'th'])
        if len(cells) < 2:
            return None
        
        # Находим индекс целевой ячейки
        target_index = None
        for idx, cell in enumerate(cells, 1):
            if target_cell in cell.find_all(recursive=True) or target_cell == cell:
                target_index = idx
                break
        
        if not target_index:
            return None
        
        # Ищем ячейку с описанием (не целевую)
        description_text = None
        for cell in cells:
            cell_text = cell.get_text(strip=True)
            if cell_text and text not in cell_text:
                description_text = cell_text
                break
        
        if not description_text:
            return None
        
        # Создаем базовый селектор для таблицы
        table_selector = get_css_path_basic(table_element)
        
        # Экранируем текст описания
        desc_escaped = description_text.replace('"', '\\"')
        
        # Создаем простой селектор
        return f'{table_selector} tr:has(td:contains("{desc_escaped}")) > td:nth-child({target_index})'

    def get_css_path_basic(element):
        """Упрощенный путь без :nth-of-type"""
        path = []
        current_element = element
        
        while current_element and current_element.name and current_element.name != "[document]":
            selector = current_element.name
            
            # ID имеет высший приоритет
            if current_element.has_attr("id"):
                element_id = current_element["id"]
                if element_id and not class_is_dangerous(element_id):
                    path.append(f"#{element_id}")
                    break
            
            # Добавляем безопасные классы
            if current_element.has_attr("class"):
                cls_parts = []
                for cls in current_element.get("class", []):
                    if cls and not class_is_dangerous(cls):
                        cls_parts.append(f'.{cls}')
                if cls_parts:
                    selector += "".join(cls_parts)
            
            # Добавляем другие значимые атрибуты
            added_attr = False
            for attr_name in PRIORITY_ATTRS:
                if current_element.has_attr(attr_name):
                    attr_value = current_element[attr_name]
                    if isinstance(attr_value, list):
                        attr_value = " ".join(attr_value)
                    if isinstance(attr_value, str) and attr_value.strip():
                        selector += f'[{attr_name}="{escape_attr_value(attr_value.strip())}"]'
                        added_attr = True
                        break
            
            path.append(selector)
            current_element = current_element.parent
        
        return " > ".join(reversed(path))

    def get_css_path(element, use_table_context=True):
        """Основная функция построения CSS пути с обработкой таблиц"""
        # Проверяем, находится ли элемент внутри таблицы
        if use_table_context:
            table_element = element.find_parent('table')
            if table_element:
                # Пытаемся найти ячейку таблицы, содержащую элемент
                cell_element = element
                while cell_element and cell_element.name not in ['td', 'th']:
                    cell_element = cell_element.parent
                    if not cell_element or cell_element.name == 'table':
                        break
                
                if cell_element and cell_element.name in ['td', 'th']:
                    table_selector = get_simple_table_selector(table_element, cell_element)
                    if table_selector:
                        return table_selector
        
        # Если не таблица или не удалось создать селектор для таблицы, используем стандартный путь
        path = []
        current_element = element
        
        while current_element and current_element.name and current_element.name != "[document]":
            selector = current_element.name

            # ID имеет высший приоритет
            if current_element.has_attr("id"):
                element_id = current_element["id"]
                if element_id and not class_is_dangerous(element_id):
                    path.append(f"#{element_id}")
                    break

            # Классы
            if current_element.has_attr("class"):
                cls_parts = []
                for cls in current_element.get("class", []):
                    if not cls:
                        continue
                    if class_is_dangerous(cls):
                        if allow_complex_classes:
                            cls_parts.append(f'[class*="{escape_attr_value(cls)}"]')
                        else:
                            continue
                    else:
                        cls_parts.append(f'.{cls}')
                if cls_parts:
                    selector += "".join(cls_parts)

            # Проверяем наличие значимых атрибутов
            has_significant_attr = any(
                (
                    attr in PRIORITY_ATTRS or not any(sub in attr for sub in IGNORED_SUBSTRS)
                )
                for attr in current_element.attrs.keys()
            )

            if not has_significant_attr and current_element.parent:
                siblings = [sib for sib in current_element.parent.find_all(current_element.name, recursive=False) 
                          if sib.name == current_element.name]
                if len(siblings) > 1:
                    try:
                        index = siblings.index(current_element) + 1
                        selector += f":nth-of-type({index})"
                    except ValueError:
                        pass

            path.append(selector)
            current_element = current_element.parent

        return " > ".join(reversed(path))

    def normalize_text(s):
        return " ".join(s.split())

    def similarity(a, b):
        return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()

    def make_selector(el, base_selector, attr_name):
        parts = [base_selector]
        is_ignored = any(sub in attr_name for sub in IGNORED_SUBSTRS)

        element_id = el.get("id")
        has_id_in_base = element_id and f"#{element_id}" in base_selector

        if is_ignored:
            for alt_attr in PRIORITY_ATTRS:
                if el.has_attr(alt_attr):
                    if alt_attr == "id" and has_id_in_base:
                        continue
                    val = el.get(alt_attr)
                    if isinstance(val, list):
                        val = " ".join(val)
                    if isinstance(val, str):
                        parts.append(f'[{alt_attr}="{escape_attr_value(val.strip())}"]')
                    break
            parts.append(f'[{attr_name}]')
        else:
            val = el.get(attr_name)
            if isinstance(val, list):
                val = " ".join(val)
            if isinstance(val, str):
                if attr_name == "id" and has_id_in_base:
                    return "".join(parts)
                parts.append(f'[{attr_name}="{escape_attr_value(val.strip())}"]')
            else:
                parts.append(f'[{attr_name}]')

        return "".join(parts)

    # --- Парсим HTML ---
    soup = BeautifulSoup(html, "html.parser")
    selectors = []

    # --- Основной поиск (точное совпадение) ---
    for el in soup.find_all(True):
        element_text = el.get_text(strip=True)
        if element_text:
            check_value = normalize_price(element_text) if isPriceHandle else element_text
            match = (text == check_value) if exact else (text in check_value)
            if match:
                selector = get_css_path(el, use_table_context)
                if return_all_selectors:
                    selectors.append(selector)
                else:
                    return selector

        for attr_name, attr_val in el.attrs.items():
            if isinstance(attr_val, list):
                attr_val = " ".join(attr_val)
            if isinstance(attr_val, str):
                check_value = normalize_price(attr_val) if isPriceHandle else attr_val
                match = (text == check_value) if exact else (text in check_value)
                if match:
                    base_selector = get_css_path(el, use_table_context)
                    selector = make_selector(el, base_selector, attr_name)
                    if return_all_selectors:
                        selectors.append(selector)
                    else:
                        return selector

    # --- Нестрогий поиск ---
    if not selectors:
        threshold = 0.7
        for el in soup.find_all(True):
            element_text = el.get_text(strip=True)
            if element_text:
                check_value = normalize_price(element_text) if isPriceHandle else element_text
                score = similarity(text, check_value)
                if score >= threshold:
                    selector = get_css_path(el, use_table_context)
                    if return_all_selectors:
                        selectors.append(selector)
                    else:
                        return selector

            for attr_name, attr_val in el.attrs.items():
                if isinstance(attr_val, list):
                    attr_val = " ".join(attr_val)
                if isinstance(attr_val, str):
                    check_value = normalize_price(attr_val) if isPriceHandle else attr_val
                    score = similarity(text, check_value)
                    if score >= threshold:
                        base_selector = get_css_path(el, use_table_context)
                        selector = make_selector(el, base_selector, attr_name)
                        if return_all_selectors:
                            selectors.append(selector)
                        else:
                            return selector

    if return_all_selectors:
        return selectors if selectors else None
    return None






# # region Поиск селекторов
# def find_text_selector(
#     html: str,
#     text: str,
#     exact: bool = True,
#     return_all_selectors: bool = False,
#     isPriceHandle: bool = False,
#     allow_complex_classes: bool = False,
#     use_table_context: bool = True,
#     isPrint_mr: bool = True ##################################################
# ) -> Optional[str | List[str]]:
    
#     # Игнорируем атрибуты, содержащие эти подстроки, при поиске css пути
#     IGNORED_SUBSTRS = ["data", "src", "href", "alt", "title", "content"]
#     # Приоритетные атрибуты для уникальности
#     PRIORITY_ATTRS = ["name", "property", "itemprop", "id"]

#     if isPrint_mr:
#         print(f"--- Начинаем поиск селектора ---")
#         print(f"Искомый текст: '{text}'")
#         print(f"Точное совпадение: {exact}")
#         print(f"Контекст таблицы: {use_table_context}")

#     if isPriceHandle:
#         html = clean_html(html)
#         text = normalize_price(text)

#     DANGEROUS_CHARS = set(':[]/%%()#') 

#     def class_is_dangerous(cls: str) -> bool:
#         if not cls:
#             return False
#         if any(ch in cls for ch in DANGEROUS_CHARS):
#             return True
#         if '"' in cls or "'" in cls or " " in cls:
#             return True
#         if cls[0].isdigit():
#             return True
#         return False

#     def escape_attr_value(val: str) -> str:
#         # Экранирование кавычек внутри значения атрибута
#         return val.replace('"', '\\"')

#     def get_simple_table_selector(table_element: Tag, target_cell: Tag) -> Optional[str]:
#         """Создает простой селектор для таблиц на основе описания и позиции ячейки."""
        
#         # ... (Логика поиска строки, ячеек и target_index - без изменений) ...
#         row = target_cell.find_parent('tr')
#         if not row:
#             if isPrint_mr: print("LOG: Table selector failed: No parent row.")
#             return None
        
#         cells = row.find_all(['td', 'th'], recursive=False)
#         if len(cells) < 2:
#             if isPrint_mr: print("LOG: Table selector failed: Row has less than 2 cells.")
#             return None
        
#         target_index = None
#         for idx, cell in enumerate(cells, 1):
#             if target_cell is cell or target_cell in cell.descendants:
#                 target_index = idx
#                 break
        
#         if not target_index:
#             if isPrint_mr: print("LOG: Table selector failed: Target cell index not found.")
#             return None
        
#         # Ищем ячейку с *уникальным* описанием
#         description_text = None
#         for cell in cells:
#             cell_text = cell.get_text(strip=True)
#             if cell_text and text not in cell_text and len(cell_text) > 5:
#                 description_text = cell_text
#                 break
        
#         if not description_text:
#             if isPrint_mr: print("LOG: Table selector failed: No suitable description text found.")
#             return None
        
#         # Создаем базовый селектор для таблицы
#         table_selector = get_css_path_basic(table_element)
#         desc_escaped = description_text.replace('"', '\\"')
        
#         final_selector = f'{table_selector} tr:has(td:contains("{desc_escaped}")) > *:nth-child({target_index})'
        
#         if isPrint_mr:
#             print(f"LOG: Table selector SUCCESS! Description: '{description_text[:30]}...' -> Selector: '{final_selector}'")
            
#         return final_selector

#     def get_css_path_basic(element: Tag) -> str:
#         """Упрощенный путь без :nth-of-type, используя ID, классы и приоритетные атрибуты."""
#         # ... (Логика get_css_path_basic - без изменений) ...
#         path = []
#         current_element = element
        
#         while current_element and current_element.name and current_element.name != "[document]":
#             selector = current_element.name
            
#             if current_element.has_attr("id"):
#                 element_id = current_element["id"]
#                 if element_id and not class_is_dangerous(element_id):
#                     path.append(f"#{element_id}")
#                     break
            
#             if current_element.has_attr("class"):
#                 cls_parts = []
#                 for cls in current_element.get("class", []):
#                     if cls and not class_is_dangerous(cls):
#                         cls_parts.append(f'.{cls}')
#                 if cls_parts:
#                     selector += "".join(cls_parts)
            
#             for attr_name in PRIORITY_ATTRS:
#                 if current_element.has_attr(attr_name) and attr_name != "id":
#                     attr_value = current_element[attr_name]
#                     if isinstance(attr_value, list):
#                         attr_value = " ".join(attr_value)
#                     if isinstance(attr_value, str) and attr_value.strip():
#                         selector += f'[{attr_name}="{escape_attr_value(attr_value.strip())}"]'
#                         break
            
#             path.append(selector)
#             current_element = current_element.parent
        
#         return " > ".join(reversed(path))

#     def get_css_path(element: Tag, use_table_context: bool) -> str:
#         """Основная функция построения CSS пути с обработкой таблиц."""
        
#         if use_table_context:
#             table_element = element.find_parent('table')
#             if table_element:
#                 cell_element = element
#                 while cell_element and cell_element.name not in ['td', 'th']:
#                     cell_element = cell_element.parent
#                     if not cell_element or cell_element.name == 'table':
#                         break
                
#                 if cell_element and cell_element.name in ['td', 'th']:
#                     table_selector = get_simple_table_selector(table_element, cell_element)
#                     if table_selector:
#                         if isPrint_mr: print(f"LOG: Final base selector from table context: '{table_selector}'")
#                         return table_selector
        
#         # Стандартный путь
#         path = []
#         current_element = element
        
#         while current_element and current_element.name and current_element.name != "[document]":
#             selector = current_element.name

#             if current_element.has_attr("id"):
#                 element_id = current_element["id"]
#                 if element_id and not class_is_dangerous(element_id):
#                     path.append(f"#{element_id}")
#                     break

#             if current_element.has_attr("class"):
#                 cls_parts = []
#                 for cls in current_element.get("class", []):
#                     if not cls: continue
#                     if class_is_dangerous(cls):
#                         if allow_complex_classes:
#                             cls_parts.append(f'[class*="{escape_attr_value(cls)}"]')
#                         else: continue
#                     else: cls_parts.append(f'.{cls}')
#                 if cls_parts: selector += "".join(cls_parts)

#             has_significant_attr = (
#                 current_element.has_attr("id") or 
#                 any(attr in PRIORITY_ATTRS for attr in current_element.attrs.keys()) or
#                 any(
#                     not any(sub in attr for sub in IGNORED_SUBSTRS)
#                     for attr in current_element.attrs.keys()
#                 )
#             )

#             if not has_significant_attr and current_element.parent:
#                 siblings = [sib for sib in current_element.parent.find_all(current_element.name, recursive=False) 
#                           if isinstance(sib, Tag) and sib.name == current_element.name]
#                 if len(siblings) > 1:
#                     try:
#                         index = siblings.index(current_element) + 1
#                         selector += f":nth-of-type({index})"
#                     except ValueError: pass 
            
#             for attr_name in PRIORITY_ATTRS:
#                 if attr_name != "id" and current_element.has_attr(attr_name):
#                     attr_value = current_element[attr_name]
#                     if isinstance(attr_value, list): attr_value = " ".join(attr_value)
#                     if attr_value.strip():
#                         selector += f'[{attr_name}="{escape_attr_value(attr_value.strip())}"]'
#                         break

#             path.append(selector)
#             current_element = current_element.parent

#         final_selector = " > ".join(reversed(path))
#         if isPrint_mr: print(f"LOG: Final base selector (standard): '{final_selector}'")
#         return final_selector

#     def normalize_text(s: str) -> str:
#         """Нормализация текста для сравнения."""
#         return " ".join(s.split())

#     def similarity(a: str, b: str) -> float:
#         """Вычисление коэффициента схожести строк."""
#         return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()

#     def make_selector(el: Tag, base_selector: str, attr_name: str) -> str:
#         """
#         Создает финальный селектор, добавляя [attr="value"] к базовому селектору.
#         """
#         parts = [base_selector]
#         is_ignored = any(sub in attr_name for sub in IGNORED_SUBSTRS)

#         element_id = el.get("id")
#         has_id_in_base = element_id and f"#{element_id}" in base_selector
        
#         added_attr_info = "" # Для логирования

#         if is_ignored:
#             found_alt = False
#             for alt_attr in PRIORITY_ATTRS:
#                 if el.has_attr(alt_attr) and alt_attr != attr_name:
#                     if alt_attr == "id" and has_id_in_base: continue
                        
#                     val = el.get(alt_attr)
#                     if isinstance(val, list): val = " ".join(val)
                    
#                     if isinstance(val, str) and val.strip():
#                         parts.append(f'[{alt_attr}="{escape_attr_value(val.strip())}"]')
#                         added_attr_info = f" (Added PRIORITY: {alt_attr})"
#                         found_alt = True
#                         break
            
#             if not found_alt:
#                 val = el.get(attr_name)
#                 if isinstance(val, list): val = " ".join(val)
                
#                 if isinstance(val, str) and val.strip():
#                     parts.append(f'[{attr_name}="{escape_attr_value(val.strip())}"]')
#                     added_attr_info = f" (Added IGNORED with value: {attr_name})"
#                 else:
#                     parts.append(f'[{attr_name}]')
#                     added_attr_info = f" (Added IGNORED without value: {attr_name})"
        
#         else: # Не игнорируемый атрибут
#             val = el.get(attr_name)
#             if isinstance(val, list): val = " ".join(val)
            
#             if isinstance(val, str) and val.strip():
#                 if attr_name == "id" and has_id_in_base:
#                     added_attr_info = f" (ID already in base selector)"
#                     return "".join(parts)
#                 parts.append(f'[{attr_name}="{escape_attr_value(val.strip())}"]')
#                 added_attr_info = f" (Added NON-IGNORED: {attr_name})"
#             else:
#                 parts.append(f'[{attr_name}]')
#                 added_attr_info = f" (Added NON-IGNORED without value: {attr_name})"
        
#         final_selector = "".join(parts)
#         if isPrint_mr: print(f"LOG: Make selector: {final_selector}{added_attr_info}")
#         return final_selector

#     # --- Парсим HTML ---
#     soup = BeautifulSoup(html, "html.parser")
#     selectors = []

#     # --- Основной поиск (точное совпадение) ---
#     if isPrint_mr: print("\n--- Фаза 1: Точное совпадение (текст / атрибуты) ---")
#     for el in soup.find_all(True):
        
#         # 1. Поиск по тексту элемента
#         element_text = el.get_text(strip=True)
#         if element_text:
#             check_value = normalize_price(element_text) if isPriceHandle else element_text
#             match = (text == check_value) if exact else (text in check_value)
            
#             if match:
#                 if isPrint_mr: 
#                     print(f"LOG: Text MATCH found in tag <{el.name}>. Full text: '{check_value[:50]}...'")
#                 selector = get_css_path(el, use_table_context)
#                 if not selector:
#                     if isPrint_mr: print("LOG: Selector generation FAILED for matched text.")
#                     continue

#                 if return_all_selectors:
#                     selectors.append(selector)
#                 else:
#                     return selector

#         # 2. Поиск по атрибутам элемента
#         for attr_name, attr_val in el.attrs.items():
#             if isinstance(attr_val, list):
#                 attr_val = " ".join(attr_val)
#             if isinstance(attr_val, str):
#                 check_value = normalize_price(attr_val) if isPriceHandle else attr_val
#                 match = (text == check_value) if exact else (text in check_value)
                
#                 if match:
#                     if isPrint_mr: 
#                         print(f"LOG: Attribute MATCH found in tag <{el.name}>. Attr: '{attr_name}', Value: '{check_value[:50]}...'")
                    
#                     base_selector = get_css_path(el, use_table_context)
#                     if not base_selector:
#                         if isPrint_mr: print("LOG: Base selector generation FAILED for matched attribute.")
#                         continue
                        
#                     selector = make_selector(el, base_selector, attr_name) 
                    
#                     if return_all_selectors:
#                         selectors.append(selector)
#                     else:
#                         return selector

#     # --- Нестрогий поиск ---
#     if not exact and not selectors:
#         if isPrint_mr: print("\n--- Фаза 2: Нестрогое совпадение (similarity) ---")
#         threshold = 0.7
#         for el in soup.find_all(True):
            
#             # 1. Поиск по тексту элемента
#             element_text = el.get_text(strip=True)
#             if element_text:
#                 check_value = normalize_price(element_text) if isPriceHandle else element_text
#                 score = similarity(text, check_value)
                
#                 if score >= threshold:
#                     if isPrint_mr: 
#                         print(f"LOG: Similarity MATCH (Score: {score:.2f}) found in tag <{el.name}>. Full text: '{check_value[:50]}...'")
#                     selector = get_css_path(el, use_table_context)
#                     if not selector: continue

#                     if return_all_selectors:
#                         selectors.append(selector)
#                     else:
#                         return selector

#             # 2. Поиск по атрибутам элемента
#             for attr_name, attr_val in el.attrs.items():
#                 if isinstance(attr_val, list):
#                     attr_val = " ".join(attr_val)
#                 if isinstance(attr_val, str):
#                     check_value = normalize_price(attr_val) if isPriceHandle else attr_val
#                     score = similarity(text, check_value)
                    
#                     if score >= threshold:
#                         if isPrint_mr: 
#                             print(f"LOG: Similarity MATCH (Score: {score:.2f}) found in tag <{el.name}>. Attr: '{attr_name}', Value: '{check_value[:50]}...'")
                        
#                         base_selector = get_css_path(el, use_table_context)
#                         if not base_selector: continue
                            
#                         selector = make_selector(el, base_selector, attr_name) 
#                         if return_all_selectors:
#                             selectors.append(selector)
#                         else:
#                             return selector


#     if return_all_selectors:
#         return selectors if selectors else None
    
#     if isPrint_mr: print("\n--- Поиск завершен. Селектор не найден. ---")
#     return None















# region Выбирает один sel
def get_css_selector_from_text_value_element(
        html, 
        finding_element, 
        is_price=False, 
        is_exact=True, 
        is_multiply_sel_result = True,
        is_low_priority_id = False):
    print("")
    if not finding_element:
        print("Поле finding_element пусто, пропускаю получение селектора")
        return ""
    if isPrint: print(f"🟦 Извлекли такие селекторы для строки \"{finding_element}\":")
    all_selectors = find_text_selector(html, 
                                       finding_element, 
                                       return_all_selectors=True, 
                                       isPriceHandle=is_price, 
                                       exact=is_exact,
                                       allow_complex_classes=False
                                       )

    if not all_selectors:
        if isPrint: print("🟡 Не найдено ни одного подходящего селектора")
        return ""

    print(f"Найдено {len(all_selectors)} возможных селекторов")

    valid_selectors = []
    seen_selectors = set()

    # Проверяем каждый селектор
    for selector in all_selectors:

        # Пропускаем дубликаты селектора
        if selector in seen_selectors:
            # if isPrint: print(f"Пропускаем дубликат селектора: {selector}")
            continue
        
        # Сразу метим, что он встречен (даже если потом отфильтруется)
        seen_selectors.add(selector)

        if isPrint: print("")
        if isPrint: print(f"🟢 Проверка селектора: {selector}")
        result_text = get_element_from_selector_universal(html, selector)

        if not result_text:
            if isPrint: print("❌ Элемент по селектору не найден или текст пуст")
            continue

        result_text = str(result_text)

        # Рассчитываем процентное соотношение
        if not is_exact:
            # Находим, какой процент искомого текста составляет от всего найденного
            finding_len = len(finding_element.strip())
            result_len = len(result_text.strip())
            
            if finding_len == 0:
                percent = 0
            else:
                # Проверяем, содержится ли искомый текст в результате
                if finding_element.strip() in result_text.strip():
                    # Находим максимальное вхождение искомого текста
                    matches = re.finditer(re.escape(finding_element.strip()), result_text.strip())
                    max_match_len = max([len(match.group()) for match in matches], default=0)
                    percent = max_match_len / result_len if result_len > 0 else 0
                else:
                    # Если точного вхождения нет, используем коэффициент сходства
                    match_score = compute_match_score_2(result_text, finding_element)
                    percent = match_score * (finding_len / result_len) if result_len > 0 else 0
        else:
            if isPrint: print("is_exact = True, устанавливаем фиктивное значение 1")
            percent = 1.0

        if isPrint: print(f"percent = {percent}")

        # Проверяем совпадение текста
        if finding_element.strip() in result_text.strip():
            match_score = 1.0
            if isPrint: print(f"✅ Строгое совпадение: [{result_text[:250]}]{':250' if len(result_text) > 250 else ''}")
        else:
            match_score = compute_match_score_2(result_text, finding_element)
            if isPrint: print(f"⚪ Совпадение {match_score*100:.1f}%: [{result_text}]")

        # Находим позицию селектора элемента на странице
        pos = html.find(result_text) if result_text else len(html)
        pos_norm = pos / len(html)

        valid_selectors.append({
            "selector": selector,
            "result": result_text,
            "score": match_score,
            "percent": percent,  # Добавляем процентное соотношение
            "pos": pos_norm
        })

    # Если ни один не подошёл
    if not valid_selectors:
        if isPrint: print("🔴 Не найдено корректных селекторов")
        return ""

    # def sort_key(x):
    #     selector = x["selector"]
    #     score = x["score"]
    #     percent = x["percent"]  # Процентное соотношение
    #     pos = x["pos"]
    #     starts_with_id = selector.strip().startswith("#")
    #     length = len(selector)
    #     ends_with_attr = selector.strip().endswith("]")



    #     ################# Вот на это место обратить внимание, при отладке

    #     if not is_low_priority_id:
    #         # Стандартное поведение
    #         return (
    #             -percent,                               # 0️⃣ По убыванию процентного соотношения соответствия исходному тексту (при is_exact=False)
    #             -score,                                 # 1️⃣ По убыванию score
    #             pos,                                    # 2️⃣ По положению в документе (выше = меньше)
    #             not starts_with_id,                     # 3️⃣ Сначала селекторы с #
    #             ends_with_attr,                         # 4️⃣ Селекторы с атрибутами в конце
    #             length if starts_with_id else -length,  # 5️⃣ Короткие селекторы лучше
    #         )
    #     else:
    #         # Требования для is_low_priority_id = True:
    #         # 3️⃣ По starts_with_id обратная: Сначала селекторы БЕЗ #
    #         # 5️⃣ По длине обратная: Сначала ДЛИННЫЕ селекторы
    #         return (
    #             -percent,        # 0️⃣ По убыванию процентного соотношения соответствия исходному тексту (при is_exact=False)
    #             -score,          # 1️⃣ По убыванию score
    #             pos,             # 2️⃣ По положению в документе (выше = меньше)
    #             starts_with_id,  # 3️⃣ Сначала селекторы с #
    #             ends_with_attr,  # 4️⃣ Селекторы с атрибутами в конце
    #             -length,         # 5️⃣ Короткие селекторы лучше
    #         )


    def sort_key(x):
        percent = x["percent"]
        score = x["score"]
        pos = x["pos"]
        sel = x["selector"].strip()
        is_id = sel.startswith("#")
        length = len(sel)

        return (
            -percent,                                                    # 0️⃣ По убыванию процентного соотношения соответствия исходному тексту (при is_exact=False)
            -score,                                                      # 1️⃣ По убыванию score
            pos,                                                         # 2️⃣ По положению в документе (выше = меньше)
            is_id if is_low_priority_id else not is_id,                  # 3️⃣ Сначала селекторы с #
            sel.endswith("]"),                                           # 4️⃣ Селекторы с атрибутами в конце
            length if (is_id and not is_low_priority_id) else -length    # 5️⃣ Короткие селекторы лучше
        )


    valid_selectors.sort(key=sort_key)

    if isPrint:
        print("\n🔵 Отсортированные селекторы:")
        for i, v in enumerate(valid_selectors, start=1):
            print(f"{i}. {v['selector']} score: {v['score']:.2f}, percent: {v['percent']:.2%}, pos: {v['pos']:.4f}")

    best = valid_selectors[0]

    if isPrint: print("")
    if isPrint: print(f"Лучший селектор: {best['selector']} (совпадение {best['score']*100:.1f}%, процент содержания: {best['percent']:.1%})")

    # Дистилляция пути
    # print(f"🔶 Селектор до дистилляции: {best["selector"]}")
    result_distill_selector = simplify_selector_keep_value(html, best["selector"], get_element_from_selector_universal, is_multiply_sel_result)
    # print(f"🔶 Селектор после дистилляции: {result_distill_selector}")
    return result_distill_selector





# region Дистилляция пути
# Дистилляция пути css селектора
# Принимает полный и точный селектор, очищает, и возвращает сокращённый
# удаляя все ненужные звенья
def simplify_selector_keep_value(
    html: str,
    selector: str,
    get_element_from_selector_universal,
    is_multiply_sel_result: bool = True,
):

    """
    Пытается удалить ненужные звенья в селекторе (слева направо).
    Возвращает упрощённый селектор, который гарантированно возвращает
    такое же значение, как исходный селектор, по вызову get_element_from_selector.
    Параметры:
      - html: текст html страницы
      - selector: исходный строгий селектор (через '>')
      - get_element_from_selector: функция (html, selector) -> value (строка)
      - is_multiply_sel_result: True — ориентируемся на количество совпадений,
        False — оставляем старую проверку уникальности (только один результат у селектора)
    """

    def _split_selector_preserving_brackets(selector: str):
        """
        Разбивает селектор по '>' но игнорирует '>' внутри [], (), '' и "".
        Возвращает список звеньев (строк) без лишних пробелов по краям.
        """
        parts = []
        buf = []
        bracket_sq = 0  # []
        bracket_par = 0 # ()
        in_single = False
        in_double = False   

        i = 0
        while i < len(selector):
            ch = selector[i]    

            # переключение состояния строк
            if ch == "'" and not in_double:
                in_single = not in_single
                buf.append(ch)
                i += 1
                continue
            if ch == '"' and not in_single:
                in_double = not in_double
                buf.append(ch)
                i += 1
                continue    

            if not in_single and not in_double:
                if ch == '[':
                    bracket_sq += 1
                    buf.append(ch)
                    i += 1
                    continue
                if ch == ']':
                    if bracket_sq > 0:
                        bracket_sq -= 1
                    buf.append(ch)
                    i += 1
                    continue
                if ch == '(':
                    bracket_par += 1
                    buf.append(ch)
                    i += 1
                    continue
                if ch == ')':
                    if bracket_par > 0:
                        bracket_par -= 1
                    buf.append(ch)
                    i += 1
                    continue    

            # разделитель '>' только если мы не внутри скобок/строк
            if ch == '>' and not in_single and not in_double and bracket_sq == 0 and bracket_par == 0:
                part = ''.join(buf).strip()
                if part != '':
                    parts.append(part)
                buf = []
                # пропускаем возможные пробелы вокруг >
                i += 1
                # skip following spaces
                while i < len(selector) and selector[i].isspace():
                    i += 1
                continue    

            buf.append(ch)
            i += 1  

        last = ''.join(buf).strip()
        if last != '':
            parts.append(last)
        return parts

    # начальная проверка: получаем исходное значение
    try:
        original_value = get_element_from_selector_universal(html, selector)
    except Exception:
        # если исходный селектор уже валидный, но функция кидает — лучше вернуть исходный
        return selector

    # Парсим дерево один раз для оценки уникальности совпадений
    tree = html_lx.fromstring(html)

    # Парсим дерево и фиксируем исходное количество совпадений
    try:
        original_nodes = tree.cssselect(selector)
        original_count = len(original_nodes)
    except Exception:
        original_count = None

    # разбиваем селектор корректно
    parts = _split_selector_preserving_brackets(selector)

    # если один сегмент — возвратим как есть
    if len(parts) <= 1:
        return selector.strip()

    i = 0
    # проходим слева направо. Для каждого индекса пробуем удалить parts[i].
    # Если после удаления результат совпадает с original_value — применяем удаление и
    # остаёмся на том же i (т.к. дальше сдвинулись элементы).
    # Иначе переходим к следующему i.
    while i < len(parts) - 1:
        # нельзя удалить все звенья — должен остаться хотя бы одно
        if len(parts) == 1:
            break

        candidate_parts = parts[:i] + parts[i+1:]
        candidate_selector = " > ".join(candidate_parts)

        # Проверяем количество элементов, которое возвращает кандидат
        try:
            candidate_nodes = tree.cssselect(candidate_selector)
        except Exception:
            candidate_nodes = []

        candidate_value = None
        candidate_match_ok = False

        if is_multiply_sel_result:
            if (
                original_count is not None
                and len(candidate_nodes) == original_count
            ):
                try:
                    candidate_value = get_element_from_selector_universal(
                        html, candidate_selector
                    )
                except Exception:
                    candidate_value = None
                candidate_match_ok = candidate_value == original_value
        else:
            if len(candidate_nodes) == 1:
                try:
                    candidate_value = get_element_from_selector_universal(
                        html, candidate_selector
                    )
                except Exception:
                    candidate_value = None
                candidate_match_ok = candidate_value == original_value

        if candidate_match_ok:
            parts = candidate_parts
            continue
        else:
            # удаление ломает — оставляем звено и идём дальше
            i += 1

    # собрать итоговый селектор
    simplified = " > ".join(parts)
    return simplified


#TODO Потом посмотреть, возможно нужно будет улучшить simplify_selector_keep_value
# добавив в него новые функции, взамен простых и устаревших


# # # region Дистилляция пути
# # Дистилляция пути css селектора
# # Принимает полный и точный селектор, очищает, и возвращает сокращённый
# # удаляя все ненужные звенья
# def simplify_selector_keep_value(
#     html: str,
#     selector: str,
#     get_element_from_selector_universal,
#     is_multiply_sel_result: bool = True,
# ):
#     print(f"🔶🔶 is_multiply_sel_result = {is_multiply_sel_result}")

#     """
#     Пытается удалить ненужные звенья в селекторе (слева направо).
#     Возвращает упрощённый селектор, который гарантированно возвращает
#     такое же значение, как исходный селектор, по вызову get_element_from_selector.
#     Параметры:
#       - html: текст html страницы
#       - selector: исходный строгий селектор (через '>')
#       - get_element_from_selector: функция (html, selector) -> value (строка)
#       - is_multiply_sel_result: True — ориентируемся на количество совпадений,
#         False — оставляем старую проверку уникальности (только один результат у селектора)
#     """

#     def _split_selector_preserving_brackets(selector: str):
#         """
#         Разбивает селектор по '>' но игнорирует '>' внутри [], (), '' и "".
#         Возвращает список звеньев (строк) без лишних пробелов по краям.
#         """
#         parts = []
#         buf = []
#         bracket_sq = 0  # []
#         bracket_par = 0 # ()
#         in_single = False
#         in_double = False   

#         i = 0
#         while i < len(selector):
#             ch = selector[i]    

#             # переключение состояния строк
#             if ch == "'" and not in_double:
#                 in_single = not in_single
#                 buf.append(ch)
#                 i += 1
#                 continue
#             if ch == '"' and not in_single:
#                 in_double = not in_double
#                 buf.append(ch)
#                 i += 1
#                 continue    

#             if not in_single and not in_double:
#                 if ch == '[':
#                     bracket_sq += 1
#                     buf.append(ch)
#                     i += 1
#                     continue
#                 if ch == ']':
#                     if bracket_sq > 0:
#                         bracket_sq -= 1
#                     buf.append(ch)
#                     i += 1
#                     continue
#                 if ch == '(':
#                     bracket_par += 1
#                     buf.append(ch)
#                     i += 1
#                     continue
#                 if ch == ')':
#                     if bracket_par > 0:
#                         bracket_par -= 1
#                     buf.append(ch)
#                     i += 1
#                     continue    

#             # разделитель '>' только если мы не внутри скобок/строк
#             if ch == '>' and not in_single and not in_double and bracket_sq == 0 and bracket_par == 0:
#                 part = ''.join(buf).strip()
#                 if part != '':
#                     parts.append(part)
#                 buf = []
#                 # пропускаем возможные пробелы вокруг >
#                 i += 1
#                 # skip following spaces
#                 while i < len(selector) and selector[i].isspace():
#                     i += 1
#                 continue    

#             buf.append(ch)
#             i += 1  

#         last = ''.join(buf).strip()
#         if last != '':
#             parts.append(last)
#         return parts

#     # начальная проверка: получаем исходное значение
#     try:
#         original_value = get_element_from_selector_universal(html, selector, is_ret_len = True, return_all = True)
#     except Exception:
#         # если исходный селектор уже валидный, но функция кидает — лучше вернуть исходный
#         return selector

#     if isPrint:
#         print(f"original_value = {original_value}")
#         print(f"selector = {selector}")

#     # Парсим дерево один раз для оценки уникальности совпадений
#     # tree = html_lx.fromstring(html)

#     # Парсим дерево и фиксируем исходное количество совпадений
#     try:
#         # original_nodes = tree.cssselect(selector)
#         # original_count = len(original_nodes)
#         original_count = get_element_from_selector_universal(html, selector, is_ret_len = True)["length_elem"]
#     except Exception:
#         original_count = None

#     # разбиваем селектор корректно
#     parts = _split_selector_preserving_brackets(selector)

#     # если один сегмент — возвратим как есть
#     if len(parts) <= 1:
#         return selector.strip()

#     if isPrint:
#         print(f"original_count = {original_count}")

#     i = 0
#     # проходим слева направо. Для каждого индекса пробуем удалить parts[i].
#     # Если после удаления результат совпадает с original_value — применяем удаление и
#     # остаёмся на том же i (т.к. дальше сдвинулись элементы).
#     # Иначе переходим к следующему i.
#     while i < len(parts) - 1:
#         # нельзя удалить все звенья — должен остаться хотя бы одно
#         if len(parts) == 1:
#             break

#         candidate_parts = parts[:i] + parts[i+1:]
#         candidate_selector = " > ".join(candidate_parts)

#         # Проверяем количество элементов, которое возвращает кандидат
#         try:
#             candidate_nodes = get_element_from_selector_universal(html, candidate_selector, return_all = True)
#         except Exception:
#             candidate_nodes = []

#         candidate_value = None
#         candidate_match_ok = False

#         if is_multiply_sel_result:
#             if (
#                 original_count is not None
#                 and len(candidate_nodes) == original_count
#             ):
#                 try:
#                     candidate_value = get_element_from_selector_universal(
#                         html, candidate_selector, is_ret_len = True, return_all = True
#                     )
#                     if isPrint:
#                         print(f"candidate_value = {candidate_value}")
#                 except Exception:
#                     candidate_value = None
#                 candidate_match_ok = candidate_value == original_value
#         else:
#             if len(candidate_nodes) == 1:
#                 try:
#                     candidate_value = get_element_from_selector_universal(
#                         html, candidate_selector, is_ret_len = True, return_all = True
#                     )
#                     if isPrint:
#                         print(f"candidate_value = {candidate_value}")
#                 except Exception:
#                     candidate_value = None
#                 candidate_match_ok = candidate_value == original_value

#         if candidate_match_ok:
#             parts = candidate_parts
#             continue
#         else:
#             # удаление ломает — оставляем звено и идём дальше
#             i += 1

#     # собрать итоговый селектор
#     simplified = " > ".join(parts)
#     return simplified

    

###### Вот эти комментарии ниже - удалить, они устарели

# region Проверка sel


# # Получает и возвращает значение элемента по селектору
# def get_element_from_selector(html, selector, is_ret_len=False):
#     # Проверяем, что селектор не пустой
#     if not selector or not selector.strip():
#         if is_ret_len:
#             return {"result": "", "length_elem": 0}
#         return ""
    
#     tree = html_lx.fromstring(html)
#     search_elem = tree.cssselect(selector)
#     if len(search_elem) == 0:
#         if is_ret_len:
#             return {"result": "", "length_elem": 0}
#         return ""
    
#     element = search_elem[0]

#     # Проверяем, есть ли в селекторе указание атрибута в []
#     attr_match = re.search(r"\[([a-zA-Z0-9_-]+)\]", selector)

#     if attr_match:
#         attr_name = attr_match.group(1)
#         result = element.get(attr_name)
#     else:
#         result = element.text_content().strip()
    
#     if not is_ret_len:
#         return result
#     else:
#         return {"result": result, "length_elem": len(search_elem)}






# # Получает и возвращает значение элемента по селектору
# def get_element_from_selector(html, selector):
#     # Проверяем, что селектор не пустой
#     if not selector or not selector.strip():
#         return ""
    
#     tree = html_lx.fromstring(html)
#     search_elem = tree.cssselect(selector)
#     if len(search_elem) == 0: 
#         # print("🟡 По селектору элемент не найден")
#         return ""
#     element = search_elem[0]

#     # Проверяем, есть ли в селекторе указание атрибута в []
#     attr_match = re.search(r"\[([a-zA-Z0-9_-]+)\]", selector)

#     if attr_match:
#         attr_name = attr_match.group(1)
#         result = element.get(attr_name)
#     else:
#         # Возвращаем только текст внутри элемента
#         result = element.text_content().strip()
    
#     return result


# # TODO Тут эти 3 процедуры устарели, их удалить


# # Возвращает элемент, и его длину
# def get_element_from_selector_and_len(html, selector):
#     # Проверяем, что селектор не пустой
#     if not selector or not selector.strip():
#         return {"result": "", "length_elem": 0}

#     tree = html_lx.fromstring(html)
#     search_elem = tree.cssselect(selector)
#     if len(search_elem) == 0:
#         return {"result": "", "length_elem": 0}
    
#     element = search_elem[0]

#     # Проверяем, есть ли в селекторе указание атрибута в []
#     attr_match = re.search(r"\[([a-zA-Z0-9_-]+)\]", selector)

#     if attr_match:
#         attr_name = attr_match.group(1)
#         result = element.get(attr_name)
#     else:
#         result = element.text_content().strip()
    
#     return {"result": result, "length_elem": len(search_elem)}
#     # Сделал 2 процедуры, потому что на оригинальную get_element_from_selector завязано очень много всего








# # Реализация поиска элемента по селектору, которая умеет искать по сложным аттрибутам, таким как :contains() и :has()
# def get_element_from_selector_universal(html, selector, is_ret_len=False):
#     # Вспомогательная функция для форматирования результата
#     def format_result(result_value, elements_count=0):
#         if is_ret_len:
#             return {"result": result_value, "length_elem": elements_count}
#         return result_value

#     # Пустой селектор → пустая строка
#     if not selector or not selector.strip():
#         return format_result("", 0)

#     # Очищаем селектор от классов с двойным дефисом
#     original_selector = selector.strip()
#     selector = clean_selector_from_double_hyphen(original_selector)

#     ## Можно раскомментировать для отладки
#     # print(f"original_selector = {original_selector}")
#     # print(f"selector = {selector}")
    
#     # Если после очистки селектор стал пустым, возвращаем пустой результат
#     if not selector:
#         return format_result("", 0)

#     sel = ParselSelector(html)

#     # Ищем все атрибуты в селекторе
#     # Сначала находим все атрибуты в квадратных скобках
    
#     # Извлекаем все атрибутные селекторы
#     attr_pattern = r'\[([^\]]+)\]'
#     attr_matches = re.findall(attr_pattern, selector)
    
#     # Разделяем атрибуты на условия и атрибут для извлечения
#     attr_conditions = []
#     extract_attr_name = None
    
#     for attr_match in attr_matches:
#         # Если атрибут имеет формат "attr_name" (без =), то это атрибут для извлечения
#         if '=' not in attr_match:
#             # Это последний атрибут без значения - атрибут для извлечения
#             extract_attr_name = attr_match.strip()
#         else:
#             # Это условие поиска с оператором (например, property="og:image")
#             attr_conditions.append(attr_match)
    
#     # Проверяем, есть ли атрибут в виде [attr] (только имя без значения)
#     # Если пользователь сам указал ::attr(...) или ::text — используем как есть
#     if "::attr(" in selector or "::text" in selector:
#         try:
#             # Получаем все элементы для подсчета
#             all_results = sel.css(selector).getall()
#             result = all_results[0].strip() if all_results and all_results[0] else ""
#             return format_result(result, len(all_results))
#         except Exception:
#             return format_result("", 0)

#     # Если у нас есть атрибут для извлечения (последний атрибут без =)
#     if extract_attr_name:
#         # Создаем селектор для поиска элемента
#         # Берем часть до первого [ и добавляем условия
#         tag_part = selector.split('[')[0].strip()
        
#         # Формируем CSS селектор с условиями
#         if attr_conditions:
#             cleaned_selector = f"{tag_part}[{']['.join(attr_conditions)}]"
#         else:
#             # Если нет условий, но есть атрибут для извлечения
#             # (случай типа "meta[content]")
#             cleaned_selector = tag_part

#         # Проверяем, содержит ли селектор сложные псевдоклассы, которые могут конфликтовать с ::text
#         # К таким относятся: :has, :contains, и другие функциональные псевдоклассы с параметрами
#         complex_pseudo_patterns = [
#             r":has\s*\(",
#             r":contains\s*\(",
#         ]
        
#         has_complex_pseudo = any(re.search(pattern, cleaned_selector, re.IGNORECASE) for pattern in complex_pseudo_patterns)

#         # Функция для преобразования CSS селектора с :contains() и :has() в XPath
#         def css_to_xpath_with_complex_pseudo(css_selector):
#             """
#             Преобразует CSS селектор с :contains() и :has() в XPath
#             Пример: tr:has(td:contains("text")) td:nth-child(2) -> //tr[td[contains(text(), 'text')]]/td[2]
#             """
#             # Обработка селектора вида: tr:has(td:contains("text")) td:nth-child(2)
#             # Паттерн для :has(td:contains("..."))
#             has_contains_pattern = r':has\s*\(\s*td\s*:\s*contains\s*\(\s*"([^"]+)"\s*\)\s*\)'
#             match = re.search(has_contains_pattern, css_selector, re.IGNORECASE)
            
#             if match:
#                 text_to_find = match.group(1)
#                 # Разделим селектор на части: до :has и после
#                 before_has = css_selector[:match.start()].strip()
#                 after_has = css_selector[match.end():].strip()
                
#                 # Извлекаем тег перед :has (например, "tr")
#                 tag_before = before_has.split()[-1] if before_has.split() else "tr"
                
#                 # Экранируем кавычки в тексте для XPath (если есть одинарные - используем двойные и наоборот)
#                 if "'" in text_to_find:
#                     # Если есть одинарные кавычки, используем двойные и экранируем их
#                     text_escaped = text_to_find.replace('"', '&quot;')
#                     xpath = f'//{tag_before}[td[contains(text(), "{text_escaped}")]]'
#                 else:
#                     # Используем одинарные кавычки
#                     xpath = f"//{tag_before}[td[contains(text(), '{text_to_find}')]]"
                
#                 # Обработаем часть после :has (например, " td:nth-child(2)")
#                 if after_has:
#                     after_has = after_has.strip()
#                     # Обработаем nth-child(n) - ищем паттерн вида "td:nth-child(2)"
#                     nth_child_match = re.search(r'(\w+)\s*:\s*nth-child\s*\(\s*(\d+)\s*\)', after_has)
#                     if nth_child_match:
#                         tag = nth_child_match.group(1)
#                         index = nth_child_match.group(2)
#                         xpath += f"/{tag}[{index}]"
#                     else:
#                         # Если нет nth-child, но есть тег и другие селекторы
#                         # Просто добавим остаток, заменив пробелы на /
#                         parts = after_has.split()
#                         for part in parts:
#                             part = part.strip()
#                             if part and not part.startswith(':'):
#                                 xpath += f"/{part}"
                
#                 return xpath
            
#             return None

#         # Если селектор содержит сложные псевдоклассы, используем XPath
#         if has_complex_pseudo:
#             try:
#                 # Преобразуем в XPath и ищем элемент
#                 xpath = css_to_xpath_with_complex_pseudo(cleaned_selector)
#                 if xpath:
#                     tree = html_lx.fromstring(html)
#                     elements = tree.xpath(xpath)
#                     if elements and len(elements) > 0:
#                         result = elements[0].get(extract_attr_name)
#                         result = result.strip() if result else ""
#                         return format_result(result, len(elements))
#                 return format_result("", 0)
#             except Exception:
#                 return format_result("", 0)
#         else:
#             try:
#                 css = f"{cleaned_selector}::attr({extract_attr_name})"
#                 # Получаем все элементы для подсчета
#                 all_results = sel.css(css).getall()
#                 result = all_results[0].strip() if all_results and all_results[0] else ""
#                 return format_result(result, len(all_results))
#             except Exception:
#                 return format_result("", 0)

#     # Функция для безопасного извлечения текста через XPath для сложных селекторов
#     def extract_via_xpath():
#         try:
#             # Используем уже импортированный html_lx через import_all_libraries
#             tree = html_lx.fromstring(html)
            
#             # Пытаемся преобразовать CSS в XPath
#             xpath = css_to_xpath_with_complex_pseudo(selector)
            
#             if xpath:
#                 # Используем XPath для поиска элементов
#                 elements = tree.xpath(xpath)
#                 if elements and len(elements) > 0:
#                     result = elements[0].text_content()
#                     result = result.strip() if result else ""
#                     return result, len(elements)
            
#             return "", 0
#         except Exception as e:
#             # В случае ошибки возвращаем пустую строку
#             return "", 0

#     # Функция для безопасного извлечения текста через HTML элемент
#     def extract_text_via_html():
#         try:
#             # Получаем все элементы для подсчета
#             all_elements = sel.css(selector).getall()
#             if all_elements and len(all_elements) > 0:
#                 from lxml import html as html_lx
#                 elem_tree = html_lx.fromstring(all_elements[0])
#                 result = elem_tree.text_content()
#                 result = result.strip() if result else ""
#                 return result, len(all_elements)
#             return "", 0
#         except Exception:
#             return "", 0

#     # Проверяем, содержит ли селектор сложные псевдоклассы, которые могут конфликтовать с ::text
#     complex_pseudo_patterns = [
#         r":has\s*\(",
#         r":contains\s*\(",
#     ]
    
#     has_complex_pseudo = any(re.search(pattern, selector, re.IGNORECASE) for pattern in complex_pseudo_patterns)

#     # Если селектор содержит сложные псевдоклассы, используем XPath
#     if has_complex_pseudo:
#         result, count = extract_via_xpath()
#         if result:
#             return format_result(result, count)
#         # Если XPath не сработал, пробуем через HTML
#         result, count = extract_text_via_html()
#         return format_result(result, count)

#     # Иначе — пробуем стандартный способ с ::text
#     try:
#         css = selector + "::text"
#         # Получаем все элементы для подсчета
#         all_results = sel.css(css).getall()
#         result = all_results[0].strip() if all_results and all_results[0] else ""
#         return format_result(result, len(all_results))
#     except Exception:
#         # Если добавление ::text вызвало ошибку, пробуем другой способ
#         result, count = extract_text_via_html()
#         return format_result(result, count)







# Реализация поиска элемента по селектору, которая умеет искать по сложным атрибутам, таким как :contains() и :has()
# Умеет возвращать все результаты
def get_element_from_selector_universal(html, selector, is_ret_len=False, return_all=False):
    # Вспомогательная функция для форматирования результата
    def format_result(result_value, elements_count=0, all_results=None):
        if return_all and all_results is not None:
            # Если нужно вернуть все результаты
            if is_ret_len:
                return {"result": all_results, "length_elem": elements_count}
            return all_results
        elif is_ret_len:
            return {"result": result_value, "length_elem": elements_count}
        return result_value

    # Пустой селектор → пустая строка
    if not selector or not selector.strip():
        return format_result("", 0, [])

    # Очищаем селектор от классов с двойным дефисом
    selector = selector.strip()
    if ".--" in selector:
        selector = clean_selector_from_double_hyphen(selector)
        # print("Внимание! Не отлаженный код! Возможны ошибки")

    # # Можно раскомментировать для отладки
    # print(f"original_selector = {selector}")
    # print(f"selector = {selector}")
    
    # Если после очистки селектор стал пустым, возвращаем пустой результат
    if not selector:
        return format_result("", 0, [])

    sel = ParselSelector(html)

    # Ищем все атрибуты в селекторе
    # Сначала находим все атрибуты в квадратных скобках
    
    # Извлекаем все атрибутные селекторы
    attr_pattern = r'\[([^\]]+)\]'
    attr_matches = re.findall(attr_pattern, selector)
    
    # Разделяем атрибуты на условия и атрибут для извлечения
    attr_conditions = []
    extract_attr_name = None
    
    for attr_match in attr_matches:
        # Если атрибут имеет формат "attr_name" (без =), то это атрибут для извлечения
        if '=' not in attr_match:
            # Это последний атрибут без значения - атрибут для извлечения
            extract_attr_name = attr_match.strip()
        else:
            # Это условие поиска с оператором (например, property="og:image")
            attr_conditions.append(attr_match)
    
    # Проверяем, есть ли атрибут в виде [attr] (только имя без значения)
    # Если пользователь сам указал ::attr(...) или ::text — используем как есть
    if "::attr(" in selector or "::text" in selector:
        try:
            # Получаем все элементы для подсчета
            all_results = sel.css(selector).getall()
            # Очищаем результаты от лишних пробелов
            cleaned_results = [r.strip() if r else "" for r in all_results]
            result = cleaned_results[0] if cleaned_results else ""
            return format_result(result, len(cleaned_results), cleaned_results)
        except Exception:
            return format_result("", 0, [])

    # Если у нас есть атрибут для извлечения (последний атрибут без =)
    if extract_attr_name:
        # Создаем селектор для поиска элемента
        # Берем часть до первого [ и добавляем условия
        tag_part = selector.split('[')[0].strip()
        
        # Формируем CSS селектор с условиями
        if attr_conditions:
            cleaned_selector = f"{tag_part}[{']['.join(attr_conditions)}]"
        else:
            # Если нет условий, но есть атрибут для извлечения
            # (случай типа "meta[content]")
            cleaned_selector = tag_part

        # Проверяем, содержит ли селектор сложные псевдоклассы, которые могут конфликтовать с ::text
        # К таким относятся: :has, :contains, и другие функциональные псевдоклассы с параметрами
        complex_pseudo_patterns = [
            r":has\s*\(",
            r":contains\s*\(",
        ]
        
        has_complex_pseudo = any(re.search(pattern, cleaned_selector, re.IGNORECASE) for pattern in complex_pseudo_patterns)

        # Функция для преобразования CSS селектора с :contains() и :has() в XPath
        def css_to_xpath_with_complex_pseudo(css_selector):
            """
            Преобразует CSS селектор с :contains() и :has() в XPath
            Пример: tr:has(td:contains("text")) td:nth-child(2) -> //tr[td[contains(text(), 'text')]]/td[2]
            """
            # Обработка селектора вида: tr:has(td:contains("text")) td:nth-child(2)
            # Паттерн для :has(td:contains("..."))
            has_contains_pattern = r':has\s*\(\s*td\s*:\s*contains\s*\(\s*"([^"]+)"\s*\)\s*\)'
            match = re.search(has_contains_pattern, css_selector, re.IGNORECASE)
            
            if match:
                text_to_find = match.group(1)
                # Разделим селектор на части: до :has и после
                before_has = css_selector[:match.start()].strip()
                after_has = css_selector[match.end():].strip()
                
                # Извлекаем тег перед :has (например, "tr")
                tag_before = before_has.split()[-1] if before_has.split() else "tr"
                
                # Экранируем кавычки в тексте для XPath (если есть одинарные - используем двойные и наоборот)
                if "'" in text_to_find:
                    # Если есть одинарные кавычки, используем двойные и экранируем их
                    text_escaped = text_to_find.replace('"', '&quot;')
                    xpath = f'//{tag_before}[td[contains(text(), "{text_escaped}")]]'
                else:
                    # Используем одинарные кавычки
                    xpath = f"//{tag_before}[td[contains(text(), '{text_to_find}')]]"
                
                # Обработаем часть после :has (например, " td:nth-child(2)")
                if after_has:
                    after_has = after_has.strip()
                    # Обработаем nth-child(n) - ищем паттерн вида "td:nth-child(2)"
                    nth_child_match = re.search(r'(\w+)\s*:\s*nth-child\s*\(\s*(\d+)\s*\)', after_has)
                    if nth_child_match:
                        tag = nth_child_match.group(1)
                        index = nth_child_match.group(2)
                        xpath += f"/{tag}[{index}]"
                    else:
                        # Если нет nth-child, но есть тег и другие селекторы
                        # Просто добавим остаток, заменив пробелы на /
                        parts = after_has.split()
                        for part in parts:
                            part = part.strip()
                            if part and not part.startswith(':'):
                                xpath += f"/{part}"
                
                return xpath
            
            return None

        # Если селектор содержит сложные псевдоклассы, используем XPath
        if has_complex_pseudo:
            try:
                # Преобразуем в XPath и ищем элемент
                xpath = css_to_xpath_with_complex_pseudo(cleaned_selector)
                if xpath:
                    tree = html_lx.fromstring(html)
                    elements = tree.xpath(xpath)
                    if elements:
                        # Получаем все значения атрибута
                        all_values = []
                        for elem in elements:
                            value = elem.get(extract_attr_name)
                            if value is not None:
                                all_values.append(value.strip())
                            else:
                                all_values.append("")
                        
                        result = all_values[0] if all_values else ""
                        return format_result(result, len(all_values), all_values)
                return format_result("", 0, [])
            except Exception:
                return format_result("", 0, [])
        else:
            try:
                css = f"{cleaned_selector}::attr({extract_attr_name})"
                # Получаем все элементы
                all_results = sel.css(css).getall()
                # Очищаем результаты от лишних пробелов
                cleaned_results = [r.strip() if r else "" for r in all_results]
                result = cleaned_results[0] if cleaned_results else ""
                return format_result(result, len(cleaned_results), cleaned_results)
            except Exception:
                return format_result("", 0, [])

    # Функция для безопасного извлечения текста через XPath для сложных селекторов
    def extract_via_xpath():
        try:
            # Используем уже импортированный html_lx через import_all_libraries
            tree = html_lx.fromstring(html)
            
            # Пытаемся преобразовать CSS в XPath
            xpath = css_to_xpath_with_complex_pseudo(selector)
            
            if xpath:
                # Используем XPath для поиска элементов
                elements = tree.xpath(xpath)
                if elements:
                    # Получаем текст из всех элементов
                    all_texts = []
                    for elem in elements:
                        text = elem.text_content()
                        all_texts.append(text.strip() if text else "")
                    
                    result = all_texts[0] if all_texts else ""
                    return result, len(all_texts), all_texts
            
            return "", 0, []
        except Exception as e:
            # В случае ошибки возвращаем пустую строку
            return "", 0, []

    # Функция для безопасного извлечения текста через HTML элемент
    def extract_text_via_html():
        try:
            # Получаем все элементы
            all_elements = sel.css(selector).getall()
            if all_elements:
                from lxml import html as html_lx
                all_texts = []
                for elem_html in all_elements:
                    elem_tree = html_lx.fromstring(elem_html)
                    text = elem_tree.text_content()
                    all_texts.append(text.strip() if text else "")
                
                result = all_texts[0] if all_texts else ""
                return result, len(all_texts), all_texts
            return "", 0, []
        except Exception:
            return "", 0, []

    # Проверяем, содержит ли селектор сложные псевдоклассы, которые могут конфликтовать с ::text
    complex_pseudo_patterns = [
        r":has\s*\(",
        r":contains\s*\(",
    ]
    
    has_complex_pseudo = any(re.search(pattern, selector, re.IGNORECASE) for pattern in complex_pseudo_patterns)

    # Если селектор содержит сложные псевдоклассы, используем XPath
    if has_complex_pseudo:
        result, count, all_results = extract_via_xpath()
        if result:
            return format_result(result, count, all_results)
        # Если XPath не сработал, пробуем через HTML
        result, count, all_results = extract_text_via_html()
        return format_result(result, count, all_results)

    # Иначе — пробуем стандартный способ с ::text
    try:
        css = selector + "::text"
        # Получаем все элементы
        all_results = sel.css(css).getall()
        # Очищаем результаты от лишних пробелов
        cleaned_results = [r.strip() if r else "" for r in all_results]
        result = cleaned_results[0] if cleaned_results else ""
        return format_result(result, len(cleaned_results), cleaned_results)
    except Exception:
        # Если добавление ::text вызвало ошибку, пробуем другой способ
        result, count, all_results = extract_text_via_html()
        return format_result(result, count, all_results)








# # Для локальной проверки

# # Поиск селекторов по подстроке на странице
# isPrint = True
# link = "https://gaz-shop78.ru/magazin/search?p=1&gr_smart_search=1&s%5Bname%5D=%D0%9A%D0%BE%D1%82%D1%91%D0%BB"
# finding_text_element = "56"
# html = get_html_from_cache(link)
# selector_result = get_css_selector_from_text_value_element(html, finding_text_element, is_exact=False)
# # selector_result = get_css_selector_from_text_value_element(html, finding_text_element)


# # Извлечение элемента по селектору
# isPrint = True
# link = "https://cosmofun.ru/search/index.php?q=%D0%B2%D0%BE%D0%BB%D0%BE%D1%81&s=&PAGEN_3=2"
# selector = 'a.bxr-item-image-wrap.js-product[href]'
# html = get_html_from_cache(link)
# # element_finded = get_element_from_selector_universal(html, selector)
# element_finded = get_element_from_selector_universal(html, selector, is_ret_len=True)
# print(f"element_finded = {element_finded}")


# # Дистилляция селектора
# isPrint = True
# link = "https://cosmofun.ru/search/index.php?q=%D0%B2%D0%BE%D0%BB%D0%BE%D1%81&s=&PAGEN_3=2"
# html = get_html_from_cache(link)
# original_selector = "div.bxr-element-container > div.bxr-element-image.bxr-img-container > a.bxr-item-image-wrap.js-product[href]"
# result_distill_selector = simplify_selector_keep_value(
#     html, 
#     original_selector, 
#     get_element_from_selector_universal, 
#     is_multiply_sel_result = True
# )
# print(f"result_distill_selector = {result_distill_selector}")