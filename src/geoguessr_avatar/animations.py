"""Built-in animation clips served from ``/static/avatar-assets/animations/{NAME}.glb``.

Players can only customise their win animation (slot 12, a purchasable asset with its
own GLB). Everything here is shared by all players.
"""

from __future__ import annotations

WIN_ANIMATIONS = (
    "WIN",
    "WIN_BALLERINA",
    "WIN_FINGERGUNS",
    "WIN_FLIP_JUMP",
    "WIN_KAWAII",
    "WIN_MEDITATION",
    "WIN_RAISE_THE_ROOF",
    "WIN_WAVE",
    "CELEBRATE",
)

LOSE_ANIMATIONS = (
    "LOSE",
    "LOSE_CROSSED_ARMS",
    "LOSE_JAWDROP",
    "LOSE_KNEES",
    "LOSE_SAGGING",
    "LOSE_SITTING",
    "LOSE_SWING_FIST",
    "UPSET",
    "UPSET_MORE",
)

TAUNT_ANIMATIONS = (
    "TAUNT_BOXER",
    "TAUNT_COME_AT_ME",
    "TAUNT_CRANE_KICK",
    "TAUNT_EYES_ON_YOU",
    "TAUNT_OBJECTION",
)

IDLE_ANIMATIONS = (
    "IDLE",
    "IDLE_EAGER",
    "IDLE_CROSSED",
    "IDLE_ARMS_CROSSED",
    "IDLE_ARMS_SIDES",
    "IDLE_DISCIPLINED",
    "IDLE_RELAXED",
    "IDLE_RESTING_ARM",
)

OTHER_ANIMATIONS = (
    "SECOND_WIND",
    "SLEEP",
    "ENERGY_BOOST",
    "OK_GUESS",
    "PING_HEAD",
    "PING_LOWER",
    "PING_UPPER",
    "BADGE_SHOW",
    "BADGE_SHOW_IDLE",
    "SELECT",
    "EMOTE_HELLO",
    "GAMING",
    "GAMING_WAITING",
    "BALANCE_LEFT",
    "BALANCE_RIGHT",
    "BALANCE_RUN",
    "BALANCE_RUN_BACK",
)

BUILTIN_ANIMATIONS = WIN_ANIMATIONS + LOSE_ANIMATIONS + TAUNT_ANIMATIONS + IDLE_ANIMATIONS + OTHER_ANIMATIONS

# Clips during which a held item stays in the hand; any other clip makes it shrink away.
HANDHELD_ANIMATIONS = (
    "IDLE",
    "IDLE_EAGER",
    "PING_HEAD",
    "PING_LOWER",
    "PING_UPPER",
    "EMOTE_HELLO",
    "BALANCE_LEFT",
    "BALANCE_RIGHT",
    "BALANCE_RUN",
    "BALANCE_RUN_BACK",
)

# The frontend plays "DEFAULT_WIN" from WIN.glb.
_ALIASES = {"DEFAULT_WIN": "WIN"}


def normalize(name: str) -> str | None:
    """Return the canonical built-in clip name, or None if ``name`` is not built in."""
    name = _ALIASES.get(name.upper(), name.upper())
    return name if name in BUILTIN_ANIMATIONS else None


def builtin_path(name: str) -> str:
    """Site-relative path of a built-in clip's GLB."""
    return f"static/avatar-assets/animations/{name}.glb"
