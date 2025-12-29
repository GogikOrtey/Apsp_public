""" 
Здесь будет реализация алгоритма работы агента для 4го шага
"""

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
from urllib.parse import urljoin, urlparse
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Подключение всех библиотек и функций
from import_all_libraries import *

from reasoning_agent.agent_main import *

from playwright_tool.playwright_toolkit import *  # регистрирует инструменты playwright
from new_program.html_toolkit import *  # регистрирует инструменты html_tool


""" 



"""

# region Алгоритмическая функция извлечения URL без агента, по селекторам

def _parse_input_data_obj(input_data: Any) -> dict[str, Any] | None:
    if isinstance(input_data, dict):
        return input_data
    if isinstance(input_data, str) and input_data.strip():
        try:
            obj = json.loads(input_data)
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None
    return None


def _looks_like_xpath_selector(selector: str) -> bool:
    s = (selector or "").strip()
    return s.startswith(("/", "./", "../", ".//", "(.//", "//*[", "("))


def _normalize_candidate_link(raw: str, page_url: str) -> str:
    if not isinstance(raw, str):
        return ""
    s = raw.strip()
    if not s:
        return ""

    if s.startswith(("http://", "https://")):
        return s

    if s.startswith("//"):
        try:
            parsed = urlparse(page_url or "")
            scheme = parsed.scheme or "https"
        except Exception:
            scheme = "https"
        return f"{scheme}:{s}"

    try:
        return urljoin(page_url or "", s)
    except Exception:
        return s


def _is_probably_link(s: str) -> bool:
    if not isinstance(s, str):
        return False
    t = s.strip()
    return bool(t) and t.startswith(("http://", "https://", "/", "//"))


def _check_url_status_any(url: str, timeout_ms: int = 10_000) -> dict[str, Any]:
    """
    Проверяет URL через Playwright `check_url_status`, а если Playwright не готов — через requests.
    Возвращает dict в формате {status, code, url, error}.
    """
    try:
        res_head = check_url_status(url=url, method="HEAD", timeout=timeout_ms)  # type: ignore[name-defined]
        if isinstance(res_head, dict) and res_head.get("status") == "ok":
            code = res_head.get("code")
            if isinstance(code, int) and 200 <= code < 400:
                return res_head

        res_get = check_url_status(url=url, method="GET", timeout=timeout_ms)  # type: ignore[name-defined]
        if isinstance(res_get, dict) and res_get.get("status") == "ok":
            code = res_get.get("code")
            if isinstance(code, int):
                return res_get
    except Exception:
        pass

    try:
        import requests  # noqa: WPS433

        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        timeout_s = max(1, int(timeout_ms / 1000))
        r_head = None
        try:
            r_head = requests.head(url, allow_redirects=True, timeout=timeout_s, headers=headers)
            code = int(getattr(r_head, "status_code", 0) or 0)
            if 200 <= code < 400:
                return {"status": "ok", "code": code, "url": url, "error": None}
        except Exception:
            r_head = None

        r = requests.get(url, allow_redirects=True, timeout=timeout_s, headers=headers, stream=True)
        return {"status": "ok", "code": int(getattr(r, "status_code", 0) or 0), "url": url, "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "code": None, "url": url, "error": str(exc)}


def _extract_hrefs_from_cached_page_html(selector: str, page_url: str) -> list[str]:
    """
    Извлекает href'ы по CSS/XPath селектору из HTML страницы (через get_html_from_cache).
    Нужен как fallback, когда extract_selector_data_from_cached_pages вернул текст вместо href.
    """
    try:
        html = get_html_from_cache(page_url, print_msg=False)  # type: ignore[name-defined]
    except Exception:
        return []

    if not html:
        return []

    sel = (selector or "").strip()
    if not sel:
        return []

    sel_lower = sel.lower()
    if sel_lower.startswith("css="):
        sel = sel[4:].strip()
    elif sel_lower.startswith("xpath="):
        sel = sel[6:].strip()

    try:
        if _looks_like_xpath_selector(sel):
            import lxml.html  # type: ignore  # noqa: WPS433

            doc = lxml.html.fromstring(html)  # type: ignore[attr-defined]
            found = doc.xpath(sel)
            elements = [x for x in found if hasattr(x, "tag")]
            out: list[str] = []
            for el in elements:
                try:
                    href = el.get("href")  # type: ignore[attr-defined]
                except Exception:
                    href = None
                if isinstance(href, str) and href.strip():
                    out.append(href.strip())
            return out

        from bs4 import BeautifulSoup  # noqa: WPS433

        soup = BeautifulSoup(html, "html.parser")
        found = soup.select(sel) or []
        out2: list[str] = []
        for el in found:
            href = None
            try:
                href = el.get("href")
            except Exception:
                href = None
            if not href:
                try:
                    a = el.find("a", href=True)
                    href = a.get("href") if a else None
                except Exception:
                    href = None
            if isinstance(href, str) and href.strip():
                out2.append(href.strip())
        return out2
    except Exception:
        return []


def _try_get_links_without_agent(input_data: Any) -> dict[str, Any] | None:
    input_obj = _parse_input_data_obj(input_data)
    if not input_obj:
        return None

    first_url = input_obj.get("first_url")
    second_url = input_obj.get("second_url")
    third_url = input_obj.get("third_url")
    selector_product = input_obj.get("selector_product")

    if not all(isinstance(x, str) and x.strip() for x in (first_url, second_url, third_url, selector_product)):
        return None

    pages = [first_url.strip(), second_url.strip(), third_url.strip()]
    selector = selector_product.strip()

    try:
        extracted = extract_selector_data_from_cached_pages(  # type: ignore[name-defined]
            selector=selector,
            links=pages,
            max_all_results=30,
            print_cache_msgs=False,
        )
    except Exception:
        extracted = []

    by_page_candidates: list[list[str]] = []
    for i, page_url in enumerate(pages):
        vals: list[str] = []
        if isinstance(extracted, list) and i < len(extracted) and isinstance(extracted[i], dict):
            ar = extracted[i].get("all_results")
            if isinstance(ar, list):
                vals = [x for x in ar if isinstance(x, str)]

        good_linkish = [v for v in vals if _is_probably_link(v)]
        if not good_linkish:
            vals = _extract_hrefs_from_cached_page_html(selector=selector, page_url=page_url)

        normalized: list[str] = []
        seen: set[str] = set()
        for raw in (vals or []):
            cand = _normalize_candidate_link(raw, page_url=page_url)
            if not cand:
                continue
            if cand in seen:
                continue
            seen.add(cand)
            normalized.append(cand)
            if len(normalized) >= 30:
                break
        by_page_candidates.append(normalized)

    out_lists: list[list[str]] = []
    for candidates in by_page_candidates:
        top5 = (candidates or [])[:5]
        if not top5:
            return None

        # По “нормальному” сценарию проверяем только 1 ссылку (как в ТЗ).
        status = _check_url_status_any(top5[0], timeout_ms=10_000)
        code = status.get("code")
        if status.get("status") == "ok" and isinstance(code, int) and 200 <= code < 400:
            out_lists.append(top5)
            continue

        # Если первая не валидна — пробуем найти валидные (дороже, но редкий случай).
        good: list[str] = []
        for cand in (candidates or []):
            st = _check_url_status_any(cand, timeout_ms=10_000)
            c = st.get("code")
            if st.get("status") == "ok" and isinstance(c, int) and 200 <= c < 400:
                good.append(cand)
            if len(good) >= 5:
                break
        if not good:
            return None
        out_lists.append(good[:5])

    return {
        "five_links_1": out_lists[0] if len(out_lists) > 0 else [],
        "five_links_2": out_lists[1] if len(out_lists) > 1 else [],
        "five_links_3": out_lists[2] if len(out_lists) > 2 else [],
    }



# region Промпт

main_task_all = """

Задача: Во входных данных будут даны 3 ссылки на страницы. Нужно будет пройтись по ним, и собрать по 5 ссылок на товары, с каждой страницы. Если найдено меньше 5 ссылок, вернуть все найденные (либо []). 

————————————————————————

Инструкция:

1. Перейди на страницу указанную в поле first_url в input_data (инструмент goto_url)

2. Получи первые 5 элементов ссылок на товары, используя селектор из поля selector_product из input_data, при помощи инструмента find_elements.

selector_product — CSS-селектор, возвращающий элементы <a> или элементы, внутри которых есть <a> с ссылкой на товар. Из полученных объектов нужно будет извлечь ссылки.

    - Если в input_data в поле additional_processing_for_the_link_value указано true, то значит для ссылки нужна дополнительная обработка. Чаще всего, в начало ссылки нужно подставить HOST текущего сайта (протокол и домен), что бы она стала валидной (преврати относительную ссылку в абсолютную, используя текущий URL страницы).

    Например, если мы сейчас на сайте https://kotel-nasos.ru/...
    и ссылка выглядит так: href="/elektricheskiy-kotel-evan-epo-pro-60/"
    То скорее всего что бы сделать её валидной, нужно будет добавить HOST в начало. В этом примере получится вот так: https://kotel-nasos.ru/elektricheskiy-kotel-evan-epo-pro-60/

    Далее нужно будет проверить, что ссылка получилась валидная. Используя инструмент check_url_status (для первой ссылки).

    Когда валидная ссылка будет получена, зафиксируй в memory, какая обработка нужна для извлекаемых со страницы ссылок, что бы они стали валидными.

    - Если в input_data в поле additional_processing_for_the_link_value указано false, то значит скорее всего дополнительной обработки для ссылок не требуется. Также проверь одну ссылку через инструмент check_url_status, и зафиксируй в memory. Если обработка всё же нужна, то определи какая именно. 

Обработка, определённая на первой странице, применяется ко всем следующим страницам без повторной проверки.

3. Запиши ранее полученные первые 5 ссылок на товары из этой страницы в result в поле five_links_1. Нужно записать именно валидные ссылки (если нужна дополнительная их обработка)

4. Перейди на вторую страницу, указанную в input_data в поле second_url

5. Получи первые 5 элементов ссылок на товары, используя селектор из поля selector_product из input_data, при помощи инструмента find_elements.

6. Запиши их в result в поле five_links_2. Нужно записать именно валидные ссылки (если нужна дополнительная их обработка)

7. Перейди на третью страницу, указанную в input_data в поле third_url

8. Получи первые 5 элементов ссылок на товары, используя селектор из поля selector_product из input_data, при помощи инструмента find_elements.

9. Запиши их в result в поле five_links_3. Нужно записать именно валидные ссылки (если нужна дополнительная их обработка)

10. На этом задача будет завершена.

————————————————————————

Входные данные (input_data):

"""




# region Схема, шаблон и план

""" 
Входные данные:
{
    "first_url"
    "second_url"
    "third_url"
    "selector_product"
    "additional_processing_for_the_link_value"
}

Результаты:
{
    "five_links_1",
    "five_links_2",
    "five_links_3",
}

"""



# Схема результата
main_result_schema = {
    "five_links_1": {
        "type": "list[str]",
        "required": True,
        "description": "Пять ссылок на товары с первой страницы"
    },
    "five_links_2": {
        "type": "list[str]",
        "required": True,
        "description": "Пять ссылок на товары со второй страницы"
    },
    "five_links_3": {
        "type": "list[str]",
        "required": True,
        "description": "Пять ссылок на товары с третьей страницы"
    }
}

# Шаблон результата, который агент заполняет в процессе работы
main_result_template = {
    "five_links_1": None,
    "five_links_2": None,
    "five_links_3": None
}



main_plan = {
    "steps": [
        {
            "step_id": 1,
            "goal": "Собрать и записать до 5 валидных ссылок на товары с первой страницы (с учетом возможной обработки ссылок, если она требуется).",
            "fills": [
                "five_links_1"
            ]
        },
        {
            "step_id": 2,
            "goal": "Собрать и записать до 5 валидных ссылок на товары со второй страницы, применяя ту же обработку ссылок, что определена на первой странице (если требуется).",
            "fills": [
                "five_links_2"
            ]
        },
        {
            "step_id": 3,
            "goal": "Собрать и записать до 5 валидных ссылок на товары с третьей страницы, применяя ту же обработку ссылок, что определена на первой странице (если требуется).",
            "fills": [
                "five_links_3"
            ]
        }
    ]
}





# region Основная функция
def agent_step_6_1_get_links_for_product_agent(input_data, search_request):
    # Приводим input_data к строке
    if isinstance(input_data, str):
        input_data_str = input_data
    else:
        try:
            input_data_str = json.dumps(input_data, ensure_ascii=False, indent=4, default=str)
        except Exception:
            input_data_str = str(input_data)

    task = (
        f"Сейчас в браузере Playwright открыта страница результатов товаров с поисковой выдачи по запросу '{search_request}'." +
        main_task_all + 
        input_data_str )

    resulr_answer = orchestrate(
        task = task,
        max_steps = 40,
        result_schema = main_result_schema,
        result_template = main_result_template,
        plan = main_plan,
        step_by_step_running = False, # Разрешаем агенту работать автоматически
    ) 

    result_task = get_result()
    return result_task


def agent_step_6_1_get_links_for_product(input_data, search_request):
    """
    Обёртка над агентом:
    - сначала пытаемся собрать ссылки без LLM (через обычные запросы + парсинг html + проверка URL),
    - если не получилось — запускаем LLM-агента (как было раньше).
    """
    fast = _try_get_links_without_agent(input_data=input_data)
    if isinstance(fast, dict):
        return fast
    return agent_step_6_1_get_links_for_product_agent(input_data=input_data, search_request=search_request)







# region Тесты

# Проверка 1:

if __name__ == "__main__":      
    input_data_test = {
        "first_url": "https://makitaclub.ru/?s=%D0%B8%D0%BD%D1%81%D1%82%D1%80%D1%83%D0%BC%D0%B5%D0%BD%D1%82&post_type=product",
        "second_url": "https://makitaclub.ru/page/2/?s=инструмент&post_type=product",
        "third_url": "https://makitaclub.ru/?s=%D0%B4%D1%80%D0%B5%D0%BB%D1%8C&post_type=product",
        "selector_product": ".products .product-card a.stretched-link[href*='/products/']",
        "additional_processing_for_the_link_value": "false"
    }

    # # Запускаю браузер с видимым окном
    # launch_browser(headless = False)

    # goto_url( 
    #     url = "https://makitaclub.ru/?s=%D0%B8%D0%BD%D1%81%D1%82%D1%80%D1%83%D0%BC%D0%B5%D0%BD%D1%82&post_type=product",
    #     wait_until = "load",
    #     timeout = 30_000
    # )

    # Если браузер не запущен, то алгоритмическая функция использует request для проверки валидности ссылок

    search_request_test = "инструмент"

    resilt = agent_step_6_1_get_links_for_product(input_data_test, search_request_test)

    print("resilt:")
    print_json(resilt)






# region Пример результата

""" 
{
    "five_links_1": [
        "https://makitaclub.ru/products/831271-6/",
        "https://makitaclub.ru/products/garantiya-5-let/",
        "https://makitaclub.ru/products/nabor-rychnyh-instrumentov-i-osnastki-makita-d-42042-103-predmeta/",
        "https://makitaclub.ru/products/nabor-instrumentov-56-sht-makita-b-53768/",
        "https://makitaclub.ru/products/akkumulyatornyj-mnogofunktsionalnyj-instrument-makita-tm30dz-10-8v-li-ion-bez-akkumulyatorov-i-zaryadnogo-ustrojstva/"
    ],
    "five_links_2": [
        "https://makitaclub.ru/products/duc204rf/",
        "https://makitaclub.ru/products/jv002gz/",
        "https://makitaclub.ru/products/duc353rf2/",
        "https://makitaclub.ru/products/duc101sf/",
        "https://makitaclub.ru/products/dtd153sy/"
    ],
    "five_links_3": [
        "https://makitaclub.ru/products/dp4021/",
        "https://makitaclub.ru/products/df488d002/",
        "https://makitaclub.ru/products/ddf489z/",
        "https://makitaclub.ru/products/m0600/",
        "https://makitaclub.ru/products/hp002gd201/"
    ]
}
"""





