"""Fetch GeoGuessr avatars, render them in any animation pose, or export them as 3D models."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from . import animations
from .client import GeoGuessrClient, GeoGuessrError, UserNotFound, parse_user_id
from .errors import BrowserNotInstalled
from .models import Avatar, AvatarItem, Slot

if TYPE_CHECKING:
    from .renderer import AvatarRenderer, ModelResult, RenderResult, SyncAvatarRenderer, render_avatar

# The renderer needs Playwright (the "render" extra). Load it on first use, so fetching avatar
# data works with just httpx installed.
_RENDERER_NAMES = {"AvatarRenderer", "ModelResult", "RenderResult", "SyncAvatarRenderer", "render_avatar"}


def __getattr__(name: str) -> Any:
    if name in _RENDERER_NAMES:
        from . import renderer

        return getattr(renderer, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Avatar",
    "AvatarItem",
    "AvatarRenderer",
    "BrowserNotInstalled",
    "GeoGuessrClient",
    "GeoGuessrError",
    "ModelResult",
    "RenderResult",
    "Slot",
    "SyncAvatarRenderer",
    "UserNotFound",
    "animations",
    "parse_user_id",
    "render_avatar",
]
