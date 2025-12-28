"""

"""

from bs4 import BeautifulSoup, Comment, NavigableString
from collections import defaultdict
from bs4 import BeautifulSoup, Tag
from typing import Optional, List, Literal, Dict, Any

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
from playwright_tool.shared_page import get_shared_page










"""

    Нужно будет реализовать:
    - Формирование curl запроса, с body, заголовками и прочим
    - Получение всех запросов в браузере, с их параметрами и частью body (обрезанной в середине)
    - Получение результатов конкретного запроса, с указанием сколько контента из ответа нужно показать
    - Поиск запросов в которых есть вхождение подстроки (как в результатах так и в запросах, это можно будет например контролировать параметрами)    
    - Max pagination

    - Реализовать инструмент, который возвращает html между двумя найденными вхождениями одинаковых селекторов
    и возможно как-то собирает полный элемент между ними. Возвращает с доп. информацией
        - Да, это прям надо сделать автоматически, для валидации селектора товара

"""














# region — OTHER TOOLS —

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


def get_host_from_link(link: str) -> str:
    """
    Возвращает HOST в виде '<scheme>://<domain>' из переданной ссылки.

    Требование из задачи: HOST должен быть равен (протокол + домен) пришедшего URL.
    """
    if not isinstance(link, str) or not link.strip():
        return ""

    url = link.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urlparse(url)
    scheme = (parsed.scheme or "https").lower()
    domain = (parsed.netloc or "").lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return f"{scheme}://{domain}" if domain else ""


# region cheerio_js_simple_sandbox_extract_vars
@tool(
    name="run_cheerio_js_extract_vars",
    description=(
        "Выполняет переданный JS-код, выполняет его и возвращает JSON со всеми переменными, "
        "объявленными в user_code через const/let/var и их значениями после выполненя. Значение для переменной HOST и объект cheerio с контентом переданной ссылки страницы уже будут инициализированы в песочнице."
    ),
    args=[
        {
            "name": "user_code",
            "type": "str",
            "required": True,
            "description": (
                "JS-код (1+ строк), в котором объявляются новые переменные через const/let/var, например:\n"
                "const name = $('h1').text().trim();\n"
                "const imageLink = HOST + $('.x a')?.attr('href');\n"
                "const stock = $('.buy').text().includes('Купить') ? 'InStock' : 'OutOfStock';"
            ),
        },
        {
            "name": "link",
            "type": "str",
            "required": True,
            "description": "URL страницы",
        },
    ],
    returns={
        "status": "ok|error",
        "vars": "dict|null — объект {varName: value} со значениями переменных из user_code",
        "error": "str|null — описание ошибки",
    },
    example_args={
        "link": "https://makitaclub.ru/?s=%D0%B8%D0%BD%D1%81%D1%82%D1%80%D1%83%D0%BC%D0%B5%D0%BD%D1%82&post_type=product",
        "user_code": "const name = $('h1').text().trim();",
    },
)
def run_cheerio_js_extract_vars(user_code: str, link: str) -> dict[str, Any]:
    """
    Выполняет user_code в Node.js+cheerio и возвращает все объявленные переменные.

    ВАЖНО: это упрощённая реализация (без vm/Proxy/жёсткой изоляции), как просил пользователь.
    """
    if not isinstance(user_code, str) or not user_code.strip():
        return {"status": "error", "vars": None, "error": "user_code должен быть непустой строкой"}
    if not isinstance(link, str) or not link.strip():
        return {"status": "error", "vars": None, "error": "link должен быть непустой строкой"}

    try:
        html_content = get_html_from_cache(link, print_msg=False)
    except Exception as e:
        return {"status": "error", "vars": None, "error": f"Не удалось получить HTML из кеша: {e}"}

    return run_cheerio_js_extract_vars_on_html(user_code=user_code, html_content=html_content, link=link)


def run_cheerio_js_extract_vars_on_html(user_code: str, html_content: str, link: str) -> dict[str, Any]:
    """
    Техническая функция: выполняет user_code на переданном html_content.
    """
    host = get_host_from_link(link)
    if not host:
        return {"status": "error", "vars": None, "error": "Не удалось вычислить HOST из link"}

    # Записываем HTML во временный файл (удалим после вызова Node)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w", encoding="utf-8") as tmp:
        tmp.write(html_content or "")
        tmp_path = tmp.name

    tmp_path_js = json.dumps(tmp_path)
    user_code_js = json.dumps(user_code)
    host_js = json.dumps(host)

    # Печатаем строго JSON последней строкой, чтобы Python мог распарсить результат.
    # Важно: выполняем user_code в vm с таймаутом и без code-generation (eval/new Function/wasm).
    node_script_template = """
const fs = require('fs');
const vm = require('vm');
const cheerio = require('cheerio');

function main() {
  try {
    const html = fs.readFileSync(__TMP_PATH__, 'utf-8');
    const data = html;
    const $raw = cheerio.load(data);
    const HOST = __HOST__;
    const userCode = __USER_CODE__;

    // --- minimal hardening to keep flexibility but block common escapes ---
    // Hide constructor/__proto__/prototype via Proxy to prevent chains like:
    //   $.constructor.constructor("return process")()
    const DENY_PROPS = new Set(['constructor', '__proto__', 'prototype']);
    const RAW_TO_PROXY = new WeakMap();
    const PROXY_TO_RAW = new WeakMap();

    function unwrap(v) { return PROXY_TO_RAW.get(v) || v; }

    function makeSafe(value) {
      if (value === null || value === undefined) return value;
      const t = typeof value;
      if (t !== 'object' && t !== 'function') return value;

      if (PROXY_TO_RAW.has(value)) return value;
      const cached = RAW_TO_PROXY.get(value);
      if (cached) return cached;

      if (t === 'function') {
        const p = new Proxy(value, {
          get(target, prop, receiver) {
            if (DENY_PROPS.has(prop)) return undefined;
            const v = Reflect.get(target, prop, receiver);
            return makeSafe(v);
          },
          apply(target, thisArg, args) {
            const realThis = unwrap(thisArg);
            const realArgs = (args || []).map(unwrap);
            const res = Reflect.apply(target, realThis, realArgs);
            return makeSafe(res);
          },
        });
        RAW_TO_PROXY.set(value, p);
        PROXY_TO_RAW.set(p, value);
        return p;
      }

      const p = new Proxy(value, {
        get(target, prop, receiver) {
          if (DENY_PROPS.has(prop)) return undefined;
          // Read with receiver=target to avoid Proxy as 'this' in internal-slot methods
          const v = Reflect.get(target, prop, target);
          if (typeof v === 'function') return makeSafe(v.bind(target));
          return makeSafe(v);
        },
      });
      RAW_TO_PROXY.set(value, p);
      PROXY_TO_RAW.set(p, value);
      return p;
    }

    const $ = makeSafe($raw);

    function extractDeclaredVarNames(code) {
      // Supports:
      //   const a = 1
      //   let a = 1, b = 2
      // Heuristic-based (good enough for our snippets).
      const names = new Set();
      const re = /(?:^|[;\\n\\r\\t ]+)(?:const|let|var)\\s+([A-Za-z_$][0-9A-Za-z_$]*)(?=\\s*=)|[,\\s]\\s*([A-Za-z_$][0-9A-Za-z_$]*)(?=\\s*=)/g;
      let m;
      while ((m = re.exec(code)) !== null) {
        const a = m[1] || m[2];
        if (a) names.add(a);
      }
      return Array.from(names);
    }

    const declared = extractDeclaredVarNames(userCode).filter(n => !['HOST', '$', '$raw', 'data', 'html', 'userCode'].includes(n));

    // Lightweight static guardrails against obvious sandbox-escape attempts.
    // We keep this intentionally small to preserve "freedom" for data transforms.
    const FORBIDDEN = [
      { re: /\\brequire\\s*\\(/, msg: "require(...) is not allowed" },
      { re: /\\bprocess\\b/, msg: "process is not allowed" },
      { re: /\\bchild_process\\b/, msg: "child_process is not allowed" },
      { re: /\\bfs\\b/, msg: "fs is not allowed" },
      { re: /\\bvm\\b/, msg: "vm is not allowed" },
      { re: /\\beval\\s*\\(/, msg: "eval(...) is not allowed" },
      { re: /\\bFunction\\s*\\(/, msg: "Function(...) is not allowed" },
      { re: /constructor\\s*\\.\\s*constructor/, msg: "constructor.constructor is not allowed" },
      { re: /\\bimport\\s*\\(/, msg: "dynamic import(...) is not allowed" },
      { re: /__proto__/, msg: "__proto__ is not allowed" },
    ];
    for (const rule of FORBIDDEN) {
      if (rule.re.test(userCode)) {
        throw new Error("Forbidden code: " + rule.msg);
      }
    }

    // Build result snippet as direct identifier references (no eval).
    const resultSnippet = declared.length
      ? '{' + declared.map(n => JSON.stringify(n) + ': (typeof ' + n + ' === \"undefined\" ? null : ' + n + ')').join(',') + '}'
      : '{}';

    const prefix = '\"use strict\";\\ntry {\\n';
    const suffix = `\\n\\nconst __safeJsonValue = (v) => {
  if (v === undefined) return null;
  const t = typeof v;
  if (t === 'bigint') return v.toString();
  if (t === 'function') return String(v);
  if (t === 'symbol') return String(v);
  try { JSON.stringify(v); return v; } catch (e) {
    try { return String(v); } catch (e2) { return null; }
  }
};\\n
const __rawOut = ${resultSnippet};\\n
const __out = {};\\n
for (const [k, v] of Object.entries(__rawOut)) { __out[k] = __safeJsonValue(v); }\\n
result = __out;\\n
} catch (e) {\\n
  result = \"__ERROR__:\" + String(e && e.message ? e.message : e);\\n
}\\n`;

    const wrappedCode = prefix + userCode + suffix;

    const sandbox = {
      $,
      HOST,
      result: null,
      // common stdlib things for data transforms
      Math, Number, String, Boolean, Array, Object, JSON, RegExp, Date,
      parseInt, parseFloat, isNaN, isFinite,
      encodeURI, decodeURI, encodeURIComponent, decodeURIComponent,
      // console is muted to keep stdout strictly JSON
      console: { log(){}, error(){}, warn(){}, info(){}, debug(){} },
    };

    // Remove Node-specific capabilities
    sandbox.process = undefined;
    sandbox.require = undefined;
    sandbox.module = undefined;
    sandbox.Buffer = undefined;
    sandbox.global = sandbox;
    sandbox.globalThis = sandbox;

    vm.runInNewContext(wrappedCode, sandbox, {
      timeout: 1000,
      codeGeneration: { strings: false, wasm: false },
    });

    const r = sandbox.result;
    if (typeof r === 'string' && r.startsWith('__ERROR__:')) {
      console.log(JSON.stringify({ status: 'error', vars: null, error: r.slice(10) }));
    } else {
      console.log(JSON.stringify({ status: 'ok', vars: r || {}, error: null }));
    }
  } catch (e) {
    console.log(JSON.stringify({ status: 'error', vars: null, error: String(e && e.message ? e.message : e) }));
  }
}

main();
""".strip()

    # IMPORTANT: node_script_template выше — raw-string, но нам нужно реально подставить JS-литералы.
    # Поэтому делаем простую подстановку на уровне Python для трёх placeholder.
    node_script = (
        node_script_template
        .replace("__TMP_PATH__", tmp_path_js)
        .replace("__HOST__", host_js)
        .replace("__USER_CODE__", user_code_js)
    )

    try:
        result = subprocess.run(
            ["node", "-e", node_script],
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )

        if result.returncode != 0:
            err = (result.stderr or "").strip() or f"Node.js exited with code {result.returncode}"
            return {"status": "error", "vars": None, "error": err}

        output = (result.stdout or "").strip()
        last_line = ""
        for line in reversed(output.splitlines()):
            if line.strip():
                last_line = line.strip()
                break
        if not last_line:
            return {"status": "error", "vars": None, "error": "Empty Node.js output"}

        try:
            parsed = json.loads(last_line)
        except Exception:
            return {"status": "error", "vars": None, "error": f"Unexpected Node.js output: {output!r}"}

        status = parsed.get("status")
        if status == "ok":
            return {"status": "ok", "vars": parsed.get("vars") or {}, "error": None}
        return {"status": "error", "vars": None, "error": parsed.get("error") or "Unknown error"}
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
# endregion cheerio_js_simple_sandbox_extract_vars


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























# region — FROM AGENT —










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








# region Max pagination
"""
Оригинал на JS:

    let totalPages = Math.max(...$(".module-pagination__wrapper > a").get().map(item => +$(item).text().trim()).filter(Boolean))

    let totalPages = Math.max(...$("/* SELECTOR_HERE */").get().map(item => +$(item).text().trim()).filter(Boolean))

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


# Обёртка для агента, с использованием локального html из открытой Page
@tool(
    name="get_total_pages_on_current_page_cheerio",
    description=(
        "Запускает JS-выражение (cheerio/Node.js) вида "
        "`let totalPages = Math.max(...$(selector).get().map(item => +$(item).text().trim()).filter(Boolean))` "
        "на HTML текущей страницы Playwright и возвращает значение totalPages."
    ),
    args=[
        {
            "name": "selector",
            "type": "str",
            "required": True,
            "description": "CSS-селектор элементов пагинации (например, '.module-pagination__wrapper > a')",
        },
    ],
    returns={
        "status": "ok|error",
        "totalPages": "str|null — значение переменной totalPages (как в JS)",
        "error": "Описание ошибки, если была",
    },
    example_args={
        "selector": ".module-pagination__wrapper > a",
    },
)
def get_total_pages_on_current_page_cheerio(selector: str) -> dict[str, str | None]:
    """
    Обёртка над get_total_pages_on_cheerio(...), которая берёт HTML через текущую Playwright page.

    Требования:
    - до вызова должна быть установлена общая page через playwright_tool.shared_page.set_shared_page(page)
    """
    page = get_shared_page()
    html_content = page.content()
    return get_total_pages_on_cheerio(selector=selector, html_content=html_content)


def get_total_pages_on_cheerio(selector: str, html_content: str) -> dict[str, str | None]:
    """
    Вычисляет totalPages по JS-формуле через cheerio (Node.js).

    Для максимальной совместимости повторяет смысл кода:
        let totalPages = Math.max(...$(selector).get().map(item => +$(item).text().trim()).filter(Boolean))
    """
    if not isinstance(selector, str) or not selector.strip():
        return {"status": "error", "totalPages": None, "error": "selector должен быть непустой строкой"}

    # Записываем HTML во временный файл (удалим после вызова Node)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w", encoding="utf-8") as tmp:
        tmp.write(html_content or "")
        tmp_path = tmp.name

    selector_js = json.dumps(selector)  # безопасно экранируем селектор
    tmp_path_js = json.dumps(tmp_path)  # безопасно экранируем путь

    # ВАЖНО: печатаем строго JSON одним console.log, чтобы Python мог распарсить результат.
    node_script_template = """
const cheerio = require('cheerio');
const fs = require('fs');

function main() {
  try {
    const html = fs.readFileSync(__TMP_PATH__, 'utf-8');
    const $ = cheerio.load(html);
    const sel = __SELECTOR__;

    const totalPages = Math.max(...$(sel).get().map(item => +$(item).text().trim()).filter(Boolean));

    console.log(JSON.stringify({ status: 'ok', totalPages: String(totalPages), error: null }));
  } catch (e) {
    console.log(JSON.stringify({ status: 'error', totalPages: null, error: String(e && e.message ? e.message : e) }));
  }
}

main();
""".strip()
    node_script = (
        node_script_template
        .replace("__TMP_PATH__", tmp_path_js)
        .replace("__SELECTOR__", selector_js)
    )

    try:
        result = subprocess.run(
            ["node", "-e", node_script],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            err = (result.stderr or "").strip() or f"Node.js exited with code {result.returncode}"
            return {"status": "error", "totalPages": None, "error": err}

        output = (result.stdout or "").strip()
        try:
            parsed = json.loads(output)
        except Exception:
            return {"status": "error", "totalPages": None, "error": f"Unexpected Node.js output: {output!r}"}

        status = parsed.get("status")
        if status == "ok":
            return {"status": "ok", "totalPages": parsed.get("totalPages"), "error": None}
        return {"status": "error", "totalPages": None, "error": parsed.get("error") or "Unknown error"}
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


# # Проверка
# url = "https://makitaclub.ru/?s=%D0%B8%D0%BD%D1%81%D1%82%D1%80%D1%83%D0%BC%D0%B5%D0%BD%D1%82&post_type=product"
# # url = "https://makitatrading.ru/catalog/?q=%D0%B8%D0%BD%D1%81%D1%82%D1%80%D1%83%D0%BC%D0%B5%D0%BD%D1%82&s=%D0%9D%D0%B0%D0%B9%D1%82%D0%B8"
# # url = "https://galleryceramics.ru/catalog/?q=%D0%BF%D0%BB%D0%B8%D1%82%D0%BA%D0%B0&type=catalog&s=%D0%9D%D0%B0%D0%B9%D1%82%D0%B8"
# html_content = get_html_from_cache(url)
# # save_page_html(html_content, filename = "page_html.html")

# selector = "nav.woocommerce-pagination a"
# # selector = "nav.woocommerce-pagination .page-numbers a, nav.woocommerce-pagination .page-numbers span"
# # selector = ".bottom_nav_wrapper .module-pagination a"
# # selector = "nav#pagination"
# result_get_total_pages_on_cheerio = get_total_pages_on_cheerio(selector, html_content)
# print(f"result_get_total_pages_on_cheerio:\n", result_get_total_pages_on_cheerio)






# region Функции-проверяльщики

"""

Здесь нужно реализовать функции-проверяльщики, которые нужны для того, что бы передать им фрагменты кода, и они запустили полный кусок кода в среде JS cheerio (с текущей html страницей), для проверки корректности написанного кода, и его работоспособности

Сейчас нужно реализовать функцию с таким кодом JS внутри:

1. Функция, которая принимает строку кода, которая может быть примерно такой:

let totalPages = +$(".page-nav__nums_desktop > a").last().text().trim()
или let totalPages = +$('.site-main__inner > a[href]').eq(-1).text().trim()
или let totalPages = +$('.pagination > span').last().find('a').text().trim()

И возвращает значение в totalPages

В отличии от реализованной выше функции get_total_pages_on_cheerio - там передавался селектор, а тут надо что бы передавалась вся строка кода (или может быть даже несколько строк, но это скорее исключение).


Для того, что бы не допустить угроз безопасности, нужно будет использовать песочницу. Вот можно написать что-то типо такого кода:

const vm = require("vm");
const cheerio = require("cheerio");

const $ = cheerio.load(html);

const sandbox = {
    $,
    cheerio,
    Math,
    Number,
    String,
    result: null
};

const wrappedCode = `
try {
    ${userCode}
    result = totalPages;
} catch (e) {
    result = "__ERROR__:" + e.message;
}
`;

vm.runInNewContext(wrappedCode, sandbox, {
    timeout: 1000,
    codeGeneration: { strings: false, wasm: false }
});

"""






# region check_total_pages_code_on_cheerio

# Обёртка для агента, с использованием локального html из открытой Page
@tool(
    name="get_total_pages_on_current_page_cheerio_code",
    description=(
        "Запускает переданный JS-код (cheerio/Node.js) на HTML текущей страницы Playwright и возвращает значение переменной totalPages. "
        "Код запускается в песочнице vm (без eval/new Function и wasm). "
        "Ожидается, что в коде будет присваивание вида `let totalPages = ...` (для проверки корректного извлечения количества максимальных страниц в пагинации)."
    ),
    args=[
        {
            "name": "user_code",
            "type": "str",
            "required": True,
            "description": "JS-код, который должен вычислить переменную totalPages (например `let totalPages = +$('.pagination a').last().text().trim()`)",
        },
    ],
    returns={
        "status": "ok|error",
        "totalPages": "str|null — значение переменной totalPages (как в JS)",
        "error": "Описание ошибки, если была",
    },
    example_args={
        "user_code": "let totalPages = +$('.pagination > a').last().text().trim()",
    },
)
def get_total_pages_on_current_page_cheerio_code(user_code: str) -> dict[str, str | None]:
    """
    Обёртка над get_total_pages_on_cheerio_code(...), которая берёт HTML через текущую Playwright page.

    Требования:
    - до вызова должна быть установлена общая page через playwright_tool.shared_page.set_shared_page(page)
    """
    page = get_shared_page()
    html_content = page.content()
    return get_total_pages_on_cheerio_code(user_code=user_code, html_content=html_content)


def get_total_pages_on_cheerio_code(user_code: str, html_content: str) -> dict[str, str | None]:
    """
    Запускает переданный фрагмент JS-кода в окружении cheerio (Node.js) на HTML-странице и возвращает totalPages.

    Безопасность:
    - выполнение в vm.runInNewContext(...)
    - timeout 1000ms
    - запрещена генерация кода из строк (eval/new Function) и wasm
    - console подавлен, чтобы stdout был строго JSON
    """
    if not isinstance(user_code, str) or not user_code.strip():
        return {"status": "error", "totalPages": None, "error": "user_code должен быть непустой строкой"}

    # Записываем HTML во временный файл (удалим после вызова Node)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w", encoding="utf-8") as tmp:
        tmp.write(html_content or "")
        tmp_path = tmp.name

    user_code_js = json.dumps(user_code)  # безопасно экранируем код как JS-строку
    tmp_path_js = json.dumps(tmp_path)  # безопасно экранируем путь

    # ВАЖНО: печатаем строго JSON одним console.log, чтобы Python мог распарсить результат.
    # Также глушим console внутри песочницы, чтобы пользовательский код не портил stdout.
    node_script_template = """
const fs = require('fs');
const vm = require('vm');
const cheerio = require('cheerio');

function main() {
  try {
    const html = fs.readFileSync(__TMP_PATH__, 'utf-8');
    const $raw = cheerio.load(html);
    const userCode = __USER_CODE__;

    // Harden: оборачиваем host-объекты/функции в Proxy, скрывая constructor/__proto__/prototype.
    // Это закрывает типичные sandbox-escape цепочки вида:
    //   $.constructor("return process")()
    //   obj.constructor.constructor("return process")()
    //
    // ВАЖНО: не ломаем встроенные итераторы/методы (например spread: Math.max(...arr)).
    // Для этого:
    // - кэшируем proxy <-> raw (WeakMap)
    // - при вызове функций "распаковываем" this/args до raw
    // - при чтении методов у объектов биндим их к raw-объекту (иначе методы с internal slots падают на Proxy receiver)
    const DENY_PROPS = new Set(['constructor', '__proto__', 'prototype']);
    const RAW_TO_PROXY = new WeakMap();
    const PROXY_TO_RAW = new WeakMap();

    function unwrap(v) {
      return PROXY_TO_RAW.get(v) || v;
    }

    function makeSafe(value) {
      if (value === null || value === undefined) return value;
      const t = typeof value;
      if (t !== 'object' && t !== 'function') return value;

      // Если это уже наш Proxy — возвращаем как есть
      if (PROXY_TO_RAW.has(value)) return value;
      // Если raw уже обёрнут — возвращаем тот же Proxy
      const cached = RAW_TO_PROXY.get(value);
      if (cached) return cached;

      if (t === 'function') {
        const p = new Proxy(value, {
          get(target, prop, receiver) {
            if (DENY_PROPS.has(prop)) return undefined;
            const v = Reflect.get(target, prop, receiver);
            return makeSafe(v);
          },
          apply(target, thisArg, args) {
            const realThis = unwrap(thisArg);
            const realArgs = (args || []).map(unwrap);
            const res = Reflect.apply(target, realThis, realArgs);
            return makeSafe(res);
          },
        });
        RAW_TO_PROXY.set(value, p);
        PROXY_TO_RAW.set(p, value);
        return p;
      }

      // object
      const p = new Proxy(value, {
        get(target, prop, receiver) {
          if (DENY_PROPS.has(prop)) return undefined;
          // Берём значение с receiver=target, чтобы не получать Proxy как this в геттерах/методах.
          const v = Reflect.get(target, prop, target);
          if (typeof v === 'function') {
            // Биндим метод к raw-объекту, иначе built-in методы с internal slots могут падать на Proxy receiver
            return makeSafe(v.bind(target));
          }
          return makeSafe(v);
        },
      });
      RAW_TO_PROXY.set(value, p);
      PROXY_TO_RAW.set(p, value);
      return p;
    }

    const $ = makeSafe($raw);

    // Sandbox: даём только то, что нужно для cheerio-выражений.
    // console глушим, чтобы stdout не ломал JSON-ответ.
    const sandbox = {
      $,
      result: null,
      console: { log: () => {}, error: () => {}, warn: () => {}, info: () => {}, debug: () => {} },
    };

    // Чуть-чуть совместимости: некоторые сниппеты ожидают global/globalThis.
    sandbox.global = sandbox;
    sandbox.globalThis = sandbox;

    // Доп. урезание окружения
    sandbox.process = undefined;
    sandbox.require = undefined;
    sandbox.Buffer = undefined;

    const prefix = `"use strict";
try{Object.defineProperty(Function.prototype,'constructor',{value:undefined,writable:false,configurable:false});}catch(e){}
try{Object.defineProperty(Object.prototype,'__proto__',{get:undefined,set:undefined,configurable:false});}catch(e){}
try {
`;
    const suffix = `
  if (typeof totalPages === "undefined") {
    result = "__ERROR__:totalPages is not defined";
  } else {
    result = totalPages;
  }
} catch (e) {
  result = "__ERROR__:" + (e && e.message ? e.message : String(e));
}
`;

    const wrappedCode = prefix + userCode + suffix;
    vm.runInNewContext(wrappedCode, sandbox, {
      timeout: 1000,
      codeGeneration: { strings: false, wasm: false },
    });

    const r = sandbox.result;
    if (typeof r === 'string' && r.startsWith('__ERROR__:')) {
      console.log(JSON.stringify({ status: 'error', totalPages: null, error: r.slice(10) }));
    } else {
      console.log(JSON.stringify({ status: 'ok', totalPages: String(r), error: null }));
    }
  } catch (e) {
    console.log(JSON.stringify({ status: 'error', totalPages: null, error: String(e && e.message ? e.message : e) }));
  }
}

main();
""".strip()
    node_script = (
        node_script_template
        .replace("__TMP_PATH__", tmp_path_js)
        .replace("__USER_CODE__", user_code_js)
    )

    try:
        result = subprocess.run(
            ["node", "-e", node_script],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            err = (result.stderr or "").strip() or f"Node.js exited with code {result.returncode}"
            return {"status": "error", "totalPages": None, "error": err}

        output = (result.stdout or "").strip()
        # На всякий случай берём последнюю непустую строку (если окружение всё же что-то напечатало)
        last_line = ""
        for line in reversed(output.splitlines()):
            if line.strip():
                last_line = line.strip()
                break
        if not last_line:
            return {"status": "error", "totalPages": None, "error": "Empty Node.js output"}

        try:
            parsed = json.loads(last_line)
        except Exception:
            return {"status": "error", "totalPages": None, "error": f"Unexpected Node.js output: {output!r}"}

        status = parsed.get("status")
        if status == "ok":
            return {"status": "ok", "totalPages": parsed.get("totalPages"), "error": None}
        return {"status": "error", "totalPages": None, "error": parsed.get("error") or "Unknown error"}
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass





# # get_total_pages_on_cheerio_code; 
# # print(get_total_pages_on_cheerio_code("let totalPages = +$(\"a\").last().text().trim()", "<a>1</a><a>5</a>"))


# """
#   "action": "get_total_pages_on_current_page_cheerio_code",
#   "args": {
#     "user_code": "let totalPages = Math.max(...$('nav.woocommerce-pagination a.page-numbers').get().map(item => +$(item).text().trim()).filter(Boolean))"
#   },
# """



# user_code_test = "let totalPages = Math.max(...$('nav.woocommerce-pagination a.page-numbers').get().map(item => +$(item).text().trim()).filter(Boolean))"
# url = "https://makitaclub.ru/?s=%D0%B8%D0%BD%D1%81%D1%82%D1%80%D1%83%D0%BC%D0%B5%D0%BD%D1%82&post_type=product"
# html_content = get_html_from_cache(url)
# result_get_total_pages_on_cheerio_code = get_total_pages_on_cheerio_code(user_code_test, html_content)
# print("result_get_total_pages_on_cheerio_code:")
# print(result_get_total_pages_on_cheerio_code)













"""

Инструмент для проверки корректности извлечения ссылок из селектора на товар. Ожидает, что будут переданы примерно такие строки:

let HOST = "https://makitaclub.ru"
let products = $('.products .card a.stretched-link')
let product = products?.eq(0)
let link = HOST + $(product)?.attr('href')
console.log("link = " + link)

"""


# region check_product_link_code_on_cheerio

# Обёртка для агента, с использованием локального html из открытой Page
@tool(
    name="get_product_link_on_current_page_cheerio_code",
    description=(
        "Запускает переданный JS-код (cheerio/Node.js) на HTML текущей страницы Playwright и возвращает значение переменной `link` "
        "(проверка корректного извлечения ссылки на товар из селектора). "
        "Код запускается в песочнице vm (без eval/new Function и wasm)."
    ),
    args=[
        {
            "name": "user_code",
            "type": "str",
            "required": True,
            "description": (
                "JS-код, который должен вычислить переменную `link`, например:\n"
                "let HOST='https://example.com';\n"
                "let products=$('.products a.stretched-link');\n"
                "let product=products?.eq(0);\n"
                "let link=HOST + $(product)?.attr('href');\n"
                "console.log('link = ' + link);"
            ),
        },
    ],
    returns={
        "status": "ok|error",
        "link": "str|null — значение переменной link (как в JS)",
        "logs": "str|null — отладочные логи console.log (по строкам), если были",
        "error": "Описание ошибки, если была",
    },
    example_args={
        "user_code": "let HOST='https://makitaclub.ru'; let products=$('.products .card a.stretched-link'); let product=products?.eq(0); let link=HOST + $(product)?.attr('href'); console.log('link = ' + link);",
    },
)
def get_product_link_on_current_page_cheerio_code(user_code: str) -> dict[str, str | None]:
    """
    Обёртка над get_product_link_on_cheerio_code(...), которая берёт HTML через текущую Playwright page.

    Требования:
    - до вызова должна быть установлена общая page через playwright_tool.shared_page.set_shared_page(page)
    """
    page = get_shared_page()
    html_content = page.content()
    return get_product_link_on_cheerio_code(user_code=user_code, html_content=html_content)


def get_product_link_on_cheerio_code(user_code: str, html_content: str) -> dict[str, str | None]:
    """
    Запускает переданный фрагмент JS-кода в окружении cheerio (Node.js) на HTML-странице и возвращает link.

    Ожидается, что пользовательский код присвоит переменную `link` (например `let link = ...`).
    console.log(...) не печатается в stdout, а собирается в logs, чтобы не ломать JSON-ответ.
    """
    if not isinstance(user_code, str) or not user_code.strip():
        return {"status": "error", "link": None, "logs": None, "error": "user_code должен быть непустой строкой"}

    # Записываем HTML во временный файл (удалим после вызова Node)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w", encoding="utf-8") as tmp:
        tmp.write(html_content or "")
        tmp_path = tmp.name

    user_code_js = json.dumps(user_code)  # безопасно экранируем код как JS-строку
    tmp_path_js = json.dumps(tmp_path)  # безопасно экранируем путь

    node_script_template = """
const fs = require('fs');
const vm = require('vm');
const cheerio = require('cheerio');

function main() {
  try {
    const html = fs.readFileSync(__TMP_PATH__, 'utf-8');
    const $raw = cheerio.load(html);
    const userCode = __USER_CODE__;

    const logs = [];
    // Harden: оборачиваем host-объекты/функции в Proxy, скрывая constructor/__proto__/prototype.
    // Это закрывает типичные sandbox-escape цепочки вида:
    //   $.constructor("return process")()
    //   obj.constructor.constructor("return process")()
    const DENY_PROPS = new Set(['constructor', '__proto__', 'prototype']);
    const RAW_TO_PROXY = new WeakMap();
    const PROXY_TO_RAW = new WeakMap();

    function unwrap(v) {
      return PROXY_TO_RAW.get(v) || v;
    }

    function makeSafe(value) {
      if (value === null || value === undefined) return value;
      const t = typeof value;
      if (t !== 'object' && t !== 'function') return value;

      if (PROXY_TO_RAW.has(value)) return value;
      const cached = RAW_TO_PROXY.get(value);
      if (cached) return cached;

      if (t === 'function') {
        const p = new Proxy(value, {
          get(target, prop, receiver) {
            if (DENY_PROPS.has(prop)) return undefined;
            const v = Reflect.get(target, prop, receiver);
            return makeSafe(v);
          },
          apply(target, thisArg, args) {
            const realThis = unwrap(thisArg);
            const realArgs = (args || []).map(unwrap);
            const res = Reflect.apply(target, realThis, realArgs);
            return makeSafe(res);
          },
        });
        RAW_TO_PROXY.set(value, p);
        PROXY_TO_RAW.set(p, value);
        return p;
      }

      const p = new Proxy(value, {
        get(target, prop, receiver) {
          if (DENY_PROPS.has(prop)) return undefined;
          const v = Reflect.get(target, prop, target);
          if (typeof v === 'function') return makeSafe(v.bind(target));
          return makeSafe(v);
        },
      });
      RAW_TO_PROXY.set(value, p);
      PROXY_TO_RAW.set(p, value);
      return p;
    }

    const $ = makeSafe($raw);

    const sandbox = {
      $,
      result: null,
      logs,
      console: {
        log: (...args) => logs.push(args.map(a => (typeof a === 'string' ? a : JSON.stringify(a))).join(' ')),
        error: (...args) => logs.push(args.map(a => (typeof a === 'string' ? a : JSON.stringify(a))).join(' ')),
        warn: (...args) => logs.push(args.map(a => (typeof a === 'string' ? a : JSON.stringify(a))).join(' ')),
        info: (...args) => logs.push(args.map(a => (typeof a === 'string' ? a : JSON.stringify(a))).join(' ')),
        debug: (...args) => logs.push(args.map(a => (typeof a === 'string' ? a : JSON.stringify(a))).join(' ')),
      },
    };

    sandbox.global = sandbox;
    sandbox.globalThis = sandbox;
    sandbox.process = undefined;
    sandbox.require = undefined;
    sandbox.Buffer = undefined;

    const prefix = `"use strict";
try{Object.defineProperty(Function.prototype,'constructor',{value:undefined,writable:false,configurable:false});}catch(e){}
try{Object.defineProperty(Object.prototype,'__proto__',{get:undefined,set:undefined,configurable:false});}catch(e){}
try {
`;
    const suffix = `
  if (typeof link === "undefined") {
    result = "__ERROR__:link is not defined";
  } else {
    result = link;
  }
} catch (e) {
  result = "__ERROR__:" + (e && e.message ? e.message : String(e));
}
`;

    const wrappedCode = prefix + userCode + suffix;
    vm.runInNewContext(wrappedCode, sandbox, {
      timeout: 1000,
      codeGeneration: { strings: false, wasm: false },
    });

    const r = sandbox.result;
    const joinedLogs = (sandbox.logs || []).join('\\n');
    if (typeof r === 'string' && r.startsWith('__ERROR__:')) {
      console.log(JSON.stringify({ status: 'error', link: null, logs: joinedLogs || null, error: r.slice(10) }));
    } else {
      console.log(JSON.stringify({ status: 'ok', link: String(r), logs: joinedLogs || null, error: null }));
    }
  } catch (e) {
    console.log(JSON.stringify({ status: 'error', link: null, logs: null, error: String(e && e.message ? e.message : e) }));
  }
}

main();
""".strip()
    node_script = (
        node_script_template
        .replace("__TMP_PATH__", tmp_path_js)
        .replace("__USER_CODE__", user_code_js)
    )

    try:
        result = subprocess.run(
            ["node", "-e", node_script],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            err = (result.stderr or "").strip() or f"Node.js exited with code {result.returncode}"
            return {"status": "error", "link": None, "logs": None, "error": err}

        output = (result.stdout or "").strip()
        last_line = ""
        for line in reversed(output.splitlines()):
            if line.strip():
                last_line = line.strip()
                break
        if not last_line:
            return {"status": "error", "link": None, "logs": None, "error": "Empty Node.js output"}

        try:
            parsed = json.loads(last_line)
        except Exception:
            return {"status": "error", "link": None, "logs": None, "error": f"Unexpected Node.js output: {output!r}"}

        status = parsed.get("status")
        if status == "ok":
            return {"status": "ok", "link": parsed.get("link"), "logs": parsed.get("logs"), "error": None}
        return {
            "status": "error",
            "link": None,
            "logs": parsed.get("logs"),
            "error": parsed.get("error") or "Unknown error",
        }
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass







# get_product_link_on_cheerio_code
# html="<div class=\"products\"><div class=\"card\"><a class=\"stretched-link\" href=\"/p/123\">x</a></div></div>"
# code="let HOST = \"https://makitaclub.ru\"; let products = $(\".products .card a.stretched-link\"); let product = products?.eq(0); let link = HOST + $(product)?.attr(\"href\"); console.log(\"link = \" + link)"; print(get_product_link_on_cheerio_code(code, html))




















# region check_selector_on_cheerio

# Обёртка для агента, с использованием локального html из открытой Page
@tool(
    name="check_selector_on_current_page_cheerio",
    description="Проверяет, является ли селектор верным и валидным в cheerio (Node.js). Возвращает количество совпадений CSS-селектора на текущей странице Playwright",
    args=[
        {
            "name": "selector",
            "type": "str",
            "required": True,
            "description": "CSS-селектор для поиска",
        },
    ],
    returns={
        "count": "int — количество найденных элементов по селектору на текущей странице Playwright, либо текст ошибки",
    },
    example_args={
        "selector": "div.item",
    },
)
def check_selector_on_current_page_cheerio(selector: str) -> int:
    """
    Обёртка над check_selector_on_cheerio(...), которая берёт HTML через текущую Playwright page.

    Требования:
    - до вызова должна быть установлена общая page через playwright_tool.shared_page.set_shared_page(page)
    """
    page = get_shared_page()
    html_content = page.content()
    return check_selector_on_cheerio(selector=selector, html_content=html_content)




# @tool(
#     name="check_selector_on_cheerio",
#     description="Считает количество совпадений CSS-селектора в HTML через cheerio (Node.js)",
#     args=[
#         {
#             "name": "selector",
#             "type": "str",
#             "required": True,
#             "description": "CSS-селектор для поиска",
#         },
#         {
#             "name": "html_content",
#             "type": "str",
#             "required": True,
#             "description": "HTML-код, в котором ищем селектор",
#         },
#     ],
#     returns={
#         "count": "int — количество найденных элементов по селектору",
#     },
#     example_args={
#         "selector": "div.item",
#         "html_content": "<div class='item'></div><div class='other'></div>",
#     },
# )

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










# region get_html_frame

# Обёртка для агента, с использованием локального html из открытой Page
@tool(
    name="get_html_frame_on_current_page",
    description="Строит компактный HTML-фрейм вокруг первого элемента по CSS-селектору, беря HTML из текущей страницы Playwright",
    args=[
        {"name": "selector", "type": "str", "required": True, "description": "CSS-селектор для поиска target"},
        {"name": "max_frame_chars", "type": "int", "required": False, "description": "Макс. длина итогового HTML-фрейма"},
        {"name": "max_container_text_chars", "type": "int", "required": False, "description": "Лимит текста при выборе контейнера"},
        {"name": "max_container_html_chars", "type": "int", "required": False, "description": "Лимит HTML при выборе контейнера"},
        {"name": "sibling_elems", "type": "int", "required": False, "description": "Сколько соседних элементов сохранять рядом с target"},
        {"name": "max_text_node_chars", "type": "int", "required": False, "description": "Лимит длины текста внутри узла"},
        {"name": "ancestor_levels", "type": "int", "required": False, "description": "Сколько уровней предков сохранять. Если нужно расширить окно, попробуй увеличить значение например до 5"},
    ],
    returns={
        "html_frame": "str — HTML-фрейм с комментариями TRIMMED_* с количеством удалённых узлов и маркерами TARGET вокруг исходного элемента",
    },
    example_args={
        "selector": ".price",
        "max_frame_chars": 2000,
    },
)
def get_html_frame_on_current_page(
    selector: str,
    *,
    max_frame_chars: int = 3000,
    max_container_text_chars: int = 1000,
    max_container_html_chars: int = 5000,
    sibling_elems: int = 2,
    max_text_node_chars: int = 200,
    ancestor_levels: int = 3,
) -> str:
    """
    Обёртка над get_html_frame(...), которая берёт HTML через текущую Playwright page.

    Требования:
    - до вызова должна быть установлена общая page через playwright_tool.shared_page.set_shared_page(page)
    """
    page = get_shared_page()
    html = page.content()
    return get_html_frame(
        html=html,
        selector=selector,
        max_frame_chars=max_frame_chars,
        max_container_text_chars=max_container_text_chars,
        max_container_html_chars=max_container_html_chars,
        sibling_elems=sibling_elems,
        max_text_node_chars=max_text_node_chars,
        ancestor_levels=ancestor_levels,
    )


# @tool(
#     name="get_html_frame",
#     description="Строит компактный HTML-фрейм вокруг первого элемента по CSS-селектору, добавляя маркеры TARGET и комментарии об усечениях.",
#     args=[
#         {"name": "html", "type": "str", "required": True, "description": "Исходный HTML-документ"},
#         {"name": "selector", "type": "str", "required": True, "description": "CSS-селектор для поиска target"},
#         {"name": "max_frame_chars", "type": "int", "required": False, "description": "Макс. длина итогового HTML-фрейма"},
#         {"name": "max_container_text_chars", "type": "int", "required": False, "description": "Лимит текста при выборе контейнера"},
#         {"name": "max_container_html_chars", "type": "int", "required": False, "description": "Лимит HTML при выборе контейнера"},
#         {"name": "sibling_elems", "type": "int", "required": False, "description": "Сколько соседних элементов сохранять рядом с target"},
#         {"name": "max_text_node_chars", "type": "int", "required": False, "description": "Лимит длины текста внутри узла"},
#         {"name": "ancestor_levels", "type": "int", "required": False, "description": "Сколько уровней предков сохранять"},
#     ],
#     returns={
#         "html_frame": "str — HTML-фрейм с комментариями TRIMMED_* и маркерами TARGET",
#     },
#     example_args={
#         "html": "<div class='card'><span class='price'>$10</span></div>",
#         "selector": ".price",
#         "max_frame_chars": 2000,
#     },
# )

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










# # Проверка
# url = "https://makitaclub.ru/?s=%D0%B8%D0%BD%D1%81%D1%82%D1%80%D1%83%D0%BC%D0%B5%D0%BD%D1%82&post_type=product"
# html_content = get_html_from_cache(url)
# # save_page_html(html_content, filename = "page_html.html")

# selector = ".products .product-card a.stretched-link[href*='/products/']"
# # selector = ".col-sm-6 .woocommerce-Price-amount.amount"
# # result_get_html_frame = get_html_frame(html_content, selector)
# result_get_html_frame = get_html_frame(html_content, selector, ancestor_levels = 5)
# # print(f"result_get_html_frame:\n", result_get_html_frame)








# region parse_product_blocks_on_current_page

# Обёртка для агента, с использованием локального html из открытой Page
@tool(
    name="parse_product_blocks_on_current_page",
    description="Анализирует HTML, находит полные блоки товаров на основе селектора ссылки внутри товара и возвращает их HTML и общий селектор. Важно: в ответе первый элемент массива blocks_html всегда будет пуст - это корректный ответ. Заполненными будут 2й и 3й элементы массива, там будут лежать объекты 2го и 3го товара на странице. Также помни, что данный инструмент не гарантирует полную правильность block_selector.",
    args=[
        {
            "name": "item_selector",
            "type": "str",
            "required": True,
            "description": "CSS селектор элемента внутри карточки товара (например, ссылка на товар)",
        }
    ],
    returns={
        "status": "ok|error",
        "blocks_html": "list[str|None]",
        "block_selector": "str",
        "error": "Описание ошибки",
    },
    example_args={
        "item_selector": "a.stretched-link",
    },
)
def parse_product_blocks_on_current_page(item_selector: str) -> Dict[str, Any]:
    """
    Обёртка над parse_product_blocks(...), которая берёт HTML через текущую Playwright page.

    Требования:
    - до вызова должна быть установлена общая page через playwright_tool.shared_page.set_shared_page(page)
    """
    page = get_shared_page()
    html_content = page.content()
    return parse_product_blocks(html_content=html_content, item_selector=item_selector)


# @tool(
#     name="parse_product_blocks",
#     description="Анализирует HTML, находит полные блоки товаров на основе селектора ссылки внутри товара и возвращает их HTML и общий селектор. Важно: первый элемент массива blocks_html всегда будет пуст - это корректный ответ. Заполненными будут 2й и 3й элементы массива, там будут лежать объекты 2го и 3го товара на странице. Также помни, что данный инструмент не гарантирует полную правильность block_selector.",
#     args=[
#         {
#             "name": "html_content",
#             "type": "str",
#             "required": True,
#             "description": "HTML код страницы"
#         },
#         {
#             "name": "item_selector",
#             "type": "str",
#             "required": True,
#             "description": "CSS селектор элемента внутри карточки товара (например, ссылка на товар)"
#         }
#     ],
#     returns={
#         "status": "ok|error",
#         "blocks_html": "list[str|None]",
#         "block_selector": "str",
#         "error": "Описание ошибки"
#     },
#     example_args={
#         "html_content": "<html>...</html>",
#         "item_selector": "a.stretched-link"
#     }
# )
def parse_product_blocks(html_content: str, item_selector: str) -> Dict[str, Any]:
    """
    Анализирует структуру HTML и извлекает полные блоки товаров.
    """
    """ 
    Алгоритм поиска блока товара (описание как работает эта функция):

    1. Мы находим целевой элемент (ссылку) внутри товара.
    2. Начинаем подниматься вверх по его родителям (от <a> к div, выше и выше).
    3. На каждом шаге проверяем: содержит ли этот родитель "соседние" целевые ссылки (предыдущую или следующую)?
    4. Как только мы находим родителя, который содержит соседей — значит, мы поднялись слишком высоко (это уже общий контейнер списка товаров).
    5. Следовательно, предыдущий проверенный узел (дочерний по отношению к общему контейнеру) и является карточкой товара.
    """

    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        elements = soup.select(item_selector)
        
        # 1. Проверяем количество элементов
        count = len(elements)
        if count < 5:
            error_msg = f"Найдено слишком мало элементов ({count}), ожидалось минимум 5."
            print(error_msg)
            return {
                "status": "error",
                "blocks_html": [],
                "block_selector": "",
                "error": error_msg
            }

        # Выбираем референсные элементы (1-й, 2-й, 3-й, 4-й)
        # Индексы: 0, 1, 2, 3
        el1 = elements[0]
        el2 = elements[1]
        el3 = elements[2]
        el4 = elements[3] # Нужен для поиска блока 3-го товара

        def find_container_block(target: Tag, neighbor_prev: Tag, neighbor_next: Tag) -> Optional[Tag]:
            """
            Находит максимально высокий родительский блок для target, 
            который НЕ содержит neighbor_prev и neighbor_next.
            """
            current = target
            # Поднимаемся по родителям target
            while current.parent:
                parent = current.parent
                
                # Если мы дошли до корня (html/body), останавливаемся
                if parent.name in ['html', 'body', '[document]']:
                    return current

                # Проверяем, содержит ли родитель соседей.
                # Метод .find() может быть медленным, лучше проверить вхождение
                # Но так как мы идем вверх, проще проверить:
                # Является ли parent предком для neighbor_prev ИЛИ neighbor_next?
                
                prev_parents = list(neighbor_prev.parents)
                next_parents = list(neighbor_next.parents)
                
                if parent in prev_parents or parent in next_parents:
                    # Родитель общий для соседей, значит current - это искомый изолированный блок
                    return current
                
                current = parent
            return target

        # 2. Находим полный блок 2-го товара (между 1 и 3)
        block2 = find_container_block(el2, el1, el3)
        
        # 3. Находим полный блок 3-го товара (между 2 и 4)
        block3 = find_container_block(el3, el2, el4)

        if not block2 or not block3:
             return {
                "status": "error",
                "blocks_html": [],
                "block_selector": "",
                "error": "Не удалось определить границы блоков товаров."
            }

        # 4. Вычисляем общий селектор для блоков
        # Логика: берем тег и классы, которые есть и у block2, и у block3
        tag_name = block2.name
        classes2 = set(block2.get('class', []))
        classes3 = set(block3.get('class', []))
        
        # Пересечение классов (чтобы исключить уникальные модификаторы типа 'first', 'hover')
        common_classes = classes2.intersection(classes3)
        
        # Формируем селектор
        generated_selector = tag_name
        if common_classes:
            # Сортируем для стабильности и добавляем точки
            sorted_classes = sorted(list(common_classes))
            generated_selector += "." + ".".join(sorted_classes)

        # 5. Формируем ответ
        result_array = [
            None,                # Первый элемент пустой по ТЗ
            str(block2),         # HTML код блока 2
            str(block3)          # HTML код блока 3
        ]

        return {
            "status": "ok",
            "blocks_html": result_array,
            "block_selector": generated_selector,
            "error": None
        }

    except Exception as e:
        return {
            "status": "error",
            "blocks_html": [],
            "block_selector": "",
            "error": str(e)
        }



# # Проверка:

# url = "https://makitaclub.ru/?s=%D0%B8%D0%BD%D1%81%D1%82%D1%80%D1%83%D0%BC%D0%B5%D0%BD%D1%82&post_type=product"
# html_content = get_html_from_cache(url)

# selector = ".products .product-card a.stretched-link[href*='/products/']"
# result_parse_product_blocks = parse_product_blocks(html_content, selector)
# print(f"result_parse_product_blocks:\n", result_parse_product_blocks)
























# region _


""" 
Код 2х методов проверки ОS кода путём их выполнения, до закрытия дыр с конструктором:
""" 


# # region Функции-проверяльщики

# """

# Здесь нужно реализовать функции-проверяльщики, которые нужны для того, что бы передать им фрагменты кода, и они запустили полный кусок кода в среде JS cheerio (с текущей html страницей), для проверки корректности написанного кода, и его работоспособности

# Сейчас нужно реализовать функцию с таким кодом JS внутри:

# 1. Функция, которая принимает строку кода, которая может быть примерно такой:

# let totalPages = +$(".page-nav__nums_desktop > a").last().text().trim()
# или let totalPages = +$('.site-main__inner > a[href]').eq(-1).text().trim()
# или let totalPages = +$('.pagination > span').last().find('a').text().trim()

# И возвращает значение в totalPages

# В отличии от реализованной выше функции get_total_pages_on_cheerio - там передавался селектор, а тут надо что бы передавалась вся строка кода (или может быть даже несколько строк, но это скорее исключение).


# Для того, что бы не допустить угроз безопасности, нужно будет использовать песочницу. Вот можно написать что-то типо такого кода:

# const vm = require("vm");
# const cheerio = require("cheerio");

# const $ = cheerio.load(html);

# const sandbox = {
#     $,
#     cheerio,
#     Math,
#     Number,
#     String,
#     result: null
# };

# const wrappedCode = `
# try {
#     ${userCode}
#     result = totalPages;
# } catch (e) {
#     result = "__ERROR__:" + e.message;
# }
# `;

# vm.runInNewContext(wrappedCode, sandbox, {
#     timeout: 1000,
#     codeGeneration: { strings: false, wasm: false }
# });

# """






# # region check_total_pages_code_on_cheerio

# # Обёртка для агента, с использованием локального html из открытой Page
# @tool(
#     name="get_total_pages_on_current_page_cheerio_code",
#     description=(
#         "Запускает переданный JS-код (cheerio/Node.js) на HTML текущей страницы Playwright и возвращает значение переменной totalPages. "
#         "Код запускается в песочнице vm (без eval/new Function и wasm). "
#         "Ожидается, что в коде будет присваивание вида `let totalPages = ...` (для проверки корректного извлечения количества максимальных страниц в пагинации)."
#     ),
#     args=[
#         {
#             "name": "user_code",
#             "type": "str",
#             "required": True,
#             "description": "JS-код, который должен вычислить переменную totalPages (например `let totalPages = +$('.pagination a').last().text().trim()`)",
#         },
#     ],
#     returns={
#         "status": "ok|error",
#         "totalPages": "str|null — значение переменной totalPages (как в JS)",
#         "error": "Описание ошибки, если была",
#     },
#     example_args={
#         "user_code": "let totalPages = +$('.pagination > a').last().text().trim()",
#     },
# )
# def get_total_pages_on_current_page_cheerio_code(user_code: str) -> dict[str, str | None]:
#     """
#     Обёртка над get_total_pages_on_cheerio_code(...), которая берёт HTML через текущую Playwright page.

#     Требования:
#     - до вызова должна быть установлена общая page через playwright_tool.shared_page.set_shared_page(page)
#     """
#     page = get_shared_page()
#     html_content = page.content()
#     return get_total_pages_on_cheerio_code(user_code=user_code, html_content=html_content)


# def get_total_pages_on_cheerio_code(user_code: str, html_content: str) -> dict[str, str | None]:
#     """
#     Запускает переданный фрагмент JS-кода в окружении cheerio (Node.js) на HTML-странице и возвращает totalPages.

#     Безопасность:
#     - выполнение в vm.runInNewContext(...)
#     - timeout 1000ms
#     - запрещена генерация кода из строк (eval/new Function) и wasm
#     - console подавлен, чтобы stdout был строго JSON
#     """
#     if not isinstance(user_code, str) or not user_code.strip():
#         return {"status": "error", "totalPages": None, "error": "user_code должен быть непустой строкой"}

#     # Записываем HTML во временный файл (удалим после вызова Node)
#     with tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w", encoding="utf-8") as tmp:
#         tmp.write(html_content or "")
#         tmp_path = tmp.name

#     user_code_js = json.dumps(user_code)  # безопасно экранируем код как JS-строку
#     tmp_path_js = json.dumps(tmp_path)  # безопасно экранируем путь

#     # ВАЖНО: печатаем строго JSON одним console.log, чтобы Python мог распарсить результат.
#     # Также глушим console внутри песочницы, чтобы пользовательский код не портил stdout.
#     node_script_template = """
# const fs = require('fs');
# const vm = require('vm');
# const cheerio = require('cheerio');

# function main() {
#   try {
#     const html = fs.readFileSync(__TMP_PATH__, 'utf-8');
#     const $ = cheerio.load(html);
#     const userCode = __USER_CODE__;

#     // Sandbox: даём только то, что нужно для cheerio-выражений + базовые примитивы.
#     // console глушим, чтобы stdout не ломал JSON-ответ.
#     const sandbox = {
#       $,
#       cheerio,
#       Math,
#       Number,
#       String,
#       Boolean,
#       Array,
#       result: null,
#       console: { log: () => {}, error: () => {}, warn: () => {}, info: () => {}, debug: () => {} },
#     };

#     // Чуть-чуть совместимости: некоторые сниппеты ожидают global/globalThis.
#     sandbox.global = sandbox;
#     sandbox.globalThis = sandbox;

#     // Доп. урезание окружения
#     sandbox.process = undefined;
#     sandbox.require = undefined;
#     sandbox.Buffer = undefined;

#     const prefix = `"use strict";\ntry {\n`;
#     const suffix = `
#   if (typeof totalPages === "undefined") {
#     result = "__ERROR__:totalPages is not defined";
#   } else {
#     result = totalPages;
#   }
# } catch (e) {
#   result = "__ERROR__:" + (e && e.message ? e.message : String(e));
# }
# `;

#     const wrappedCode = prefix + userCode + suffix;
#     vm.runInNewContext(wrappedCode, sandbox, {
#       timeout: 1000,
#       codeGeneration: { strings: false, wasm: false },
#     });

#     const r = sandbox.result;
#     if (typeof r === 'string' && r.startsWith('__ERROR__:')) {
#       console.log(JSON.stringify({ status: 'error', totalPages: null, error: r.slice(10) }));
#     } else {
#       console.log(JSON.stringify({ status: 'ok', totalPages: String(r), error: null }));
#     }
#   } catch (e) {
#     console.log(JSON.stringify({ status: 'error', totalPages: null, error: String(e && e.message ? e.message : e) }));
#   }
# }

# main();
# """.strip()
#     node_script = (
#         node_script_template
#         .replace("__TMP_PATH__", tmp_path_js)
#         .replace("__USER_CODE__", user_code_js)
#     )

#     try:
#         result = subprocess.run(
#             ["node", "-e", node_script],
#             capture_output=True,
#             text=True,
#             check=False,
#         )

#         if result.returncode != 0:
#             err = (result.stderr or "").strip() or f"Node.js exited with code {result.returncode}"
#             return {"status": "error", "totalPages": None, "error": err}

#         output = (result.stdout or "").strip()
#         # На всякий случай берём последнюю непустую строку (если окружение всё же что-то напечатало)
#         last_line = ""
#         for line in reversed(output.splitlines()):
#             if line.strip():
#                 last_line = line.strip()
#                 break
#         if not last_line:
#             return {"status": "error", "totalPages": None, "error": "Empty Node.js output"}

#         try:
#             parsed = json.loads(last_line)
#         except Exception:
#             return {"status": "error", "totalPages": None, "error": f"Unexpected Node.js output: {output!r}"}

#         status = parsed.get("status")
#         if status == "ok":
#             return {"status": "ok", "totalPages": parsed.get("totalPages"), "error": None}
#         return {"status": "error", "totalPages": None, "error": parsed.get("error") or "Unknown error"}
#     finally:
#         try:
#             os.remove(tmp_path)
#         except OSError:
#             pass







# """

# Инструмент для проверки корректности извлечения ссылок из селектора на товар. Ожидает, что будут переданы примерно такие строки:

# let HOST = "https://makitaclub.ru"
# let products = $('.products .card a.stretched-link')
# let product = products?.eq(0)
# let link = HOST + $(product)?.attr('href')
# console.log("link = " + link)

# """


# # region check_product_link_code_on_cheerio

# # Обёртка для агента, с использованием локального html из открытой Page
# @tool(
#     name="get_product_link_on_current_page_cheerio_code",
#     description=(
#         "Запускает переданный JS-код (cheerio/Node.js) на HTML текущей страницы Playwright и возвращает значение переменной `link` "
#         "(проверка корректного извлечения ссылки на товар из селектора). "
#         "Код запускается в песочнице vm (без eval/new Function и wasm)."
#     ),
#     args=[
#         {
#             "name": "user_code",
#             "type": "str",
#             "required": True,
#             "description": (
#                 "JS-код, который должен вычислить переменную `link`, например:\n"
#                 "let HOST='https://example.com';\n"
#                 "let products=$('.products a.stretched-link');\n"
#                 "let product=products?.eq(0);\n"
#                 "let link=HOST + $(product)?.attr('href');\n"
#                 "console.log('link = ' + link);"
#             ),
#         },
#     ],
#     returns={
#         "status": "ok|error",
#         "link": "str|null — значение переменной link (как в JS)",
#         "logs": "str|null — отладочные логи console.log (по строкам), если были",
#         "error": "Описание ошибки, если была",
#     },
#     example_args={
#         "user_code": "let HOST='https://makitaclub.ru'; let products=$('.products .card a.stretched-link'); let product=products?.eq(0); let link=HOST + $(product)?.attr('href'); console.log('link = ' + link);",
#     },
# )
# def get_product_link_on_current_page_cheerio_code(user_code: str) -> dict[str, str | None]:
#     """
#     Обёртка над get_product_link_on_cheerio_code(...), которая берёт HTML через текущую Playwright page.

#     Требования:
#     - до вызова должна быть установлена общая page через playwright_tool.shared_page.set_shared_page(page)
#     """
#     page = get_shared_page()
#     html_content = page.content()
#     return get_product_link_on_cheerio_code(user_code=user_code, html_content=html_content)


# def get_product_link_on_cheerio_code(user_code: str, html_content: str) -> dict[str, str | None]:
#     """
#     Запускает переданный фрагмент JS-кода в окружении cheerio (Node.js) на HTML-странице и возвращает link.

#     Ожидается, что пользовательский код присвоит переменную `link` (например `let link = ...`).
#     console.log(...) не печатается в stdout, а собирается в logs, чтобы не ломать JSON-ответ.
#     """
#     if not isinstance(user_code, str) or not user_code.strip():
#         return {"status": "error", "link": None, "logs": None, "error": "user_code должен быть непустой строкой"}

#     # Записываем HTML во временный файл (удалим после вызова Node)
#     with tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w", encoding="utf-8") as tmp:
#         tmp.write(html_content or "")
#         tmp_path = tmp.name

#     user_code_js = json.dumps(user_code)  # безопасно экранируем код как JS-строку
#     tmp_path_js = json.dumps(tmp_path)  # безопасно экранируем путь

#     node_script_template = """
# const fs = require('fs');
# const vm = require('vm');
# const cheerio = require('cheerio');

# function main() {
#   try {
#     const html = fs.readFileSync(__TMP_PATH__, 'utf-8');
#     const $ = cheerio.load(html);
#     const userCode = __USER_CODE__;

#     const logs = [];
#     const sandbox = {
#       $,
#       cheerio,
#       Math,
#       Number,
#       String,
#       Boolean,
#       Array,
#       result: null,
#       logs,
#       console: {
#         log: (...args) => logs.push(args.map(a => (typeof a === 'string' ? a : JSON.stringify(a))).join(' ')),
#         error: (...args) => logs.push(args.map(a => (typeof a === 'string' ? a : JSON.stringify(a))).join(' ')),
#         warn: (...args) => logs.push(args.map(a => (typeof a === 'string' ? a : JSON.stringify(a))).join(' ')),
#         info: (...args) => logs.push(args.map(a => (typeof a === 'string' ? a : JSON.stringify(a))).join(' ')),
#         debug: (...args) => logs.push(args.map(a => (typeof a === 'string' ? a : JSON.stringify(a))).join(' ')),
#       },
#     };

#     sandbox.global = sandbox;
#     sandbox.globalThis = sandbox;
#     sandbox.process = undefined;
#     sandbox.require = undefined;
#     sandbox.Buffer = undefined;

#     const prefix = `"use strict";\ntry {\n`;
#     const suffix = `
#   if (typeof link === "undefined") {
#     result = "__ERROR__:link is not defined";
#   } else {
#     result = link;
#   }
# } catch (e) {
#   result = "__ERROR__:" + (e && e.message ? e.message : String(e));
# }
# `;

#     const wrappedCode = prefix + userCode + suffix;
#     vm.runInNewContext(wrappedCode, sandbox, {
#       timeout: 1000,
#       codeGeneration: { strings: false, wasm: false },
#     });

#     const r = sandbox.result;
#     const joinedLogs = (sandbox.logs || []).join('\\n');
#     if (typeof r === 'string' && r.startsWith('__ERROR__:')) {
#       console.log(JSON.stringify({ status: 'error', link: null, logs: joinedLogs || null, error: r.slice(10) }));
#     } else {
#       console.log(JSON.stringify({ status: 'ok', link: String(r), logs: joinedLogs || null, error: null }));
#     }
#   } catch (e) {
#     console.log(JSON.stringify({ status: 'error', link: null, logs: null, error: String(e && e.message ? e.message : e) }));
#   }
# }

# main();
# """.strip()
#     node_script = (
#         node_script_template
#         .replace("__TMP_PATH__", tmp_path_js)
#         .replace("__USER_CODE__", user_code_js)
#     )

#     try:
#         result = subprocess.run(
#             ["node", "-e", node_script],
#             capture_output=True,
#             text=True,
#             check=False,
#         )

#         if result.returncode != 0:
#             err = (result.stderr or "").strip() or f"Node.js exited with code {result.returncode}"
#             return {"status": "error", "link": None, "logs": None, "error": err}

#         output = (result.stdout or "").strip()
#         last_line = ""
#         for line in reversed(output.splitlines()):
#             if line.strip():
#                 last_line = line.strip()
#                 break
#         if not last_line:
#             return {"status": "error", "link": None, "logs": None, "error": "Empty Node.js output"}

#         try:
#             parsed = json.loads(last_line)
#         except Exception:
#             return {"status": "error", "link": None, "logs": None, "error": f"Unexpected Node.js output: {output!r}"}

#         status = parsed.get("status")
#         if status == "ok":
#             return {"status": "ok", "link": parsed.get("link"), "logs": parsed.get("logs"), "error": None}
#         return {
#             "status": "error",
#             "link": None,
#             "logs": parsed.get("logs"),
#             "error": parsed.get("error") or "Unknown error",
#         }
#     finally:
#         try:
#             os.remove(tmp_path)
#         except OSError:
#             pass




""" 
Закрытые дыры:

Constructor escape через host-объекты ($, результаты $()):
Теперь $ (и всё, что возвращается при вызовах/чейнинге) оборачивается в Proxy, который скрывает свойства constructor / __proto__ / prototype.
Поэтому $.constructor("return process")() больше не работает.
Constructor escape через встроенные конструкторы ([].constructor.constructor(...)):
Внутри vm-контекста перед выполнением user-кода добавил hardening:
Function.prototype.constructor принудительно обнуляется (через Object.defineProperty(...))
Object.prototype.__proto__ отключается
Поэтому [].constructor.constructor(...) теперь падает.

"""

