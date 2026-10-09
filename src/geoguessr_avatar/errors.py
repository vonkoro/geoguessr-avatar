"""Exceptions that are importable without the rendering extra installed."""

from __future__ import annotations

RENDER_EXTRA_HINT = (
    "Rendering needs the 'render' extra (Playwright). Install it with:\n"
    "    pip install 'geoguessr-avatar[render]'\n"
    "    playwright install chromium"
)


INSTALL_HINT = (
    "Chromium for Playwright is not installed. Run:\n"
    "    playwright install chromium\n"
    "On a Linux server use:\n"
    "    playwright install --with-deps --only-shell chromium"
)


class BrowserNotInstalled(RuntimeError):
    """Playwright's Chromium hasn't been downloaded yet."""

    def __init__(self) -> None:
        super().__init__(INSTALL_HINT)
