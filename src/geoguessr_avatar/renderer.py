"""Render avatars in any animation pose with headless Chromium + three.js."""

from __future__ import annotations

import asyncio
import base64
import concurrent.futures
import difflib
import logging
import mimetypes
import threading
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any, Literal

from playwright.async_api import Browser, Page, Playwright, Route, async_playwright
from playwright.async_api import Error as PlaywrightError

from . import animations
from .client import SITE_URL, GeoGuessrClient
from .models import Avatar, AvatarItem, Slot

log = logging.getLogger(__name__)

_ORIGIN = "https://geoguessr-avatar.local"
_WEB_DIR = resources.files("geoguessr_avatar") / "web"

_CONTENT_TYPES = {
    ".js": "text/javascript",
    ".html": "text/html",
    ".wasm": "application/wasm",
    ".glb": "model/gltf-binary",
    ".webp": "image/webp",
    ".png": "image/png",
}

# Software WebGL: works on GPU-less servers and gives identical output everywhere.
SWIFTSHADER_ARGS = ("--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist")

# Camera for framing="fixed": same scale for every player and pose, matching the
# composition of GeoGuessr's own 1080x1440 full-body image. Units are metres-ish;
# the frame spans FIXED_HEIGHT vertically, starting FIXED_BOTTOM below the feet.
FIXED_FOV = 20.0
FIXED_HEIGHT = 1.184
FIXED_BOTTOM = 0.497 - FIXED_HEIGHT / 2

Framing = Literal["fixed", "fit"]

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


@dataclass(frozen=True)
class RenderResult:
    png: bytes = field(repr=False)
    animation: str
    """Built-in clip name, or the asset ID of an equipped/purchasable win animation."""
    duration: float
    """Clip length in seconds."""
    time: float
    """The moment of the clip that was rendered, in seconds."""
    bounds: tuple[tuple[float, float, float], tuple[float, float, float]]
    """World-space bounding box (min, max) of the posed avatar."""

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.write_bytes(self.png)
        return path


@dataclass(frozen=True)
class ModelResult:
    glb: bytes = field(repr=False)
    """Binary glTF 2.0 file."""
    animation: str
    """Built-in clip name, or the asset ID of an equipped/purchasable win animation."""
    duration: float
    """Clip length in seconds."""
    time: float
    """The moment of the clip the model is posed at, in seconds."""

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.write_bytes(self.glb)
        return path


class AvatarRenderer:
    """Renders still PNG frames of a player's avatar, or exports it as a 3D model.

    Keep one renderer alive and reuse it: starting Chromium takes a moment, and parsed
    meshes stay cached in the page between renders::

        async with AvatarRenderer() as renderer:
            result = await renderer.render("656461a8a02239a1b6a4482e", "LOSE_KNEES", progress=0.6)
            result.save("knees.png")
    """

    def __init__(
        self,
        client: GeoGuessrClient | None = None,
        *,
        cache_dir: str | Path | None = None,
        software_gl: bool = True,
        browser_args: list[str] | None = None,
        executable_path: str | None = None,
    ) -> None:
        self._owns_client = client is None
        self.client = client or GeoGuessrClient(cache_dir=cache_dir)
        args = list(SWIFTSHADER_ARGS) if software_gl else []
        self._browser_args = args + (browser_args or [])
        self._executable_path = executable_path
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._page: Page | None = None
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> AvatarRenderer:
        await self.start()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def start(self) -> None:
        if self._page:
            return
        self._pw = await async_playwright().start()
        try:
            self._browser = await self._pw.chromium.launch(
                args=self._browser_args, executable_path=self._executable_path
            )
        except PlaywrightError as exc:
            await self._pw.stop()
            self._pw = None
            if "Executable doesn't exist" in str(exc):
                raise BrowserNotInstalled() from None
            raise
        page = await self._browser.new_page()
        page.on("console", _log_console)
        page.on("pageerror", lambda e: log.error("renderer page error: %s", e))
        await page.route(f"{_ORIGIN}/**", self._serve)
        await page.goto(f"{_ORIGIN}/web/render.html")
        await page.wait_for_function("window.rendererReady === true")
        self._page = page

    async def aclose(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()
        self._page = self._browser = self._pw = None
        if self._owns_client:
            await self.client.aclose()

    async def render(
        self,
        user: str | Avatar,
        animation: str | AvatarItem | None = None,
        *,
        time: float | None = None,
        progress: float | None = None,
        width: int = 1080,
        height: int = 1440,
        supersample: float = 2.0,
        framing: Framing = "fixed",
        zoom: float = 1.0,
        margin: float = 0.04,
        background: str | None = None,
    ) -> RenderResult:
        """Render one frame of ``user``'s avatar.

        :param user: GeoGuessr user ID, or an :class:`Avatar` you already fetched.
        :param animation: ``None`` for the player's own win animation (or the default
            ``WIN`` if they have none equipped); a built-in clip name such as
            ``"LOSE_KNEES"`` (see :mod:`geoguessr_avatar.animations`); or an
            animation asset ID / :class:`AvatarItem`.
        :param time: Seconds into the clip. Clamped to the clip's length.
        :param progress: Alternative to ``time``: 0.0 = start, 1.0 = end.
            With neither, renders 1 s before the end, which is the frame GeoGuessr
            itself uses when it holds a pose.
        :param framing: ``"fixed"`` uses one camera for everyone, matching GeoGuessr's
            own full-body image (consistent scale on a podium). ``"fit"`` frames the posed
            avatar tightly, so scale varies between renders.
        :param zoom: ``"fixed"`` only. Below 1 zooms out with the feet kept in place,
            leaving headroom for tall hats and jumps (GeoGuessr's framing crops those);
            0.85 is a good podium value.
        :param margin: ``"fit"`` only. Empty space around the avatar, as a fraction.
        :param background: CSS-style hex colour, or ``None`` for transparency.
        """
        if zoom <= 0:
            raise ValueError("zoom must be positive")
        spec = await self._pose_spec(user, animation, time, progress)
        frame_height = FIXED_HEIGHT / zoom
        camera: dict[str, Any] = {
            "mode": framing,
            "margin": margin,
            "fov": FIXED_FOV if framing == "fixed" else 30.0,
            "height": frame_height,
            "centerY": FIXED_BOTTOM + frame_height / 2,
        }
        spec.update(width=width, height=height, supersample=supersample, camera=camera, background=background)
        out = await self._evaluate("window.renderAvatar", spec)
        b = out["bounds"]
        return RenderResult(
            png=_decode_data_url(out["png"]),
            animation=spec["clip"]["name"],
            duration=out["duration"],
            time=out["time"],
            bounds=(tuple(b["min"]), tuple(b["max"])),
        )

    async def export_model(
        self,
        user: str | Avatar,
        animation: str | AvatarItem | None = None,
        *,
        time: float | None = None,
        progress: float | None = None,
    ) -> ModelResult:
        """Export ``user``'s avatar as a 3D model: a binary glTF (``.glb``) file.

        The model is the whole assembled avatar, textured and skinned to one skeleton,
        posed at the chosen moment of ``animation``. The clip itself is included too, so
        viewers and 3D tools that play glTF animations can play it.

        Takes the same ``user``, ``animation``, ``time`` and ``progress`` as
        :meth:`render`. The face expression and whether a held item is shown are fixed at
        the chosen moment; glTF can't animate them.
        """
        spec = await self._pose_spec(user, animation, time, progress)
        out = await self._evaluate("window.exportAvatar", spec)
        return ModelResult(
            glb=_decode_data_url(out["glb"]),
            animation=spec["clip"]["name"],
            duration=out["duration"],
            time=out["time"],
        )

    async def _pose_spec(
        self,
        user: str | Avatar,
        animation: str | AvatarItem | None,
        time: float | None,
        progress: float | None,
    ) -> dict[str, Any]:
        if time is not None and progress is not None:
            raise ValueError("pass time or progress, not both")
        await self.start()
        avatar = user if isinstance(user, Avatar) else await self.client.get_avatar(user)
        clip = await self._resolve_clip(avatar, animation)
        return {**_avatar_spec(avatar), "clip": clip, "time": time, "progress": progress}

    async def _evaluate(self, function: str, spec: dict[str, Any]) -> dict[str, Any]:
        async with self._lock:
            assert self._page
            return await self._page.evaluate(f"spec => {function}(spec)", spec)

    async def _resolve_clip(self, avatar: Avatar, animation: str | AvatarItem | None) -> dict[str, Any]:
        if animation is None:
            animation = avatar.win_animation or "WIN"
        if isinstance(animation, str):
            name = animations.normalize(animation)
            if name:
                return {
                    "name": name,
                    "glb": _proxy(animations.builtin_path(name)),
                    "texture": None,
                    "basic": name in animations.HANDHELD_ANIMATIONS,
                }
            found = await self.client.get_assets([animation])
            if not found:
                close = difflib.get_close_matches(animation.upper(), animations.BUILTIN_ANIMATIONS, n=3)
                hint = f" Did you mean {' or '.join(close)}?" if close else ""
                raise ValueError(
                    f"unknown animation {animation!r}: not a built-in clip or a known asset ID.{hint}"
                    " (Built-in clips are listed in geoguessr_avatar.animations or by"
                    " `geoguessr-avatar animations`.)"
                )
            animation = found[0]
        if not animation.mesh_glb:
            raise ValueError(f"asset {animation.id} has no animation GLB")
        return {
            "name": animation.id,
            "glb": _proxy(f"assets/{animation.mesh_glb}"),
            "texture": _proxy(f"assets/{animation.texture}") if animation.texture else None,
            "basic": False,
        }

    async def _serve(self, route: Route) -> None:
        path = route.request.url.removeprefix(_ORIGIN + "/").split("?", 1)[0]
        try:
            if ".." in path.split("/"):
                raise FileNotFoundError(path)
            if path.startswith("web/"):
                body = _WEB_DIR.joinpath(path.removeprefix("web/")).read_bytes()
            elif path.startswith("gg/"):
                site_path = path.removeprefix("gg/")
                body = await self.client.fetch(
                    f"{SITE_URL}/{site_path}", immutable=site_path.startswith("assets/")
                )
            else:
                raise FileNotFoundError(path)
        except Exception as exc:  # report to the page as a failed request
            log.warning("renderer could not serve %s: %s", path, exc)
            await route.fulfill(status=404, body=str(exc))
            return
        suffix = Path(path).suffix
        ctype = _CONTENT_TYPES.get(suffix) or mimetypes.guess_type(path)[0] or "application/octet-stream"
        await route.fulfill(status=200, body=body, headers={"Content-Type": ctype})


def _proxy(site_path: str) -> str:
    return f"{_ORIGIN}/gg/{site_path}"


def _decode_data_url(url: str) -> bytes:
    return base64.b64decode(url.split(",", 1)[1])


def _avatar_spec(avatar: Avatar) -> dict[str, Any]:
    hidden = avatar.hidden_slots
    skip = {Slot.ANIMATION_WIN, Slot.COMPANION}
    items = [
        {
            "id": i.id,
            "mesh": _proxy(f"assets/{i.mesh_glb}"),
            "texture": _proxy(f"assets/{i.texture}") if i.texture else None,
            "handheld": i.slot == Slot.HANDHELD,
        }
        for i in avatar.items
        if i.mesh_glb and i.slot not in skip and i.slot not in hidden
    ]

    handheld = avatar.item(Slot.HANDHELD)

    def tex(slot: Slot) -> str | None:
        item = avatar.item(slot)
        return _proxy(f"assets/{item.texture}") if item and item.texture else None

    return {
        "head": _proxy("static/avatar-assets/head/head.glb"),
        "skin": tex(Slot.SKIN),
        "eyes": tex(Slot.EYES),
        "mouth": tex(Slot.MOUTH),
        "hideHead": Slot.EYES in hidden,
        "items": items,
        "handheld": _proxy(f"assets/{handheld.mesh_glb}")
        if handheld and handheld.mesh_glb and handheld.slot not in hidden
        else None,
        "morphTargets": [i.morph_target for i in avatar.items if i.mesh_glb and i.morph_target],
    }


def _log_console(msg: Any) -> None:
    level = {"error": logging.ERROR, "warning": logging.WARNING}.get(msg.type, logging.DEBUG)
    # Some clips animate helper nodes that have no mesh; the site gets the same warnings.
    if "No target node found for track" in msg.text or "GPU stall due to ReadPixels" in msg.text:
        level = logging.DEBUG
    log.log(level, "renderer console: %s", msg.text)


class SyncAvatarRenderer:
    """Blocking version of :class:`AvatarRenderer`, for code that doesn't use asyncio.

    The browser runs on its own event loop in a background thread, so this also works
    when called from inside a running event loop, and from several threads at once
    (renders are queued). Keep one instance for the lifetime of your program::

        renderer = SyncAvatarRenderer()
        renderer.render("<user-id>", "LOSE_KNEES").save("knees.png")
        ...
        renderer.close()
    """

    def __init__(
        self,
        *,
        cache_dir: str | Path | None = None,
        software_gl: bool = True,
        browser_args: list[str] | None = None,
        executable_path: str | None = None,
    ) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, name="geoguessr-avatar", daemon=True)
        self._thread.start()
        self._closed = False
        try:
            self._renderer = self._call(
                _make_renderer(cache_dir, software_gl, browser_args, executable_path), timeout=None
            )
        except BaseException:
            self._stop_loop()
            raise

    def __enter__(self) -> SyncAvatarRenderer:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def render(
        self,
        user: str | Avatar,
        animation: str | AvatarItem | None = None,
        *,
        timeout: float | None = 120.0,
        **kwargs: Any,
    ) -> RenderResult:
        """Same arguments as :meth:`AvatarRenderer.render`. ``timeout`` is in seconds."""
        if self._closed:
            raise RuntimeError("renderer is closed")
        return self._call(self._renderer.render(user, animation, **kwargs), timeout=timeout)

    def export_model(
        self,
        user: str | Avatar,
        animation: str | AvatarItem | None = None,
        *,
        timeout: float | None = 120.0,
        **kwargs: Any,
    ) -> ModelResult:
        """Same arguments as :meth:`AvatarRenderer.export_model`. ``timeout`` is in seconds."""
        if self._closed:
            raise RuntimeError("renderer is closed")
        return self._call(self._renderer.export_model(user, animation, **kwargs), timeout=timeout)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._call(self._renderer.aclose(), timeout=30)
        finally:
            self._stop_loop()

    def _call(self, coro: Any, timeout: float | None) -> Any:
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            return future.result(timeout)
        except concurrent.futures.TimeoutError:
            future.cancel()
            raise TimeoutError(f"renderer did not finish within {timeout} s") from None

    def _stop_loop(self) -> None:
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=10)
        self._loop.close()


async def _make_renderer(
    cache_dir: str | Path | None,
    software_gl: bool,
    browser_args: list[str] | None,
    executable_path: str | None,
) -> AvatarRenderer:
    renderer = AvatarRenderer(
        cache_dir=cache_dir,
        software_gl=software_gl,
        browser_args=browser_args,
        executable_path=executable_path,
    )
    try:
        await renderer.start()
    except BaseException:
        await renderer.aclose()
        raise
    return renderer


def render_avatar(user: str, animation: str | None = None, **kwargs: Any) -> RenderResult:
    """One-shot helper for scripts. Starts and stops a browser per call, so use
    :class:`SyncAvatarRenderer` when rendering more than one image."""
    with SyncAvatarRenderer() as renderer:
        return renderer.render(user, animation, **kwargs)
