import pytest

from geoguessr_avatar import Avatar, AvatarItem, AvatarRenderer

from .conftest import item


class FakeClient:
    def __init__(self, assets=()):
        self.assets = {a["id"]: a for a in assets}

    async def get_assets(self, ids):
        return [AvatarItem.from_api(self.assets[i]) for i in ids if i in self.assets]

    async def aclose(self):
        pass


@pytest.fixture
def renderer():
    return AvatarRenderer(FakeClient([item("BOW_WIN", 12, mesh="mesh/bow.glb")]))


async def test_default_clip_is_equipped_win_animation(renderer, avatar_payload):
    clip = await renderer._resolve_clip(Avatar.from_api("u", avatar_payload), None)
    assert clip["name"] == "CHAIR_WIN"
    assert clip["glb"].endswith("/gg/assets/mesh/chair_anim.glb")
    assert clip["texture"].endswith("/gg/assets/texture/chair.webp")
    assert clip["basic"] is False


async def test_default_clip_falls_back_to_win(renderer):
    clip = await renderer._resolve_clip(Avatar.from_api("u", {"equipped": []}), None)
    assert clip["name"] == "WIN"
    assert clip["glb"].endswith("/gg/static/avatar-assets/animations/WIN.glb")


async def test_builtin_and_asset_clips(renderer, avatar_payload):
    avatar = Avatar.from_api("u", avatar_payload)
    idle = await renderer._resolve_clip(avatar, "idle")
    assert (idle["name"], idle["basic"]) == ("IDLE", True)
    bow = await renderer._resolve_clip(avatar, "BOW_WIN")
    assert bow["glb"].endswith("/gg/assets/mesh/bow.glb")
    with pytest.raises(ValueError):
        await renderer._resolve_clip(avatar, "NOT_A_THING")


async def test_time_and_progress_are_exclusive(renderer):
    with pytest.raises(ValueError):
        await renderer.render("u", time=1, progress=0.5)


async def test_unknown_animation_suggests_close_match(renderer, avatar_payload):
    with pytest.raises(ValueError, match="Did you mean LOSE_KNEES"):
        await renderer._resolve_clip(Avatar.from_api("u", avatar_payload), "LOSE_KNEE")


def test_cli_prints_errors_without_traceback(capsys):
    from geoguessr_avatar.__main__ import main

    assert main(["info", "not-a-user"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("error: expected a GeoGuessr user ID") and "Traceback" not in err
