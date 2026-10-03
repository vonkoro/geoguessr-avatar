"""Render the top three players in their win/lose poses and lay them out on a podium.

uv run --with pillow examples/podium.py <first-id> <second-id> <third-id> -o podium.png
"""

import argparse
import io

from PIL import Image

from geoguessr_avatar import SyncAvatarRenderer

TILE = (540, 720)
PODIUM = [  # (place, x, y offset) -- winner in the middle, raised
    (1, 540, 0),
    (2, 0, 120),
    (3, 1080, 180),
]


def render_podium(renderer: SyncAvatarRenderer, user_ids: list[str]) -> Image.Image:
    canvas = Image.new("RGBA", (TILE[0] * 3, TILE[1] + 200), "#1d1b2e")
    for (place, x, y), user_id in zip(PODIUM, user_ids, strict=True):
        # Winner gets their own (possibly purchased) win animation; the rest a built-in pose.
        animation = None if place == 1 else "IDLE_ARMS_CROSSED"
        # Fixed framing keeps every avatar at the same scale; zoom out for tall hats.
        result = renderer.render(user_id, animation, width=TILE[0], height=TILE[1], zoom=0.85)
        canvas.alpha_composite(Image.open(io.BytesIO(result.png)), (x, y))
    return canvas


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("users", nargs=3, metavar="USER_ID")
    parser.add_argument("-o", "--output", default="podium.png")
    args = parser.parse_args()
    # In a long-running bot, create the renderer once at startup and reuse it.
    with SyncAvatarRenderer() as renderer:
        render_podium(renderer, args.users).save(args.output)


if __name__ == "__main__":
    main()
