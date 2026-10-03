"""Async client for GeoGuessr's (undocumented) avatar endpoints, with a disk cache.

None of the endpoints used here need authentication. An ``_ncfa`` cookie can still be
passed for endpoints that do (e.g. browsing the shop catalogue).
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import time
from pathlib import Path
from typing import Any

import httpx

from .models import Avatar, AvatarItem

SITE_URL = "https://www.geoguessr.com"
ASSETS_URL = f"{SITE_URL}/assets"
IMAGES_URL = f"{SITE_URL}/images"

USER_AGENT = "geoguessr-avatar/0.1 (+https://github.com/vonkoro/geoguessr-avatar)"

# Content-hashed CDN paths never change; anything else is re-fetched after this long.
MUTABLE_TTL = 7 * 24 * 3600


class GeoGuessrError(RuntimeError):
    pass


class UserNotFound(GeoGuessrError):
    pass


def default_cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "geoguessr-avatar"


def _is_immutable(path: str) -> bool:
    return path.startswith(("mesh/", "texture/", "pin/", "avatarasseticon/"))


class GeoGuessrClient:
    """Fetches avatar data and asset files.

    Use as an async context manager, or call :meth:`aclose` when done::

        async with GeoGuessrClient() as gg:
            avatar = await gg.get_avatar("656461a8a02239a1b6a4482e")
    """

    def __init__(
        self,
        *,
        ncfa: str | None = None,
        cache_dir: str | Path | None = None,
        http: httpx.AsyncClient | None = None,
        timeout: float = 20.0,
    ) -> None:
        self.cache_dir = Path(cache_dir) if cache_dir else default_cache_dir()
        self._owns_http = http is None
        self._http = http or httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
            cookies={"_ncfa": ncfa} if ncfa else None,
            follow_redirects=True,
        )
        self._inflight: dict[str, asyncio.Future[bytes]] = {}

    async def __aenter__(self) -> GeoGuessrClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    # -- API ---------------------------------------------------------------------

    async def _get_json(self, url: str, **params: Any) -> Any:
        resp = await self._http.get(url, params=params or None)
        if resp.status_code == 404:
            raise UserNotFound(url)
        if resp.status_code == 204:
            return None
        if resp.status_code >= 400:
            raise GeoGuessrError(f"GET {url} -> HTTP {resp.status_code}")
        return resp.json()

    async def get_user(self, user_id: str) -> dict[str, Any]:
        """Raw public profile (``/api/v3/users/{id}``): nick, country, fullBodyPin, ..."""
        return await self._get_json(f"{SITE_URL}/api/v3/users/{user_id}")

    async def get_avatar(self, user_id: str) -> Avatar:
        """The player's equipped items (``/api/v4/avatar/user/{id}``)."""
        data = await self._get_json(f"{SITE_URL}/api/v4/avatar/user/{user_id}")
        if not data:
            raise UserNotFound(user_id)
        return Avatar.from_api(user_id, data)

    async def get_assets(self, ids: list[str]) -> list[AvatarItem]:
        """Look up any assets by ID (``/api/v4/avatar/assets?ids=...``)."""
        if not ids:
            return []
        resp = await self._http.get(f"{SITE_URL}/api/v4/avatar/assets", params=[("ids", i) for i in ids])
        resp.raise_for_status()
        return [AvatarItem.from_api(d) for d in resp.json() or ()]

    async def get_background(self, user_id: str) -> dict[str, Any] | None:
        """Equipped profile background, or None if the player has none."""
        return await self._get_json(f"{SITE_URL}/api/v4/avatar/user/{user_id}/background")

    # -- Files -------------------------------------------------------------------

    async def asset(self, path: str) -> bytes:
        """A file from the assets CDN, e.g. ``mesh/<hash>.glb`` or ``texture/<hash>.webp``."""
        return await self.fetch(f"{ASSETS_URL}/{path}", immutable=_is_immutable(path))

    async def image(self, path: str) -> bytes:
        """A file from the image CDN, e.g. a profile ``pin/<hash>.png``."""
        return await self.fetch(f"{IMAGES_URL}/plain/{path}", immutable=_is_immutable(path))

    async def full_body_png(self, user_id: str) -> bytes:
        """GeoGuessr's own static 1080x1440 full-body render. No 3D rendering involved."""
        user = await self.get_user(user_id)
        path = (user.get("avatar") or {}).get("fullBodyPath") or user.get("fullBodyPin")
        if not path:
            raise GeoGuessrError(f"user {user_id} has no full-body image")
        return await self.image(path)

    async def fetch(self, url: str, *, immutable: bool = False) -> bytes:
        """GET ``url`` through the disk cache. Concurrent requests for one URL share a download."""
        if url in self._inflight:
            return await asyncio.shield(self._inflight[url])
        future: asyncio.Future[bytes] = asyncio.get_running_loop().create_future()
        self._inflight[url] = future
        try:
            data = await self._fetch_uncoalesced(url, immutable)
            future.set_result(data)
            return data
        except BaseException as exc:
            future.set_exception(exc)
            future.exception()  # mark retrieved so lone failures don't warn
            raise
        finally:
            del self._inflight[url]

    async def _fetch_uncoalesced(self, url: str, immutable: bool) -> bytes:
        cached = self._cache_path(url)
        if cached.exists() and (immutable or time.time() - cached.stat().st_mtime < MUTABLE_TTL):
            return cached.read_bytes()
        resp = await self._http.get(url)
        if resp.status_code >= 400:
            raise GeoGuessrError(f"GET {url} -> HTTP {resp.status_code}")
        data = resp.content
        cached.parent.mkdir(parents=True, exist_ok=True)
        tmp = cached.with_suffix(cached.suffix + f".{os.getpid()}.tmp")
        tmp.write_bytes(data)
        tmp.replace(cached)
        return data

    def _cache_path(self, url: str) -> Path:
        digest = hashlib.sha256(url.encode()).hexdigest()
        return self.cache_dir / digest[:2] / f"{digest}{Path(url).suffix}"
