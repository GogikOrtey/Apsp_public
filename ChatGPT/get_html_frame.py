from __future__ import annotations

import re
from copy import deepcopy
from urllib.parse import urlsplit, urlunsplit

def build_html_frame(
    html: str,
    selector: str,
    *,
    max_frame_chars: int = 3000,
    max_container_text_chars: int = 1000,
    max_container_html_chars: int = 5000,
    sibling_elems: int = 2,
    max_text_node_chars: int = 200,
) -> str:
    """
    Build a compact, informative HTML snapshot ("html_frame") around the first element
    matching a CSS selector.

    - Picks a container ancestor by size heuristics (not fixed levels).
    - Keeps path container->target + a few siblings around target.
    - Adds <!--TARGET_START--> and <!--TARGET_END--> markers.
    - Sanitizes tags/attrs and collapses whitespace.
    - Truncates to max_frame_chars.
    """
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

    # Compute absolute xpath of container and target; create relative xpath to find same nodes inside clone
    tree = container.getroottree()
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

    # Prune: remove any element not in keep_nodes (post-order)
    for el in list(clone.iterdescendants())[::-1]:
        if el not in keep_nodes:
            parent = el.getparent()
            if parent is not None:
                parent.remove(el)

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
    out = etree.tostring(clone, encoding="unicode", with_tail=False, method="html")

    # Collapse whitespace between tags + inside text reasonably
    out = re.sub(r">\s+<", "><", out)
    out = re.sub(r"\s{2,}", " ", out).strip()

    # Enforce max_frame_chars
    if len(out) > max_frame_chars:
        out = out[:max_frame_chars - 1] + "…"

    return out
