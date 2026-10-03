"""Regenerate the images in docs/ used by the README.

uv run scripts/make_docs_images.py
"""

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from geoguessr_avatar import SyncAvatarRenderer, animations

USER = "656461a8a02239a1b6a4482e"  # the README's example player (used with permission)
DOCS = Path(__file__).resolve().parent.parent / "docs"
BACKGROUND = "#1d1b2e"
LABEL = "#e8e6f3"

HERO = [
    ("IDLE", {"time": 0}, "IDLE"),
    (None, {}, "own win animation"),
    ("WINANIMATION_HERMANMILLER_XZNC", {"progress": 0.6}, "purchasable win"),
    ("WIN_RAISE_THE_ROOF", {}, "WIN_RAISE_THE_ROOF"),
    ("LOSE_KNEES", {"progress": 0.5}, "LOSE_KNEES"),
    ("TAUNT_CRANE_KICK", {"progress": 0.5}, "TAUNT_CRANE_KICK"),
]


def tile(renderer: SyncAvatarRenderer, animation, size, label, font, **kwargs) -> Image.Image:
    result = renderer.render(USER, animation, width=size[0], height=size[1], zoom=0.8, **kwargs)
    img = Image.new("RGBA", (size[0], size[1] + font.size + 16), BACKGROUND)
    img.alpha_composite(Image.open(io.BytesIO(result.png)))
    draw = ImageDraw.Draw(img)
    width = draw.textlength(label, font=font)
    draw.text(((size[0] - width) / 2, size[1] + 4), label, fill=LABEL, font=font)
    return img


def grid(tiles: list[Image.Image], columns: int) -> Image.Image:
    w, h = tiles[0].size
    rows = -(-len(tiles) // columns)
    sheet = Image.new("RGBA", (w * columns, h * rows), BACKGROUND)
    for i, t in enumerate(tiles):
        sheet.alpha_composite(t, ((i % columns) * w, (i // columns) * h))
    return sheet


def main() -> None:
    DOCS.mkdir(exist_ok=True)
    with SyncAvatarRenderer() as renderer:
        font = ImageFont.load_default(size=20)
        hero = [tile(renderer, a, (300, 400), label, font, **kw) for a, kw, label in HERO]
        grid(hero, len(hero)).convert("RGB").save(DOCS / "hero.png", optimize=True)

        font = ImageFont.load_default(size=13)
        gallery = [tile(renderer, n, (160, 213), n, font) for n in animations.BUILTIN_ANIMATIONS]
        grid(gallery, 8).convert("RGB").save(DOCS / "animations.png", optimize=True)
    print(f"wrote {DOCS / 'hero.png'} and {DOCS / 'animations.png'}")


if __name__ == "__main__":
    main()
