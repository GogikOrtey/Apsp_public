from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from import_all_libraries import get_html
from playwright_tool.playwright_toolkit import get_current_url, goto_url, page_restart
from playwright_tool.shared_page import get_shared_page


@dataclass(frozen=True)
class PageMetrics:
    node_count: int
    text_length: int
    div_count: int
    a_count: int
    img_count: int
    button_count: int
    input_count: int
    max_depth: int

    def to_dict(self) -> dict[str, int]:
        return {
            "node_count": int(self.node_count),
            "text_length": int(self.text_length),
            "div_count": int(self.div_count),
            "a_count": int(self.a_count),
            "img_count": int(self.img_count),
            "button_count": int(self.button_count),
            "input_count": int(self.input_count),
            "max_depth": int(self.max_depth),
        }


def _normalize_url_for_compare(url: str | None) -> str | None:
    if not url:
        return None
    u = str(url).strip()
    if not u:
        return None
    parts = urlsplit(u)
    scheme = (parts.scheme or "").lower()
    netloc = (parts.netloc or "").lower()
    path = parts.path or ""

    # Сравнение без #fragment и без "лишнего" / на конце.
    fragment = ""
    if path != "/":
        path = path.rstrip("/")

    return urlunsplit((scheme, netloc, path, parts.query or "", fragment))


def _safe_ratio(num: int, den: int) -> float:
    """
    Возвращает num/den, защищая от den==0.
    Если den==0 и num>0 => inf (считаем сильно хуже).
    Если den==0 и num==0 => 1.0 (считаем равным).
    """
    if den == 0:
        return float("inf") if num > 0 else 1.0
    return float(num) / float(den)


def _max_depth_bs4(tag: Any) -> int:
    # tag: bs4.Tag
    try:
        from bs4 import Tag  # type: ignore
    except Exception:
        Tag = None  # type: ignore

    if tag is None:
        return 0

    max_d = 1
    stack: list[tuple[Any, int]] = [(tag, 1)]
    while stack:
        node, d = stack.pop()
        if d > max_d:
            max_d = d
        try:
            children = getattr(node, "children", None)
            if children is None:
                continue
            for ch in children:
                if Tag is not None and isinstance(ch, Tag):
                    stack.append((ch, d + 1))
        except Exception:
            continue
    return int(max_d)


def _max_depth_lxml(el: Any) -> int:
    if el is None:
        return 0
    max_d = 1
    stack: list[tuple[Any, int]] = [(el, 1)]
    while stack:
        node, d = stack.pop()
        if d > max_d:
            max_d = d
        try:
            for ch in list(node):
                stack.append((ch, d + 1))
        except Exception:
            continue
    return int(max_d)


def _metrics_from_html_request(html: str) -> PageMetrics:
    """
    Метрики для HTML, полученного через обычный запрос (requests).
    Важно: это не браузерный DOM, но метрики подобраны так, чтобы быть сопоставимыми с Playwright.
    """
    html = html or ""

    # Пытаемся через lxml (быстрее/стабильнее для подсчётов).
    try:
        from lxml import html as lxml_html  # type: ignore

        root = lxml_html.fromstring(html) if html.strip() else lxml_html.fromstring("<html></html>")
        body_nodes = root.xpath("//body")
        body = body_nodes[0] if body_nodes else root

        node_count = int(len(root.xpath("//*")))
        div_count = int(len(root.xpath("//div")))
        a_count = int(len(root.xpath("//a")))
        img_count = int(len(root.xpath("//img")))
        button_count = int(len(root.xpath("//button")))
        input_count = int(len(root.xpath("//input")))

        text = body.text_content() if body is not None else ""
        text_length = int(len(text or ""))

        max_depth = _max_depth_lxml(body)
        return PageMetrics(
            node_count=node_count,
            text_length=text_length,
            div_count=div_count,
            a_count=a_count,
            img_count=img_count,
            button_count=button_count,
            input_count=input_count,
            max_depth=max_depth,
        )
    except Exception:
        pass

    # Fallback через bs4
    from bs4 import BeautifulSoup  # type: ignore

    soup = BeautifulSoup(html, "lxml")
    body = soup.body or soup

    node_count = len(soup.find_all(True))
    div_count = len(soup.find_all("div"))
    a_count = len(soup.find_all("a"))
    img_count = len(soup.find_all("img"))
    button_count = len(soup.find_all("button"))
    input_count = len(soup.find_all("input"))

    text = body.get_text(" ", strip=True) if body is not None else ""
    text_length = int(len(text or ""))
    max_depth = _max_depth_bs4(body)

    return PageMetrics(
        node_count=node_count,
        text_length=text_length,
        div_count=div_count,
        a_count=a_count,
        img_count=img_count,
        button_count=button_count,
        input_count=input_count,
        max_depth=max_depth,
    )


def _metrics_from_playwright_current_page() -> PageMetrics:
    page = get_shared_page()
    data = page.evaluate(
        """
        () => {
          const doc = document;
          const body = doc && doc.body ? doc.body : null;

          const node_count = doc ? doc.querySelectorAll("*").length : 0;
          const div_count = doc ? doc.getElementsByTagName("div").length : 0;
          const a_count = doc ? doc.getElementsByTagName("a").length : 0;
          const img_count = doc ? doc.getElementsByTagName("img").length : 0;
          const button_count = doc ? doc.getElementsByTagName("button").length : 0;
          const input_count = doc ? doc.getElementsByTagName("input").length : 0;

          const inner_text = body ? (body.innerText || "") : "";
          const text_length = inner_text.length;

          function maxDepth(el) {
            if (!el || !el.children) return 0;
            let maxD = 1;
            const stack = [[el, 1]];
            while (stack.length) {
              const pair = stack.pop();
              const node = pair[0];
              const d = pair[1];
              if (d > maxD) maxD = d;
              const kids = node.children;
              for (let i = 0; i < kids.length; i++) {
                stack.push([kids[i], d + 1]);
              }
            }
            return maxD;
          }

          const max_depth = maxDepth(body);

          return {
            node_count,
            text_length,
            div_count,
            a_count,
            img_count,
            button_count,
            input_count,
            max_depth,
          };
        }
        """
    )

    return PageMetrics(
        node_count=int(data.get("node_count") or 0),
        text_length=int(data.get("text_length") or 0),
        div_count=int(data.get("div_count") or 0),
        a_count=int(data.get("a_count") or 0),
        img_count=int(data.get("img_count") or 0),
        button_count=int(data.get("button_count") or 0),
        input_count=int(data.get("input_count") or 0),
        max_depth=int(data.get("max_depth") or 0),
    )


def check_request_this_site_ok(
    url: str,
    *,
    wait_until: str = "load",
    timeout_ms: int = 30_000,
    request_timeout_s: int = 20,
) -> dict[str, Any]:
    """
    Проверяет, достаточно ли "обычного" запроса (requests) для получения страницы.

    Алгоритм:
    - Получаем метрики страницы через Playwright (как в браузере).
    - Получаем HTML через обычный requests и считаем метрики по распарсенному HTML.
    - Сравниваем коэффициенты и глубину.
    - Если хотя бы одно условие превышения порога — request_ok=False (нужен браузер), иначе True.

    Важно: после проверки возвращает Playwright на страницу, которая была открыта до проверки.
    """
    target_norm = _normalize_url_for_compare(url)
    cur = get_current_url()
    if cur.get("status") != "ok":
        return {
            "status": "error",
            "url": url,
            "request_ok": False,
            "error": f"Playwright page is not available: {cur.get('error')}",
        }

    prev_url = cur.get("url")
    prev_norm = _normalize_url_for_compare(prev_url)

    navigated = False
    try:
        # 1) Playwright: либо reload (если уже на нужной странице), либо goto_url.
        if target_norm and prev_norm and target_norm == prev_norm:
            r = page_restart(wait_until=wait_until, timeout=timeout_ms)
        else:
            r = goto_url(url=url, wait_until=wait_until, timeout=timeout_ms)
            navigated = True

        if r.get("status") != "ok":
            return {
                "status": "error",
                "url": url,
                "request_ok": False,
                "error": f"Playwright navigation failed: {r.get('error')}",
            }

        metrics_pw = _metrics_from_playwright_current_page()

        # 2) requests: берём RAW html (без clean_html_preserve_structure), чтобы метрики были ближе к DOM.
        html_req = get_html(url, timeout=request_timeout_s, is_clear_html=False, is_use_proxy=False)
        metrics_req = _metrics_from_html_request(html_req)

        # 3) ratios + thresholds
        node_ratio = _safe_ratio(metrics_pw.node_count, metrics_req.node_count)
        text_ratio = _safe_ratio(metrics_pw.text_length, metrics_req.text_length)
        a_ratio = _safe_ratio(metrics_pw.a_count, metrics_req.a_count)
        img_ratio = _safe_ratio(metrics_pw.img_count, metrics_req.img_count)
        depth_diff = int(metrics_pw.max_depth - metrics_req.max_depth)

        triggered: list[str] = []
        if node_ratio > 2:
            triggered.append("node_ratio > 2")
        if text_ratio > 1.5:
            triggered.append("text_ratio > 1.5")
        if a_ratio > 3:
            triggered.append("a_ratio > 3")
        if img_ratio > 3:
            triggered.append("img_ratio > 3")
        if depth_diff > 15:
            triggered.append("depth_diff > 15")

        request_ok = len(triggered) == 0
        return {
            "status": "ok",
            "url": url,
            "request_ok": request_ok,
            "metrics": {
                "playwright": metrics_pw.to_dict(),
                "request": metrics_req.to_dict(),
            },
            "ratios": {
                "node_ratio": node_ratio,
                "text_ratio": text_ratio,
                "a_ratio": a_ratio,
                "img_ratio": img_ratio,
                "depth_diff": depth_diff,
            },
            "thresholds_triggered": triggered,
        }
    finally:
        # Важно: возвращаемся назад на предыдущую страницу, только если мы реально уходили с неё.
        try:
            if navigated and prev_url:
                goto_url(url=str(prev_url), wait_until=wait_until, timeout=timeout_ms)
        except Exception:
            # Не ломаем основной результат, если "возврат" не удался.
            pass

