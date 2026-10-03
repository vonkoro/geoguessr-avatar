"""Typed views over GeoGuessr's avatar API payloads."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class Slot(IntEnum):
    """Equipment slots, mirroring the enum in GeoGuessr's frontend."""

    NONE = 0
    HAIR = 1
    UPPER_BODY = 2
    LOWER_BODY = 3
    MASK = 4
    EYES = 5
    MOUTH = 6
    HATS = 7
    SKIN = 8
    BEARD = 9
    SPECIAL = 10
    ACHIEVEMENTS = 11
    ANIMATION_WIN = 12
    COMPANION = 20
    HANDHELD = 21
    BORDER = 22
    BACKGROUND = 23
    EMOTE = 24


def _slot(value: int) -> Slot | int:
    try:
        return Slot(value)
    except ValueError:
        return value


@dataclass(frozen=True)
class AvatarItem:
    """One cosmetic asset (clothing piece, face texture, win animation, ...)."""

    id: str
    slot: Slot | int
    type: str
    variant: str
    mesh_glb: str
    """Path relative to the assets CDN, e.g. ``mesh/<hash>.glb``; empty if none."""
    texture: str
    """Path relative to the assets CDN, e.g. ``texture/<hash>.webp``; empty if none."""
    icon: str
    morph_target: str
    hides: tuple[int, ...]
    rarity: int
    raw: dict[str, Any] = field(repr=False, compare=False)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> AvatarItem:
        return cls(
            id=data["id"],
            slot=_slot(data.get("slot", 0)),
            type=data.get("type", ""),
            variant=data.get("variant", ""),
            mesh_glb=data.get("meshGlb") or "",
            texture=data.get("texture") or "",
            icon=data.get("icon") or "",
            morph_target=data.get("morphTarget") or "",
            hides=tuple(data.get("hides") or ()),
            rarity=data.get("rarity", 0),
            raw=data,
        )


@dataclass(frozen=True)
class Avatar:
    """A player's equipped avatar, as returned by ``/api/v4/avatar/user/{id}``."""

    user_id: str
    items: tuple[AvatarItem, ...]
    emotes: dict[str, AvatarItem]
    raw: dict[str, Any] = field(repr=False, compare=False)

    @classmethod
    def from_api(cls, user_id: str, data: dict[str, Any]) -> Avatar:
        emotes = {
            slot: AvatarItem.from_api(item)
            for slot, item in (data.get("equippedEmoteSlotAssets") or {}).items()
            if item
        }
        return cls(
            user_id=user_id,
            items=tuple(AvatarItem.from_api(i) for i in data.get("equipped") or ()),
            emotes=emotes,
            raw=data,
        )

    def item(self, slot: Slot) -> AvatarItem | None:
        return next((i for i in self.items if i.slot == slot), None)

    @property
    def win_animation(self) -> AvatarItem | None:
        """The equipped win animation, or None if the player uses the default ``WIN``."""
        item = self.item(Slot.ANIMATION_WIN)
        return item if item and item.mesh_glb else None

    @property
    def hidden_slots(self) -> frozenset[int]:
        return frozenset(s for i in self.items for s in i.hides)
