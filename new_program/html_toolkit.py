"""

"""

from bs4 import BeautifulSoup, Comment, NavigableString
from collections import defaultdict

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
from typing import Any
from urllib.parse import urlparse

# from __future__ import annotations

import re
from copy import deepcopy
from urllib.parse import urlsplit, urlunsplit

import subprocess
import tempfile

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Подключение всех библиотек и функций
from import_all_libraries import *
from ChatGPT.OpenAI_ChatGPT import send_message_to_ChatGPT

from reasoning_agent.agent_tools import tool






# Приводит любую ссылку на сайт к виду https://makitaclub.ru
def normalize_url(url: str) -> str:
    """
    Приводит любую ссылку на сайт к виду https://makitaclub.ru
    """
    url = url.strip()

    # Если схема не указана — добавляем https
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urlparse(url)

    domain = parsed.netloc.lower()

    # Убираем www.
    if domain.startswith("www."):
        domain = domain[4:]

    result =  f"https://{domain}"
    print("Нормализовали ссылку, получилось:", result)
    return result







# Очищает html перед отправкой в LLM
def clean_html_universal(html_content: str) -> str:
    """
    Универсальная очистка HTML для LLM (Black-list подход).
    Удаляет скрипты и стили, но сохраняет структуру, мета-теги и контент.
    Длинные тексты и Base64-изображения обрезаются.
    """
    print(f"\nСжимаем страницу\n")

    if not html_content:
        return ""

    soup = BeautifulSoup(html_content, 'html.parser')

    # 1. Удаляем ТОЛЬКО явный технический мусор
    # script - исполняемый код
    # style - глобальные стили (забивают контекст)
    # noscript - дублирующий контент
    for tag in soup(['script', 'style', 'noscript']):
        tag.decompose()

    # 2. Удаляем комментарии (часто содержат старый код)
    for comment in soup.find_all(text=lambda text: isinstance(text, Comment)):
        comment.extract()

    # 3. Обработка SVG
    # Оставляем сам тег SVG (чтобы было видно, что тут иконка), но чистим внутренности
    for svg in soup.find_all('svg'):
        # Сохраняем атрибуты, но удаляем вложенные path, circle и т.д.
        svg.clear() 
        # Можно добавить пометку, что контент удален
        svg.append(NavigableString(""))

    # 4. Обработка атрибутов (Base64 и события)
    for tag in soup.find_all(True):
        attrs_to_modify = {}
        for attr, value in tag.attrs.items():
            # Проверка на Base64 (картинки, зашитые в код)
            # Если значение атрибута - строка и начинается с data:image
            if isinstance(value, str) and value.startswith('data:'):
                if len(value) > 50: # Если это не коротенький пиксель
                    attrs_to_modify[attr] = "<--BASE64_DATA_TRUNCATED-->"

        # Применяем изменения атрибутов
        for attr, val in attrs_to_modify.items():
            if val is None:
                del tag.attrs[attr]
            else:
                tag.attrs[attr] = val

        # Удаляем пустые атрибуты (только те, которые реально пустые: "", [], None)
        # Мы оставляем 0, False и другие значения, которые могут быть важны
        tag.attrs = {
            k: v for k, v in tag.attrs.items() 
            if v is not None and (not hasattr(v, '__len__') or len(v) > 0)
        }

    # 5. Умное обрезание длинного текста (Truncate)
    # Проходимся по всем текстовым узлам
    for text_node in soup.find_all(text=True):
        # Игнорируем пробельные узлы
        if not text_node.strip():
            continue
        
        # Если текст слишком длинный (например, статья или описание)
        if len(text_node) > 250:
            # Оставляем 200 символов сначала и 50 с конца
            head = text_node[:200]
            tail = text_node[-50:]
            # Заменяем содержимое узла
            new_text = f"{head} ... <--TRUNCATED_TEXT--> ... {tail}"
            text_node.replace_with(new_text)

    # 6. Финальная сборка
    # cleaned_html = soup.prettify() # Формирует красивый html код, но нам нужен именно сжатый

    # Сборка компактным методом
    content = str(soup)
    # Удаляем лишние пустые строки, которые могли остаться после decompose()
    cleaned_html = "\n".join([line.strip() for line in content.splitlines() if line.strip()])

    # Вычисление и вывод статистики
    original_len = len(html_content)
    cleaned_len = len(cleaned_html)
    compression_percent = round((1 - cleaned_len / original_len) * 100, 2) if original_len else 0

    print(f"Исходное количество символов: {original_len}")
    print(f"После сжатия: {cleaned_len}")
    print(f"Страница сжалась на {compression_percent}%\n")

    return cleaned_html




# region Max pagination
"""
Оригинал на JS:

    let totalPages = Math.max(...$(".module-pagination__wrapper > a").get().map(item => +$(item).text().trim()).filter(Boolean))

Полная версия на питоне:

    from bs4 import BeautifulSoup

    # Допустим, html_content — это содержимое вашей страницы
    soup = BeautifulSoup(html_content, 'html.parser')

    # 1. Находим все ссылки 'a' внутри контейнера
    links = soup.select(".module-pagination__wrapper > a")

    # 2. Извлекаем текст, очищаем его, переводим в числа и фильтруем (убираем ошибки и пустые значения)
    page_numbers = []
    for item in links:
        text = item.get_text(strip=True)
        if text.isdigit(): # Аналог .filter(Boolean) и проверки на число
            page_numbers.append(int(text))

    # 3. Находим максимум (с проверкой на пустой список, чтобы не было ошибки)
    total_pages = max(page_numbers) if page_numbers else 0

    print(total_pages)

Компактная версия на питоне:

    total_pages = max([int(a.text.strip()) for a in soup.select(".module-pagination__wrapper > a") if a.text.strip().isdigit()] or [0])


"""

# region check_selector_on_cheerio

@tool(
    name="check_selector_on_cheerio",
    description="Считает количество совпадений CSS-селектора в HTML через cheerio (Node.js)",
    args=[
        {
            "name": "selector",
            "type": "str",
            "required": True,
            "description": "CSS-селектор для поиска",
        },
        {
            "name": "html_content",
            "type": "str",
            "required": True,
            "description": "HTML-код, в котором ищем селектор",
        },
    ],
    returns={
        "count": "int — количество найденных элементов по селектору",
    },
    example_args={
        "selector": "div.item",
        "html_content": "<div class='item'></div><div class='other'></div>",
    },
)
def check_selector_on_cheerio(selector: str, html_content: str) -> int:
    """
    Проверяет количество совпадений селектора через cheerio (Node.js).
    HTML кладем во временный файл, чтобы не строить гигантскую команду.
    """
    if not selector:
        raise ValueError("Selector must be non-empty")

    # Записываем HTML во временный файл (удалим после вызова Node)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w", encoding="utf-8") as tmp:
        tmp.write(html_content or "")
        tmp_path = tmp.name

    selector_js = json.dumps(selector)          # безопасно экранируем селектор
    tmp_path_js = json.dumps(tmp_path)          # безопасно экранируем путь

    node_script = (
        "const cheerio=require('cheerio');"
        "const fs=require('fs');"
        f"const html=fs.readFileSync({tmp_path_js}, 'utf-8');"
        "const $=cheerio.load(html);"
        f"const count=$({selector_js}).length;"
        "console.log(count);"
    )

    try:
        result = subprocess.run(
            ["node", "-e", node_script],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            print("Node.js error:", result.stderr.strip())
            return 0

        output = result.stdout.strip()
        try:
            return int(output)
        except ValueError:
            print("Unexpected Node.js output:", output)
            return 0
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


# # Проверка
# url = "https://makitaclub.ru/"
# html_content = get_html_from_cache(url)
# selector = "form.woocommerce-product-search button[type=\"submit\"]"
# result_check_selector = check_selector_on_cheerio(selector, html_content)
# print("result_check_selector =", result_check_selector)













"""

    Нужно будет реализовать:
    - Формирование curl запроса, с body, заголовками и прочим
    - Получение всех запросов в браузере, с их параметрами и частью body (обрезанной в середине)
    - Получение результатов конкретного запроса, с указанием сколько контента из ответа нужно показать
    - Поиск запросов в которых есть вхождение подстроки (как в результатах так и в запросах, это можно будет например контролировать параметрами)    

    - Реализовать инструмент, который возвращает html между двумя найденными вхождениями одинаковых селекторов
    и возможно как-то собирает полный элемент между ними. Возвращает с доп. информацией
        - Да, это прям надо сделать автоматически, для валидации селектора товара

"""














# region get_html_frame
@tool(
    name="get_html_frame",
    description="Строит компактный HTML-фрейм вокруг первого элемента по CSS-селектору, добавляя маркеры TARGET и комментарии об усечениях.",
    args=[
        {"name": "html", "type": "str", "required": True, "description": "Исходный HTML-документ"},
        {"name": "selector", "type": "str", "required": True, "description": "CSS-селектор для поиска target"},
        {"name": "max_frame_chars", "type": "int", "required": False, "description": "Макс. длина итогового HTML-фрейма"},
        {"name": "max_container_text_chars", "type": "int", "required": False, "description": "Лимит текста при выборе контейнера"},
        {"name": "max_container_html_chars", "type": "int", "required": False, "description": "Лимит HTML при выборе контейнера"},
        {"name": "sibling_elems", "type": "int", "required": False, "description": "Сколько соседних элементов сохранять рядом с target"},
        {"name": "max_text_node_chars", "type": "int", "required": False, "description": "Лимит длины текста внутри узла"},
        {"name": "ancestor_levels", "type": "int", "required": False, "description": "Сколько уровней предков сохранять"},
    ],
    returns={
        "html_frame": "str — HTML-фрейм с комментариями TRIMMED_* и маркерами TARGET",
    },
    example_args={
        "html": "<div class='card'><span class='price'>$10</span></div>",
        "selector": ".price",
        "max_frame_chars": 2000,
    },
)
def get_html_frame(
    html: str,
    selector: str,
    *,
    max_frame_chars: int = 3000,           # Максимальная длина всего итогового html-фрейма (после всех сокращений)
    max_container_text_chars: int = 1000,  # Максимальная длина текста контейнера при выборе подходящего родителя
    max_container_html_chars: int = 5000,  # Максимальная длина HTML-кода контейнера при выборе родителя
    sibling_elems: int = 2,                # Количество соседних элементов на том же уровне, которые нужно сохранить рядом с target
    max_text_node_chars: int = 200,        # Максимальная длина текста внутри узла (длинный текст будет обрезан)
    ancestor_levels: int = 3,              # Количество уровней предков target, которые нужно сохранить для контекста
) -> str:
    """
    Создаёт компактный и информативный HTML-фрейм вокруг первого элемента, найденного по CSS-селектору.
    
    Параметры:
    - html: исходный HTML-документ.
    - selector: CSS-селектор для выбора target-элемента.
    - max_frame_chars: максимальная длина итогового HTML-фрейма.
    - max_container_text_chars: лимит текста при выборе контейнера-родителя.
    - max_container_html_chars: лимит HTML-кода при выборе контейнера.
    - sibling_elems: количество соседних элементов target на одном уровне, которые нужно сохранить.
    - max_text_node_chars: максимальная длина текстового содержимого в узле (обрезка длинных текстов).
    - ancestor_levels: сколько уровней предков target сохранить для контекста.
    
    Возвращает:
    - HTML-фрейм с пометками <!--TARGET_START-->, <!--TARGET_END--> и комментариями о вырезанных узлах.
    """

    print(f"\nЗапустили get_html_frame с селектором:", selector)

    try:
        import lxml.html
        from lxml import etree
    except Exception as e:
        raise RuntimeError(
            "This function requires 'lxml' (pip install lxml). "
            "If you prefer BeautifulSoup/soupsieve version, tell me."
        ) from e

    if not html or not selector:
        return ""

    # Parse document
    try:
        doc = lxml.html.fromstring(html)
    except Exception:
        return ""

    # Count total nodes in original document
    orig_nodes = sum(1 for _ in doc.iter())

    # Find target (first match)
    try:
        targets = doc.cssselect(selector)
    except Exception:
        # invalid CSS selector for cssselect
        return ""

    if not targets:
        return ""

    target = targets[0]

    # Helper: compute normalized text length and serialized html length
    def _norm_text_len(el) -> int:
        txt = el.text_content() if hasattr(el, "text_content") else ""
        txt = " ".join(txt.split())
        return len(txt)

    def _html_len(el) -> int:
        try:
            s = etree.tostring(el, encoding="unicode", with_tail=False, method="html")
        except Exception:
            return 10**9
        return len(s)

    SEMANTIC_TAGS = {"section", "article", "main", "header", "aside", "div", "li", "td", "dd", "dl", "table"}
    STOP_TAGS = {"html", "body"}

    # Choose container: climb ancestors, pick first "semantic-ish" node within size thresholds
    # If none fit, pick the smallest ancestor above target (closest) and we will trim harder later.
    chosen = None
    best_fallback = None

    cur = target
    while cur is not None and getattr(cur, "tag", None) is not None:
        tag = (cur.tag or "").lower() if isinstance(cur.tag, str) else ""
        if tag in STOP_TAGS:
            break

        tlen = _norm_text_len(cur)
        hlen = _html_len(cur)

        # fallback: keep the smallest seen so far (closest ancestor tends to be smaller)
        if best_fallback is None:
            best_fallback = cur

        # candidate preference
        if tag in SEMANTIC_TAGS:
            if tlen <= max_container_text_chars and hlen <= max_container_html_chars:
                chosen = cur
                break

        cur = cur.getparent()

    if chosen is not None:
        container = chosen
    elif best_fallback is not None:
        container = best_fallback
    else:
        container = target

    # Count nodes inside chosen container and compute trimmed nodes before/after by source line
    container_nodes = sum(1 for _ in container.iter())
    container_nodes_set = set(container.iter())
    container_line = getattr(container, "sourceline", None)
    container_line = container_line if container_line is not None else -1

    def _sline(node):
        try:
            return node.sourceline
        except Exception:
            return None

    trimmed_outside_before = sum(
        1 for n in doc.iter()
        if n not in container_nodes_set and (_sline(n) is not None and _sline(n) < container_line)
    )
    trimmed_outside_after = sum(
        1 for n in doc.iter()
        if n not in container_nodes_set and (_sline(n) is not None and _sline(n) > container_line)
    )
    trimmed_outside_container = trimmed_outside_before + trimmed_outside_after

    # Compute tree once after container selection
    tree = container.getroottree()

    # Enforce ancestor_levels: container must be at least N levels above target
    cur = target
    for _ in range(ancestor_levels):
        if cur.getparent() is None:
            break
        cur = cur.getparent()

    # cur is now the minimal allowed container
    if cur is not None:
        # if heuristic container is below required level → lift it
        if container is not None:
            # check if container is inside required ancestor
            if tree.getpath(container).startswith(tree.getpath(cur)):
                container = cur

    # Compute absolute xpath of container and target; create relative xpath to find same nodes inside clone
    container_path = tree.getpath(container)
    target_path = tree.getpath(target)

    def _rel_path(abs_path: str) -> str:
        # make path relative to container root
        if abs_path == container_path:
            return ""  # container itself
        if abs_path.startswith(container_path):
            rp = abs_path[len(container_path):]
            return rp  # starts with '/'
        return ""  # should not happen for descendants

    # Choose element siblings around the target (element nodes only)
    def _element_siblings(el, k: int):
        prevs = []
        nxts = []
        p = el.getprevious()
        while p is not None and len(prevs) < k:
            if isinstance(p.tag, str):  # element
                prevs.append(p)
            p = p.getprevious()
        n = el.getnext()
        while n is not None and len(nxts) < k:
            if isinstance(n.tag, str):
                nxts.append(n)
            n = n.getnext()
        return list(reversed(prevs)), nxts

    keep_abs_paths = set()

    # Always keep target
    keep_abs_paths.add(target_path)

    # Keep N ancestors above target
    cur = target.getparent()
    for _ in range(ancestor_levels):
        if cur is None:
            break
        keep_abs_paths.add(tree.getpath(cur))
        cur = cur.getparent()

    # Keep siblings around target
    prevs, nxts = _element_siblings(target, sibling_elems)
    for s in prevs + nxts:
        keep_abs_paths.add(tree.getpath(s))

    # Label heuristic: if target is <dd> keep previous <dt>; if <td> keep previous <th>
    ttag = (target.tag or "").lower() if isinstance(target.tag, str) else ""
    if ttag in {"dd", "td"}:
        p = target.getprevious()
        while p is not None:
            ptag = (p.tag or "").lower() if isinstance(p.tag, str) else ""
            if ttag == "dd" and ptag == "dt":
                keep_abs_paths.add(tree.getpath(p))
                break
            if ttag == "td" and ptag == "th":
                keep_abs_paths.add(tree.getpath(p))
                break
            # stop if we hit a non-empty element that isn't label — prevents scanning too far
            if isinstance(p.tag, str) and _norm_text_len(p) > 0:
                break
            p = p.getprevious()

    # Also keep ancestors from container down to each kept node (so structure remains valid)
    def _add_ancestors_to_container(el):
        cur2 = el
        while cur2 is not None:
            keep_abs_paths.add(tree.getpath(cur2))
            if cur2 is container:
                break
            cur2 = cur2.getparent()

    # Add ancestors for each kept element
    for ap in list(keep_abs_paths):
        try:
            node = tree.xpath(ap)
            if node:
                _add_ancestors_to_container(node[0])
        except Exception:
            pass

    # Clone container subtree
    clone = deepcopy(container)
    # In cloned subtree, find nodes to keep by relative xpaths
    keep_nodes = set([clone])  # always keep root

    # Map: abs->rel, then locate in clone
    for ap in keep_abs_paths:
        rp = _rel_path(ap)
        if rp == "":
            continue
        try:
            found = clone.xpath("." + rp)
        except Exception:
            found = []
        for f in found:
            keep_nodes.add(f)
            # add ancestors inside clone up to clone root
            cur3 = f
            while cur3 is not None:
                keep_nodes.add(cur3)
                if cur3 is clone:
                    break
                cur3 = cur3.getparent()

    # Find target clone to insert markers (using target relative path)
    target_rel = _rel_path(target_path)
    target_clone = None
    if target_rel == "":
        target_clone = clone
    else:
        try:
            found = clone.xpath("." + target_rel)
            target_clone = found[0] if found else None
        except Exception:
            target_clone = None

    # Keep full subtree of target (otherwise inner price nodes get removed)
    if target_clone is not None:
        for el in target_clone.iter():
            keep_nodes.add(el)

    # Подсчёт удалённых узлов по краям (до/после) для каждого родителя
    edge_trim_counts = {}
    for parent in list(clone.iter()):
        children = list(parent)
        if not children:
            continue
        kept_flags = [child in keep_nodes for child in children]
        kept_indices = [i for i, k in enumerate(kept_flags) if k]
        if kept_indices:
            first_keep = min(kept_indices)
            last_keep = max(kept_indices)
            trimmed_before = sum(1 for i in range(first_keep) if not kept_flags[i])
            trimmed_after = sum(1 for i in range(last_keep + 1, len(children)) if not kept_flags[i])
        else:
            # нет сохранённых детей — считаем все удалёнными "сверху"
            trimmed_before = len(children)
            trimmed_after = 0
        if trimmed_before > 0 or trimmed_after > 0:
            edge_trim_counts[parent] = (trimmed_before, trimmed_after)

    # Prune: remove any element not in keep_nodes (post-order) and count removals
    trim_map = defaultdict(int)  # parent_node -> count
    for el in list(clone.iterdescendants())[::-1]:
        if el not in keep_nodes:
            parent = el.getparent()
            if parent is not None:
                trim_map[parent] += 1
                parent.remove(el)

    trimmed_inside_container = sum(trim_map.values())
    outside_trim_info = (trimmed_outside_before, trimmed_outside_after)

    if trimmed_outside_container > 0 or trimmed_inside_container > 0:
        from lxml import etree

        # Локальные маркеры: вставляем внутрь родителя с раздельным счётом сверху/снизу
        for parent, counts in edge_trim_counts.items():
            before_count, after_count = counts
            children = list(parent)
            if children:
                if before_count > 0:
                    parent.insert(0, etree.Comment(f"TRIMMED_BEFORE {before_count} NODES"))
                if after_count > 0:
                    parent.append(etree.Comment(f"TRIMMED_AFTER {after_count} NODES"))
            else:
                # если после очистки родитель пуст
                parent.text = (parent.text or "") + f"<!--TRIMMED_BEFORE {before_count} AFTER {after_count} NODES-->"

    # Sanitize: remove disallowed tags just in case
    DISALLOWED_TAGS = {"script", "style", "noscript", "svg"}
    for el in list(clone.iter()):
        tag = (el.tag or "").lower() if isinstance(el.tag, str) else ""
        if tag in DISALLOWED_TAGS:
            parent = el.getparent()
            if parent is not None:
                parent.remove(el)

    # Attribute cleanup
    ATTR_WHITELIST = {"class", "id", "itemprop", "content", "href", "aria-label", "role", "title"}
    def _clean_href(h: str) -> str:
        try:
            parts = urlsplit(h)
            # drop query+fragment
            return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
        except Exception:
            return h

    for el in clone.iter():
        if not isinstance(el.tag, str):
            continue
        new_attrs = {}
        for k, v in (el.attrib or {}).items():
            lk = k.lower()
            if lk.startswith("on") or lk == "style":
                continue
            if lk in ATTR_WHITELIST:
                if lk == "href" and isinstance(v, str):
                    v = _clean_href(v)
                if isinstance(v, str) and len(v) > 200:
                    v = v[:200] + "…"
                new_attrs[k] = v
                continue
            if lk.startswith("data-"):
                # keep only short data-* (often helpful), but prevent bloat
                if isinstance(v, str) and len(v) <= 80:
                    new_attrs[k] = v
        el.attrib.clear()
        el.attrib.update(new_attrs)

    # Truncate long text nodes
    def _truncate_text(s: str) -> str:
        s2 = " ".join(s.split())
        if len(s2) > max_text_node_chars:
            return s2[:max_text_node_chars] + "…"
        return s2

    for el in clone.iter():
        if el.text:
            el.text = _truncate_text(el.text)
        if el.tail:
            el.tail = _truncate_text(el.tail)

    # Insert markers around target element (as sibling comments)
    if target_clone is not None:
        from lxml import etree
        parent = target_clone.getparent()
        if parent is not None:
            idx = parent.index(target_clone)
            parent.insert(idx, etree.Comment("TARGET_START"))
            parent.insert(idx + 2, etree.Comment("TARGET_END"))
        else:
            # target is root of clone: wrap inside a dummy container
            wrapper = etree.Element("div")
            wrapper.append(etree.Comment("TARGET_START"))
            wrapper.append(clone)
            wrapper.append(etree.Comment("TARGET_END"))
            clone = wrapper

    # Serialize
    from lxml import etree
    def _serialize_with_outside_comments():
        before, after = outside_trim_info
        if before == 0 and after == 0:
            return etree.tostring(clone, encoding="unicode", with_tail=False, method="html")
        before_comment = etree.Comment(f"TRIMMED_OUTSIDE_CONTAINER_BEFORE: {before} NODES")
        after_comment = etree.Comment(f"TRIMMED_OUTSIDE_CONTAINER_AFTER: {after} NODES")
        parts = [
            etree.tostring(before_comment, encoding="unicode", with_tail=False, method="html"),
            etree.tostring(clone, encoding="unicode", with_tail=False, method="html"),
            etree.tostring(after_comment, encoding="unicode", with_tail=False, method="html"),
        ]
        return "".join(parts)

    out = _serialize_with_outside_comments()

    # Collapse whitespace between tags + inside text reasonably
    out = re.sub(r">\s+<", "><", out)
    out = re.sub(r"\s{2,}", " ", out).strip()

    # Enforce max_frame_chars
    if len(out) > max_frame_chars:
        out = out[:max_frame_chars - 1] + "…"

    print(f"\nРезультат get_html_frame:\n", out)
    return out









# def get_html_frame(
#     html: str,
#     selector: str,
#     *,
#     max_frame_chars: int = 3000,           # Максимальная длина всего итогового html-фрейма (после всех сокращений)
#     max_container_text_chars: int = 1000,  # Максимальная длина текста контейнера при выборе подходящего родителя
#     max_container_html_chars: int = 5000,  # Максимальная длина HTML-кода контейнера при выборе родителя
#     sibling_elems: int = 2,                # Количество соседних элементов на том же уровне, которые нужно сохранить рядом с target
#     max_text_node_chars: int = 200,        # Максимальная длина текста внутри узла (длинный текст будет обрезан)
#     ancestor_levels: int = 3,              # Количество уровней предков target, которые нужно сохранить для контекста
# ) -> str:
#     """
#     Создаёт компактный и информативный HTML-фрейм вокруг первого элемента, найденного по CSS-селектору.
    
#     Параметры:
#     - html: исходный HTML-документ.
#     - selector: CSS-селектор для выбора target-элемента.
#     - max_frame_chars: максимальная длина итогового HTML-фрейма.
#     - max_container_text_chars: лимит текста при выборе контейнера-родителя.
#     - max_container_html_chars: лимит HTML-кода при выборе контейнера.
#     - sibling_elems: количество соседних элементов target на одном уровне, которые нужно сохранить.
#     - max_text_node_chars: максимальная длина текстового содержимого в узле (обрезка длинных текстов).
#     - ancestor_levels: сколько уровней предков target сохранить для контекста.
    
#     Возвращает:
#     - HTML-фрейм с пометками <!--TARGET_START-->, <!--TARGET_END--> и комментариями о вырезанных узлах.
#     """

#     print(f"\nЗапустили get_html_frame с селектором:", selector)

#     try:
#         import lxml.html
#         from lxml import etree
#     except ImportError:
#         raise RuntimeError("Required library 'lxml' is missing.")

#     if not html or not selector:
#         return ""

#     try:
#         doc = lxml.html.fromstring(html)
#     except Exception:
#         return ""

#     # Находим цель
#     try:
#         targets = doc.cssselect(selector)
#     except Exception:
#         return ""

#     if not targets:
#         return ""

#     target = targets[0]

#     # Хелперы для замеров
#     def _norm_text_len(el) -> int:
#         txt = el.text_content() if hasattr(el, "text_content") else ""
#         return len(" ".join(txt.split()))

#     def _html_len(el) -> int:
#         try:
#             return len(etree.tostring(el, encoding="unicode", with_tail=False, method="html"))
#         except:
#             return 10**9

#     SEMANTIC_TAGS = {"section", "article", "main", "header", "aside", "div", "li", "td", "dd", "dl", "table"}
#     STOP_TAGS = {"html", "body"}

#     # Выбор контейнера
#     chosen = None
#     best_fallback = None
#     cur = target
#     while cur is not None and isinstance(cur.tag, str):
#         tag = cur.tag.lower()
#         if tag in STOP_TAGS:
#             break
        
#         tlen, hlen = _norm_text_len(cur), _html_len(cur)
#         if best_fallback is None:
#             best_fallback = cur
#         if tag in SEMANTIC_TAGS and tlen <= max_container_text_chars and hlen <= max_container_html_chars:
#             chosen = cur
#             break
#         cur = cur.getparent()

#     container = chosen or best_fallback or target

#     # Оптимизированный подсчет удаленных узлов снаружи (Fix #4)
#     container_nodes_set = set(container.iter())
#     container_line = getattr(container, "sourceline", -1) or -1
    
#     trimmed_outside_before = 0
#     trimmed_outside_after = 0
#     for n in doc.iter():
#         if n in container_nodes_set: continue
#         line = getattr(n, "sourceline", None)
#         if line is not None:
#             if line < container_line: trimmed_outside_before += 1
#             else: trimmed_outside_after += 1

#     tree = container.getroottree()
#     container_path = tree.getpath(container)
#     target_path = tree.getpath(target)

#     # Исправленный релятивный путь (Fix #3)
#     def _rel_path(abs_path: str) -> str:
#         if abs_path == container_path: return ""
#         prefix = container_path + "/"
#         if abs_path.startswith(prefix):
#             return abs_path[len(container_path):]
#         return ""

#     # Собираем пути для сохранения
#     keep_abs_paths = {target_path}
    
#     # Соседи и предки
#     def _add_to_keep(el, levels):
#         c = el
#         for _ in range(levels + 1):
#             if c is None: break
#             keep_abs_paths.add(tree.getpath(c))
#             if c == container: break
#             c = c.getparent()

#     _add_to_keep(target, ancestor_levels)

#     # Сиблинги
#     p, n = target.getprevious(), target.getnext()
#     for _ in range(sibling_elems):
#         if p is not None: keep_abs_paths.add(tree.getpath(p)); p = p.getprevious()
#         if n is not None: keep_abs_paths.add(tree.getpath(n)); n = n.getnext()

#     # Клонирование и очистка
#     clone = deepcopy(container)
#     keep_nodes = {clone}
    
#     for ap in keep_abs_paths:
#         rp = _rel_path(ap)
#         if not rp: continue
#         for f in clone.xpath("." + rp):
#             curr = f
#             while curr is not None:
#                 keep_nodes.add(curr)
#                 if curr == clone: break
#                 curr = curr.getparent()

#     # Сохраняем все внутри цели
#     target_rel = _rel_path(target_path)
#     target_clones = clone.xpath("." + target_rel) if target_rel else [clone]
#     target_clone = target_clones[0] if target_clones else None
#     if target_clone is not None:
#         keep_nodes.update(target_clone.iter())

#     # Прунинг
#     edge_trim_counts = {}
#     for parent in list(clone.iter()):
#         childs = list(parent)
#         if not childs: continue
#         kept = [c in keep_nodes for c in childs]
#         if any(kept):
#             first, last = kept.index(True), len(kept) - 1 - kept[::-1].index(True)
#             tb = sum(1 for i in range(first) if not kept[i])
#             ta = sum(1 for i in range(last + 1, len(childs)) if not kept[i])
#             if tb > 0 or ta > 0: edge_trim_counts[parent] = (tb, ta)

#     for el in list(clone.iterdescendants())[::-1]:
#         if el not in keep_nodes:
#             el.getparent().remove(el)

#     # Вставка комментариев (Fix #2)
#     for parent, (tb, ta) in edge_trim_counts.items():
#         if list(parent):
#             if tb > 0: parent.insert(0, etree.Comment(f"TRIMMED_BEFORE {tb} NODES"))
#             if ta > 0: parent.append(etree.Comment(f"TRIMMED_AFTER {ta} NODES"))
#         else:
#             parent.append(etree.Comment(f"TRIMMED_BEFORE {tb} AFTER {ta} NODES"))

#     # Атрибуты и тексты
#     ATTR_WHITELIST = {"class", "id", "itemprop", "content", "href", "aria-label", "role", "title"}
#     for el in clone.iter():
#         if not isinstance(el.tag, str): continue
#         # Очистка атрибутов
#         attrs = {}
#         for k, v in el.attrib.items():
#             if k.lower() in ATTR_WHITELIST or k.lower().startswith("data-"):
#                 attrs[k] = v[:200] + "…" if len(v) > 200 else v
#         el.attrib.clear()
#         el.attrib.update(attrs)
#         # Тексты
#         if el.text:
#             t = " ".join(el.text.split())
#             el.text = (t[:max_text_node_chars] + "…") if len(t) > max_text_node_chars else t

#     # Маркеры цели
#     if target_clone is not None:
#         p = target_clone.getparent()
#         if p is not None:
#             idx = p.index(target_clone)
#             p.insert(idx, etree.Comment("TARGET_START"))
#             p.insert(idx + 2, etree.Comment("TARGET_END"))

#     # Сериализация (Fix #1)
#     res = [etree.tostring(etree.Comment(f"TRIMMED_OUTSIDE_BEFORE: {trimmed_outside_before}"), encoding="unicode")]
#     res.append(etree.tostring(clone, encoding="unicode", method="html"))
#     res.append(etree.tostring(etree.Comment(f"TRIMMED_OUTSIDE_AFTER: {trimmed_outside_after}"), encoding="unicode"))
    
#     out = "".join(res)
#     out = re.sub(r">\s+<", "><", out)
#     result = re.sub(r"\s{2,}", " ", out).strip()
#     print(f"\nРезультат get_html_frame:\n", result)

#     return result 

# region Доп. функции

def save_page_html(html: str, filename: str = "page_html.html") -> str:
    """
    Сохраняет HTML в файл рядом со скриптом и возвращает путь к файлу.
    
    Args:
        html: html-содержимое страницы
    """
    print("Сохраняем html страницы в файл", filename)
    output_path = Path(__file__).resolve().parent / filename
    output_path.write_text(html, encoding="utf-8")
    return str(output_path)


# # Проверка
# url = "https://makitaclub.ru/products/df488d002/"
# html_content = get_html_from_cache(url)
# # save_page_html(html_content, filename = "page_html.html")

# selector = "#main .product_title.entry-title"
# # selector = ".col-sm-6 .woocommerce-Price-amount.amount"
# result_get_html_frame = get_html_frame(html_content, selector)
# # print(f"result_get_html_frame:\n", result_get_html_frame)