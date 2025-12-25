"""Shared Playwright page holder to avoid circular imports."""

from __future__ import annotations

from typing import Any
from playwright.sync_api import Page

_current_page: Page | None = None


def set_shared_page(page: Page) -> None:
    """Store Playwright page for reuse across toolkit helpers."""
    global _current_page
    _current_page = page


def get_shared_page() -> Page:
    """Return stored Playwright page or raise if it is not set."""
    if _current_page is None:
        raise RuntimeError(
            "Playwright page is not initialized. Call set_shared_page(page) before using toolkit tools."
        )
    return _current_page

