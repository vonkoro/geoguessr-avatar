import pytest


def item(id, slot, *, mesh="", texture="", morph="", hides=()):
    return {
        "id": id,
        "slot": slot,
        "type": id.split("_")[0],
        "variant": id.split("_")[-1],
        "meshGlb": mesh,
        "texture": texture,
        "icon": "",
        "morphTarget": morph,
        "hides": list(hides),
        "rarity": 1,
    }


@pytest.fixture
def avatar_payload():
    """Shape of /api/v4/avatar/user/{id}, with made-up asset hashes."""
    return {
        "equipped": [
            item("HAIR_PINK", 1, mesh="mesh/hair.glb", texture="texture/hair.webp"),
            item("CAP_BLUE", 7, mesh="mesh/cap.glb", texture="texture/cap.webp", morph="Hat01"),
            item("SHIRT_YELLOW", 2, mesh="mesh/shirt.glb", texture="texture/shirt.webp"),
            item("PANTS_BLUE", 3, mesh="mesh/pants.glb", texture="texture/pants.webp"),
            item("BROWS_BLACK", 5, texture="texture/eyes.webp"),
            item("LIPS_PINK", 6, texture="texture/mouth.webp"),
            item("SKIN_TAN", 8, texture="texture/skin.webp"),
            item("STAFF_YELLOW", 21, mesh="mesh/staff.glb", texture="texture/staff.webp"),
            item("CAT_BASIC", 20, mesh="mesh/cat.glb", texture="texture/cat.webp"),
            item("BORDER_18", 22, texture="texture/border.webp"),
            item("CHAIR_WIN", 12, mesh="mesh/chair_anim.glb", texture="texture/chair.webp"),
        ],
        "equippedBadge": None,
        "equippedEmoteSlotAssetIds": {"slot1": "EMOTE_GG_DEFAULT"},
        "equippedEmoteSlotAssets": {"slot1": item("EMOTE_GG_DEFAULT", 24)},
    }
