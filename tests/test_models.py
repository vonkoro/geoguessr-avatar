import pytest

from geoguessr_avatar import Avatar, Slot, animations
from geoguessr_avatar.renderer import _avatar_spec

from .conftest import item


def test_parses_equipped_items(avatar_payload):
    avatar = Avatar.from_api("u1", avatar_payload)
    assert avatar.item(Slot.HATS).morph_target == "Hat01"
    assert avatar.item(Slot.SKIN).texture == "texture/skin.webp"
    assert avatar.emotes["slot1"].id == "EMOTE_GG_DEFAULT"
    assert avatar.win_animation.id == "CHAIR_WIN"


def test_unknown_slot_numbers_are_kept():
    avatar = Avatar.from_api("u1", {"equipped": [item("NEW_THING", 99)]})
    assert avatar.items[0].slot == 99


def test_no_win_animation_means_default():
    avatar = Avatar.from_api("u1", {"equipped": [item("HAIR_PINK", 1, mesh="mesh/h.glb")]})
    assert avatar.win_animation is None


def test_spec_skips_non_wearables(avatar_payload):
    spec = _avatar_spec(Avatar.from_api("u1", avatar_payload))
    meshes = [i["mesh"].rsplit("/", 1)[-1] for i in spec["items"]]
    assert meshes == ["hair.glb", "cap.glb", "shirt.glb", "pants.glb", "staff.glb"]
    assert spec["morphTargets"] == ["Hat01"]
    assert spec["handheld"].endswith("mesh/staff.glb")
    assert spec["eyes"].endswith("texture/eyes.webp")
    assert spec["hideHead"] is False


def test_spec_applies_hides(avatar_payload):
    avatar_payload["equipped"].append(
        item("GHOST_SHEET", 10, mesh="mesh/ghost.glb", texture="texture/ghost.webp", hides=[1, 2, 5, 21])
    )
    spec = _avatar_spec(Avatar.from_api("u1", avatar_payload))
    meshes = [i["mesh"].rsplit("/", 1)[-1] for i in spec["items"]]
    assert "hair.glb" not in meshes and "shirt.glb" not in meshes and "staff.glb" not in meshes
    assert "ghost.glb" in meshes
    assert spec["hideHead"] is True
    assert spec["handheld"] is None


def test_animation_names():
    assert animations.normalize("lose_knees") == "LOSE_KNEES"
    assert animations.normalize("DEFAULT_WIN") == "WIN"
    assert animations.normalize("CHAIR_WIN") is None
    assert len(set(animations.BUILTIN_ANIMATIONS)) == len(animations.BUILTIN_ANIMATIONS)
    assert set(animations.HANDHELD_ANIMATIONS) <= set(animations.BUILTIN_ANIMATIONS)


def test_parse_user_id_accepts_ids_and_profile_urls():
    from geoguessr_avatar import parse_user_id

    uid = "656461a8a02239a1b6a4482e"
    for value in (
        uid,
        uid.upper(),
        f" {uid} ",
        f"https://www.geoguessr.com/user/{uid}",
        f"geoguessr.com/uk/user/{uid}?tab=stats",
    ):
        assert parse_user_id(value) == uid
    for bad in ("", "656461a8", f"{uid}ff", "https://www.geoguessr.com/maps/abc"):
        with pytest.raises(ValueError):
            parse_user_id(bad)
