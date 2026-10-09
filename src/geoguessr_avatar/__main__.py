"""Command line interface: ``geoguessr-avatar render|model|info|animations``."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from . import animations
from .client import GeoGuessrClient, GeoGuessrError, parse_user_id
from .models import Slot
from .renderer import AvatarRenderer, BrowserNotInstalled


def _size(value: str) -> tuple[int, int]:
    w, _, h = value.lower().partition("x")
    return int(w), int(h)


def _add_pose_args(p: argparse.ArgumentParser, suffix: str) -> None:
    p.add_argument("user", help="GeoGuessr user ID or profile URL (geoguessr.com/user/<id>)")
    p.add_argument("-a", "--animation", help="built-in clip or asset ID (default: player's win animation)")
    when = p.add_mutually_exclusive_group()
    when.add_argument("-t", "--time", type=float, help="seconds into the clip")
    when.add_argument("-p", "--progress", type=float, help="0.0-1.0 through the clip")
    p.add_argument("-o", "--output", type=Path, help=f"output file (default: <user>_<animation>{suffix})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="geoguessr-avatar", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    r = sub.add_parser("render", help="render a still PNG of a player's avatar")
    _add_pose_args(r, ".png")
    r.add_argument("--framing", choices=["fixed", "fit"], default="fixed")
    r.add_argument("--zoom", type=float, default=1.0, help="fixed framing: <1 zooms out (e.g. 0.85)")
    r.add_argument("--size", type=_size, default=(1080, 1440), help="WIDTHxHEIGHT (default 1080x1440)")
    r.add_argument("--background", help="hex colour, e.g. '#1d1b2e' (default: transparent)")

    m = sub.add_parser("model", help="export a player's avatar as a 3D model (.glb), posed and animated")
    _add_pose_args(m, ".glb")

    i = sub.add_parser("info", help="show a player's equipped items")
    i.add_argument("user", help="GeoGuessr user ID or profile URL")

    sub.add_parser("animations", help="list built-in animation clips")

    args = parser.parse_args(argv)
    if args.command == "animations":
        groups = {
            "win": animations.WIN_ANIMATIONS,
            "lose": animations.LOSE_ANIMATIONS,
            "taunt": animations.TAUNT_ANIMATIONS,
            "idle": animations.IDLE_ANIMATIONS,
            "other": animations.OTHER_ANIMATIONS,
        }
        for group, names in groups.items():
            print(f"{group}: {', '.join(names)}")
        return 0
    try:
        commands = {"info": _info, "render": _render, "model": _model}
        return asyncio.run(commands[args.command](args))
    except (GeoGuessrError, BrowserNotInstalled, ValueError, TimeoutError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


async def _info(args: argparse.Namespace) -> int:
    async with GeoGuessrClient() as gg:
        avatar = await gg.get_avatar(args.user)
    for item in sorted(avatar.items, key=lambda i: int(i.slot)):
        slot = item.slot.name if isinstance(item.slot, Slot) else str(item.slot)
        print(f"{slot:<14} {item.id}")
    win = avatar.win_animation
    print(f"{'win animation':<14} {win.id if win else 'WIN (default)'}")
    return 0


async def _render(args: argparse.Namespace) -> int:
    width, height = args.size
    async with AvatarRenderer() as renderer:
        result = await renderer.render(
            args.user,
            args.animation,
            time=args.time,
            progress=args.progress,
            width=width,
            height=height,
            framing=args.framing,
            zoom=args.zoom,
            background=args.background,
        )
    out = args.output or Path(f"{parse_user_id(args.user)}_{result.animation}.png")
    result.save(out)
    print(f"{out}  ({result.animation} at {result.time:.2f}s of {result.duration:.2f}s)", file=sys.stderr)
    return 0


async def _model(args: argparse.Namespace) -> int:
    async with AvatarRenderer() as renderer:
        result = await renderer.export_model(
            args.user, args.animation, time=args.time, progress=args.progress
        )
    out = args.output or Path(f"{parse_user_id(args.user)}_{result.animation}.glb")
    result.save(out)
    print(
        f"{out}  ({result.animation}, {result.duration:.2f}s, posed at {result.time:.2f}s)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
