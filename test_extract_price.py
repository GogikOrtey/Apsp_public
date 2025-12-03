# import re
# from lxml import html as html_lx, etree


# # Извлекает селекторы цены
# # Перед этим очистив html от мусорных спецсимволов
# def handle_selector_price(html, finding_element):
#     # 1. Очистка HTML
#     def clean_html(text: str) -> str:
#         text = text.replace("&nbsp;", " ").replace("\xa0", " ")
#         text = re.sub(r"[\u200b\u200e\u200f\r\n\t]+", " ", text)
#         return text.strip()

#     # 2. Нормализация чисел/цен
#     def normalize_price(s: str) -> str:
#         if not s:
#             return ""
#         s = s.strip().lower()
#         s = re.sub(r"[^\d,\.]", "", s)
#         s = re.sub(r"[^\d]", "", s)
#         return s

#     # 3. Функция построения CSS-пути для элемента
#     def get_css_path(element):
#         path = []
#         while element is not None and isinstance(element.tag, str):
#             selector = element.tag

#             # Если есть ID — уникальный селектор
#             if 'id' in element.attrib:
#                 selector = f"#{element.attrib['id']}"
#                 path.append(selector)
#                 break

#             # Если есть классы
#             if 'class' in element.attrib:
#                 classes = element.attrib['class'].split()
#                 selector += '.' + '.'.join(classes)

#             # nth-of-type среди сиблингов
#             parent = element.getparent()
#             if parent is not None:
#                 same_tag_siblings = [sib for sib in parent if isinstance(sib.tag, str) and sib.tag == element.tag]
#                 if len(same_tag_siblings) > 1:
#                     index = same_tag_siblings.index(element) + 1
#                     selector += f":nth-of-type({index})"

#             path.append(selector)
#             element = parent

#         return " > ".join(reversed(path))

#     # 4. Основная функция поиска селекторов по цене
#     def find_price_selectors(html: str, finding_element: str, return_all_selectors: bool = False):
#         html = clean_html(html)
#         target_norm = normalize_price(finding_element)

#         tree = html_lx.fromstring(html)
#         selectors = []

#         for elem in tree.iter():
#             # Пропускаем комментарии, доктайпы
#             if not isinstance(elem.tag, str):
#                 continue

#             # Проверяем текст
#             text = elem.text_content().strip() if elem.text_content() else ""
#             if text and normalize_price(text) == target_norm:
#                 selector = get_css_path(elem)
#                 if return_all_selectors:
#                     selectors.append(selector)
#                 else:
#                     return selector

#             # Проверяем все атрибуты
#             for attr_name, attr_val in elem.attrib.items():
#                 if isinstance(attr_val, str) and normalize_price(attr_val) == target_norm:
#                     selector = f"{get_css_path(elem)}[{attr_name}]"
#                     if return_all_selectors:
#                         selectors.append(selector)
#                     else:
#                         return selector

#         if return_all_selectors:
#             return selectors if selectors else None

#         return None
    
#     # Вернуть все селекторы
#     all_selectors = find_price_selectors(html, finding_element, return_all_selectors=True)
#     # print(all_selectors)

#     # # Вернуть первый найденный селектор
#     # first_selector = find_price_selectors(html, finding_element)
#     # print(first_selector)

#     return all_selectors




# with open("test.html", "r", encoding="utf-8") as f:
#     html = f.read()

# finding_element = "10 320"

# print(handle_selector_price(html, finding_element)[0])