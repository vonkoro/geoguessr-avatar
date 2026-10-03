"""End-to-end checks against the live site. Opt in with GEOGUESSR_AVATAR_NETWORK_TESTS=1."""

import io
import os

import pytest

from geoguessr_avatar import AvatarRenderer, GeoGuessrClient, UserNotFound

pytestmark = [
    pytest.mark.network,
    pytest.mark.skipif(not os.environ.get("GEOGUESSR_AVATAR_NETWORK_TESTS"), reason="network tests disabled"),
]

USER = os.environ.get("GEOGUESSR_AVATAR_TEST_USER", "656461a8a02239a1b6a4482e")


async def test_fetch_avatar():
    async with GeoGuessrClient() as gg:
        avatar = await gg.get_avatar(USER)
        assert avatar.items
        with pytest.raises(UserNotFound):
            await gg.get_avatar("000000000000000000000000")


async def test_render_poses():
    from PIL import Image

    async with AvatarRenderer() as renderer:
        for anim in (None, "LOSE_KNEES", "IDLE"):
            result = await renderer.render(USER, anim, width=270, height=360)
            img = Image.open(io.BytesIO(result.png))
            assert img.size == (270, 360) and img.mode == "RGBA"
            alpha = img.getchannel("A")
            assert alpha.getextrema() == (0, 255), "expected transparent background and opaque avatar"
            assert 0 <= result.time <= result.duration


def test_sync_renderer_threads_and_running_loop():
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    from geoguessr_avatar import SyncAvatarRenderer

    with SyncAvatarRenderer() as renderer:
        first = renderer.render(USER, "IDLE", width=135, height=180)
        assert first.png.startswith(b"\x89PNG")

        with ThreadPoolExecutor(3) as pool:
            anims = ["WIN", "LOSE", "TAUNT_BOXER"]
            results = list(pool.map(lambda a: renderer.render(USER, a, width=135, height=180), anims))
        assert [r.animation for r in results] == anims

        async def from_async_code():
            return renderer.render(USER, "LOSE_SITTING", width=135, height=180)

        assert asyncio.run(from_async_code()).animation == "LOSE_SITTING"

    renderer.close()  # second close is a no-op
    with pytest.raises(RuntimeError):
        renderer.render(USER)
